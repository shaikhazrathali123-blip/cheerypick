from django.db import migrations

from listings.models import DEFAULT_AMENITIES


def seed(apps, schema_editor):
    Amenity = apps.get_model("listings", "Amenity")
    for slug, name, emoji in DEFAULT_AMENITIES:
        Amenity.objects.update_or_create(slug=slug, defaults={"name": name, "emoji": emoji})


def unseed(apps, schema_editor):
    Amenity = apps.get_model("listings", "Amenity")
    Amenity.objects.filter(slug__in=[s for s, _, _ in DEFAULT_AMENITIES]).delete()


class Migration(migrations.Migration):
    dependencies = [("listings", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
