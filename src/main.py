import time
import base64
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

import requests

from src.ai_provider import analyze_email_with_ai
from src.config import (
    API_SECRET,
    AUTH_SERVER_URL,
    CLIENT_ID,
    CLIENT_SECRET,
    MAIL_POLL_INTERVAL,
    TELEGRAM_TOKEN,
    TOKEN_POLL_INTERVAL,
)
from src.db import (
    clear_useless_mails,
    get_accounts,
    get_mail_analysis,
    get_useless_mails,
    init_db,
    is_mail_processed,
    mark_mail_processed,
    save_mail_analysis,
    save_useless_mail,
    update_access_token,
    upsert_token,
)


processed_ids = set()


def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=10)


def auth_headers():
    if not API_SECRET:
        return {}
    return {"X-API-Key": API_SECRET}


def sync_tokens_from_auth_server():
    try:
        response = requests.get(
            f"{AUTH_SERVER_URL}/pending_tokens",
            headers=auth_headers(),
            timeout=10,
        )
    except Exception as exc:
        print(f"Sync OAuth indisponible : {exc}")
        return

    if response.status_code == 404:
        return

    if response.status_code != 200:
        print(f"Erreur sync OAuth : {response.status_code} {response.text}")
        return

    tokens = response.json().get("tokens", [])
    saved_token_ids = []
    for token in tokens:
        if not token.get("chat_id"):
            print(f"Token OAuth ignore sans chat_id : {token.get('gmail')}")
            continue
        upsert_token(token)
        if token.get("id"):
            saved_token_ids.append(token["id"])
        print(f"Compte Gmail synchronise en local : {token.get('gmail')}")
        send_message(token["chat_id"], f"Gmail connecte : {token.get('gmail')}")

    if saved_token_ids:
        try:
            ack_response = requests.post(
                f"{AUTH_SERVER_URL}/ack_tokens",
                json={"token_ids": saved_token_ids},
                headers=auth_headers(),
                timeout=10,
            )
            if ack_response.status_code != 200:
                print(f"Erreur ack OAuth : {ack_response.status_code} {ack_response.text}")
        except Exception as exc:
            print(f"Accuse de reception OAuth indisponible : {exc}")


def is_token_expired(expires_at):
    return time.time() > (int(expires_at) - 300)


def refresh_access_token(refresh_token):
    response = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }, timeout=15)
    data = response.json()
    if "access_token" not in data:
        print("Erreur refresh_token : impossible de recuperer un nouvel access_token.")
        return None, None
    return data["access_token"], int(time.time()) + int(data.get("expires_in", 3600))


def get_unread(token):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages?q=is:unread",
        headers=headers,
        timeout=15,
    )
    return response.json().get("messages", [])


def get_mail(token, msg_id):
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(
        f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}",
        headers=headers,
        timeout=15,
    )
    return response.json()


def extract(msg):
    payload = msg.get("payload", {})
    headers = payload.get("headers", [])
    subject = ""
    sender = ""
    date_header = ""
    attachments = []
    body_parts = []

    for header in headers:
        if header["name"] == "Subject":
            subject = header["value"]
        if header["name"] == "From":
            sender = header["value"]
        if header["name"] == "Date":
            date_header = header["value"]

    for part in walk_parts(payload):
        if part.get("filename"):
            attachments.append(part["filename"])
        mime_type = part.get("mimeType", "")
        if mime_type in {"text/plain", "text/html"}:
            text = decode_part_body(part)
            if text:
                body_parts.append(clean_email_body(text, mime_type))

    body = "\n\n".join(part for part in body_parts if part).strip()
    mail_date = parse_mail_date(date_header, msg.get("internalDate"))

    return {
        "subject": subject,
        "sender": sender,
        "date": date_header,
        "mail_date": mail_date,
        "snippet": msg.get("snippet", ""),
        "body": body,
        "attachments": attachments,
    }


def walk_parts(part):
    yield part
    for child in part.get("parts", []) or []:
        yield from walk_parts(child)


def decode_part_body(part):
    data = part.get("body", {}).get("data")
    if not data:
        return ""
    try:
        raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
        return raw.decode("utf-8", errors="replace")
    except Exception:
        return ""


def clean_email_body(text, mime_type):
    if mime_type == "text/html":
        import re

        text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", text)
        text = re.sub(r"(?s)<[^>]+>", " ", text)
    return " ".join(text.split())


def parse_mail_date(date_header, internal_date):
    if date_header:
        try:
            parsed = parsedate_to_datetime(date_header)
            return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
        except Exception:
            pass
    if internal_date:
        try:
            return datetime.fromtimestamp(int(internal_date) / 1000)
        except (TypeError, ValueError):
            return None
    return None


def should_notify_medium(email, analysis):
    if analysis.get("requires_reply"):
        return True
    if int(analysis.get("importance_score", 0)) >= 55:
        return True
    mail_date = email.get("mail_date")
    return bool(mail_date and datetime.now() - mail_date >= timedelta(days=2))


