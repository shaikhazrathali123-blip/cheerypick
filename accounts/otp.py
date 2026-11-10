"""
Phone OTP — placeholder implementation, no paid SMS service.

send_otp() generates a 6-digit code, stores a hash of it in the session for
10 minutes and logs it to the console. Swap `_deliver` for Twilio/MSG91/etc.
when you're ready.
"""
import hashlib
import logging
import secrets
import time

logger = logging.getLogger(__name__)
SESSION_KEY = "cheeripick_phone_otp"
TTL_SECONDS = 600


def _hash(code, phone):
    return hashlib.sha256(f"{phone}:{code}".encode()).hexdigest()


def _deliver(phone, code):
    # STUB: print instead of sending an SMS.
    print(f"\n📱 [CheeriPick OTP stub] Code for {phone}: {code}\n")
    logger.info("OTP for %s generated (stub delivery)", phone)


def send_otp(request, phone):
    code = f"{secrets.randbelow(1_000_000):06d}"
    request.session[SESSION_KEY] = {"phone": phone, "hash": _hash(code, phone), "ts": time.time()}
    _deliver(phone, code)
    return True


def verify_otp(request, phone, code):
    data = request.session.get(SESSION_KEY)
    if not data or data.get("phone") != phone:
        return False
    if time.time() - data.get("ts", 0) > TTL_SECONDS:
        request.session.pop(SESSION_KEY, None)
        return False
    ok = secrets.compare_digest(data["hash"], _hash(code.strip(), phone))
    if ok:
        request.session.pop(SESSION_KEY, None)
    return ok
