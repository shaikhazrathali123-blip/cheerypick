from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils import timezone

from . import choices as c

CFG = settings.CHEERIPICK


class Interest(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=40)
    emoji = models.CharField(max_length=8, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.emoji} {self.name}".strip()


class User(AbstractUser):
    email = models.EmailField("email address", unique=True)

    # --- Basics -----------------------------------------------------------
    role = models.CharField(max_length=10, choices=c.ROLE_CHOICES, default=c.ROLE_SEEKER)
    name = models.CharField(max_length=60, blank=True)
    age = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(18), MaxValueValidator(99)]
    )
    gender = models.CharField(max_length=12, choices=c.GENDER_CHOICES, blank=True)
    pronouns = models.CharField(max_length=30, blank=True)
    bio = models.TextField(max_length=300, blank=True)
    occupation = models.CharField(max_length=12, choices=c.OCCUPATION_CHOICES, blank=True)

    # --- Location ---------------------------------------------------------
    city = models.CharField(max_length=80, blank=True)
    latitude = models.FloatField(null=True, blank=True, db_index=True)
    longitude = models.FloatField(null=True, blank=True, db_index=True)
    search_radius_km = models.PositiveSmallIntegerField(
        default=CFG["DEFAULT_RADIUS_KM"], validators=[MinValueValidator(1), MaxValueValidator(CFG["MAX_RADIUS_KM"])]
    )

    # --- Budget & timing --------------------------------------------------
    budget_min = models.PositiveIntegerField(null=True, blank=True)
    budget_max = models.PositiveIntegerField(null=True, blank=True)
    move_in_date = models.DateField(null=True, blank=True)
    stay_months = models.PositiveSmallIntegerField(
        null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(60)]
    )

    # --- Vibe -------------------------------------------------------------
    sleep_schedule = models.CharField(max_length=10, choices=c.SLEEP_CHOICES, blank=True)
    cleanliness = models.PositiveSmallIntegerField(choices=c.SCALE_CHOICES, null=True, blank=True)
    noise_tolerance = models.PositiveSmallIntegerField(choices=c.SCALE_CHOICES, null=True, blank=True)
    guests_frequency = models.CharField(max_length=10, choices=c.GUESTS_CHOICES, blank=True)
    smoking = models.CharField(max_length=10, choices=c.SMOKING_CHOICES, blank=True)
    drinking = models.CharField(max_length=10, choices=c.DRINKING_CHOICES, blank=True)
    pets = models.CharField(max_length=10, choices=c.PETS_CHOICES, blank=True)
    food_habits = models.CharField(max_length=10, choices=c.FOOD_CHOICES, blank=True)
    work_from_home = models.CharField(max_length=10, choices=c.WFH_CHOICES, blank=True)
    social_style = models.CharField(max_length=10, choices=c.SOCIAL_CHOICES, blank=True)

    interests = models.ManyToManyField(Interest, blank=True, related_name="users")
    dealbreakers = models.JSONField(default=list, blank=True, help_text="Up to 3 vibe field names that must match")

    preferred_gender = models.CharField(
        max_length=10, choices=c.PREFERRED_GENDER_CHOICES, default=c.PREF_GENDER_ANY
    )
    preferred_gender_value = models.CharField(
        "specific gender", max_length=12, choices=c.GENDER_CHOICES, blank=True
    )

    # --- Trust & safety ---------------------------------------------------
    email_verified = models.BooleanField(default=False)
    google_sub = models.CharField(
        max_length=255, unique=True, null=True, blank=True, editable=False,
        help_text="Google account ID, set when the user signs in with Google",
    )
    phone = models.CharField(max_length=20, blank=True)
    phone_verified = models.BooleanField(default=False)
    last_active = models.DateTimeField(default=timezone.now, db_index=True)
    is_hidden_inactive = models.BooleanField(default=False, help_text="Auto-hidden after 30 days of inactivity")
    is_under_review = models.BooleanField(default=False, help_text="Hidden after 3 reports, pending admin review")

    # Cached numbers so discovery can filter in SQL. Refreshed via refresh_stats().
    profile_completion = models.PositiveSmallIntegerField(default=0, db_index=True)
    trust_score = models.PositiveSmallIntegerField(default=0)

    class Meta:
        indexes = [models.Index(fields=["latitude", "longitude"])]

    def __str__(self):
        return self.display_name

    # ----------------------------------------------------------------------
    @property
    def display_name(self):
        return self.name or self.username

    @property
    def is_host(self):
        return self.role == c.ROLE_HOST

    @property
    def has_location(self):
        return self.latitude is not None and self.longitude is not None

    def get_absolute_url(self):
        return reverse("accounts:profile", args=[self.pk])

    def photo_list(self):
        """Photos in order. Uses the prefetch cache when available."""
        return list(self.photos.all())

    @property
    def main_photo(self):
        photos = self.photo_list()
        return photos[0] if photos else None

    @property
    def is_verified_badge(self):
        """Verified = confirmed email + at least one photo."""
        return self.email_verified and bool(self.photo_list())

    @property
    def initials(self):
        parts = self.display_name.split()
        return "".join(p[0] for p in parts[:2]).upper() or "?"

    @property
    def completion_label(self):
        return "Looking great ✨" if self.profile_completion >= 90 else (
            "Almost there" if self.profile_completion >= CFG["MIN_COMPLETION_FOR_DISCOVERY"] else "Keep going"
        )

    def is_discoverable(self):
        return (
            self.is_active
            and self.email_verified
            and not self.is_hidden_inactive
            and not self.is_under_review
            and self.profile_completion >= CFG["MIN_COMPLETION_FOR_DISCOVERY"]
        )

    # --- Completion -------------------------------------------------------
    def completion_checks(self):
        """(label, done, points). Photos and interests weigh more on purpose."""
        has_photo = bool(self.pk) and self.photos.exists()
        interest_count = self.interests.count() if self.pk else 0
        checks = [
            ("Name", bool(self.name), 1),
            ("Age", self.age is not None, 1),
            ("Gender", bool(self.gender), 1),
            ("Bio", len(self.bio or "") >= 20, 1),
            ("Occupation", bool(self.occupation), 1),
            ("City", bool(self.city), 1),
            ("Location pin", self.has_location, 2),
            ("Budget", bool(self.budget_min is not None and self.budget_max), 1),
            ("Move-in date", self.move_in_date is not None, 1),
            ("Stay duration", bool(self.stay_months), 1),
        ]
        for f in c.VIBE_FIELDS:
            val = getattr(self, f)
            checks.append((c.VIBE_FIELD_LABELS[f], val not in (None, ""), 1))
        checks.append(("3+ interests", interest_count >= 3, 2))
        checks.append(("A photo", has_photo, 3))
        return checks

    def compute_completion(self):
        checks = self.completion_checks()
        total = sum(p for _, _, p in checks)
        done = sum(p for _, ok, p in checks if ok)
        return round(done * 100 / total)

    def missing_items(self):
        return [label for label, ok, _ in self.completion_checks() if not ok]

    def refresh_stats(self):
        """Recompute cached completion + trust score and persist them."""
        from .trust import compute_trust_score

        self.profile_completion = self.compute_completion()
        self.trust_score = compute_trust_score(self)
        User.objects.filter(pk=self.pk).update(
            profile_completion=self.profile_completion, trust_score=self.trust_score
        )

    @property
    def account_age_days(self):
        return (timezone.now() - self.date_joined).days

    def is_inactive(self):
        return self.last_active < timezone.now() - timedelta(days=CFG["INACTIVE_DAYS"])


