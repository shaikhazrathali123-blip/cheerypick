from django.db.models import Q

from .models import Message


def unread_for(user):
    return (
        Message.objects.filter(Q(match__user_a=user) | Q(match__user_b=user), read_at__isnull=True)
        .exclude(sender=user)
        .count()
    )


def unread_messages(request):
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {"unread_count": 0}
    return {"unread_count": unread_for(user)}
