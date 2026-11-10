"""
CheeriPick matching algorithm
=============================

Pipeline for one viewer:

    1. Hard filters  — people who fail any of these never show up:
         * outside the viewer's distance radius
         * budget ranges don't overlap
         * any dealbreaker (either person's) doesn't match
         * gender preference not satisfied, checked in BOTH directions
         * blocked (either way), reported or passed by the viewer
         * move-in dates more than 60 days apart
    2. Distance      — cheap lat/lon bounding box in SQL, then exact
                       Haversine distance in Python.
    3. Score 0–100   — weighted blend (weights live in settings.CHEERIPICK):
         lifestyle 45% · interests 15% · budget 15% · distance 15% · trust 10%
    4. Presentation  — label ("Vibe twins 💯" …), distance, top-3 reasons.

Everything that doesn't touch the database is a pure function so it can be
unit-tested with unsaved User objects.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Prefetch, Q
from django.utils import timezone

from accounts import choices as c

EARTH_RADIUS_KM = 6371.0088


def _cfg():
    return settings.CHEERIPICK


def match_weights():
    return _cfg()["MATCH_WEIGHTS"]


# ---------------------------------------------------------------------------
# Step 2 — Distance
# ---------------------------------------------------------------------------
def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two points in kilometres."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def bounding_box(lat, lon, radius_km):
    """
    (min_lat, max_lat, min_lon, max_lon) of a box that fully contains the
    circle of `radius_km` around (lat, lon). Used as a fast SQL pre-filter;
    the exact circle check happens afterwards with haversine_km().
    """
    dlat = math.degrees(radius_km / EARTH_RADIUS_KM)
    cos_lat = math.cos(math.radians(lat))
    if cos_lat < 1e-6:  # at the poles every longitude is "close"
        dlon = 180.0
    else:
        dlon = math.degrees(radius_km / (EARTH_RADIUS_KM * cos_lat))
    min_lat, max_lat = max(-90.0, lat - dlat), min(90.0, lat + dlat)
    min_lon, max_lon = lon - dlon, lon + dlon
    # Crossing the antimeridian: just widen to all longitudes (rare, still correct).
    if min_lon < -180 or max_lon > 180:
        min_lon, max_lon = -180.0, 180.0
    return min_lat, max_lat, min_lon, max_lon


def distance_between(a, b):
    if not (a.has_location and b.has_location):
        return None
    return haversine_km(a.latitude, a.longitude, b.latitude, b.longitude)


# ---------------------------------------------------------------------------
# Step 1 — Hard filters (pure functions)
# ---------------------------------------------------------------------------
def budget_overlap(a_min, a_max, b_min, b_max):
    """Overlap size of two ranges, or None when they don't overlap / are missing."""
    if None in (a_min, a_max, b_min, b_max):
        return None
    overlap = min(a_max, b_max) - max(a_min, b_min)
    return overlap if overlap >= 0 else None


def gender_pref_satisfied(chooser, other):
    """Does `other` satisfy `chooser`'s roommate gender preference?"""
    pref = chooser.preferred_gender
    if pref == c.PREF_GENDER_SAME:
        return bool(chooser.gender) and other.gender == chooser.gender
    if pref == c.PREF_GENDER_SPECIFIC:
        return bool(chooser.preferred_gender_value) and other.gender == chooser.preferred_gender_value
    return True


def values_compatible(field_name, a, b):
    """
    Used for dealbreakers: is this a "match" on this field?
    Slightly human-friendly rather than strictly equal:
      * 1–5 scales match within 1 step
      * "flexible" sleepers fit anyone; "okay with pets" fits pet owners and pet-free people
      * "any" food fits anyone
    Missing values never match (a dealbreaker is a must-know).
    """
    if a in (None, "") or b in (None, ""):
        return False
    if field_name in c.VIBE_SCALE_FIELDS:
        return abs(a - b) <= 1
    if field_name == "sleep_schedule":
        return a == b or "flexible" in (a, b)
    if field_name == "pets":
        return {a, b} != {"have", "no"}
    if field_name == "food_habits":
        return a == b or "any" in (a, b)
    return a == b


def dealbreakers_ok(a, b):
    fields = set(a.dealbreakers or []) | set(b.dealbreakers or [])
    return all(values_compatible(f, getattr(a, f), getattr(b, f)) for f in fields if f in c.VIBE_FIELDS)


def failed_dealbreakers(a, b):
    fields = set(a.dealbreakers or []) | set(b.dealbreakers or [])
    return [f for f in fields if f in c.VIBE_FIELDS and not values_compatible(f, getattr(a, f), getattr(b, f))]