def profile_photo_path(instance, filename):
    return f"profiles/{instance.user_id}/{filename}"


class ProfilePhoto(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to=profile_photo_path)
    order = models.PositiveSmallIntegerField(default=0)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"Photo of {self.user}"

    def delete(self, *args, **kwargs):
        storage, name = self.image.storage, self.image.name
        super().delete(*args, **kwargs)
        if name:
            storage.delete(name)


class Block(models.Model):
    blocker = models.ForeignKey(User, on_delete=models.CASCADE, related_name="blocks_made")
    blocked = models.ForeignKey(User, on_delete=models.CASCADE, related_name="blocks_received")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["blocker", "blocked"], name="unique_block")]

    def __str__(self):
        return f"{self.blocker} blocked {self.blocked}"


class Report(models.Model):
    REASONS = [
        ("fake", "Fake profile / catfish"),
        ("spam", "Spam or scam"),
        ("rude", "Rude or harassing"),
        ("timewaster", "Time-waster / ghosting"),
        ("other", "Something else"),
    ]
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reports_made")
    reported = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reports_received")
    reason = models.CharField(max_length=12, choices=REASONS)
    details = models.TextField(max_length=500, blank=True)
    resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["reporter", "reported"], name="unique_report")]

    def __str__(self):
        return f"{self.reporter} reported {self.reported} ({self.reason})"
