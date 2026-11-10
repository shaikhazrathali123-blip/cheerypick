from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from . import pwa, views

admin.site.site_header = "CheeriPick admin 🍒"
admin.site.site_title = "CheeriPick admin"

urlpatterns = [
    path("", views.landing, name="landing"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("listings/", include("listings.urls")),
    path("chat/", include("chat.urls")),
    path("notifications/", include("notifications.urls")),
    path("sw.js", pwa.service_worker, name="service_worker"),
    path("manifest.webmanifest", pwa.manifest, name="manifest"),
    path("offline/", pwa.offline, name="offline"),
    path("favicon.ico", RedirectView.as_view(url=settings.STATIC_URL + "icons/favicon.ico", permanent=True)),
    path("", include("matching.urls")),
]

if settings.SERVE_MEDIA:
    from django.urls import re_path
    from django.views.static import serve

    urlpatterns += [re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT})]

if settings.DEBUG:
    # Preview the 404 page while DEBUG is on
    urlpatterns += [path("oops/", views.preview_404)]

handler404 = "cheeripick.views.page_not_found"
