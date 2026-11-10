from datetime import timedelta

from django.utils import timezone

from .models import User

THROTTLE = timedelta(minutes=5)


class LastActiveMiddleware:
    """
    Bumps user.last_active (at most every 5 minutes) and un-hides people who
    were auto-hidden for inactivity once they come back.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            now = timezone.now()
            if user.is_hidden_inactive or now - user.last_active > THROTTLE:
                User.objects.filter(pk=user.pk).update(last_active=now, is_hidden_inactive=False)
                user.last_active = now
                user.is_hidden_inactive = False
        return self.get_response(request)
