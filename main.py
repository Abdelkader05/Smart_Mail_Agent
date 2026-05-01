import sqlite3
import requests
import random
import time
from datetime import datetime, timedelta
from config import bd_file, TELEGRAM_TOKEN

# =========================
# TELEGRAM
# =========================

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": text})

# =========================
# DB
# =========================

def get_accounts():
    conn = sqlite3.connect(bd_file)
    cur = conn.cursor()

    cur.execute("SELECT chat_id, gmail, access_token FROM oauth_tokens")
    data = cur.fetchall()

    conn.close()
    return data


def save_useless(msg_id, subject, sender, attachments):
    conn = sqlite3.connect(bd_file)
    cur = conn.cursor()

    cur.execute("""
    INSERT OR IGNORE INTO useless_mails
    (msg_id, subject, sender, attachments, seen_at)
    VALUES (?, ?, ?, ?, ?)
    """, (
        msg_id,
        subject,
        sender,
        ",".join(attachments),
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


def get_useless():
    conn = sqlite3.connect(bd_file)
    cur = conn.cursor()

    cur.execute("""
    SELECT subject, sender, attachments, seen_at FROM useless_mails
    """)

    rows = cur.fetchall()
    conn.close()

    return rows


def clear_useless():
    conn = sqlite3.connect(bd_file)
    cur = conn.cursor()

    cur.execute("DELETE FROM useless_mails")
    conn.commit()
    conn.close()

# =========================
# GMAIL
# =========================

def get_unread(token):
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.get(
        "https://gmail.googleapis.com/gmail/v1/users/me/messages?q=is:unread",
        headers=headers
    )

    return r.json().get("messages", [])


def get_mail(token, msg_id):
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.get(
        f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{msg_id}",
        headers=headers
    )

    return r.json()

# =========================
# EXTRACTION
# =========================

def extract(msg):
    payload = msg.get("payload", {})
    headers = payload.get("headers", [])

    subject = ""
    sender = ""
    attachments = []

    for h in headers:
        if h["name"] == "Subject":
            subject = h["value"]
        if h["name"] == "From":
            sender = h["value"]

    for part in payload.get("parts", []):
        if part.get("filename"):
            attachments.append(part["filename"])

    return subject, sender, attachments

# =========================
# CLASSIFICATION (V1 RANDOM)
# =========================

def classify():
    return random.choice(["urgent", "moyen", "inutile"])

# =========================
# INUTILES FORMAT
# =========================

def format_useless():
    data = get_useless()

    if not data:
        return ""

    text = "\n📦 MAILS MARQUÉS COMME LUS:\n"

    for subject, sender, attachments, seen_at in data:
        text += f"\n- Sujet: {subject}"
        text += f"\n  De: {sender}"
        text += f"\n  PJ: {attachments if attachments else 'Aucune'}"
        text += f"\n  Lu le: {seen_at}\n"

    clear_useless()

    return text

# =========================
# MAIN LOOP
# =========================

def run():
    print("Agent Gmail V3 lancé...")

    while True:
        accounts = get_accounts()

        for chat_id, gmail, token in accounts:

            try:
                messages = get_unread(token)

                for msg in messages:
                    msg_id = msg["id"]
                    full = get_mail(token, msg_id)

                    subject, sender, attachments = extract(full)

                    category = classify()

                    # ================= URGENT =================
                    if category == "urgent":
                        useless_block = format_useless()

                        text = f"🚨 URGENT\nSujet: {subject}\nDe: {sender}\nPJ: {attachments if attachments else 'Aucune'}"

                        if useless_block:
                            text += useless_block

                        send_message(chat_id, text)

                    # ================= MOYEN =================
                    elif category == "moyen":
                        date = int(full.get("internalDate", 0)) / 1000
                        mail_date = datetime.fromtimestamp(date)

                        if datetime.now() - mail_date >= timedelta(days=2):
                            useless_block = format_useless()

                            text = f"⚠️ MOYEN\nSujet: {subject}\nDe: {sender}\nPJ: {attachments if attachments else 'Aucune'}"

                            if useless_block:
                                text += useless_block

                            send_message(chat_id, text)

                    # ================= INUTILE =================
                    else:
                        save_useless(msg_id, subject, sender, attachments)

            except Exception as e:
                print("Erreur:", gmail, e)

        time.sleep(30)

# =========================
# START
# =========================

if __name__ == "__main__":
    run()