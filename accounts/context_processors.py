from django.conf import settings


def cheeripick(request):
    cfg = settings.CHEERIPICK
    return {
        "CURRENCY": cfg["CURRENCY_SYMBOL"],
        "MIN_COMPLETION": cfg["MIN_COMPLETION_FOR_DISCOVERY"],
        "GOOGLE_LOGIN_ENABLED": bool(settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET),
    }