def format_notification(category, email, analysis):
    lines = [
        f"{category.upper()} - Score {analysis['importance_score']}/100",
        f"Sujet: {email['subject'] or '(sans sujet)'}",
        f"De: {email['sender'] or '(inconnu)'}",
        f"Resume: {analysis['summary']}",
        f"Pourquoi: {analysis['reason']}",
        f"Action: {analysis['suggested_action']}",
    ]
    if analysis.get("deadline_detected"):
        lines.append(f"Deadline: {analysis['deadline_detected']}")
    lines.append(f"Reponse requise: {'oui' if analysis.get('requires_reply') else 'non'}")
    lines.append(f"Confiance: {analysis['confidence']}/100")
    lines.append(f"PJ: {email['attachments'] if email['attachments'] else 'Aucune'}")
    return "\n".join(lines)


def format_useless():
    data = get_useless_mails()
    if not data:
        return ""

    text = "\nMAILS EN ATTENTE:\n"
    for item in data:
        text += f"\n- Sujet: {item['subject']}"
        text += f"\n  De: {item['sender']}"
        text += f"\n  PJ: {item['attachments'] if item['attachments'] else 'Aucune'}"
        text += f"\n  Lu le: {item['seen_at']}\n"

    clear_useless_mails()
    return text


def preload_existing_emails(token, gmail):
    try:
        messages = get_unread(token)
        count = 0
        for msg in messages:
            msg_id = msg["id"]
            if msg_id not in processed_ids and not is_mail_processed(msg_id):
                processed_ids.add(msg_id)
                mark_mail_processed(msg_id, gmail, "preloaded")
                count += 1
        if count > 0:
            print(f"[{gmail}] {count} email(s) existant(s) ignores au demarrage")
    except Exception as exc:
        print(f"[{gmail}] Erreur preload : {exc}")


def run():
    init_db()
    print("Agent Gmail demarre...")
    preloaded_accounts = set()
    initialized_announced = False
    last_mail_check = 0

    while True:
        sync_tokens_from_auth_server()
        now = time.time()
        if preloaded_accounts and now - last_mail_check < MAIL_POLL_INTERVAL:
            time.sleep(TOKEN_POLL_INTERVAL)
            continue

        last_mail_check = now
        accounts = get_accounts()

        for account in accounts:
            chat_id = account["chat_id"]
            gmail = account["gmail"]
            token = account["access_token"]
            refresh_token = account["refresh_token"]
            expires_at = account["expires_at"]

            try:
                if is_token_expired(expires_at):
                    print(f"Token expire pour {gmail}, rafraichissement...")
                    new_token, new_expires_at = refresh_access_token(refresh_token)
                    if new_token:
                        update_access_token(chat_id, new_token, new_expires_at)
                        token = new_token
                        print(f"Token rafraichi pour {gmail}")
                    else:
                        print(f"Impossible de rafraichir le token pour {gmail}, skip.")
                        continue

                if chat_id not in preloaded_accounts:
                    preload_existing_emails(token, gmail)
                    preloaded_accounts.add(chat_id)
                    continue

                messages = get_unread(token)

                for msg in messages:
                    msg_id = msg["id"]
                    if msg_id in processed_ids or is_mail_processed(msg_id):
                        continue

                    full = get_mail(token, msg_id)
                    email = extract(full)
                    analysis = get_mail_analysis(msg_id)
                    if not analysis:
                        analysis = analyze_email_with_ai(email)
                        save_mail_analysis(msg_id, gmail, analysis)
                    category = analysis["category"]

                    if category == "urgent":
                        useless_block = format_useless()
                        text = format_notification(category, email, analysis)
                        if useless_block:
                            text += useless_block
                        send_message(chat_id, text)
                        mark_mail_processed(msg_id, gmail, category)
                        processed_ids.add(msg_id)

                    elif category == "moyen":
                        if should_notify_medium(email, analysis):
                            useless_block = format_useless()
                            text = format_notification(category, email, analysis)
                            if useless_block:
                                text += useless_block
                            send_message(chat_id, text)
                        mark_mail_processed(msg_id, gmail, category)
                        processed_ids.add(msg_id)

                    else:
                        save_useless_mail(
                            msg_id,
                            email["subject"],
                            email["sender"],
                            ",".join(email["attachments"]),
                            datetime.now().isoformat(),
                        )
                        mark_mail_processed(msg_id, gmail, category)
                        processed_ids.add(msg_id)

            except Exception as exc:
                print(f"Erreur [{gmail}]: {exc}")

        if not initialized_announced and accounts and len(preloaded_accounts) >= len(accounts):
            print("Initialisation terminee. Surveillance des nouveaux emails...")
            initialized_announced = True

        time.sleep(TOKEN_POLL_INTERVAL)


if __name__ == "__main__":
    run()