def move_in_ok(a_date, b_date, window_days=None):
    """Unknown dates pass; known dates must be within the window."""
    window_days = window_days if window_days is not None else _cfg()["MOVE_IN_WINDOW_DAYS"]
    if a_date is None or b_date is None:
        return True
    return abs((a_date - b_date).days) <= window_days


def hard_filter_failures(viewer, candidate, radius_km, distance_km=None, budget=None, move_in=None):
    """
    List of human-readable reasons the pair fails the hard filters (empty = pass).
    Relationship filters (blocked / reported / passed) are handled in SQL by
    candidate_queryset() because they need the database.

    `budget` and `move_in` let the Discover filter form override the viewer's own values.
    """
    failures = []
    if distance_km is None:
        distance_km = distance_between(viewer, candidate)
    if distance_km is None:
        failures.append("Missing location")
    elif distance_km > radius_km:
        failures.append(f"More than {radius_km} km away")

    v_min, v_max = budget if budget else (viewer.budget_min, viewer.budget_max)
    if budget_overlap(v_min, v_max, candidate.budget_min, candidate.budget_max) is None:
        failures.append("Budgets don't overlap")

    broken = failed_dealbreakers(viewer, candidate)
    if broken:
        names = ", ".join(c.VIBE_FIELD_LABELS[f].lower() for f in sorted(broken))
        failures.append(f"Dealbreaker: {names}")

    if not gender_pref_satisfied(viewer, candidate) or not gender_pref_satisfied(candidate, viewer):
        failures.append("Gender preferences don't line up")

    if not move_in_ok(move_in or viewer.move_in_date, candidate.move_in_date):
        failures.append(f"Move-in dates over {_cfg()['MOVE_IN_WINDOW_DAYS']} days apart")
    return failures


# ---------------------------------------------------------------------------
# Step 3 — Compatibility score
# ---------------------------------------------------------------------------
def lifestyle_similarity(a, b):
    """
    Average per-field similarity over vibe fields both people filled in:
      * 1–5 scales: 1 − |a − b| / 4
      * choice fields: 1 if identical else 0
    Returns 0.5 (neutral) if there's nothing to compare.
    """
    scores = []
    for f in c.VIBE_SCALE_FIELDS:
        x, y = getattr(a, f), getattr(b, f)
        if x is not None and y is not None:
            scores.append(1 - abs(x - y) / 4)
    for f in c.VIBE_CHOICE_FIELDS:
        x, y = getattr(a, f), getattr(b, f)
        if x and y:
            scores.append(1.0 if x == y else 0.0)
    return sum(scores) / len(scores) if scores else 0.5


def jaccard(a_set, b_set):
    if not a_set and not b_set:
        return 0.0
    return len(a_set & b_set) / len(a_set | b_set)


def budget_score(a_min, a_max, b_min, b_max):
    """
    Overlap relative to the narrower range: 1.0 when one range sits fully
    inside the other, approaching 0 as the overlap shrinks to a sliver.
    """
    overlap = budget_overlap(a_min, a_max, b_min, b_max)
    if overlap is None:
        return 0.0
    narrower = min(a_max - a_min, b_max - b_min)
    if narrower <= 0:
        return 1.0  # a fixed number that sits inside the other range
    return min(1.0, overlap / narrower)


def distance_score(distance_km, radius_km):
    """Linear decay: 1.0 at 0 km, 0.0 at the radius limit."""
    if distance_km is None or radius_km <= 0:
        return 0.0
    return max(0.0, 1 - distance_km / radius_km)


def interest_map(user):
    """
    {id: Interest}, cached on the instance so scoring many candidates against
    one viewer costs a single query (candidates come prefetched).
    """
    cached = getattr(user, "_interest_map", None)
    if cached is not None:
        return cached
    result = {i.id: i for i in user.interests.all()} if user.pk else {}
    user._interest_map = result
    return result


def score_label(score):
    if score >= 85:
        return "Vibe twins 💯"
    if score >= 70:
        return "Solid match"
    if score >= 55:
        return "Could work"
    return "Wildcard 🎲"


def score_tone(score):
    """CSS hook for badge colour."""
    if score >= 85:
        return "twins"
    if score >= 70:
        return "solid"
    if score >= 55:
        return "maybe"
    return "wild"


def compatibility(viewer, candidate, distance_km, radius_km, budget=None):
    """
    Returns (score 0–100, breakdown dict of 0–1 components).
    """
    w = match_weights()
    v_min, v_max = budget if budget else (viewer.budget_min, viewer.budget_max)
    parts = {
        "lifestyle": lifestyle_similarity(viewer, candidate),
        "interests": jaccard(set(interest_map(viewer)), set(interest_map(candidate))),
        "budget": budget_score(v_min, v_max, candidate.budget_min, candidate.budget_max),
        "distance": distance_score(distance_km, radius_km),
        "trust": (candidate.trust_score or 0) / 100,
    }
    total_weight = sum(w.values()) or 1
    raw = sum(parts[k] * w.get(k, 0) for k in parts) / total_weight
    return round(raw * 100), parts


