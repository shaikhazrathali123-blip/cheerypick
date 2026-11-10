"""
python manage.py generate_vapid_keys          # print keys to paste into .env
python manage.py generate_vapid_keys --write  # append them to .env

VAPID keys identify this server to browser push services (Chrome/FCM, Firefox, Apple).
Generate once per deployment and keep the private key secret.
"""
import base64
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


def b64url(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


class Command(BaseCommand):
    help = "Generate a VAPID key pair for Web Push notifications."

    def add_arguments(self, parser):
        parser.add_argument("--write", action="store_true", help="Append the keys to .env")

    def handle(self, *args, write, **opts):
        key = ec.generate_private_key(ec.SECP256R1())
        private = b64url(key.private_numbers().private_value.to_bytes(32, "big"))
        public = b64url(key.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint))
        lines = f"VAPID_PUBLIC_KEY={public}\nVAPID_PRIVATE_KEY={private}\n"

        if not write:
            self.stdout.write(lines)
            return
        env = Path(settings.BASE_DIR) / ".env"
        existing = env.read_text(encoding="utf-8") if env.exists() else ""
        if "VAPID_PRIVATE_KEY=" in existing and not existing.split("VAPID_PRIVATE_KEY=")[1].split("\n")[0].strip() == "":
            raise CommandError(".env already has VAPID keys. Remove them first if you really want new ones "
                               "(existing push subscriptions will stop working).")
        with env.open("a", encoding="utf-8") as fh:
            fh.write(("\n" if existing and not existing.endswith("\n") else "") + "\n# Web Push (generated)\n" + lines)
        self.stdout.write(self.style.SUCCESS(f"Wrote VAPID keys to {env}. Restart the server."))
