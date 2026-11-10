from django.conf import settings
from django.db import models


class Message(models.Model):
    match = models.ForeignKey("matching.Match", on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="messages_sent")
    body = models.TextField(max_length=1000)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [models.Index(fields=["match", "read_at"])]

    def __str__(self):
        return f"{self.sender}: {self.body[:40]}"

    def as_dict(self, viewer):
        from django.utils import timezone

        return {
            "id": self.id,
            "body": self.body,
            "mine": self.sender_id == viewer.pk,
            "time": timezone.localtime(self.created_at).strftime("%H:%M"),
        }
