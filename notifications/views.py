import json

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .models import Notification, PushSubscription
from .service import mark_read, notify, push_enabled, unread_count


@login_required
def inbox(request):
    items = list(Notification.objects.filter(user=request.user)[:60])
    mark_read(request.user)  # opening the inbox clears the badge
    return render(request, "notifications/inbox.html", {"items": items})


@login_required
def open_notification(request, pk):
    n = get_object_or_404(Notification, pk=pk, user=request.user)
    if n.read_at is None:
        n.read_at = timezone.now()
        n.save(update_fields=["read_at"])
    # Only follow our own relative URLs
    return redirect(n.url if n.url.startswith("/") and not n.url.startswith("//") else "notifications:inbox")


@login_required
@require_GET
def unread(request):
    return JsonResponse({"count": unread_count(request.user)})


@login_required
@require_POST
def mark_all_read(request):
    mark_read(request.user)
    if request.headers.get("x-requested-with") == "fetch":
        return JsonResponse({"ok": True})
    return redirect("notifications:inbox")


def _json(request):
    try:
        return json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return None


@login_required
@require_POST
def push_subscribe(request):
    if not push_enabled():
        return JsonResponse({"ok": False, "error": "Push isn't configured on this server."}, status=503)
    data = _json(request)
    if not data:
        return HttpResponseBadRequest("Bad JSON")
    endpoint = data.get("endpoint") or ""
    keys = data.get("keys") or {}
    if not endpoint.startswith("https://") or len(endpoint) > 500 or not keys.get("p256dh") or not keys.get("auth"):
        return HttpResponseBadRequest("Bad subscription")
    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "user": request.user,
            "p256dh": keys["p256dh"][:200],
            "auth": keys["auth"][:100],
            "user_agent": request.headers.get("user-agent", "")[:200],
        },
    )
    return JsonResponse({"ok": True})


@login_required
@require_POST
def push_unsubscribe(request):
    data = _json(request) or {}
    PushSubscription.objects.filter(user=request.user, endpoint=data.get("endpoint", "")).delete()
    return JsonResponse({"ok": True})


@login_required
@require_POST
def push_test(request):
    notify(request.user, Notification.SYSTEM, "Notifications are on 🎉",
           "You'll hear about new matches and messages here.", "/notifications/", group="test")
    return JsonResponse({"ok": True, "devices": request.user.push_subscriptions.count()})
