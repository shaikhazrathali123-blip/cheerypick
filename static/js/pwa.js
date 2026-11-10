/* CheeriPick PWA glue: service worker, install button, push notifications, live bell badge. */
(function () {
  "use strict";
  var body = document.body;
  var loggedIn = body.hasAttribute("data-auth");
  var vapidKey = body.dataset.vapidKey || "";

  function csrf() {
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : "";
  }
  function post(url, data) {
    return fetch(url, {
      method: "POST", credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrf(), "X-Requested-With": "fetch" },
      body: JSON.stringify(data || {}),
    });
  }
  function toast(msg, kind) {
    var box = document.querySelector(".toasts");
    if (!box) { box = document.createElement("div"); box.className = "toasts"; box.setAttribute("role", "status"); document.body.appendChild(box); }
    var t = document.createElement("div");
    t.className = "toast toast-" + (kind || "success");
    t.textContent = msg;
    box.appendChild(t);
    setTimeout(function () { t.classList.add("is-leaving"); setTimeout(function () { t.remove(); }, 350); }, 3800);
  }

  /* ---------------- Service worker ---------------- */
  var swReady = null;
  if ("serviceWorker" in navigator) {
    swReady = navigator.serviceWorker.register("/sw.js", { scope: "/" })
      .then(function () { return navigator.serviceWorker.ready; })
      .catch(function () { return null; });
  }

  var standalone = matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
  if (standalone) document.documentElement.classList.add("is-standalone");

  /* ---------------- Install ---------------- */
  var deferred = null;
  var isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
  function showInstall(state) {
    document.querySelectorAll("[data-install]").forEach(function (el) { el.hidden = state !== "prompt"; });
    document.querySelectorAll("[data-install-ios]").forEach(function (el) { el.hidden = state !== "ios"; });
    document.querySelectorAll("[data-installed]").forEach(function (el) { el.hidden = state !== "installed"; });
    document.querySelectorAll("[data-install-fallback]").forEach(function (el) { el.hidden = state === "ios" || state === "installed"; });
  }
  if (standalone) showInstall("installed");
  else if (isIOS) showInstall("ios");

  window.addEventListener("beforeinstallprompt", function (e) {
    e.preventDefault();
    deferred = e;
    showInstall("prompt");
  });
  window.addEventListener("appinstalled", function () {
    deferred = null;
    showInstall("installed");
    toast("CheeriPick installed 🍒 Find it on your home screen.");
  });
  document.querySelectorAll("[data-install]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      if (!deferred) return;
      deferred.prompt();
      deferred.userChoice.finally(function () { deferred = null; showInstall("none"); });
    });
  });

  /* ---------------- Push notifications ---------------- */
  var pushSupported = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

  function urlB64ToUint8(b64) {
    var pad = "=".repeat((4 - (b64.length % 4)) % 4);
    var raw = atob((b64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
    var out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }

  function getSub() {
    if (!swReady) return Promise.resolve(null);
    return swReady.then(function (reg) { return reg ? reg.pushManager.getSubscription() : null; });
  }

  function setPushUI(state) {
    // state: unsupported | unconfigured | blocked | ios-install | off | on | busy
    var labels = {
      unsupported: "This browser can't do push notifications.",
      unconfigured: "Push isn't set up on this server yet (missing VAPID keys).",
      blocked: "Notifications are blocked. Allow them in your browser's site settings.",
      "ios-install": "On iPhone, add CheeriPick to your Home Screen first, then turn notifications on from the app.",
      off: "Get a ping for new matches and messages, even when the app is closed.",
      on: "On for this device. You'll hear about matches and messages.",
      busy: "One sec…",
    };
    document.querySelectorAll("[data-push-status]").forEach(function (el) { el.textContent = labels[state] || ""; });
    document.querySelectorAll("[data-push-toggle]").forEach(function (btn) {
      btn.hidden = !(state === "off" || state === "on" || state === "busy");
      btn.disabled = state === "busy";
      btn.textContent = state === "on" ? "Turn off" : "Turn on notifications";
      btn.classList.toggle("btn-primary", state !== "on");
      btn.classList.toggle("btn-ghost", state === "on");
      btn.dataset.state = state;
    });
    document.querySelectorAll("[data-push-test]").forEach(function (btn) { btn.hidden = state !== "on"; });
    document.querySelectorAll("[data-push-nudge]").forEach(function (el) { el.hidden = state !== "off"; });
  }

  function refreshPushUI() {
    if (!pushSupported) return setPushUI(isIOS && !standalone ? "ios-install" : "unsupported");
    if (!vapidKey) return setPushUI("unconfigured");
    if (Notification.permission === "denied") return setPushUI("blocked");
    getSub().then(function (sub) { setPushUI(sub && Notification.permission === "granted" ? "on" : "off"); });
  }

  function subscribe() {
    setPushUI("busy");
    return Notification.requestPermission().then(function (perm) {
      if (perm !== "granted") { refreshPushUI(); return; }
      return swReady.then(function (reg) {
        return reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlB64ToUint8(vapidKey) });
      }).then(function (sub) {
        return post("/notifications/push/subscribe/", sub.toJSON());
      }).then(function (r) {
        if (!r.ok) throw new Error(r.status);
        toast("Notifications on 🔔");
        refreshPushUI();
      });
    }).catch(function () {
      toast("Couldn't turn on notifications. Try again?", "error");
      refreshPushUI();
    });
  }

  function unsubscribe() {
    setPushUI("busy");
    return getSub().then(function (sub) {
      if (!sub) return;
      var endpoint = sub.endpoint;
      return sub.unsubscribe().then(function () { return post("/notifications/push/unsubscribe/", { endpoint: endpoint }); });
    }).then(function () { toast("Notifications off for this device."); refreshPushUI(); })
      .catch(function () { refreshPushUI(); });
  }

  document.querySelectorAll("[data-push-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () { (btn.dataset.state === "on" ? unsubscribe : subscribe)(); });
  });
  document.querySelectorAll("[data-push-test]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      btn.disabled = true;
      post("/notifications/push/test/").then(function (r) { return r.json(); })
        .then(function () { toast("Test sent. Check your notifications!"); })
        .catch(function () { toast("Couldn't send a test.", "error"); })
        .finally(function () { btn.disabled = false; });
    });
  });
  if (loggedIn && document.querySelector("[data-push-status], [data-push-toggle], [data-push-nudge]")) refreshPushUI();

  // Keep the server in sync if this device was subscribed before (e.g. after a reinstall).
  if (loggedIn && pushSupported && vapidKey && Notification.permission === "granted") {
    getSub().then(function (sub) { if (sub) post("/notifications/push/subscribe/", sub.toJSON()); });
  }

  /* ---------------- Live bell badge ---------------- */
  if (loggedIn) {
    var setBadge = function (n) {
      document.querySelectorAll("[data-notif-count]").forEach(function (el) {
        el.textContent = n > 9 ? "9+" : String(n);
        el.hidden = n === 0;
      });
      if ("setAppBadge" in navigator) { (n ? navigator.setAppBadge(n) : navigator.clearAppBadge()).catch(function () {}); }
    };
    var last = parseInt((document.querySelector("[data-notif-count]") || {}).textContent || "0", 10) || 0;
    setBadge(last);
    var check = function () {
      if (document.hidden) return;
      fetch("/notifications/unread/", { credentials: "same-origin", headers: { Accept: "application/json" } })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) { if (d) setBadge(d.count); })
        .catch(function () {});
    };
    setInterval(check, 30000);
    document.addEventListener("visibilitychange", function () { if (!document.hidden) check(); });
  }
})();
