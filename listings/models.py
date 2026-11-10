from django.conf import settings
from django.db import models
from django.urls import reverse


class Amenity(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=40)
    emoji = models.CharField(max_length=8, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "amenities"

    def __str__(self):
        return f"{self.emoji} {self.name}".strip()


DEFAULT_AMENITIES = [
    ("wifi", "Wi-Fi", "📶"),
    ("ac", "AC", "❄️"),
    ("washing-machine", "Washing machine", "🧺"),
    ("parking", "Parking", "🅿️"),
    ("fridge", "Fridge", "🧊"),
    ("kitchen", "Kitchen access", "🍳"),
    ("power-backup", "Power backup", "🔋"),
    ("geyser", "Geyser / hot water", "🚿"),
    ("balcony", "Balcony", "🌇"),
    ("lift", "Lift", "🛗"),
    ("gym", "Gym", "🏋️"),
    ("security", "24/7 security", "🛡️"),
    ("housekeeping", "Housekeeping", "🧹"),
    ("tv", "TV", "📺"),
]


class Listing(models.Model):
    ROOM_PRIVATE, ROOM_SHARED = "private", "shared"
    ROOM_TYPE_CHOICES = [(ROOM_PRIVATE, "Private room"), (ROOM_SHARED, "Shared room")]
    FURNISHED_CHOICES = [("yes", "Furnished"), ("semi", "Semi-furnished"), ("no", "Unfurnished")]
    STATUS_ACTIVE, STATUS_PAUSED = "active", "paused"
    STATUS_CHOICES = [(STATUS_ACTIVE, "Active"), (STATUS_PAUSED, "Paused")]

    host = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="listings")
    title = models.CharField(max_length=80)
    description = models.TextField(max_length=1500)
    rent = models.PositiveIntegerField(help_text="Monthly rent for this room")
    deposit = models.PositiveIntegerField(default=0)
    room_type = models.CharField(max_length=10, choices=ROOM_TYPE_CHOICES, default=ROOM_PRIVATE)
    furnished = models.CharField(max_length=5, choices=FURNISHED_CHOICES, default="semi")
    amenities = models.ManyToManyField(Amenity, blank=True, related_name="listings")
    available_from = models.DateField()
    address = models.CharField(max_length=200, help_text="Area / landmark is fine — no need for flat number")
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    house_rules = models.TextField(max_length=800, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_ACTIVE, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("listings:detail", args=[self.pk])

    @property
    def is_active(self):
        return self.status == self.STATUS_ACTIVE

    @property
    def main_photo(self):
        photos = list(self.photos.all())
        return photos[0] if photos else None


def listing_photo_path(instance, filename):
    return f"listings/{instance.listing_id}/{filename}"


class ListingPhoto(models.Model):
    listing = models.ForeignKey(Listing, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to=listing_photo_path)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        return f"Photo for {self.listing}"

    def delete(self, *args, **kwargs):
        storage, name = self.image.storage, self.image.name
        super().delete(*args, **kwargs)
        if name:
            storage.delete(name)
