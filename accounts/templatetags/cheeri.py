from django import template
from django.conf import settings
from django.contrib.humanize.templatetags.humanize import intcomma

from accounts.choices import VIBE_FIELD_LABELS

register = template.Library()


@register.filter
def money(value):
    if value in (None, ""):
        return "—"
    return f"{settings.CHEERIPICK['CURRENCY_SYMBOL']}{intcomma(int(value))}"


@register.filter
def km(value):
    if value is None:
        return "?"
    if value < 1:
        return f"{int(value * 1000)} m"
    return f"{value:.1f} km"


@register.filter
def ago(value):
    """'just now' for the last minute, otherwise '5 minutes ago'."""
    from django.utils import timezone
    from django.utils.timesince import timesince

    if not value:
        return ""
    if (timezone.now() - value).total_seconds() < 60:
        return "just now"
    return f"{timesince(value).split(',')[0]} ago"


@register.filter
def vibe_label(field_name):
    return VIBE_FIELD_LABELS.get(field_name, field_name)


@register.filter
def trust_tone(score):
    return "high" if score >= 70 else ("mid" if score >= 40 else "low")


@register.simple_tag(takes_context=True)
def active(context, *url_prefixes):
    """'is-active' when the current path starts with any prefix."""
    path = context["request"].path
    return "is-active" if any(path.startswith(p) for p in url_prefixes) else ""
