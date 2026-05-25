import importlib.util
import sys

from src import config
from src.db import init_db


CHECKS = [
    ("TELEGRAM_TOKEN", config.TELEGRAM_TOKEN, True),
    ("GOOGLE_CLIENT_ID", config.CLIENT_ID, True),
    ("GOOGLE_CLIENT_SECRET", config.CLIENT_SECRET, True),
    ("REDIRECT_URI", config.REDIRECT_URI, True),
    ("AUTH_SERVER_URL", config.AUTH_SERVER_URL, True),
    ("API_SECRET", config.API_SECRET, True),
    ("STATE_SECRET", config.STATE_SECRET, True),
    ("LOCAL_DB_PATH", config.LOCAL_DB_PATH, True),
]


def ok(label):
    print(f"[OK] {label}")


def fail(label, details):
    print(f"[FAIL] {label}: {details}")


def warn(label, details):
    print(f"[WARN] {label}: {details}")


def check_required_settings():
    missing = []
    for name, value, required in CHECKS:
        if required and not value:
            missing.append(name)
            fail(name, "manquant")
        else:
            ok(name)
    return missing


def check_oauth_state():
    try:
        state = config.generate_oauth_state("setup-check-user", "setup-check-chat")
        verified = config.verify_oauth_state(state)
    except Exception as exc:
        fail("OAuth state signe", str(exc))
        return False

    if verified["user_id"] != "setup-check-user" or verified["chat_id"] != "setup-check-chat":
        fail("OAuth state signe", "payload verifie incorrect")
        return False

    ok("OAuth state signe")
    return True


def check_dependencies():
    required_modules = {
        "flask": "flask",
        "requests": "requests",
        "dotenv": "python-dotenv",
        "openai": "openai",
    }
    missing = []
    for module_name, package_name in required_modules.items():
        if importlib.util.find_spec(module_name):
            ok(f"dependance {package_name}")
        else:
            missing.append(package_name)
            fail(f"dependance {package_name}", "non installee")
    return missing


def check_database():
    try:
        init_db()
    except Exception as exc:
        fail("base SQLite locale", str(exc))
        return False

    ok("base SQLite locale")
    return True


def check_ai_settings():
    if not config.AI_ENABLED or config.AI_PROVIDER == "rules":
        ok("IA desactivee ou fallback rules")
        return True

    if config.AI_PROVIDER == "openai" and not config.OPENAI_API_KEY:
        warn("IA OpenAI", "OPENAI_API_KEY manquante, fallback rules utilise au runtime")
        return True

    ok(f"IA provider {config.AI_PROVIDER}")
    return True


def main():
    print("=== Smart Mail Agent setup check ===")
    missing_settings = check_required_settings()
    missing_deps = check_dependencies()
    db_ok = check_database()
    state_ok = check_oauth_state()
    check_ai_settings()

    if missing_settings or missing_deps or not db_ok or not state_ok:
        print("\nSetup incomplet. Corrige les lignes [FAIL], puis relance:")
        print("python -m scripts.check_setup")
        return 1

    print("\nSetup pret pour un test reel.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