# ---------------------------------------------------------------------------
# Step 4 — Why you matched
# ---------------------------------------------------------------------------
HIGH_PRIORITY_FIELDS = {"sleep_schedule", "smoking", "social_style", "food_habits", "pets"}


def match_reasons(viewer, candidate, distance_km=None, limit=3):
    """Top `limit` short, emoji-flavoured reasons this pair works."""
    reasons = []  # (priority, text)

    for f in c.VIBE_CHOICE_FIELDS:
        x, y = getattr(viewer, f), getattr(candidate, f)
        if x and x == y and (f, x) in c.SHARED_VIBE_REASONS:
            reasons.append((3.0 if f in HIGH_PRIORITY_FIELDS else 2.0, c.SHARED_VIBE_REASONS[(f, x)]))

    vc, cc = viewer.cleanliness, candidate.cleanliness
    if vc and cc:
        if vc >= 4 and cc >= 4:
            reasons.append((3.2, "Both neat freaks ✨"))
        elif vc == cc:
            reasons.append((2.0, "Same take on tidiness 🧽"))
    vn, cn = viewer.noise_tolerance, candidate.noise_tolerance
    if vn and cn:
        if vn <= 2 and cn <= 2:
            reasons.append((2.6, "Both love a quiet home 🤫"))
        elif vn >= 4 and cn >= 4:
            reasons.append((2.4, "Both fine with a bit of noise 🔊"))

    mine, theirs = interest_map(viewer), interest_map(candidate)
    shared = sorted(set(mine) & set(theirs), key=lambda i: mine[i].name)
    for i, iid in enumerate(shared[:2]):
        it = mine[iid]
        reasons.append((3.1 - i * 0.6, f"Both love {it.name.lower()} {it.emoji}".strip()))

    if distance_km is not None and distance_km < 2:
        reasons.append((2.8, f"Only {distance_km:.1f} km apart 📍"))
    if budget_score(viewer.budget_min, viewer.budget_max, candidate.budget_min, candidate.budget_max) >= 0.8:
        reasons.append((2.2, "Budgets line up 💸"))
    if viewer.move_in_date and candidate.move_in_date and abs((viewer.move_in_date - candidate.move_in_date).days) <= 7:
        reasons.append((2.1, "Moving around the same time 📦"))

    reasons.sort(key=lambda r: -r[0])
    seen, out = set(), []
    for _, text in reasons:
        if text not in seen:
            seen.add(text)
            out.append(text)
        if len(out) == limit:
            break
    return out


# ---------------------------------------------------------------------------
# Putting it together
# ---------------------------------------------------------------------------
@dataclass
class MatchResult:
    user: object
    score: int
    distance_km: float | None
    reasons: list = field(default_factory=list)
    breakdown: dict = field(default_factory=dict)
    failures: list = field(default_factory=list)

    @property
    def label(self):
        return score_label(self.score)

    @property
    def tone(self):
        return score_tone(self.score)

    @property
    def is_fit(self):
        return not self.failures

    @property
    def breakdown_percent(self):
        return {k: round(v * 100) for k, v in self.breakdown.items()}


def build_result(viewer, candidate, radius_km, distance_km=None, budget=None, move_in=None):
    if distance_km is None:
        distance_km = distance_between(viewer, candidate)
    score, parts = compatibility(viewer, candidate, distance_km, radius_km, budget=budget)
    return MatchResult(
        user=candidate,
        score=score,
        distance_km=distance_km,
        reasons=match_reasons(viewer, candidate, distance_km),
        breakdown=parts,
        failures=hard_filter_failures(viewer, candidate, radius_km, distance_km, budget=budget, move_in=move_in),
    )


def explain_pair(viewer, other):
    """Score + hard-filter verdict for a single profile page (radius = viewer's own)."""
    return build_result(viewer, other, viewer.search_radius_km or _cfg()["DEFAULT_RADIUS_KM"])


def excluded_ids(viewer, exclude_liked=False):
    """Everyone the viewer must never see: blocks (both ways), reports, passes (+ likes)."""
    from accounts.models import Block, Report

    from .models import Swipe

    ids = set(Block.objects.filter(blocker=viewer).values_list("blocked_id", flat=True))
    ids |= set(Block.objects.filter(blocked=viewer).values_list("blocker_id", flat=True))
    ids |= set(Report.objects.filter(reporter=viewer).values_list("reported_id", flat=True))
    actions = [Swipe.PASS, Swipe.LIKE] if exclude_liked else [Swipe.PASS]
    ids |= set(Swipe.objects.filter(from_user=viewer, action__in=actions).values_list("to_user_id", flat=True))
    ids.add(viewer.pk)
    return ids


