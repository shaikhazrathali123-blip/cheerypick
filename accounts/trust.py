"""
"Serious score" — a 0–100 trust indicator.

    40%  profile completeness
    30%  verification (email 15, photo 10, phone 5)
    20%  chat response rate (replies to people who messaged them first)
    10%  account age (maxes out at 90 days)
"""
from django.db.models import Q


def chat_response_rate(user):
    """
    Share of matches where the other person messaged this user AND this user
    replied at least once. Returns None when nobody has messaged them yet.
    """
    from chat.models import Message
    from matching.models import Match

    match_ids = Match.objects.filter(Q(user_a=user) | Q(user_b=user)).values_list("id", flat=True)
    incoming = set(
        Message.objects.filter(match_id__in=match_ids).exclude(sender=user).values_list("match_id", flat=True)
    )
    if not incoming:
        return None
    replied = set(
        Message.objects.filter(match_id__in=incoming, sender=user).values_list("match_id", flat=True)
    )
    return len(replied) / len(incoming)


def compute_trust_score(user):
    completeness = user.profile_completion / 100

    has_photo = user.photos.exists() if user.pk else False
    verification = (
        (0.5 if user.email_verified else 0)
        + (1 / 3 if has_photo else 0)
        + (1 / 6 if user.phone_verified else 0)
    )

    rate = chat_response_rate(user) if user.pk else None
    response = 0.5 if rate is None else rate  # neutral until there's data

    age = min(user.account_age_days / 90, 1.0) if user.date_joined else 0

    score = 0.40 * completeness + 0.30 * verification + 0.20 * response + 0.10 * age
    return round(score * 100)


def trust_label(score):
    if score >= 80:
        return "Super serious 🔥"
    if score >= 60:
        return "Legit"
    if score >= 40:
        return "Getting there"
    return "New here"
