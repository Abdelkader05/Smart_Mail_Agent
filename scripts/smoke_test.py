import os
import tempfile
import time


tmp_dir = tempfile.TemporaryDirectory()
os.environ.setdefault("TELEGRAM_TOKEN", "test-telegram-token")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("REDIRECT_URI", "http://localhost:8000/callback")
os.environ.setdefault("AUTH_SERVER_URL", "http://localhost:8000")
os.environ.setdefault("API_SECRET", "test-api-secret")
os.environ.setdefault("STATE_SECRET", "test-state-secret")
os.environ.setdefault("LOCAL_DB_PATH", os.path.join(tmp_dir.name, "smoke.db"))
os.environ.setdefault("PENDING_TOKENS_PATH", os.path.join(tmp_dir.name, "pending_tokens.json"))
os.environ.setdefault("AI_ENABLED", "false")
os.environ.setdefault("AI_PROVIDER", "rules")

from src.ai_provider import analyze_email_with_ai
from src.config import generate_oauth_state, verify_oauth_state
from src.db import (
    get_accounts,
    get_mail_analysis,
    init_db,
    is_mail_processed,
    mark_mail_processed,
    save_mail_analysis,
    save_user,
    upsert_token,
)
from src.main import extract
from src.pending_tokens import ack_pending_tokens, append_pending_token, get_unconsumed_tokens


def assert_true(condition, message):
    if not condition:
        raise AssertionError(message)


def test_oauth_state():
    state = generate_oauth_state("user-1", "chat-1")
    verified = verify_oauth_state(state)
    assert_true(verified == {"user_id": "user-1", "chat_id": "chat-1"}, "state OAuth invalide")


def test_database():
    init_db()
    save_user("chat-1", "user-1")
    upsert_token({
        "chat_id": "chat-1",
        "user_id": "user-1",
        "gmail": "user@example.com",
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_at": int(time.time()) + 3600,
    })
    accounts = get_accounts()
    assert_true(len(accounts) == 1, "compte OAuth non sauvegarde")

    assert_true(not is_mail_processed("msg-1"), "mail marque traite trop tot")
    mark_mail_processed("msg-1", "user@example.com", "urgent")
    assert_true(is_mail_processed("msg-1"), "mail traite non persiste")

    analysis = {
        "category": "urgent",
        "importance_score": 90,
        "summary": "Resume",
        "reason": "Raison",
        "suggested_action": "Action",
        "deadline_detected": None,
        "requires_reply": True,
        "confidence": 80,
        "provider": "rules",
    }
    save_mail_analysis("msg-1", "user@example.com", analysis)
    saved = get_mail_analysis("msg-1")
    assert_true(saved["category"] == "urgent", "analyse non sauvegardee")
    assert_true(saved["requires_reply"] is True, "requires_reply mal restaure")


def test_pending_tokens():
    append_pending_token({
        "chat_id": "chat-1",
        "user_id": "user-1",
        "gmail": "user@example.com",
        "access_token": "access",
        "refresh_token": "refresh",
        "expires_at": int(time.time()) + 3600,
    })
    tokens = get_unconsumed_tokens()
    assert_true(len(tokens) == 1 and tokens[0].get("id"), "pending token non cree")
    removed = ack_pending_tokens([tokens[0]["id"]])
    assert_true(removed == 1, "pending token non ack")
    assert_true(get_unconsumed_tokens() == [], "pending token encore present")


def test_email_extract_and_analysis():
    msg = {
        "internalDate": str(int(time.time() * 1000)),
        "snippet": "Deadline importante demain",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "URGENT deadline projet"},
                {"name": "From", "value": "client@example.com"},
                {"name": "Date", "value": "Mon, 25 May 2026 10:00:00 +0200"},
            ],
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": "TWVyY2kgZGUgdmFsaWRlciByYXBpZGVtZW50Lg=="},
                },
                {"filename": "facture.pdf", "mimeType": "application/pdf", "body": {}},
            ],
        },
    }
    email = extract(msg)
    assert_true(email["subject"] == "URGENT deadline projet", "sujet non extrait")
    assert_true(email["attachments"] == ["facture.pdf"], "piece jointe non extraite")
    analysis = analyze_email_with_ai(email)
    assert_true(analysis["category"] == "urgent", "fallback rules devrait classer urgent")


def main():
    try:
        test_oauth_state()
        test_database()
        test_pending_tokens()
        test_email_extract_and_analysis()
    finally:
        tmp_dir.cleanup()
    print("Smoke test OK.")


if __name__ == "__main__":
    main()
