# Deploying CheeriPick on PythonAnywhere

This guide puts CheeriPick at `https://YOURNAME.pythonanywhere.com`, where `YOURNAME` is your
PythonAnywhere username. Replace `YOURNAME` with it everywhere below.

A free ("Beginner") account is enough. The data and uploaded photos stay on PythonAnywhere's
disk, so the SQLite database keeps working and photos aren't lost when you reload the app.

---

## 0. Before you start (on your PC)

1. **Make sure the code is on GitHub.** The push was blocked earlier because an old commit
   contains the Google secret, so fix that first (see the git commands I gave you). Then:
   ```bash
   git add -A
   git commit -m "Deploy setup"
   git push -u origin main
   ```
   If you'd rather not use GitHub, see **Option B** in step 2.
2. **Never upload `.env`.** You'll create a new one on the server in step 5.
3. Keep your local `.env` open. You'll copy the Google and VAPID keys from it.

---

## 1. Create the account

1. Sign up at https://www.pythonanywhere.com → **Pricing & signup** → **Create a Beginner account**.
2. Confirm your email and log in.

---

## 2. Get the code onto PythonAnywhere

Open **Consoles → Bash** (it starts a terminal in your browser).

**Option A: from GitHub (recommended)**
```bash
cd ~
git clone https://github.com/shaikhazrathali123-blip/cheerypick.git
cd cheerypick
ls            # you should see manage.py, requirements.txt, cheeripick/ ...
```
If the repo is private, GitHub will ask for a password. Use a **Personal Access Token**
(GitHub → Settings → Developer settings → Tokens), not your real password.

**Option B: upload a zip**
1. On your PC, zip the project folder. Leave out `.venv`, `.env`, `db.sqlite3`, `staticfiles`
   and `__pycache__`.
2. On PythonAnywhere: **Files** → **Upload a file** → choose the zip.
3. In the Bash console:
   ```bash
   cd ~
   unzip cheerypick.zip -d cheerypick    # adjust the name if your zip is different
   cd cheerypick && ls
   ```
   If `ls` shows a single folder instead of `manage.py`, `cd` into that folder. The path you
   use from here on is the one that contains `manage.py`.

The rest of this guide assumes the project is at **`/home/YOURNAME/cheerypick`**.

---

## 3. Create a virtualenv and install packages

