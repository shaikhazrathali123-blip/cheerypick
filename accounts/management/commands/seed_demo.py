"""
python manage.py seed_demo            # 30 fake users around Bengaluru + a demo login
python manage.py seed_demo --reset    # wipe previous seed data first
python manage.py seed_demo --city Pune --lat 18.5204 --lon 73.8567

Every seeded account uses the password "cherry123".
Log in as  demo@cheeripick.app / cherry123  to try everything.
"""
import io
import math
import random
from datetime import date, timedelta

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw, ImageFont

from accounts import choices as c
from accounts.models import Interest, ProfilePhoto, User
from chat.models import Message
from listings.models import Amenity, Listing, ListingPhoto
from matching.models import Match, Swipe

PASSWORD = "cherry123"
SEED_PREFIX = "seed_"

FIRST_NAMES = {
    "woman": ["Aanya", "Diya", "Isha", "Meera", "Riya", "Sana", "Tara", "Zoya", "Kavya", "Naina", "Ira", "Maya", "Leah", "Anika"],
    "man": ["Arjun", "Kabir", "Rohan", "Vihaan", "Aarav", "Dev", "Ishaan", "Neil", "Reyansh", "Sid", "Omar", "Karan", "Leo", "Yash"],
    "nonbinary": ["Ari", "Sam", "Rumi", "Kai", "Noor"],
}
PRONOUNS = {"woman": "she/her", "man": "he/him", "nonbinary": "they/them"}
BIOS = [
    "Chai > coffee. Will water your plants if you water mine 🪴",
    "Software dev by day, amateur chef by night. I clean as I cook, promise.",
    "Grad student, mostly quiet, occasionally sing in the shower (badly).",
    "Gym at 6am, asleep by 11. Looking for someone chill and tidy.",
    "Night owl, anime binger, makes a mean maggi at 2am 🍜",
    "Designer who loves thrifting and Sunday brunch. Big on good vibes only.",
    "Moved here for work, looking for a roommate who's down for weekend treks 🥾",
    "Introvert with a big Spotify library. Respect the headphones 🎧",
    "Freelance photographer, always out shooting. Low maintenance roomie.",
    "Med student — I'm either studying or sleeping. Very clean, very quiet.",
    "Plant mom x2, cat mom x1. Looking for a pet-friendly flatmate 🐱",
    "Startup life. WFH most days so a calm home matters to me.",
]
FLAT_TITLES = [
    "Sunny room in a chill 3BHK", "Cozy private room near metro", "Big room with balcony 🌇",
    "Shared room in a fun flat", "Furnished room, 5 min from tech park", "Quiet room in a plant-filled flat",
    "Room in a 2BHK with a gamer flatmate", "Bright room, pets welcome 🐶",
]
AREAS = ["Indiranagar", "Koramangala", "HSR Layout", "Whitefield", "Jayanagar", "BTM Layout", "Marathahalli", "JP Nagar", "Bellandur", "Malleshwaram"]
PALETTE = [(230, 57, 70), (255, 180, 194), (42, 157, 143), (255, 140, 105), (131, 56, 236), (58, 134, 255), (255, 190, 11)]


def _font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # very old Pillow
        return ImageFont.load_default()


def avatar_image(initials, seed):
    rnd = random.Random(seed)
    c1, c2 = rnd.sample(PALETTE, 2)
    img = Image.new("RGB", (600, 600), c1)
    draw = ImageDraw.Draw(img)
    for y in range(600):  # vertical gradient
        t = y / 599
        draw.line([(0, y), (600, y)], fill=tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3)))
    for _ in range(6):
        r = rnd.randint(30, 110)
        x, y = rnd.randint(0, 600), rnd.randint(0, 600)
        draw.ellipse([x - r, y - r, x + r, y + r], outline=(255, 255, 255), width=4)
    draw.text((300, 300), initials, fill=(255, 255, 255), font=_font(220), anchor="mm")
    return _jpeg(img)


def room_image(seed):
    rnd = random.Random(seed)
    wall = rnd.choice([(255, 236, 228), (232, 244, 241), (240, 234, 255), (255, 245, 214)])
    img = Image.new("RGB", (900, 600), wall)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 430, 900, 600], fill=(196, 160, 120))  # floor
    d.rectangle([560, 90, 800, 300], fill=(170, 215, 255), outline=(255, 255, 255), width=12)  # window
    d.line([(680, 90), (680, 300)], fill=(255, 255, 255), width=8)
    bed = rnd.choice(PALETTE)
    d.rounded_rectangle([80, 330, 480, 470], radius=24, fill=bed)  # bed
    d.rounded_rectangle([100, 300, 220, 350], radius=16, fill=(255, 255, 255))  # pillow
    d.rectangle([520, 380, 560, 470], fill=(42, 157, 143))  # plant pot
    d.ellipse([490, 290, 590, 390], fill=(80, 180, 120))
    return _jpeg(img)


def _jpeg(img):
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=82)
    return buf.getvalue()


