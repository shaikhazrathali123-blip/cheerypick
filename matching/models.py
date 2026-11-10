from django.conf import settings
from django.db import models
from django.db.models import Q


class Swipe(models.Model):
    """One person's decision about another (from Discover, Quick Pick or a profile)."""

    LIKE, PASS = "like", "pass"
    ACTION_CHOICES = [(LIKE, "Like"), (PASS, "Pass")]

    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="swipes_made")
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="swipes_received")
    action = models.CharField(max_length=4, choices=ACTION_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["from_user", "to_user"], name="unique_swipe")]
        indexes = [models.Index(fields=["to_user", "action"])]

    def __str__(self):
        return f"{self.from_user} {self.action}d {self.to_user}"


class Match(models.Model):
    """Mutual like. user_a always has the lower id so each pair exists once."""

    user_a = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="matches_as_a")
    user_b = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="matches_as_b")
    score = models.PositiveSmallIntegerField(default=0, help_text="Compatibility at match time")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "matches"
        constraints = [models.UniqueConstraint(fields=["user_a", "user_b"], name="unique_match")]

    def __str__(self):
        return f"{self.user_a} 🍒 {self.user_b}"

    @staticmethod
    def ordered(u1, u2):
        return (u1, u2) if u1.pk < u2.pk else (u2, u1)

    @classmethod
    def between(cls, u1, u2):
        a, b = cls.ordered(u1, u2)
        return cls.objects.filter(user_a=a, user_b=b).first()

    @classmethod
    def for_user(cls, user):
        return cls.objects.filter(Q(user_a=user) | Q(user_b=user))

    def other(self, user):
        return self.user_b if self.user_a_id == user.pk else self.user_a

    def includes(self, user):
        return user.pk in (self.user_a_id, self.user_b_id)
