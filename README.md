# CheeriPick 🍒

Find a roommate (and a room). Django 5.1 app with profiles, compatibility matching,
Quick Pick swiping, room listings and chat.

## Run it locally

```bash
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env          # macOS/Linux: cp .env.example .env
python manage.py migrate        # also seeds interests + amenities
python manage.py seed_demo      # optional: demo users, listings, likes
python manage.py createsuperuser  # optional: for /admin/
python manage.py runserver
```

Open http://127.0.0.1:8000. After `seed_demo`, log in with **demo@cheeripick.app / cherry123**.
Re-create the seed data with `python manage.py seed_demo --reset`.

Emails (verification links) are printed to the console by default.

## Apps

| App | What it does |
| --- | --- |
| `accounts` | Custom user, signup/login, email verification, onboarding steps, photos, trust score, report/block |
| `matching` | Compatibility algorithm (`matching/algorithm.py`), Discover, Quick Pick swipes, matches |
| `listings` | Room listings with photos and amenities |
| `chat` | Per-match message threads with polling |

## Configuration

- `.env`: secret key, debug, allowed hosts, database, email (see `.env.example`).
- Set `DB_ENGINE=postgres` and install `psycopg[binary]` to use PostgreSQL.
- Matching weights and limits live in `CHEERIPICK` in `cheeripick/settings.py`.

## Google sign-in (optional)

1. Go to https://console.cloud.google.com/apis/credentials (create a project if asked).
2. Set up the **OAuth consent screen** (External, add your email as a test user while testing).
3. **Create credentials → OAuth client ID → Web application**, and add this
   *Authorized redirect URI*: `http://127.0.0.1:8000/accounts/google/callback/`
   (add your real domain's `/accounts/google/callback/` too when you deploy).
4. Put the client ID and secret in `.env`:
   ```
   GOOGLE_CLIENT_ID=xxxx.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=xxxx
   ```
5. Restart `runserver`. A "Continue with Google" button now shows on the login and signup pages.

Visit the site at `127.0.0.1`, not `localhost`: the address must match the redirect URI exactly.
New Google users go through onboarding like everyone else. If the email already belongs to an
account, Google sign-in logs into that account and links it.

## Installable app (PWA) + notifications

CheeriPick is a Progressive Web App: it can be installed to the home screen, opens full-screen,
loads instantly from cache, and shows an offline page with no connection.

- **Install:** Settings → *App & notifications* → **Install** (Chrome/Edge/Android).
  On iPhone: Safari → Share → **Add to Home Screen**.
- **Notifications:** new matches, new messages and "someone likes you" appear under the 🔔 bell.
  With Web Push turned on they also reach the device when the app is closed.

Web Push needs a key pair (one-time):

```bash
python manage.py generate_vapid_keys --write   # adds VAPID_* to .env
```

Then Settings → **Turn on notifications** → **Send me a test notification**.

Service workers and push only run on **HTTPS** or `localhost`/`127.0.0.1`. To try it on your
phone, expose the dev server over HTTPS (for example `cloudflared tunnel --url http://127.0.0.1:8000`
or `ngrok http 8000`) and add that host to `DJANGO_ALLOWED_HOSTS` (and `CSRF_TRUSTED_ORIGINS`).
iPhone push needs iOS 16.4+ and the app installed to the Home Screen first.

## Deploying

- PythonAnywhere: step-by-step guide in [DEPLOY_PYTHONANYWHERE.md](DEPLOY_PYTHONANYWHERE.md).
- Render: build command `./build.sh`, start command `gunicorn cheeripick.wsgi:application`.

## Maintenance commands

- `python manage.py refresh_scores`: recompute profile completion and trust scores
- `python manage.py hide_inactive`: hide profiles inactive for `INACTIVE_DAYS`
