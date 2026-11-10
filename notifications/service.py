"""
notify(user, kind, title, body, url) creates an in-app notification and, if Web Push
is configured (VAPID keys in .env) and the user has subscribed a device, pushes it
to their phone/desktop too, even when CheeriPick is closed.

Pushes are delivered on a background thread after the DB transaction commits,
so a slow push service never slows down a swipe or a chat message.
"""
import json
import logging
import threading

from django.conf import settings
from django.db import close_old_connections, transaction
from django.templatetags.static import static
from django.utils import timezone

from .models import Notification, PushSubscription

log = logging.getLogger(__name__)


def push_enabled():
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def notify(user, kind, title, body="", url="", group=""):
    """Create (or refresh, when `group` matches an unread one) a notification and push it."""
    n = None
    if group:
        n = Notification.objects.filter(user=user, group=group, read_at__isnull=True).first()
    if n:
        n.title, n.body, n.url, n.created_at = title, body, url, timezone.now()
        n.save(update_fields=["title", "body", "url", "created_at"])
    else:
        n = Notification.objects.create(user=user, kind=kind, title=title, body=body, url=url, group=group)

    payload = {
        "title": title,
        "body": body,
        "url": url or "/",
        "tag": group or f"n{n.pk}",
        "icon": static("icons/icon-192.png"),
        "badge": static("icons/badge-72.png"),
        "unread": Notification.objects.filter(user=user, read_at__isnull=True).count(),
    }
    if push_enabled():
        transaction.on_commit(lambda: send_push_async(user.pk, payload))
    return n


def send_push_async(user_id, payload):
    subs = list(PushSubscription.objects.filter(user_id=user_id))
    if not subs:
        return
    if getattr(settings, "PUSH_IN_BACKGROUND", True):
        threading.Thread(target=_deliver, args=(subs, payload), daemon=True).start()
    else:  # hosts without thread support (e.g. PythonAnywhere): send inline
        _deliver(subs, payload)


def _deliver(subs, payload):
    from pywebpush import WebPushException, webpush

    data = json.dumps(payload)
    dead = []
    try:
        for s in subs:
            try:
                webpush(
                    subscription_info={"endpoint": s.endpoint, "keys": {"p256dh": s.p256dh, "auth": s.auth}},
                    data=data,
                    vapid_private_key=settings.VAPID_PRIVATE_KEY,
                    vapid_claims={"sub": settings.VAPID_SUBJECT},
                    ttl=60 * 60 * 24,
                    timeout=10,
                )
            except WebPushException as exc:
                status = getattr(exc.response, "status_code", None)
                if status in (404, 410):  # device unsubscribed or expired
                    dead.append(s.pk)
                else:
                    log.warning("Web push failed (%s): %s", status, exc)
            except Exception as exc:  # network trouble etc. must never crash the app
                log.warning("Web push error: %s", exc)
        if dead:
            PushSubscription.objects.filter(pk__in=dead).delete()
    finally:
        close_old_connections()


def mark_read(user, **filters):
    Notification.objects.filter(user=user, read_at__isnull=True, **filters).update(read_at=timezone.now())


def unread_count(user):
    return Notification.objects.filter(user=user, read_at__isnull=True).count()
