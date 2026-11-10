"""Progressive Web App endpoints: manifest, service worker (served from / so it controls the whole site), offline page."""
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.cache import cache_control

# Files the service worker pre-caches so the app shell opens instantly / offline.
SHELL_STATIC = [
    "css/main.css", "js/main.js", "js/deck.js", "js/pwa.js",
    "icons/icon-192.png", "icons/icon-512.png", "icons/badge-72.png",
]


def _static_version():
    """Changes whenever a shell file (or the worker itself) changes, so phones pick up new CSS/JS."""
    base = Path(settings.BASE_DIR)
    files = [base / "static" / rel for rel in SHELL_STATIC] + [base / "templates" / "pwa" / "sw.js"]
    h = hashlib.sha1()
    for p in files:
        if p.exists():
            h.update(f"{p.name}:{p.stat().st_mtime_ns}".encode())
    return h.hexdigest()[:10]


# In DEBUG recompute every time (instant updates while developing); in production compute once per process.
version = _static_version if settings.DEBUG else lru_cache(maxsize=1)(_static_version)


@cache_control(max_age=3600)
def manifest(request):
    icon192 = static("icons/icon-192.png")
    data = {
        "name": "CheeriPick: find your roomie",
        "short_name": "CheeriPick",
        "description": "Swipe, match and chat with roommates whose vibe fits.",
        "id": "/",
        "start_url": reverse("matching:deck") + "?source=pwa",
        "scope": "/",
        "display": "standalone",
        "orientation": "portrait",
        "background_color": "#09090D",
        "theme_color": "#09090D",
        "categories": ["lifestyle", "social"],
        "icons": [
            {"src": icon192, "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": static("icons/icon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": static("icons/maskable-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
        "shortcuts": [
            {"name": "Swipe", "url": reverse("matching:deck"), "icons": [{"src": icon192, "sizes": "192x192"}]},
            {"name": "Chats", "url": reverse("matching:matches"), "icons": [{"src": icon192, "sizes": "192x192"}]},
            {"name": "Notifications", "url": reverse("notifications:inbox"), "icons": [{"src": icon192, "sizes": "192x192"}]},
        ],
    }
    return JsonResponse(data, content_type="application/manifest+json")


def service_worker(request):
    body = render_to_string("pwa/sw.js", {
        "version": version(),
        "offline_url": reverse("offline"),
        "shell_json": json.dumps([static(p) for p in SHELL_STATIC]),
    })
    resp = HttpResponse(body, content_type="application/javascript; charset=utf-8")
    resp["Service-Worker-Allowed"] = "/"
    resp["Cache-Control"] = "no-cache"  # browsers must always check for a new worker
    return resp


def offline(request):
    return render(request, "pwa/offline.html")
