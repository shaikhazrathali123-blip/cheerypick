from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from django.urls import reverse

from matching.models import Match
from notifications.models import Notification
from notifications.service import mark_read as mark_notifications_read
from notifications.service import notify

from .forms import MessageForm
from .models import Message


def _get_match(request, pk):
    match = get_object_or_404(
        Match.objects.select_related("user_a", "user_b").prefetch_related("user_a__photos", "user_b__photos"), pk=pk
    )
    if not match.includes(request.user):
        raise Http404  # only matched users can chat
    return match


def _mark_read(match, user):
    Message.objects.filter(match=match, read_at__isnull=True).exclude(sender=user).update(read_at=timezone.now())
    mark_notifications_read(user, group__in=[f"chat-{match.pk}", f"match-{match.pk}"])


@login_required
def thread(request, pk):
    match = _get_match(request, pk)
    other = match.other(request.user)
    form = MessageForm(request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            msg = Message.objects.create(match=match, sender=request.user, body=form.cleaned_data["body"])
            notify(other, Notification.MESSAGE, request.user.display_name, msg.body[:140],
                   reverse("chat:thread", args=[match.pk]), group=f"chat-{match.pk}")
            request.user.refresh_stats()  # response rate feeds the serious score
            if request.headers.get("x-requested-with") == "fetch":
                return JsonResponse({"ok": True})
            return redirect("chat:thread", pk=match.pk)
        if request.headers.get("x-requested-with") == "fetch":
            return JsonResponse({"ok": False, "errors": form.errors}, status=400)

    _mark_read(match, request.user)
    chat_messages = list(match.messages.all())
    return render(
        request,
        "chat/thread.html",
        {
            "match": match,
            "other": other,
            "chat_messages": chat_messages,
            "form": form,
            "last_id": chat_messages[-1].id if chat_messages else 0,
            "poll_ms": settings.CHEERIPICK["CHAT_POLL_SECONDS"] * 1000,
        },
    )


@login_required
@require_GET
def poll(request, pk):
    """Light JS polling endpoint: new messages since ?after=<id>."""
    match = _get_match(request, pk)
    try:
        after = int(request.GET.get("after", 0))
    except ValueError:
        after = 0
    new = list(match.messages.filter(id__gt=after))
    _mark_read(match, request.user)
    return JsonResponse({"messages": [m.as_dict(request.user) for m in new]})


@login_required
@require_GET
def unread_count(request):
    from .context_processors import unread_for

    return JsonResponse({"unread": unread_for(request.user)})
