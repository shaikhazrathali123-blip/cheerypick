from django.conf import settings
from django.db import models


class Notification(models.Model):
    """In-app notification (the bell). Push notifications are sent alongside these."""

    MATCH, MESSAGE, LIKE, SYSTEM = "match", "message", "like", "system"
    KIND_CHOICES = [(MATCH, "New match"), (MESSAGE, "New message"), (LIKE, "New like"), (SYSTEM, "System")]
    ICONS = {MATCH: "🍒", MESSAGE: "💬", LIKE: "👀", SYSTEM: "🔔"}

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    kind = models.CharField(max_length=10, choices=KIND_CHOICES)
    title = models.CharField(max_length=120)
    body = models.CharField(max_length=255, blank=True)
    url = models.CharField(max_length=255, blank=True)
    # Groups notifications that should replace each other (e.g. one per chat)
    group = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "read_at"])]

    def __str__(self):
        return f"{self.user}: {self.title}"

    @property
    def icon(self):
        return self.ICONS.get(self.kind, "🔔")

    @property
    def is_unread(self):
        return self.read_at is None


class PushSubscription(models.Model):
    """One browser/device that agreed to receive push notifications."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="push_subscriptions")
    endpoint = models.URLField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    user_agent = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} @ {self.user_agent[:40] or self.endpoint[:40]}"
