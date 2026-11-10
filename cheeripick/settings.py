"""
Django settings for CheeriPick.

Secrets and environment-specific values come from a .env file (python-dotenv).
SQLite by default; set DB_ENGINE=postgres to switch to PostgreSQL.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()]
# Needed when serving over an HTTPS tunnel/domain, e.g. "https://abc.trycloudflare.com"
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

# Render sets this automatically (e.g. "cheeripick.onrender.com")
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # CheeriPick apps
    "accounts",
    "listings",
    "matching",
    "chat",
    "notifications",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # serves /static/ in production
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "accounts.middleware.LastActiveMiddleware",
]

ROOT_URLCONF = "cheeripick.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "accounts.context_processors.cheeripick",
                "chat.context_processors.unread_messages",
                "notifications.context_processors.notifications",
            ],
        },
    },
]

WSGI_APPLICATION = "cheeripick.wsgi.application"

# --- Database --------------------------------------------------------------
if os.getenv("DATABASE_URL"):
    # Render / Heroku style: postgres://user:pass@host:5432/name
    import dj_database_url

    DATABASES = {"default": dj_database_url.config(conn_max_age=60, conn_health_checks=True)}
elif os.getenv("DB_ENGINE", "sqlite").lower() in {"postgres", "postgresql"}:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "cheeripick"),
            "USER": os.getenv("DB_USER", "cheeripick"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "localhost"),
            "PORT": os.getenv("DB_PORT", "5432"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["accounts.backends.EmailOrUsernameBackend"]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "matching:deck"
LOGOUT_REDIRECT_URL = "landing"

LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage" if DEBUG
        else "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "CheeriPick <hello@cheeripick.local>")
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)

# Upload limits (Django rejects bigger request bodies in memory; we validate per file too)
DATA_UPLOAD_MAX_MEMORY_SIZE = 40 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

# Serve uploaded photos from Django itself (fine for a small app). Off by default in production.
SERVE_MEDIA = env_bool("SERVE_MEDIA", DEBUG)

if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Render terminates HTTPS at its proxy; trust its header so links/redirects use https://
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SECURE_CONTENT_TYPE_NOSNIFF = True

# --- Google sign-in -------------------------------------------------------
# Create an OAuth client (type: Web application) at
# https://console.cloud.google.com/apis/credentials and add the redirect URI
#   http://127.0.0.1:8000/accounts/google/callback/  (plus your production URL)
# The "Continue with Google" button only appears when both values are set.
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

# --- Web Push notifications --------------------------------------------------
# Generate keys once with:  python manage.py generate_vapid_keys --write
# Without them, in-app notifications (the bell) still work; push to devices is off.
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_SUBJECT = os.getenv("VAPID_SUBJECT", "mailto:hello@cheeripick.local")
# Set PUSH_IN_BACKGROUND=False on hosts whose web workers can't run threads (PythonAnywhere).
PUSH_IN_BACKGROUND = env_bool("PUSH_IN_BACKGROUND", True)

# --- CheeriPick knobs ------------------------------------------------------
CHEERIPICK = {
    # Compatibility weights (should add up to 1.0). Tweak freely.
    "MATCH_WEIGHTS": {
        "lifestyle": 0.45,
        "interests": 0.15,
        "budget": 0.15,
        "distance": 0.15,
        "trust": 0.10,
    },
    "MIN_COMPLETION_FOR_DISCOVERY": 70,
    "MOVE_IN_WINDOW_DAYS": 60,
    "DEFAULT_RADIUS_KM": 10,
    "MAX_RADIUS_KM": 50,
    "INACTIVE_DAYS": 30,
    "REPORTS_TO_HIDE": 3,
    "MAX_PROFILE_PHOTOS": 4,
    "MAX_LISTING_PHOTOS": 6,
    "MAX_DEALBREAKERS": 3,
    "MAX_UPLOAD_MB": 5,
    "IMAGE_MAX_PX": 1280,
    "DISCOVER_PAGE_SIZE": 12,
    # Swipe deck: which way means "like". "right" = swipe right to like, left to pass.
    "SWIPE_LIKE_DIRECTION": "right",
    "CHAT_POLL_SECONDS": 5,
    "CURRENCY_SYMBOL": os.getenv("CURRENCY_SYMBOL", "₹"),
}
