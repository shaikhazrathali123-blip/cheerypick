/* CheeriPick service worker, version {{ version }}
   - App shell (CSS/JS/icons) cached for instant loads
   - Pages: network first, offline page as fallback
   - Static & media: served from cache, refreshed in the background
   - Web Push: shows notifications, opens the right screen on tap */
"use strict";
const VERSION = "{{ version }}";
const SHELL_CACHE = "cp-shell-" + VERSION;
const RUNTIME_CACHE = "cp-runtime-v1";
const OFFLINE_URL = "{{ offline_url }}";
const SHELL = {{ shell_json|safe }};
const RUNTIME_MAX = 150;

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then((c) => c.addAll(SHELL.concat([OFFLINE_URL])))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys();
    await Promise.all(keys.filter((k) => k.startsWith("cp-shell-") && k !== SHELL_CACHE).map((k) => caches.delete(k)));
    if (self.registration.navigationPreload) await self.registration.navigationPreload.enable();
    await self.clients.claim();
  })());
});

async function trimRuntime() {
  const cache = await caches.open(RUNTIME_CACHE);
  const keys = await cache.keys();
  for (let i = 0; i < keys.length - RUNTIME_MAX; i++) await cache.delete(keys[i]);
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // fonts/CDNs: let the browser handle them
  if (url.pathname.startsWith("/admin")) return;

  // Pages: always try the network so you never see stale matches; offline page if it fails.
  if (req.mode === "navigate") {
    event.respondWith((async () => {
      try {
        const preload = await event.preloadResponse;
        return preload || await fetch(req);
      } catch (e) {
        return (await caches.match(OFFLINE_URL)) || Response.error();
      }
    })());
    return;
  }

  // CSS/JS/icons/photos: cache first, refresh in the background.
  if (url.pathname.startsWith("/static/") || url.pathname.startsWith("/media/")) {
    event.respondWith((async () => {
      const cached = await caches.match(req);
      const network = fetch(req).then(async (res) => {
        if (res.ok) {
          const name = SHELL.includes(url.pathname) ? SHELL_CACHE : RUNTIME_CACHE;
          await (await caches.open(name)).put(req, res.clone());
          if (name === RUNTIME_CACHE) trimRuntime();
        }
        return res;
      }).catch(() => cached);
      if (cached) { event.waitUntil(network); return cached; }
      return network;
    })());
  }
  // Everything else (JSON feeds, chat polling): network only, never cached.
});

/* ---------------- Push notifications ---------------- */
self.addEventListener("push", (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; }
  catch (e) { data = { body: event.data ? event.data.text() : "" }; }
  const options = {
    body: data.body || "",
    icon: data.icon || "/static/icons/icon-192.png",
    badge: data.badge || "/static/icons/badge-72.png",
    tag: data.tag || undefined,
    renotify: Boolean(data.tag),
    data: { url: data.url || "/" },
    vibrate: [80, 40, 80],
  };
  const jobs = [self.registration.showNotification(data.title || "CheeriPick", options)];
  if (typeof data.unread === "number" && self.navigator && "setAppBadge" in self.navigator) {
    jobs.push(self.navigator.setAppBadge(data.unread).catch(() => {}));
  }
  event.waitUntil(Promise.all(jobs));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL((event.notification.data && event.notification.data.url) || "/", self.location.origin).href;
  event.waitUntil((async () => {
    const wins = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const w of wins) {
      if (new URL(w.url).origin === self.location.origin) {
        await w.focus();
        if (w.url !== target && "navigate" in w) await w.navigate(target);
        return;
      }
    }
    await self.clients.openWindow(target);
  })());
});
