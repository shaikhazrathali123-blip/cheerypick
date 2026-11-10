from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Count, OuterRef, Q, Subquery
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import discovery_required
from accounts.models import Block, User
from accounts.views import safe_next
from chat.models import Message

from notifications.models import Notification
from notifications.service import notify

from .algorithm import explain_pair, find_matches
from .forms import DiscoverFilterForm
from .models import Match, Swipe

CFG = settings.CHEERIPICK


@discovery_required
def discover(request):
    viewer = request.user
    data = None
    if any(k != "page" for k in request.GET):
        data = request.GET.copy()
        data.setdefault("radius", str(viewer.search_radius_km))
        data.setdefault("sort", "best")
    form = DiscoverFilterForm(data, initial={"radius": viewer.search_radius_km, "sort": "best"})
    radius = viewer.search_radius_km
    sort = "best"
    filters = {}
    if form.is_bound and form.is_valid():
        radius = form.cleaned_data.get("radius") or radius
        sort = form.cleaned_data.get("sort") or "best"
        filters = form.to_filters(viewer)

    results = find_matches(viewer, radius_km=radius, filters=filters, sort=sort)
    page = Paginator(results, CFG["DISCOVER_PAGE_SIZE"]).get_page(request.GET.get("page"))

    liked_ids = set(
        Swipe.objects.filter(from_user=viewer, action=Swipe.LIKE, to_user__in=[r.user.pk for r in page])
        .values_list("to_user_id", flat=True)
    )
    for r in page:
        r.liked = r.user.pk in liked_ids
    params = request.GET.copy()
    params.pop("page", None)
    return render(
        request,
        "matching/discover.html",
        {
            "form": form,
            "page": page,
            "radius": radius,
            "total": len(results),
            "querystring": params.urlencode(),
        },
    )


@discovery_required
def quick_pick(request):
    results = find_matches(request.user, filters={"exclude_liked": True}, sort="best")
    current = results[0] if results else None
    return render(request, "matching/quick_pick.html", {"result": current, "remaining": max(len(results) - 1, 0)})


def swipe_target(viewer, pk):
    """The user being swiped on, or 404 if they're yourself, hidden or blocked."""
    target = get_object_or_404(User, pk=pk, is_active=True, is_under_review=False)
    if target == viewer:
        raise Http404
    if Block.objects.filter(Q(blocker=viewer, blocked=target) | Q(blocker=target, blocked=viewer)).exists():
        raise Http404
    return target


def record_swipe(viewer, target, action):
    """Save a like/pass. Returns the Match if this like made it mutual, else None."""
    _, new_swipe = Swipe.objects.update_or_create(from_user=viewer, to_user=target, defaults={"action": action})
    if action != Swipe.LIKE:
        return None
    if not Swipe.objects.filter(from_user=target, to_user=viewer, action=Swipe.LIKE).exists():
        if new_swipe:
            # Anonymous on purpose: they find out who by swiping. Grouped so it never spams.
            notify(target, Notification.LIKE, "Someone likes you 👀",
                   "Keep swiping to find out who.", reverse("matching:deck"), group="likes")
        return None
    a, b = Match.ordered(viewer, target)
    try:
        with transaction.atomic():
            match, created = Match.objects.get_or_create(
                user_a=a, user_b=b, defaults={"score": explain_pair(viewer, target).score}
            )
    except IntegrityError:
        match, created = Match.objects.get(user_a=a, user_b=b), False
    if created:
        chat_url = reverse("chat:thread", args=[match.pk])
        for me, them in ((viewer, target), (target, viewer)):
            notify(me, Notification.MATCH, "It's a match! 🍒",
                   f"You and {them.display_name} liked each other. Say hi 👋", chat_url, group=f"match-{match.pk}")
    return match


@discovery_required
@require_POST
def swipe(request, pk):
    viewer = request.user
    target = swipe_target(viewer, pk)

    action = Swipe.LIKE if request.POST.get("action") == "like" else Swipe.PASS
    match = record_swipe(viewer, target, action)
    if match:
        return redirect("matching:its_a_match", pk=match.pk)
    if action == Swipe.LIKE:
        messages.success(request, f"Liked {target.display_name} 💖 We'll tell you if it's mutual.")
    return redirect(safe_next(request, reverse("matching:quick_pick")))


