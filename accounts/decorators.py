from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def discovery_required(view):
    """
    Gate for discovery / quick pick / liking:
      1. logged in
      2. email verified
      3. profile at least 70% complete with a location pin
    """

    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.email_verified:
            return redirect("accounts:verify_pending")
        if user.profile_completion < settings.CHEERIPICK["MIN_COMPLETION_FOR_DISCOVERY"] or not user.has_location:
            messages.info(request, "Finish your profile (70%+ and a location) to start discovering 🍒")
            return redirect("accounts:onboarding_start")
        return view(request, *args, **kwargs)

    return wrapper
