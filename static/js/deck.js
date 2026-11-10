/* CheeriPick swipe deck.
   Drag a card sideways to decide (direction from data-like-dir, default right = like).
   Scroll the card up/down to read the details under the photo.
   Tap the left/right side of the photo to flip photos. Arrow keys work too. */
(function () {
  "use strict";
  var root = document.querySelector("[data-deck]");
  if (!root) return;

  var LIKE_DIR = root.dataset.likeDir === "left" ? "left" : "right";
  var PASS_DIR = LIKE_DIR === "left" ? "right" : "left";
  var FEED_URL = root.dataset.feedUrl;
  var CSRF = root.querySelector("[name=csrfmiddlewaretoken]").value;
  var REDUCED = window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches;
  var FLY_MS = REDUCED ? 150 : 380;
  var THRESHOLD = 110;     // px to commit a swipe
  var FLICK_SPEED = 0.6;   // px/ms: a quick flick commits from a shorter drag
  var AXIS_LOCK = 8;       // px before we decide "swipe" vs "scroll"
  var VISIBLE = 3;         // cards rendered in the stack at once
  var REFILL_AT = 4;       // fetch more when this few are left

  var stack = root.querySelector("[data-deck-stack]");
  var emptyEl = root.querySelector("[data-deck-empty]");
  var loadingEl = root.querySelector("[data-deck-loading]");
  var matchEl = document.querySelector("[data-deck-match]");

  var queue = JSON.parse(document.getElementById("deck-cards").textContent || "[]");
  var seen = {};
  queue.forEach(function (c) { seen[c.id] = true; });
  var exhausted = !queue.length;
  var fetching = false;
  var busy = false; // a card is flying out

  /* ---------------- Rendering ---------------- */
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  function buildCard(c) {
    var card = el("article", "deck-card");
    card.dataPayload = c;
    card.photoIndex = 0;
    card.setAttribute("aria-label", c.name + (c.age ? ", " + c.age : ""));

    var scroller = el("div", "deck-scroll");

    // --- Photo (fills the card) ---
    var photo = el("div", "deck-photo");
    if (c.photos.length) {
      var img = el("img");
      img.src = c.photos[0];
      img.alt = c.name;
      img.draggable = false;
      photo.appendChild(img);
      c.photos.slice(1).forEach(function (src) { new Image().src = src; }); // preload
    } else {
      photo.appendChild(el("span", "media-initials", c.initials));
    }
    if (c.photos.length > 1) {
      var bars = el("div", "photo-bars");
      c.photos.forEach(function (_, i) { bars.appendChild(el("i", i === 0 ? "on" : "")); });
      photo.appendChild(bars);
    }

    var badges = el("div", "deck-badges");
    var pill = el("span", "deck-match-pill tone-" + c.tone);
    pill.appendChild(el("b", null, c.score + "%"));
    pill.appendChild(document.createTextNode(" match"));
    badges.appendChild(pill);
    badges.appendChild(el("span", "deck-glass", c.role));
    photo.appendChild(badges);

    var overlay = el("div", "deck-overlay");
    var h = el("h2");
    h.appendChild(document.createTextNode(c.name));
    if (c.age) h.appendChild(el("span", "age", c.age));
    if (c.verified) {
      var v = el("span", "verified-dot", "✓");
      v.title = "Verified";
      h.appendChild(v);
    }
    if (c.active) {
      var dot = el("span", "online-dot");
      dot.title = "Active today";
      h.appendChild(dot);
    }
    overlay.appendChild(h);
    overlay.appendChild(el("p", null, "📍 " + c.distance + " away" + (c.occupation ? " · " + c.occupation : "")));
    if (c.reasons.length) {
      var rc = el("div", "deck-reason-chips");
      c.reasons.slice(0, 2).forEach(function (r) { rc.appendChild(el("span", "deck-glass", r)); });
      overlay.appendChild(rc);
    }
    var hint = el("span", "deck-more-hint", "Scroll for more ");
    hint.appendChild(el("i", null, "↓"));
    overlay.appendChild(hint);
    photo.appendChild(overlay);
    scroller.appendChild(photo);

    // --- Details (below the photo, reached by scrolling) ---
    var d = el("div", "deck-details");
    var metaItems = [c.pronouns, c.occupation, c.city].filter(Boolean);
    if (metaItems.length) {
      var meta = el("div", "deck-meta");
      metaItems.forEach(function (m) { meta.appendChild(el("span", null, m)); });
      d.appendChild(meta);
    }
    if (c.bio) {
      d.appendChild(el("h3", null, "About " + c.name));
      d.appendChild(el("p", null, c.bio));
    }
    if (c.reasons.length) {
      d.appendChild(el("h3", null, "Why you'd click"));
      var ul = el("ul", "reasons");
      c.reasons.forEach(function (r) { ul.appendChild(el("li", null, r)); });
      d.appendChild(ul);
    }
    if (c.interests.length) {
      d.appendChild(el("h3", null, "Interests"));
      var chips = el("div", "deck-chips");
      c.interests.forEach(function (i) { chips.appendChild(el("span", "deck-chip", i)); });
      d.appendChild(chips);
    }
    if (c.price) {
      d.appendChild(el("h3", null, c.price.indexOf("Budget") === 0 ? "Budget" : "Their room"));
      d.appendChild(el("p", "price", c.price.replace(/^Budget /, "")));
    }
    var link = el("a", "btn btn-ghost btn-block deck-profile-link", "See full profile");
    link.href = c.profile_url;
    d.appendChild(link);
    scroller.appendChild(d);
    card.appendChild(scroller);

    // Stamps live on the card (not the scroller) so they show even when scrolled down.
    // Each sits on the side the card is leaving from, like a rubber stamp.
    card.appendChild(stamp("deck-like at-" + PASS_DIR, "♥", "Like"));
    card.appendChild(stamp("deck-pass at-" + LIKE_DIR, "✕", "Nope"));
    return card;
  }

  function stamp(cls, icon, label) {
    var s = el("div", "deck-stamp " + cls);
    var badge = el("span", "deck-stamp-badge");
    badge.appendChild(el("i", null, icon));
    badge.appendChild(document.createTextNode(label));
    s.appendChild(badge);
    return s;
  }

  function cardsInStack() {
    return Array.prototype.slice.call(stack.querySelectorAll(".deck-card:not(.is-gone)"));
  }

  function topCard() {
    var cards = cardsInStack();
    return cards.length ? cards[cards.length - 1] : null; // last child paints on top
  }

  function layout() {
    var cards = cardsInStack().reverse(); // [top, next, third]
    cards.forEach(function (card, i) {
      card.classList.toggle("is-top", i === 0);
      card.classList.toggle("is-next", i === 1);
      card.classList.toggle("is-third", i >= 2);
      card.setAttribute("aria-hidden", i === 0 ? "false" : "true");
    });
    var none = cards.length === 0;
    emptyEl.hidden = !(none && exhausted && !fetching);
    loadingEl.hidden = !(none && fetching);
  }

  function fill() {
    while (cardsInStack().length < VISIBLE && queue.length) {
      var card = buildCard(queue.shift());
      stack.insertBefore(card, stack.firstChild); // new cards go underneath
      bindDrag(card);
    }
    layout();
    if (!exhausted && !fetching && queue.length + cardsInStack().length <= REFILL_AT) loadMore();
  }

  function loadMore() {
    fetching = true;
    layout();
    var url = FEED_URL + "?exclude=" + Object.keys(seen).join(",");
    fetch(url, { headers: { Accept: "application/json" }, credentials: "same-origin" })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (data) {
        var fresh = data.cards.filter(function (c) { return !seen[c.id]; });
        fresh.forEach(function (c) { seen[c.id] = true; });
        if (!fresh.length) exhausted = true;
        queue = queue.concat(fresh);
      })
      .catch(function () { exhausted = true; toast("Couldn't load more people. Refresh to try again."); })
      .then(function () { fetching = false; fill(); });
  }

  /* ---------------- Photos ---------------- */
  function showPhoto(card, delta) {
    var c = card.dataPayload;
    if (c.photos.length < 2) return;
    var next = card.photoIndex + delta;
    if (next < 0 || next >= c.photos.length) {
      card.classList.remove("bump");
      void card.offsetWidth; // restart the "no more photos" nudge
      card.classList.add("bump");
      return;
    }
    card.photoIndex = next;
    card.querySelector(".deck-photo img").src = c.photos[next];
    card.querySelectorAll(".photo-bars i").forEach(function (b, i) { b.classList.toggle("on", i === next); });
  }

  /* ---------------- Dragging ---------------- */
  function setDragVisuals(card, dx, dy) {
    card.style.transform = "translate(" + dx + "px," + dy + "px) rotate(" + dx * 0.07 + "deg)";
    var p = Math.min(1, Math.abs(dx) / THRESHOLD);
    var likeAmt = (LIKE_DIR === "right" ? dx > 0 : dx < 0) ? p : 0;
    card.querySelector(".deck-like").style.opacity = likeAmt;
    card.querySelector(".deck-pass").style.opacity = likeAmt ? 0 : p;
    var next = stack.querySelector(".deck-card.is-next");
    if (next) next.style.transform = "scale(" + (0.95 + 0.05 * p) + ") translateY(" + (10 - 10 * p) + "px)";
  }

  function resetVisuals(card) {
    card.style.transition = "transform .3s cubic-bezier(.34,1.56,.64,1)";
    card.style.transform = "";
    card.querySelector(".deck-like").style.opacity = 0;
    card.querySelector(".deck-pass").style.opacity = 0;
    var next = stack.querySelector(".deck-card.is-next");
    if (next) next.style.transform = "";
    setTimeout(function () { card.style.transition = ""; }, 300);
  }

  function bindDrag(card) {
    var scroller = card.querySelector(".deck-scroll");
    var s = null; // current gesture

    scroller.addEventListener("pointerdown", function (e) {
      if (busy || !card.classList.contains("is-top") || e.button > 0) return;
      if (e.target.closest("a, button")) return;
      s = { x: e.clientX, y: e.clientY, t: 0, axis: null, dx: 0, dy: 0, id: e.pointerId, target: e.target };
    });

    scroller.addEventListener("pointermove", function (e) {
      if (!s || e.pointerId !== s.id) return;
      s.dx = e.clientX - s.x;
      s.dy = e.clientY - s.y;
      if (!s.axis) {
        if (Math.abs(s.dx) < AXIS_LOCK && Math.abs(s.dy) < AXIS_LOCK) return;
        if (Math.abs(s.dx) > Math.abs(s.dy)) {
          s.axis = "x"; // it's a swipe: take over the pointer
          s.t = performance.now();
          scroller.setPointerCapture(e.pointerId);
          card.style.transition = "none";
          card.classList.add("is-dragging");
        } else {
          s = null; // it's a scroll: let the browser handle it
          return;
        }
      }
      setDragVisuals(card, s.dx, s.dy * 0.15);
    });

    function end(e) {
      if (!s || e.pointerId !== s.id) return;
      var g = s;
      s = null;
      card.classList.remove("is-dragging");
      if (!g.axis) {
        // A tap. On the photo: left half = previous, right half = next.
        if (e.type === "pointercancel") return;
        var photo = g.target.closest && g.target.closest(".deck-photo");
        if (photo) {
          var rect = photo.getBoundingClientRect();
          showPhoto(card, e.clientX - rect.left < rect.width / 2 ? -1 : 1);
        }
        return;
      }
      var speed = Math.abs(g.dx) / Math.max(1, performance.now() - g.t);
      if (e.type !== "pointercancel" && (Math.abs(g.dx) > THRESHOLD || (Math.abs(g.dx) > 40 && speed > FLICK_SPEED))) {
        decide(g.dx < 0 ? "left" : "right", g.dy * 0.15);
      } else {
        resetVisuals(card);
      }
    }
    scroller.addEventListener("pointerup", end);
    scroller.addEventListener("pointercancel", end);
  }

  /* ---------------- Deciding ---------------- */
  function decide(direction, dy) {
    var card = topCard();
    if (!card || busy) return;
    busy = true;
    var action = direction === LIKE_DIR ? "like" : "pass";
    var sign = direction === "left" ? -1 : 1;
    setDragVisuals(card, sign * THRESHOLD, dy || 0); // make sure the right stamp shows
    card.style.transition = "transform " + FLY_MS + "ms ease-out, opacity " + FLY_MS + "ms ease-out";
    card.style.transform = "translate(" + sign * (window.innerWidth + 200) + "px," + ((dy || 0) + 40) + "px) rotate(" + sign * 28 + "deg)";
    card.style.opacity = "0";
    card.classList.add("is-gone");
    var next = stack.querySelector(".deck-card.is-next");
    if (next) next.style.transform = "";
    layout();
    setTimeout(function () {
      card.remove();
      busy = false;
      fill();
    }, FLY_MS);
    send(card.dataPayload, action);
  }

  function send(c, action) {
    fetch(c.swipe_url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRFToken": CSRF, Accept: "application/json" },
      body: new URLSearchParams({ action: action }),
    })
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (data) { if (data.match) showMatch(data.match); })
      .catch(function () { toast("That swipe didn't save. Check your connection."); });
  }

  /* ---------------- Match pop-up ---------------- */
  function face(slot, src, initials) {
    slot.textContent = "";
    if (src) { var i = el("img"); i.src = src; i.alt = ""; slot.appendChild(i); }
    else slot.textContent = initials;
  }

  var lastFocus = null;
  function showMatch(m) {
    face(matchEl.querySelector("[data-match-me]"), m.my_photo, m.my_initials);
    face(matchEl.querySelector("[data-match-them]"), m.photo, m.initials);
    matchEl.querySelector("[data-match-text]").textContent =
      "You and " + m.name + " liked each other · " + m.score + "% compatible";
    matchEl.querySelector("[data-match-chat]").href = m.chat_url;
    lastFocus = document.activeElement;
    matchEl.hidden = false;
    matchEl.querySelector("[data-match-chat]").focus();
  }
  function closeMatch() {
    matchEl.hidden = true;
    if (lastFocus) lastFocus.focus();
  }
  matchEl.querySelector("[data-match-close]").addEventListener("click", closeMatch);
  matchEl.addEventListener("click", function (e) { if (e.target === matchEl) closeMatch(); });

  /* ---------------- Toasts ---------------- */
  function toast(msg) {
    var box = document.querySelector(".toasts");
    if (!box) { box = el("div", "toasts"); box.setAttribute("role", "status"); document.body.appendChild(box); }
    var t = el("div", "toast toast-error", msg);
    box.appendChild(t);
    setTimeout(function () { t.remove(); }, 4000);
  }

  /* ---------------- Keys ---------------- */
  document.addEventListener("keydown", function (e) {
    if (e.target.closest("input, textarea, select") || e.metaKey || e.ctrlKey || e.altKey) return;
    if (!matchEl.hidden) { if (e.key === "Escape") closeMatch(); return; }
    if (e.key === "ArrowLeft") { e.preventDefault(); decide("left"); }
    else if (e.key === "ArrowRight") { e.preventDefault(); decide("right"); }
    else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      var c = topCard();
      if (c) { e.preventDefault(); c.querySelector(".deck-scroll").scrollBy({ top: e.key === "ArrowDown" ? 220 : -220, behavior: "smooth" }); }
    }
    else if (e.key === " ") { var t = topCard(); if (t) { e.preventDefault(); showPhoto(t, 1); } }
  });

  fill();
})();