def random_point(lat, lon, max_km, rnd):
    """Uniform random point within max_km of (lat, lon)."""
    r = max_km * math.sqrt(rnd.random())
    theta = rnd.uniform(0, 2 * math.pi)
    dlat = (r * math.cos(theta)) / 110.574
    dlon = (r * math.sin(theta)) / (111.320 * math.cos(math.radians(lat)))
    return round(lat + dlat, 6), round(lon + dlon, 6)


class Command(BaseCommand):
    help = "Create fake users (default 30) (with photos, listings, likes and a chat) for testing."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=30)
        parser.add_argument("--reset", action="store_true", help="Delete previously seeded users first")
        parser.add_argument("--city", default="Bengaluru")
        parser.add_argument("--lat", type=float, default=12.9716)
        parser.add_argument("--lon", type=float, default=77.5946)
        parser.add_argument("--seed", type=int, default=42, help="Random seed for repeatable data")

    def handle(self, *args, count, reset, city, lat, lon, seed, **opts):
        rnd = random.Random(seed)
        if reset:
            self._reset()
        if User.objects.filter(username__startswith=SEED_PREFIX).exists():
            self.stdout.write(self.style.WARNING("Seed users already exist - run with --reset to recreate them."))
            return

        interests = list(Interest.objects.all())
        amenities = list(Amenity.objects.all())
        if not interests or not amenities:
            self.stderr.write("No interests/amenities found. Did you run `migrate`?")
            return

        today = date.today()
        with transaction.atomic():
            demo = self._make_demo(city, lat, lon, today, interests)
            users = []
            for i in range(count):
                users.append(self._make_user(i, count, rnd, city, lat, lon, today, interests, amenities))

            # A few people already like the demo user, so Quick Pick can produce matches.
            nearby = users[: max(1, count - 4)]
            fans = rnd.sample(nearby, min(len(nearby), max(8, count // 6)))
            for u in fans:
                Swipe.objects.get_or_create(from_user=u, to_user=demo, defaults={"action": Swipe.LIKE})

            # One ready-made match with a chat so you can see the inbox straight away.
            buddy = fans[0]
            Swipe.objects.get_or_create(from_user=demo, to_user=buddy, defaults={"action": Swipe.LIKE})
            a, b = Match.ordered(demo, buddy)
            match, _ = Match.objects.get_or_create(user_a=a, user_b=b, defaults={"score": 80})
            for sender, body in [
                (buddy, f"Heyy! Saw we're both in {city} — still looking for a place?"),
                (demo, "Yes!! Your profile was such a vibe 😄"),
                (buddy, "Haha same. Wanna grab chai this weekend and talk flat stuff? ☕"),
            ]:
                Message.objects.create(match=match, sender=sender, body=body)

        for u in [demo, *users]:
            u.refresh_stats()

        self.stdout.write(self.style.SUCCESS(f"Created {count} seed users + demo account in/around {city}."))
        self.stdout.write("Log in with  demo@cheeripick.app  /  cherry123")
        self.stdout.write(f"(All seed users also use the password '{PASSWORD}'.)")

    # ------------------------------------------------------------------
    def _reset(self):
        qs = User.objects.filter(username__startswith=SEED_PREFIX) | User.objects.filter(username="demo")
        for p in ProfilePhoto.objects.filter(user__in=qs):
            p.delete()
        for p in ListingPhoto.objects.filter(listing__host__in=qs):
            p.delete()
        n = qs.count()
        qs.delete()
        self.stdout.write(f"Removed {n} previously seeded user(s).")

    def _make_demo(self, city, lat, lon, today, interests):
        demo = User.objects.filter(username="demo").first()
        if demo:
            return demo
        demo = User.objects.create_user(
            username="demo", email="demo@cheeripick.app", password=PASSWORD,
            name="Alex", age=23, gender="nonbinary", pronouns="they/them", occupation="working",
            bio="Product designer who loves cooking on Sundays and gaming on Fridays. Tidy-ish, very friendly 🍒",
            role=c.ROLE_SEEKER, city=city, latitude=lat, longitude=lon, search_radius_km=15,
            budget_min=9000, budget_max=18000, move_in_date=today + timedelta(days=20), stay_months=12,
            sleep_schedule="night", cleanliness=4, noise_tolerance=3, guests_frequency="sometimes",
            smoking="no", drinking="socially", pets="okay", food_habits="any", work_from_home="hybrid",
            social_style="friendly", email_verified=True, preferred_gender=c.PREF_GENDER_ANY,
            dealbreakers=["smoking"],
        )
        demo.interests.set([i for i in interests if i.slug in {"gaming", "cooking", "music", "movies", "coffee"}])
        ProfilePhoto.objects.create(user=demo, image=ContentFile(avatar_image("AX", "demo"), name="demo.jpg"))
        return demo

    def _make_user(self, i, count, rnd, city, lat, lon, today, interests, amenities):
        gender = rnd.choices(["woman", "man", "nonbinary"], weights=[45, 45, 10])[0]
        name = rnd.choice(FIRST_NAMES[gender])
        is_host = rnd.random() < 0.4
        far_away = i >= count - 4  # last 4 live in another city → filtered out by distance
        u_lat, u_lon = (19.0760, 72.8777) if far_away else random_point(lat, lon, 14, rnd)
        u_city = "Mumbai" if far_away else city

        budget_min = rnd.randrange(6000, 18001, 500)
        budget_max = budget_min + rnd.randrange(3000, 10001, 500)
        joined = timezone.now() - timedelta(days=rnd.randint(1, 150))
        last_active = timezone.now() - timedelta(days=rnd.randint(0, 8))
        if i in (24, 25):  # two ghosts — inactive for 40 days
            last_active = timezone.now() - timedelta(days=40)

        dealbreakers = []
        roll = rnd.random()
        if roll < 0.25:
            dealbreakers = ["smoking"]
        elif roll < 0.35:
            dealbreakers = ["pets", "smoking"]
        elif roll < 0.42:
            dealbreakers = ["cleanliness"]

        pref = rnd.choices([c.PREF_GENDER_ANY, c.PREF_GENDER_SAME], weights=[80, 20])[0]

        user = User.objects.create_user(
            username=f"{SEED_PREFIX}{i:02d}_{name.lower()}",
            email=f"{name.lower()}{i}@seed.cheeripick.app",
            password=PASSWORD,
            name=name,
            age=rnd.randint(19, 30),
            gender=gender,
            pronouns=PRONOUNS[gender] if rnd.random() < 0.7 else "",
            occupation=rnd.choices(["student", "working", "freelancer", "other"], weights=[30, 50, 15, 5])[0],
            bio=rnd.choice(BIOS),
            role=c.ROLE_HOST if is_host else c.ROLE_SEEKER,
            city=u_city, latitude=u_lat, longitude=u_lon,
            search_radius_km=rnd.choice([5, 10, 15, 20]),
            budget_min=budget_min, budget_max=budget_max,
            move_in_date=today + timedelta(days=rnd.randint(0, 75)),
            stay_months=rnd.choice([3, 6, 6, 11, 12, 12, 24]),
            sleep_schedule=rnd.choice(["early", "night", "flexible"]),
            cleanliness=rnd.choices([1, 2, 3, 4, 5], weights=[5, 10, 30, 35, 20])[0],
            noise_tolerance=rnd.randint(1, 5),
            guests_frequency=rnd.choice(["rarely", "sometimes", "often"]),
            smoking=rnd.choices(["no", "outside", "yes"], weights=[70, 20, 10])[0],
            drinking=rnd.choice(["no", "socially", "often"]),
            pets=rnd.choice(["have", "okay", "no"]),
            food_habits=rnd.choice(["veg", "nonveg", "vegan", "any"]),
            work_from_home=rnd.choice(["yes", "no", "hybrid"]),
            social_style=rnd.choice(["private", "friendly", "besties"]),
            dealbreakers=dealbreakers,
            preferred_gender=pref,
            email_verified=i not in (5, 17, 29),  # a few unverified → no badge
            phone_verified=rnd.random() < 0.3,
            phone=f"+9198{rnd.randint(10000000, 99999999)}",
        )
        User.objects.filter(pk=user.pk).update(date_joined=joined, last_active=last_active)
        user.date_joined, user.last_active = joined, last_active
        user.interests.set(rnd.sample(interests, rnd.randint(3, 6)))

        if rnd.random() < 0.9:  # most people have a photo
            initials = name[:2].upper()
            for n in range(rnd.choice([1, 2, 2, 3])):
                ProfilePhoto.objects.create(
                    user=user, order=n,
                    image=ContentFile(avatar_image(initials, f"{i}-{n}"), name=f"seed{i}_{n}.jpg"),
                )

        if is_host:
            l_lat, l_lon = random_point(u_lat, u_lon, 0.5, rnd)
            listing = Listing.objects.create(
                host=user,
                title=rnd.choice(FLAT_TITLES),
                description="Spacious room in a well-kept flat. Flatmates are working professionals, "
                            "kitchen is fully equipped and there's a small balcony for morning chai.",
                rent=rnd.randrange(max(budget_min, 6000), budget_max + 1, 500),
                deposit=rnd.choice([0, 10000, 20000, 30000]),
                room_type=rnd.choice([Listing.ROOM_PRIVATE, Listing.ROOM_PRIVATE, Listing.ROOM_SHARED]),
                furnished=rnd.choice(["yes", "semi", "no"]),
                available_from=today + timedelta(days=rnd.randint(0, 45)),
                address=f"{rnd.choice(AREAS)}, {u_city}",
                latitude=l_lat, longitude=l_lon,
                house_rules="Clean up after cooking. Quiet hours after 11pm. Guests okay with a heads-up.",
                status=Listing.STATUS_PAUSED if rnd.random() < 0.1 else Listing.STATUS_ACTIVE,
            )
            listing.amenities.set(rnd.sample(amenities, rnd.randint(4, 8)))
            for n in range(rnd.randint(1, 3)):
                ListingPhoto.objects.create(
                    listing=listing, order=n,
                    image=ContentFile(room_image(f"{i}-{n}"), name=f"room{i}_{n}.jpg"),
                )
        return user
