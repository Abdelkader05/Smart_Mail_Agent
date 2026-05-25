import base64
import hashlib
import hmac
import json
import os
import time
from urllib.parse import urlencode

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name, default):
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


# Runtime mode
APP_ENV = os.getenv("APP_ENV", "development").lower()
IS_RENDER = _env_bool("RENDER") or bool(os.getenv("RENDER_EXTERNAL_URL"))
REQUIRE_API_SECRET = _env_bool("REQUIRE_API_SECRET", APP_ENV == "production" or IS_RENDER)

# Telegram
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")

# Google OAuth
CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8000/callback")

# Local SQLite database used by collector, main and scripts.
LOCAL_DB_PATH = os.getenv("LOCAL_DB_PATH", "data/smart_mail_agent.db")

# Public auth server. In production this is the Render URL.
AUTH_SERVER_URL = os.getenv("AUTH_SERVER_URL", os.getenv("SERVER_URL", "http://localhost:8000"))

# Shared secrets. STATE_SECRET falls back to API_SECRET so one secret is enough.
API_SECRET = os.getenv("API_SECRET", "")
STATE_SECRET = os.getenv("STATE_SECRET", API_SECRET)
STATE_MAX_AGE_SECONDS = _env_int("STATE_MAX_AGE_SECONDS", 3600)

# Polling / worker timing
TOKEN_POLL_INTERVAL = max(1, _env_int("TOKEN_POLL_INTERVAL", 10))
MAIL_POLL_INTERVAL = max(TOKEN_POLL_INTERVAL, _env_int("MAIL_POLL_INTERVAL", 30))

# AI analysis
AI_ENABLED = _env_bool("AI_ENABLED", False)
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai").lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", os.getenv("AI_MODEL", "gpt-4.1-mini"))
AI_MODEL = OPENAI_MODEL
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
LOCAL_OPENAI_BASE_URL = os.getenv("LOCAL_OPENAI_BASE_URL", "http://localhost:1234/v1")
LOCAL_OPENAI_API_KEY = os.getenv("LOCAL_OPENAI_API_KEY", "local-key")
LOCAL_OPENAI_MODEL = os.getenv("LOCAL_OPENAI_MODEL", "local-model")
AI_TIMEOUT = max(1, _env_int("AI_TIMEOUT", 20))
AI_MAX_EMAIL_CHARS = max(500, _env_int("AI_MAX_EMAIL_CHARS", 6000))

# Render-side pending token storage. This is intentionally small and temporary.
PENDING_TOKENS_PATH = os.getenv("PENDING_TOKENS_PATH", "data/pending_tokens.json")

# Rule-based classifier settings
IMPORTANT_SENDERS = [
    item.strip().lower()
    for item in os.getenv("IMPORTANT_SENDERS", "").split(",")
    if item.strip()
]

URGENT_KEYWORDS = [
    item.strip().lower()
    for item in os.getenv(
        "URGENT_KEYWORDS",
        "urgent,asap,important,critique,deadline,relance,action requise,immediat",
    ).split(",")
    if item.strip()
]

USELESS_KEYWORDS = [
    item.strip().lower()
    for item in os.getenv(
        "USELESS_KEYWORDS",
        "newsletter,promo,promotion,publicite,unsubscribe,offre speciale",
    ).split(",")
    if item.strip()
]


if REQUIRE_API_SECRET and not API_SECRET:
    raise RuntimeError(
        "API_SECRET est obligatoire en production/Render. "
        "Definis API_SECRET dans .env local et dans les variables Render."
    )

if not API_SECRET:
    print("DEV WARNING: API_SECRET vide, routes internes permissives en mode local uniquement.")


def require_state_secret():
    if not STATE_SECRET:
        raise RuntimeError(
            "STATE_SECRET ou API_SECRET est requis pour signer le state OAuth."
        )


def _b64url_encode(raw):
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(value):
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def generate_oauth_state(user_id, chat_id):
    require_state_secret()
    payload = {
        "user_id": str(user_id),
        "chat_id": str(chat_id),
        "iat": int(time.time()),
    }
    payload_raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_part = _b64url_encode(payload_raw)
    signature = hmac.new(
        STATE_SECRET.encode("utf-8"),
        payload_part.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{payload_part}.{_b64url_encode(signature)}"


def verify_oauth_state(state):
    require_state_secret()
    if not state or "." not in state:
        raise ValueError("state OAuth manquant ou mal forme")

    payload_part, signature_part = state.split(".", 1)
    expected = hmac.new(
        STATE_SECRET.encode("utf-8"),
        payload_part.encode("ascii"),
        hashlib.sha256,
    ).digest()

    try:
        received = _b64url_decode(signature_part)
    except Exception as exc:
        raise ValueError("signature state invalide") from exc

    if not hmac.compare_digest(expected, received):
        raise ValueError("signature state invalide")

    try:
        payload = json.loads(_b64url_decode(payload_part).decode("utf-8"))
    except Exception as exc:
        raise ValueError("payload state invalide") from exc

    issued_at = int(payload.get("iat", 0))
    if issued_at <= 0 or time.time() - issued_at > STATE_MAX_AGE_SECONDS:
        raise ValueError("state OAuth expire")

    user_id = payload.get("user_id")
    chat_id = payload.get("chat_id")
    if not user_id or not chat_id:
        raise ValueError("state OAuth incomplet")

    return {"user_id": str(user_id), "chat_id": str(chat_id)}


def generate_auth_url(user_id, chat_id):
    state = generate_oauth_state(user_id, chat_id)
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/gmail.readonly",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
