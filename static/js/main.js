/* CheeriPick — small vanilla JS touches only. Everything works without JS. */
(function () {
  "use strict";
  var root = document.documentElement;

  /* ---------- Theme toggle (system default, remembered in localStorage) ---------- */
  function setTheme(t, save) {
    root.setAttribute("data-theme", t);
    if (save) { try { localStorage.setItem("cp-theme", t); } catch (e) {} }
  }
  document.querySelectorAll("[data-theme-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      setTheme(root.getAttribute("data-theme") === "dark" ? "light" : "dark", true);
    });
  });
  if (window.matchMedia) {
    var mq = matchMedia("(prefers-color-scheme: dark)");
    var follow = function (e) {
      var saved = null;
      try { saved = localStorage.getItem("cp-theme"); } catch (err) {}
      if (!saved) setTheme(e.matches ? "dark" : "light", false);
    };
    mq.addEventListener ? mq.addEventListener("change", follow) : mq.addListener(follow);
  }

  /* ---------- Toasts auto-dismiss ---------- */
  document.querySelectorAll("[data-toast]").forEach(function (el, i) {
    setTimeout(function () {
      el.classList.add("is-leaving");
      setTimeout(function () { el.remove(); }, 350);
    }, 3800 + i * 400);
  });

  /* ---------- Range sliders show their value ---------- */
  document.querySelectorAll('input[type="range"]').forEach(function (input) {
    var out = document.createElement("span");
    out.className = "range-value";
    var unit = /radius/.test(input.name) ? " km" : "";
    var render = function () {
      out.textContent = input.value + unit;
      var min = parseFloat(input.min || 0), max = parseFloat(input.max || 100);
      input.style.setProperty("--fill", ((input.value - min) / (max - min || 1)) * 100 + "%");
    };
    input.insertAdjacentElement("afterend", out);
    input.addEventListener("input", render);
    render();
  });

  /* ---------- Geolocation (asks permission; falls back to typed city) ---------- */
  document.querySelectorAll("[data-geolocate]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var status = document.querySelector(btn.dataset.status);
      var lat = document.querySelector(btn.dataset.lat);
      var lon = document.querySelector(btn.dataset.lon);
      var say = function (msg) { if (status) status.textContent = msg; };
      if (!("geolocation" in navigator)) { say("Your browser can't share location — type your city instead."); return; }
      btn.disabled = true;
      say("Finding you… 🛰️");
      navigator.geolocation.getCurrentPosition(
        function (pos) {
          lat.value = pos.coords.latitude.toFixed(6);
          lon.value = pos.coords.longitude.toFixed(6);
          btn.disabled = false;
          say("Got it ✔️ Location pinned (±" + Math.round(pos.coords.accuracy) + " m).");
        },
        function () {
          btn.disabled = false;
          say("No worries — just type your city below and we'll place you.");
        },
        { enableHighAccuracy: false, timeout: 10000, maximumAge: 600000 }
      );
    });
  });
  // If someone types a new city after geolocating, drop the stale pin so the city lookup runs.
  document.querySelectorAll("[data-city-input]").forEach(function (input) {
    var original = input.value;
    input.addEventListener("change", function () {
      if (input.value.trim().toLowerCase() !== original.trim().toLowerCase()) {
        var lat = document.getElementById("id_latitude");
        var lon = document.getElementById("id_longitude");
        if (lat && lon && lat.dataset.fromGeo !== "1") { lat.value = ""; lon.value = ""; }
      }
    });
  });
  document.querySelectorAll("[data-geolocate]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var lat = document.querySelector(btn.dataset.lat);
      if (lat) lat.dataset.fromGeo = "1";
    });
  });

  /* ---------- Quick Pick swipe animation (forms still POST normally) ---------- */
  var card = document.querySelector("[data-pick-card]");
  if (card) {
    var forms = document.querySelectorAll("form[data-swipe]");
    var busy = false;
    var go = function (form) {
      if (busy) return;
      busy = true;
      card.classList.add(form.dataset.swipe === "right" ? "swipe-right" : "swipe-left");
      setTimeout(function () { form.submit(); }, 320);
    };
    forms.forEach(function (form) {
      form.addEventListener("submit", function (e) { e.preventDefault(); go(form); });
    });
    document.addEventListener("keydown", function (e) {
      if (e.target.closest("input, textarea")) return;
      if (e.key === "ArrowRight") go(document.querySelector('form[data-swipe="right"]'));
      if (e.key === "ArrowLeft") go(document.querySelector('form[data-swipe="left"]'));
    });
    // Touch drag
    var startX = null;
    card.addEventListener("touchstart", function (e) { startX = e.touches[0].clientX; }, { passive: true });
    card.addEventListener("touchmove", function (e) {
      if (startX === null) return;
      var dx = e.touches[0].clientX - startX;
      card.style.transform = "translateX(" + dx + "px) rotate(" + dx / 20 + "deg)";
    }, { passive: true });
    card.addEventListener("touchend", function (e) {
      if (startX === null) return;
      var dx = e.changedTouches[0].clientX - startX;
      startX = null;
      card.style.transform = "";
      if (dx > 90) go(document.querySelector('form[data-swipe="right"]'));
      else if (dx < -90) go(document.querySelector('form[data-swipe="left"]'));
    });
  }

  /* ---------- Chat: light polling every N seconds + fetch send ---------- */
  var chat = document.querySelector("[data-chat]");
  if (chat) {
    var lastId = parseInt(chat.dataset.lastId || "0", 10);
    var pollMs = parseInt(chat.dataset.pollMs || "5000", 10);
    var form = document.querySelector("[data-chat-form]");
    var box = form.querySelector("textarea");
    var scrollDown = function () { chat.scrollTop = chat.scrollHeight; };

    var addBubble = function (m) {
      var empty = chat.querySelector("[data-chat-empty]");
      if (empty) empty.remove();
      var div = document.createElement("div");
      div.className = "bubble " + (m.mine ? "mine" : "theirs");
      var p = document.createElement("p");
      p.textContent = m.body; // textContent = no HTML injection
      var t = document.createElement("time");
      t.textContent = m.time;
      div.appendChild(p); div.appendChild(t);
      chat.appendChild(div);
    };

    var polling = false;
    var poll = function () {
      if (polling) return;
      polling = true;
      fetch(chat.dataset.pollUrl + "?after=" + lastId, { credentials: "same-origin" })
        .then(function (r) { return r.ok ? r.json() : { messages: [] }; })
        .then(function (data) {
          if (data.messages.length) {
            data.messages.forEach(function (m) { addBubble(m); lastId = Math.max(lastId, m.id); });
            scrollDown();
          }
        })
        .catch(function () {})
        .finally(function () { polling = false; });
    };

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!box.value.trim()) return;
      var body = new FormData(form);
      box.value = "";
      fetch(window.location.pathname, {
        method: "POST", body: body, credentials: "same-origin",
        headers: { "X-Requested-With": "fetch" }
      }).then(poll);
    });
    box.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); form.requestSubmit(); }
    });

    scrollDown();
    setInterval(function () { if (!document.hidden) poll(); }, pollMs);
  }

  /* ---------- Unread badge refresh (cheap, every 30s) ---------- */
  var badges = document.querySelectorAll("[data-unread]");
  if (document.body.classList.contains("has-tabbar") && !chat) {
    setInterval(function () {
      if (document.hidden) return;
      fetch("/chat/unread/", { credentials: "same-origin" })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (d) {
          if (!d) return;
          badges.forEach(function (b) { b.textContent = d.unread; b.hidden = !d.unread; });
        })
        .catch(function () {});
    }, 30000);
  }
})();
