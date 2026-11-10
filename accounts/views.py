from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import url_has_allowed_host_and_scheme, urlsafe_base64_decode, urlsafe_base64_encode
from django.views.decorators.http import require_POST

from . import otp
from .forms import (
    ONBOARDING_STEPS,
    LoginForm,
    OtpForm,
    PhoneForm,
    PhotoUploadForm,
    ReportForm,
    RoleSwitchForm,
    SignUpForm,
)
from .images import process_image
from .models import Block, ProfilePhoto, Report, User
from .tokens import email_verification_token
from .trust import trust_label

CFG = settings.CHEERIPICK
STEP_SLUGS = [s[0] for s in ONBOARDING_STEPS]


def safe_next(request, fallback):
    """Only follow ?next= / POST next values that point back at this site."""
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return nxt
    return fallback


# --- Auth ------------------------------------------------------------------
def send_verification_email(request, user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_verification_token.make_token(user)
    link = request.build_absolute_uri(reverse("accounts:verify_email", args=[uid, token]))
    send_mail(
        "Verify your CheeriPick email 🍒",
        f"Hey {user.display_name}!\n\nTap to verify your email and start finding your people:\n{link}\n\n— CheeriPick",
        None,
        [user.email],
    )


def signup(request):
    if request.user.is_authenticated:
        return redirect("matching:deck")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user, backend="accounts.backends.EmailOrUsernameBackend")
        send_verification_email(request, user)
        messages.success(request, "Welcome to CheeriPick! Check your inbox to verify your email ✉️")
        return redirect("accounts:onboarding_start")
    return render(request, "accounts/signup.html", {"form": form})


class CheeriLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True


def verify_email(request, uidb64, token):
    try:
        user = User.objects.get(pk=force_str(urlsafe_base64_decode(uidb64)))
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        user = None
    if user and email_verification_token.check_token(user, token):
        user.email_verified = True
        user.save(update_fields=["email_verified"])
        user.refresh_stats()
        messages.success(request, "Email verified ✅ You're officially legit.")
        return redirect("matching:deck" if request.user.is_authenticated else "accounts:login")
    messages.error(request, "That link is expired or already used.")
    return redirect("accounts:verify_pending" if request.user.is_authenticated else "accounts:login")


@login_required
def verify_pending(request):
    if request.user.email_verified:
        return redirect("matching:deck")
    return render(request, "accounts/verify_pending.html")


@login_required
@require_POST
def resend_verification(request):
    if not request.user.email_verified:
        send_verification_email(request, request.user)
        messages.success(request, "New link sent! (In dev it's printed in the runserver terminal.)")
    return redirect(safe_next(request, reverse("accounts:verify_pending")))


# --- Onboarding wizard -----------------------------------------------------
@login_required
def onboarding_start(request):
    """Jump to the first step that still has gaps."""
    u = request.user
    if not (u.name and u.age and u.gender and u.occupation):
        step = "basics"
    elif not u.has_location:
        step = "location"
    elif not (u.budget_max and u.move_in_date):
        step = "budget"
    elif not all(getattr(u, f) not in (None, "") for f in ("sleep_schedule", "cleanliness", "smoking", "social_style")):
        step = "vibe"
    elif u.interests.count() < 3:
        step = "interests"
    else:
        step = "photos"
    return redirect("accounts:onboarding", step=step)


@login_required
def onboarding(request, step):
    if step not in STEP_SLUGS:
        raise Http404
    index = STEP_SLUGS.index(step)
    slug, title, subtitle, form_class = ONBOARDING_STEPS[index]
    user = request.user
    is_photos = slug == "photos"

    if is_photos:
        form = PhotoUploadForm(request.POST or None, request.FILES or None, user=user)
    else:
        form = form_class(request.POST or None, instance=user)

    if request.method == "POST" and form.is_valid():
        if is_photos:
            start = user.photos.count()
            for i, f in enumerate(form.cleaned_data["photos"]):
                ProfilePhoto.objects.create(user=user, image=process_image(f), order=start + i)
        else:
            form.save()
        user.refresh_stats()

        if is_photos and request.POST.get("action") == "upload":
            messages.success(request, "Looking good 📸")
            return redirect("accounts:onboarding", step="photos")
        if index + 1 < len(STEP_SLUGS):
            return redirect("accounts:onboarding", step=STEP_SLUGS[index + 1])
        messages.success(request, f"Profile {user.profile_completion}% done — let's find your people ✨")
        return redirect("matching:deck")

    context = {
        "form": form,
        "step": slug,
        "title": title,
        "subtitle": subtitle,
        "step_number": index + 1,
        "step_total": len(STEP_SLUGS),
        "step_percent": round((index + 1) * 100 / len(STEP_SLUGS)),
        "prev_step": STEP_SLUGS[index - 1] if index else None,
        "steps": ONBOARDING_STEPS,
        "photos": user.photos.all() if is_photos else None,
        "max_photos": CFG["MAX_PROFILE_PHOTOS"],
    }
    return render(request, "accounts/onboarding.html", context)


@login_required
@require_POST
def delete_photo(request, pk):
    photo = get_object_or_404(ProfilePhoto, pk=pk, user=request.user)
    photo.delete()
    request.user.refresh_stats()
    messages.info(request, "Photo removed.")
    return redirect(safe_next(request, reverse("accounts:onboarding", args=["photos"])))


