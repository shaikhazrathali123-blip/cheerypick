from django.db import migrations

from accounts.choices import DEFAULT_INTERESTS


def seed(apps, schema_editor):
    Interest = apps.get_model("accounts", "Interest")
    for slug, name, emoji in DEFAULT_INTERESTS:
        Interest.objects.update_or_create(slug=slug, defaults={"name": name, "emoji": emoji})


def unseed(apps, schema_editor):
    Interest = apps.get_model("accounts", "Interest")
    Interest.objects.filter(slug__in=[s for s, _, _ in DEFAULT_INTERESTS]).delete()


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