def candidate_queryset(viewer, radius_km, filters=None):
    """
    Database pre-filter: visibility rules, bounding box, budget overlap,
    move-in window, the viewer's own gender preference, relationship
    exclusions and the Discover form filters. Exact checks happen in Python.
    """
    from accounts.models import User
    from listings.models import Listing

    cfg = _cfg()
    filters = filters or {}
    now = timezone.now()

    qs = User.objects.filter(
        is_active=True,
        is_staff=False,
        is_hidden_inactive=False,
        is_under_review=False,
        profile_completion__gte=cfg["MIN_COMPLETION_FOR_DISCOVERY"],
        last_active__gte=now - timedelta(days=cfg["INACTIVE_DAYS"]),
        latitude__isnull=False,
        longitude__isnull=False,
    ).exclude(pk__in=excluded_ids(viewer, filters.get("exclude_liked", False)))

    # Bounding box — uses the (latitude, longitude) index
    min_lat, max_lat, min_lon, max_lon = bounding_box(viewer.latitude, viewer.longitude, radius_km)
    qs = qs.filter(latitude__range=(min_lat, max_lat), longitude__range=(min_lon, max_lon))

    # Budget overlap: their min <= my max AND their max >= my min
    b_min, b_max = filters.get("budget") or (viewer.budget_min, viewer.budget_max)
    if b_min is not None and b_max is not None:
        qs = qs.filter(budget_min__lte=b_max, budget_max__gte=b_min)

    move_in = filters.get("move_in") or viewer.move_in_date
    if move_in:
        window = timedelta(days=cfg["MOVE_IN_WINDOW_DAYS"])
        qs = qs.filter(Q(move_in_date__isnull=True) | Q(move_in_date__range=(move_in - window, move_in + window)))

    # Viewer's own gender preference (the reverse direction is checked in Python)
    if viewer.preferred_gender == c.PREF_GENDER_SAME and viewer.gender:
        qs = qs.filter(gender=viewer.gender)
    elif viewer.preferred_gender == c.PREF_GENDER_SPECIFIC and viewer.preferred_gender_value:
        qs = qs.filter(gender=viewer.preferred_gender_value)

    # Discover form filters
    if filters.get("role"):
        qs = qs.filter(role=filters["role"])
    if filters.get("room_type"):
        qs = qs.filter(
            role=c.ROLE_HOST,
            listings__status=Listing.STATUS_ACTIVE,
            listings__room_type=filters["room_type"],
        ).distinct()
    if filters.get("verified_only") or filters.get("has_photos"):
        qs = qs.annotate(n_photos=Count("photos", distinct=True)).filter(n_photos__gt=0)
    if filters.get("verified_only"):
        qs = qs.filter(email_verified=True)

    active_listings = Prefetch(
        "listings",
        queryset=Listing.objects.filter(status=Listing.STATUS_ACTIVE).prefetch_related("photos"),
        to_attr="active_listings",
    )
    return qs.prefetch_related("photos", "interests", active_listings)


def lowest_rent(user):
    rents = [l.rent for l in getattr(user, "active_listings", [])]
    if rents:
        return min(rents)
    return user.budget_min if user.budget_min is not None else float("inf")


SORTERS = {
    "best": lambda r: (-r.score, r.distance_km or 0),
    "nearest": lambda r: (r.distance_km or 0, -r.score),
    "newest": lambda r: (-r.user.date_joined.timestamp(), -r.score),
    "rent": lambda r: (lowest_rent(r.user), -r.score),
}


def find_matches(viewer, radius_km=None, filters=None, sort="best"):
    """
    Full pipeline for Discover / Quick Pick. Returns a sorted list of
    MatchResult objects that passed every hard filter.
    """
    if not viewer.has_location:
        return []
    filters = filters or {}
    cfg = _cfg()
    radius_km = max(1, min(radius_km or viewer.search_radius_km or cfg["DEFAULT_RADIUS_KM"], cfg["MAX_RADIUS_KM"]))

    budget = filters.get("budget")
    move_in = filters.get("move_in")
    results = []
    for cand in candidate_queryset(viewer, radius_km, filters):
        d = haversine_km(viewer.latitude, viewer.longitude, cand.latitude, cand.longitude)
        if d > radius_km:
            continue  # inside the box but outside the circle
        result = build_result(viewer, cand, radius_km, d, budget=budget, move_in=move_in)
        if result.failures:
            continue
        results.append(result)

    results.sort(key=SORTERS.get(sort, SORTERS["best"]))
    return results
