from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import User


class Command(BaseCommand):
    help = "Hide profiles inactive for 30+ days (run daily via cron / Task Scheduler)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=settings.CHEERIPICK["INACTIVE_DAYS"])

    def handle(self, *args, days, **options):
        cutoff = timezone.now() - timedelta(days=days)
        n = User.objects.filter(last_active__lt=cutoff, is_hidden_inactive=False, is_staff=False).update(
            is_hidden_inactive=True
        )
        self.stdout.write(self.style.SUCCESS(f"Hid {n} profile(s) inactive since before {cutoff:%Y-%m-%d}."))
