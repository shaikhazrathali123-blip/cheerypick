"""
Swipe deck ranking
==================

The deck starts from the same candidate pool as Discover (`find_matches`: every
hard filter and the 0–100 compatibility score), then re-ranks it to put the
people you're most likely to match with, and who are most likely to reply,
at the top:

    deck_score =  personal compatibility        0–100  (learned from your swipes)
               +  they already liked you           +8  (a match is one swipe away)
               +  recently active               up to +6  (fades over ~3 days)
               +  new on CheeriPick             up to +4  (first week, cold start)
               +  profile quality               up to +3  (completion %)
               −  no photo                         −10  (photo-less cards get passed)
               −  attention balancing           up to −6  (lots of unanswered likes already)
               +  daily shuffle                  0 to +3  (stable within a day)

Personal compatibility: the base weights in settings.CHEERIPICK["MATCH_WEIGHTS"]
are nudged by what you actually like. After at least 10 swipes (3+ likes and
3+ passes), each part of the score (lifestyle, interests, budget, distance, trust)
counts for more if it separates your likes from your passes, and less if it
doesn't. A weight can never drop below half or rise above double its base value.

The ranking signals are only used for ordering and are never sent to the
browser, so the client never learns who liked whom.
"""
from __future__ import annotations

import hashlib
import math
from datetime import date

from django.core.cache import cache
from django.db.models import Count, Exists, OuterRef
from django.utils import timezone

from .algorithm import compatibility, distance_between, find_matches, match_weights

LEARN_SAMPLE = 80          # most recent swipes to learn from
LEARN_MIN_SWIPES = 10
LEARN_MIN_EACH = 3         # likes AND passes needed
LEARN_STRENGTH = 2.0       # how hard a clear preference pulls a weight
CACHE_SECONDS = 600

BOOST_LIKED_YOU = 8.0
BOOST_ACTIVE = 6.0
ACTIVE_DECAY_DAYS = 3.0
BOOST_NEW = 4.0
NEW_USER_DAYS = 7
BOOST_QUALITY = 3.0
PENALTY_NO_PHOTO = 10.0
PENALTY_POPULAR_MAX = 6.0
POPULAR_LIKES_PER_POINT = 5   # −1 point per 5 unanswered incoming likes
JITTER_MAX = 3.0


# ---------------------------------------------------------------------------
# Learning from the viewer's swipes
# ---------------------------------------------------------------------------
def learned_weights(viewer):
    """Base weights nudged towards what this viewer actually likes."""
    from .models import Swipe

    base = dict(match_weights())
    n_swipes = Swipe.objects.filter(from_user=viewer).count()
    if n_swipes < LEARN_MIN_SWIPES or not viewer.has_location:
        return base

    key = f"deck-weights:{viewer.pk}:{n_swipes}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    swipes = (
        Swipe.objects.filter(from_user=viewer, to_user__is_active=True)
        .select_related("to_user")
        .prefetch_related("to_user__interests")
        .order_by("-created_at")[:LEARN_SAMPLE]
    )
    radius = viewer.search_radius_km or 10
    sums = {"like": dict.fromkeys(base, 0.0), "pass": dict.fromkeys(base, 0.0)}
    counts = {"like": 0, "pass": 0}
    for s in swipes:
        other = s.to_user
        if not other.has_location:
            continue
        _, parts = compatibility(viewer, other, distance_between(viewer, other), radius)
        bucket = "like" if s.action == Swipe.LIKE else "pass"
        counts[bucket] += 1
        for k in base:
            sums[bucket][k] += parts.get(k, 0.0)

    if counts["like"] < LEARN_MIN_EACH or counts["pass"] < LEARN_MIN_EACH:
        weights = base
    else:
        weights = {}
        for k, w in base.items():
            gap = sums["like"][k] / counts["like"] - sums["pass"][k] / counts["pass"]  # −1 … 1
            factor = min(2.0, max(0.5, 1 + LEARN_STRENGTH * gap))
            weights[k] = w * factor
        total = sum(weights.values()) or 1
        base_total = sum(base.values()) or 1
        weights = {k: v / total * base_total for k, v in weights.items()}

    cache.set(key, weights, CACHE_SECONDS)
    return weights


def personal_score(breakdown, weights):
    total = sum(weights.values()) or 1
    return 100 * sum(breakdown.get(k, 0.0) * w for k, w in weights.items()) / total


# ---------------------------------------------------------------------------
# Ranking signals
# ---------------------------------------------------------------------------
def activity_boost(last_active, now):
    if not last_active:
        return 0.0
    days = max(0.0, (now - last_active).total_seconds() / 86400)
    return BOOST_ACTIVE * math.exp(-days / ACTIVE_DECAY_DAYS)


def newcomer_boost(date_joined, now):
    if not date_joined:
        return 0.0
    days = (now - date_joined).total_seconds() / 86400
    return BOOST_NEW * max(0.0, 1 - days / NEW_USER_DAYS)


def daily_jitter(viewer_id, candidate_id, day=None):
    """Same order all day (so batches don't shuffle), fresh order tomorrow."""
    day = day or date.today()
    digest = hashlib.sha1(f"{viewer_id}:{candidate_id}:{day.isoformat()}".encode()).digest()
    return JITTER_MAX * digest[0] / 255


def popularity_penalty(pending_likes):
    return min(PENALTY_POPULAR_MAX, pending_likes / POPULAR_LIKES_PER_POINT)


# ---------------------------------------------------------------------------
# The deck
# ---------------------------------------------------------------------------
def deck_results(viewer, exclude_ids=(), limit=10):
    """Next `limit` MatchResults for the swipe deck, best first."""
    from .models import Swipe

    exclude = set(exclude_ids)
    results = [r for r in find_matches(viewer, filters={"exclude_liked": True}, sort="best") if r.user.pk not in exclude]
    if not results:
        return []

    ids = [r.user.pk for r in results]
    liked_me = set(
        Swipe.objects.filter(to_user=viewer, from_user__in=ids, action=Swipe.LIKE).values_list("from_user_id", flat=True)
    )
    # Likes each candidate has received and not answered yet (their "inbox size")
    answered = Swipe.objects.filter(from_user=OuterRef("to_user"), to_user=OuterRef("from_user"))
    pending_likes = dict(
        Swipe.objects.filter(to_user__in=ids, action=Swipe.LIKE)
        .exclude(Exists(answered))
        .values("to_user")
        .annotate(n=Count("id"))
        .values_list("to_user", "n")
    )

    weights = learned_weights(viewer)
    now = timezone.now()
    today = date.today()
    for r in results:
        u = r.user
        r.deck_score = (
            personal_score(r.breakdown, weights)
            + (BOOST_LIKED_YOU if u.pk in liked_me else 0.0)
            + activity_boost(u.last_active, now)
            + newcomer_boost(u.date_joined, now)
            + BOOST_QUALITY * (u.profile_completion or 0) / 100
            - (0.0 if u.photo_list() else PENALTY_NO_PHOTO)
            - popularity_penalty(pending_likes.get(u.pk, 0))
            + daily_jitter(viewer.pk, u.pk, today)
        )

    results.sort(key=lambda r: (-r.deck_score, r.distance_km or 0))
    return results[:limit]
