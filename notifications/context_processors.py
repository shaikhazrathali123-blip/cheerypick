from django.conf import settings

from .service import push_enabled, unread_count


def notifications(request):
    user = getattr(request, "user", None)
    return {
        "notif_count": unread_count(user) if user is not None and user.is_authenticated else 0,
        "PUSH_ENABLED": push_enabled(),
        "VAPID_PUBLIC_KEY": settings.VAPID_PUBLIC_KEY,
    }
