"""
"Continue with Google" via OAuth 2.0 / OpenID Connect (authorization code flow).

Standard library only, no extra packages. Flow:
  1. google_login    -> redirect to Google with a random `state` kept in the session
  2. google_callback -> check `state`, swap the code for tokens (server to server),
                        read the user's profile, then log in / link / create the account.
"""
import json
import logging
import re
import secrets
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.db import IntegrityError, transaction
from django.shortcuts import redirect
from django.urls import reverse

from .models import User

log = logging.getLogger(__name__)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
SESSION_STATE = "google_oauth_state"
SESSION_NEXT = "google_oauth_next"
BACKEND = "accounts.backends.EmailOrUsernameBackend"


def _enabled():
    return bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET)


def _redirect_uri(request):
    return request.build_absolute_uri(reverse("accounts:google_callback"))


def _fail(request, msg="Google sign-in didn't work. Try again, or use your email and password."):
    messages.error(request, msg)
    return redirect("accounts:login")


def google_login(request):
    if not _enabled():
        return _fail(request, "Google sign-in isn't set up on this server yet.")
    if request.user.is_authenticated:
        return redirect("matching:deck")

    from .views import safe_next  # local import avoids a circular import

    state = secrets.token_urlsafe(32)
    request.session[SESSION_STATE] = state
    request.session[SESSION_NEXT] = safe_next(request, "")
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": _redirect_uri(request),
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "prompt": "select_account",
    }
    return redirect(f"{AUTH_URL}?{urlencode(params)}")


def _post_json(url, data):
    req = Request(url, data=urlencode(data).encode(), headers={"Accept": "application/json"})
    with urlopen(req, timeout=10) as resp:
        return json.load(resp)


def _get_json(url, token):
    req = Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    with urlopen(req, timeout=10) as resp:
        return json.load(resp)


def _unique_username(email):
    base = re.sub(r"[^\w.+-]", "", email.split("@")[0])[:30] or "cheeri"
    username, n = base, 1
    while User.objects.filter(username__iexact=username).exists():
        n += 1
        username = f"{base}{n}"
    return username


def _find_or_create_user(info):
    """Return (user, created). Raises ValueError if the account can't be used."""
    sub = info.get("sub")
    email = (info.get("email") or "").lower()
    if not sub or not email:
        raise ValueError("Google didn't share an email address.")
    if not info.get("email_verified"):
        raise ValueError("Your Google email isn't verified yet.")

    # 1) Already linked
    user = User.objects.filter(google_sub=sub).first()
    if user:
        return user, False

    # 2) Existing email/password account with the same (Google-verified) email: link it
    user = User.objects.filter(email__iexact=email).first()
    if user:
        user.google_sub = sub
        user.email_verified = True
        user.save(update_fields=["google_sub", "email_verified"])
        return user, False

    # 3) Brand-new account
    with transaction.atomic():
        user = User(
            username=_unique_username(email),
            email=email,
            name=(info.get("given_name") or info.get("name") or "")[:60],
            google_sub=sub,
            email_verified=True,
        )
        user.set_unusable_password()
        user.save()
    return user, True


def google_callback(request):
    if not _enabled():
        return _fail(request, "Google sign-in isn't set up on this server yet.")

    expected_state = request.session.pop(SESSION_STATE, None)
    next_url = request.session.pop(SESSION_NEXT, "")

    if request.GET.get("error"):
        # User hit "Cancel" on Google's screen, or similar
        return _fail(request, "Google sign-in was cancelled.")
    state, code = request.GET.get("state"), request.GET.get("code")
    if not expected_state or not state or not secrets.compare_digest(state, expected_state) or not code:
        return _fail(request, "That sign-in link expired. Please try again.")

    try:
        tokens = _post_json(TOKEN_URL, {
            "code": code,
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "redirect_uri": _redirect_uri(request),
            "grant_type": "authorization_code",
        })
        info = _get_json(USERINFO_URL, tokens["access_token"])
    except (URLError, KeyError, ValueError, TimeoutError) as exc:
        log.warning("Google OAuth exchange failed: %s", exc)
        return _fail(request)

    try:
        user, created = _find_or_create_user(info)
    except ValueError as exc:
        return _fail(request, str(exc))
    except IntegrityError:
        # Two sign-ins racing to create the same account: just retry once
        user, created = _find_or_create_user(info)

    if not user.is_active:
        return _fail(request, "This account is disabled.")

    login(request, user, backend=BACKEND)
    user.refresh_stats()
    if created:
        messages.success(request, "Welcome to CheeriPick! Let's set up your profile 🍒")
        return redirect("accounts:onboarding_start")
    messages.success(request, f"Welcome back, {user.display_name}!")
    return redirect(next_url or settings.LOGIN_REDIRECT_URL)