Still in the Bash console:
```bash
cd ~/cheerypick
mkvirtualenv cheeripick --python=python3.12
pip install -r requirements.txt
```
- The prompt now starts with `(cheeripick)`. That means the virtualenv is active.
- Installing takes a few minutes. (`gunicorn` gets installed but isn't used here, which is fine.)
- If you open a new console later, run `workon cheeripick` first.
- If `python3.12` isn't offered, use the newest version listed in
  **Account → System image**. It must be 3.10 or newer.

---

## 4. Make a secret key and the push keys

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```
Copy the output. That's your `DJANGO_SECRET_KEY`.

**VAPID keys:** reuse the `VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` from your local `.env`.
Don't generate new ones unless you have none. New keys break notifications for devices that
already subscribed.

---

## 5. Create the `.env` file on the server

```bash
nano ~/cheerypick/.env
```
Paste this, fill in your values, then save with **Ctrl+O, Enter, Ctrl+X**:

```ini
DJANGO_DEBUG=False
DJANGO_SECRET_KEY=paste-the-key-from-step-4
DJANGO_ALLOWED_HOSTS=YOURNAME.pythonanywhere.com
CSRF_TRUSTED_ORIGINS=https://YOURNAME.pythonanywhere.com

# PythonAnywhere does the HTTPS redirect itself (step 8), so Django doesn't
SECURE_SSL_REDIRECT=False

# PythonAnywhere serves /static/ and /media/ through the Web tab (step 7)
SERVE_MEDIA=False

# Web workers here can't run background threads, so send push notifications inline
PUSH_IN_BACKGROUND=False

# Google sign-in (copy from your local .env)
GOOGLE_CLIENT_ID=xxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=xxxx

# Web Push (copy from your local .env)
VAPID_PUBLIC_KEY=xxxx
VAPID_PRIVATE_KEY=xxxx
VAPID_SUBJECT=mailto:you@example.com
```

Protect it so only you can read it:
```bash
chmod 600 ~/cheerypick/.env
```

---

## 6. Set up the database and static files

```bash
cd ~/cheerypick
workon cheeripick
python manage.py migrate                # creates db.sqlite3 and seeds interests and amenities
python manage.py collectstatic --noinput
python manage.py createsuperuser        # your admin login for /admin/
python manage.py seed_demo --count 60   # optional: demo users to swipe on
mkdir -p media
python manage.py check --deploy
```
`check --deploy` may warn about `SECURE_HSTS_SECONDS` (W004) and `SECURE_SSL_REDIRECT`
(W008). Both are fine here. Any **error** has to be fixed before you continue.

---

## 7. Create the web app

1. Go to the **Web** tab → **Add a new web app** → **Next**.
2. Choose **Manual configuration**, *not* "Django". The Django option would create a new
   empty project.
3. Pick the **same Python version** you used for the virtualenv (e.g. 3.12) → **Next**.

Then fill in the Web tab page:

### Code
| Field | Value |
|---|---|
| Source code | `/home/YOURNAME/cheerypick` |
| Working directory | `/home/YOURNAME/cheerypick` |

### Virtualenv
| Field | Value |
|---|---|
| Virtualenv | `/home/YOURNAME/.virtualenvs/cheeripick` |

### WSGI configuration file
Click the link (it looks like `/var/www/YOURNAME_pythonanywhere_com_wsgi.py`), **delete
everything in it**, and paste:

```python
import os
import sys

path = "/home/YOURNAME/cheerypick"
if path not in sys.path:
    sys.path.insert(0, path)

os.environ["DJANGO_SETTINGS_MODULE"] = "cheeripick.settings"

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```
Click **Save**. (`settings.py` loads `.env` by itself, so nothing else is needed here.)

### Static files
Add two rows in the **Static files** section:

| URL | Directory |
|---|---|
| `/static/` | `/home/YOURNAME/cheerypick/staticfiles` |
| `/media/` | `/home/YOURNAME/cheerypick/media` |

Don't add `/sw.js` or `/manifest.webmanifest`. Django serves those itself so the app works
offline and can be installed.

---

## 8. Turn on HTTPS

In the **Web** tab, under **Security**:
- **Force HTTPS: Enabled**. HTTPS is required for login cookies, installing the app and push
  notifications.

---

## 9. Start it

1. Scroll to the top of the Web tab and click the big green **Reload YOURNAME.pythonanywhere.com** button.
2. Open `https://YOURNAME.pythonanywhere.com`.
3. Log in with your superuser, or with `demo@cheeripick.app` / `cherry123` if you ran `seed_demo`.

**Check that:**
- [ ] The landing page has its full design. If it's plain unstyled HTML, the `/static/`
  mapping is wrong (step 7).
- [ ] You can sign up and log in. If you get a 403 CSRF error, check `CSRF_TRUSTED_ORIGINS` in `.env`.
- [ ] `/deck/` shows cards you can swipe.
- [ ] A photo uploaded in Settings shows up. If not, the `/media/` mapping is wrong.
- [ ] `/admin/` works.

---

## 10. Google sign-in

1. Go to https://console.cloud.google.com/apis/credentials and open your OAuth client.
2. Under **Authorized redirect URIs**, **add**, and keep the existing `127.0.0.1` one too:
   ```
   https://YOURNAME.pythonanywhere.com/accounts/google/callback/
   ```
   The `https`, the exact spelling and the slash at the end all have to match.
3. Under **Authorized JavaScript origins**, add `https://YOURNAME.pythonanywhere.com`.
4. Save. Changes can take a few minutes to apply.
5. **OAuth consent screen:** while it's in "Testing" mode, only the test users listed there
   can sign in. Add your friends' emails, or click **Publish app** to let anyone in.

If Google says **`redirect_uri_mismatch`**, the error page shows the URI the app sent. Copy
that exact value into the Google console.

---

## 11. Install the app and notifications

1. Open the site on your phone (Chrome on Android, Safari on iPhone).
2. **Settings → App & notifications → Install**. On iPhone, use Share → **Add to Home Screen**.
3. Open the installed app → **Turn on notifications** → **Send me a test notification**.

⚠️ **Free-account limit:** free PythonAnywhere accounts can only connect out to sites on an
[allowlist](https://www.pythonanywhere.com/whitelist/).
- Google (sign-in) and Chrome/Android push (`fcm.googleapis.com`) are allowed.
- Pushes to some other browsers may be blocked: Edge on Windows, Safari/iPhone, and possibly
  Firefox.
- The 🔔 bell inside the app always works.
- To get push on every browser, either upgrade to a paid plan (unrestricted internet), or ask
  PythonAnywhere support to add the push domain to the allowlist.

If a push fails, the reason is in **Web tab → Log files → error log**.

---

## Updating the site later

Each time you change code on your PC:
```bash
# On your PC
git add -A && git commit -m "my change" && git push

# In a PythonAnywhere Bash console
cd ~/cheerypick
workon cheeripick
git pull
pip install -r requirements.txt          # only if requirements changed
python manage.py migrate
python manage.py collectstatic --noinput
```
Then click **Reload** on the Web tab. **Nothing changes until you reload.**

Phones with the installed app pick up new CSS/JS automatically on their next visit, because
the service worker version changes.

---

## Keep it running (free accounts)

- A free web app **switches off after 3 months** unless you log in and click
  **"Run until 3 months from today"** on the Web tab. PythonAnywhere emails you before it
  happens.
- Optional daily jobs: **Tasks** tab → add a daily scheduled task:
  ```
  /home/YOURNAME/.virtualenvs/cheeripick/bin/python /home/YOURNAME/cheerypick/manage.py refresh_scores
  /home/YOURNAME/.virtualenvs/cheeripick/bin/python /home/YOURNAME/cheerypick/manage.py hide_inactive
  ```
- **Back up the database** now and then: **Files** → `cheerypick/db.sqlite3` → download.
- Disk space on the free plan is 512 MB, and photos use it up. Check **Account → Files**.

---

## Troubleshooting

| What you see | Fix |
|---|---|
| "Something went wrong :-(" | Web tab → **error log**. The last lines show the real Python error. |
| `ModuleNotFoundError: No module named 'django'` or `'dotenv'` | The Virtualenv path in the Web tab is wrong, or you ran `pip install` outside `workon cheeripick`. |
| `DisallowedHost` / Bad Request (400) | `DJANGO_ALLOWED_HOSTS` in `.env` must be exactly `YOURNAME.pythonanywhere.com`. |
| 403 CSRF verification failed | `CSRF_TRUSTED_ORIGINS=https://YOURNAME.pythonanywhere.com`, and open the site with `https://`. |
| Page has no styling | Run `collectstatic` again, check the `/static/` → `.../staticfiles` mapping, then Reload. |
| Photos broken | Check the `/media/` → `.../media` mapping and that the `media` folder exists. |
| "Too many redirects" | Make sure `.env` has `SECURE_SSL_REDIRECT=False`. |
| Google `redirect_uri_mismatch` | See step 10. The URI must be `https://...pythonanywhere.com/accounts/google/callback/`. |
| Edited `.env` or code but nothing changed | Click **Reload** on the Web tab. |
| "Push isn't set up on this server yet" | The `VAPID_*` lines are missing from the server's `.env`. Add them and Reload. |
