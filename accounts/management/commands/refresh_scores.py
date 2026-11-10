from django.core.management.base import BaseCommand

from accounts.models import User


class Command(BaseCommand):
    help = "Recompute cached profile completion and serious (trust) scores for everyone."

    def handle(self, *args, **options):
        count = 0
        for user in User.objects.iterator():
            user.refresh_stats()
            count += 1
        self.stdout.write(self.style.SUCCESS(f"Refreshed {count} user(s)."))