@login_required
def its_a_match(request, pk):
    match = get_object_or_404(Match.objects.select_related("user_a", "user_b"), pk=pk)
    if not match.includes(request.user):
        raise Http404
    other = match.other(request.user)
    return render(request, "matching/its_a_match.html", {"match": match, "other": other, "pair": explain_pair(request.user, other)})


@login_required
def my_matches(request):
    me = request.user
    last_msg = Message.objects.filter(match=OuterRef("pk")).order_by("-created_at")
    matches = (
        Match.for_user(me)
        .select_related("user_a", "user_b")
        .prefetch_related("user_a__photos", "user_b__photos")
        .annotate(
            last_body=Subquery(last_msg.values("body")[:1]),
            last_at=Subquery(last_msg.values("created_at")[:1]),
            unread=Count("messages", filter=Q(messages__read_at__isnull=True) & ~Q(messages__sender=me)),
        )
    )
    rows = sorted(
        ({"match": m, "other": m.other(me)} for m in matches),
        key=lambda r: r["match"].last_at or r["match"].created_at,
        reverse=True,
    )
    likes_you = Swipe.objects.filter(to_user=me, action=Swipe.LIKE).exclude(
        from_user__in=Swipe.objects.filter(from_user=me).values("to_user")
    ).count()
    return render(request, "matching/matches.html", {"rows": rows, "likes_you": likes_you})


# --- Swipe deck (card stack, drag to decide) --------------------------------
DECK_BATCH = 10


def deck_card(result):
    """JSON for one card. Only public profile info: no ranking signals."""
    from accounts.templatetags.cheeri import km, money

    u = result.user
    listing = (getattr(u, "active_listings", None) or [None])[0]
    if listing:
        price = f"{money(listing.rent)}/mo · {listing.title}"
    elif u.budget_max:
        price = f"Budget {money(u.budget_min)}–{money(u.budget_max)}"
    else:
        price = ""
    recently = timezone.now() - timedelta(hours=24)
    return {
        "id": u.pk,
        "name": u.display_name,
        "active": bool(u.last_active and u.last_active >= recently),
        "city": u.city,
        "age": u.age,
        "pronouns": u.pronouns,
        "verified": u.is_verified_badge,
        "initials": u.initials,
        "photos": [p.image.url for p in u.photo_list()],
        "distance": km(result.distance_km),
        "role": "🏠 Has a room" if u.is_host else "🔎 Looking",
        "occupation": u.get_occupation_display() if u.occupation else "",
        "bio": u.bio,
        "score": result.score,
        "label": result.label,
        "tone": result.tone,
        "reasons": result.reasons,
        "interests": [str(i) for i in u.interests.all()][:8],
        "price": price,
        "profile_url": u.get_absolute_url(),
        "swipe_url": reverse("matching:deck_swipe", args=[u.pk]),
    }


@discovery_required
def deck(request):
    from .ranking import deck_results

    cards = [deck_card(r) for r in deck_results(request.user, limit=DECK_BATCH)]
    return render(
        request,
        "matching/deck.html",
        {
            "cards": cards,
            "like_direction": CFG.get("SWIPE_LIKE_DIRECTION", "right"),
            "feed_url": reverse("matching:deck_feed"),
        },
    )


@discovery_required
def deck_feed(request):
    from .ranking import deck_results

    exclude = {int(x) for x in request.GET.get("exclude", "").split(",") if x.strip().isdigit()}
    results = deck_results(request.user, exclude_ids=exclude, limit=DECK_BATCH)
    return JsonResponse({"cards": [deck_card(r) for r in results]})


@discovery_required
@require_POST
def deck_swipe(request, pk):
    viewer = request.user
    target = swipe_target(viewer, pk)
    action = Swipe.LIKE if request.POST.get("action") == "like" else Swipe.PASS
    match = record_swipe(viewer, target, action)
    if not match:
        return JsonResponse({"ok": True, "match": None})
    photo = target.main_photo
    return JsonResponse({
        "ok": True,
        "match": {
            "name": target.display_name,
            "photo": photo.image.url if photo else "",
            "initials": target.initials,
            "my_photo": viewer.main_photo.image.url if viewer.main_photo else "",
            "my_initials": viewer.initials,
            "score": match.score,
            "chat_url": reverse("chat:thread", args=[match.pk]),
        },
    })