@login_required
@require_POST
def make_main_photo(request, pk):
    photo = get_object_or_404(ProfilePhoto, pk=pk, user=request.user)
    others = list(request.user.photos.exclude(pk=photo.pk))
    photo.order = 0
    photo.save(update_fields=["order"])
    for i, p in enumerate(others, start=1):
        if p.order != i:
            p.order = i
            p.save(update_fields=["order"])
    return redirect("accounts:onboarding", step="photos")


# --- Profiles --------------------------------------------------------------
@login_required
def profile_detail(request, pk):
    from matching.algorithm import explain_pair
    from matching.models import Match, Swipe

    qs = User.objects.prefetch_related("photos", "interests", "listings__photos", "listings__amenities")
    profile = get_object_or_404(qs, pk=pk, is_active=True)
    me = request.user
    is_me = profile.pk == me.pk

    if not is_me:
        blocked_either = Block.objects.filter(
            Q(blocker=me, blocked=profile) | Q(blocker=profile, blocked=me)
        ).exists()
        if blocked_either or (profile.is_under_review and not me.is_staff):
            raise Http404

    context = {
        "profile": profile,
        "is_me": is_me,
        "trust_label": trust_label(profile.trust_score),
        "listings": [l for l in profile.listings.all() if l.is_active or is_me],
        "vibe_rows": vibe_rows(profile),
    }
    if not is_me:
        context.update(
            {
                "pair": explain_pair(me, profile),
                "my_swipe": Swipe.objects.filter(from_user=me, to_user=profile).first(),
                "match": Match.between(me, profile),
                "already_reported": Report.objects.filter(reporter=me, reported=profile).exists(),
                "report_form": ReportForm(),
            }
        )
    return render(request, "accounts/profile_detail.html", context)


def vibe_rows(user):
    from .choices import VIBE_FIELD_LABELS, VIBE_FIELDS

    rows = []
    for f in VIBE_FIELDS:
        value = getattr(user, f"get_{f}_display")()
        if value:
            rows.append((VIBE_FIELD_LABELS[f], value, f))
    return rows


@login_required
def my_profile(request):
    return redirect("accounts:profile", pk=request.user.pk)


# --- Report / block --------------------------------------------------------
@login_required
@require_POST
def report_user(request, pk):
    target = get_object_or_404(User, pk=pk)
    if target == request.user:
        return redirect("accounts:profile", pk=pk)
    form = ReportForm(request.POST)
    if form.is_valid():
        report, created = Report.objects.get_or_create(
            reporter=request.user, reported=target, defaults=form.cleaned_data
        )
        open_reports = Report.objects.filter(reported=target, resolved=False).count()
        if open_reports >= CFG["REPORTS_TO_HIDE"] and not target.is_under_review:
            User.objects.filter(pk=target.pk).update(is_under_review=True)
        messages.success(request, "Thanks for the heads up. Our team will take a look 🛡️")
    return redirect("matching:deck")


@login_required
@require_POST
def block_user(request, pk):
    from matching.models import Match, Swipe

    target = get_object_or_404(User, pk=pk)
    if target == request.user:
        return redirect("accounts:profile", pk=pk)
    with transaction.atomic():
        Block.objects.get_or_create(blocker=request.user, blocked=target)
        m = Match.between(request.user, target)
        if m:
            m.delete()
        Swipe.objects.filter(
            Q(from_user=request.user, to_user=target) | Q(from_user=target, to_user=request.user)
        ).delete()
    messages.success(request, f"{target.display_name} is blocked. You won't see each other anymore.")
    return redirect("matching:deck")


@login_required
@require_POST
def unblock_user(request, pk):
    Block.objects.filter(blocker=request.user, blocked_id=pk).delete()
    messages.info(request, "Unblocked.")
    return redirect("accounts:settings")


# --- Settings --------------------------------------------------------------
@login_required
def settings_view(request):
    user = request.user
    role_form = RoleSwitchForm(instance=user, prefix="role")
    phone_form = PhoneForm(prefix="phone", initial={"phone": user.phone})
    otp_form = OtpForm(prefix="otp")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "role":
            role_form = RoleSwitchForm(request.POST, instance=user, prefix="role")
            if role_form.is_valid():
                role_form.save()
                messages.success(request, f"You're now a {user.get_role_display().lower()} 🔁")
                return redirect("accounts:settings")
        elif action == "send_otp":
            phone_form = PhoneForm(request.POST, prefix="phone")
            if phone_form.is_valid():
                phone = phone_form.cleaned_data["phone"]
                if phone != user.phone:
                    user.phone, user.phone_verified = phone, False
                    user.save(update_fields=["phone", "phone_verified"])
                otp.send_otp(request, phone)
                messages.info(request, "Code sent! (Dev stub: check the runserver terminal.)")
                return redirect("accounts:settings")
        elif action == "verify_otp":
            otp_form = OtpForm(request.POST, prefix="otp")
            if otp_form.is_valid() and user.phone and otp.verify_otp(request, user.phone, otp_form.cleaned_data["code"]):
                user.phone_verified = True
                user.save(update_fields=["phone_verified"])
                user.refresh_stats()
                messages.success(request, "Phone verified 📱")
                return redirect("accounts:settings")
            messages.error(request, "That code didn't work. Try sending a new one.")

    context = {
        "role_form": role_form,
        "phone_form": phone_form,
        "otp_form": otp_form,
        "steps": ONBOARDING_STEPS,
        "blocked": Block.objects.filter(blocker=user).select_related("blocked"),
        "trust_label": trust_label(user.trust_score),
        "missing": user.missing_items(),
    }
    return render(request, "accounts/settings.html", context)
