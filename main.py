import requests
import random
import time
from datetime import datetime, timedelta
from config import TELEGRAM_TOKEN, SERVER_URL, CLIENT_ID, CLIENT_SECRET

# =========================
# TELEGRAM
# =========================

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": text})

# =========================
# API SERVEUR — remplace toutes les connexions DB directes
# =========================

def get_accounts():
    r = requests.get(f"{SERVER_URL}/get_tokens", timeout=10)
    return r.json()

def update_access_token(chat_id, new_token, new_expires_at):
    requests.post(f"{SERVER_URL}/update_token", json={
        "chat_id":      chat_id,
        "access_token": new_token,
        "expires_at":   new_expires_at
    }, timeout=10)

def save_useless(msg_id, subject, sender, attachments):
    requests.post(f"{SERVER_URL}/save_useless", json={
        "msg_id":      msg_id,
        "subject":     subject,
        "sender":      sender,
        "attachments": ",".join(attachments),
        "seen_at":     datetime.now().isoformat()
    }, timeout=10)

def get_useless():
    r = requests.get(f"{SERVER_URL}/get_useless", timeout=10)
    return r.json()

def clear_useless():
    requests.post(f"{SERVER_URL}/clear_useless", timeout=10)

# =========================
# REFRESH TOKEN
# =========================

def is_token_expired(expires_at):
    return time.time() > (expires_at - 300)

def refresh_access_token(refresh_token):
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id":     CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type":    "refresh_token"
    })
    data = r.json()
    if "access_token" not in data:
        print(f"Erreur refresh_token : {data}")
        return None, None
    new_token      = data["access_token"]
    new_expires_at = int(time.time()) + int(data.get("expires_in", 3600))
    return new_token, new_expires_at

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
    payload     = msg.get("payload", {})
    headers     = payload.get("headers", [])
    subject     = ""
    sender      = ""
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
# FORMAT INUTILES
# =========================

def format_useless():
    data = get_useless()
    if not data:
        return ""

    text = "\n📦 MAILS EN ATTENTE:\n"
    for item in data:
        text += f"\n- Sujet: {item['subject']}"
        text += f"\n  De: {item['sender']}"
        text += f"\n  PJ: {item['attachments'] if item['attachments'] else 'Aucune'}"
        text += f"\n  Lu le: {item['seen_at']}\n"

    clear_useless()
    return text

# =========================
# MAIN LOOP
# =========================

def run():
    print("Agent Gmail démarré...")

    while True:
        try:
            accounts = get_accounts()
        except Exception as e:
            print(f"Erreur get_accounts : {e}")
            time.sleep(30)
            continue

        for account in accounts:
            chat_id      = account["chat_id"]
            gmail        = account["gmail"]
            token        = account["access_token"]
            refresh_token = account["refresh_token"]
            expires_at   = account["expires_at"]

            try:
                # Refresh si token expiré ou proche de l'expiration
                if is_token_expired(expires_at):
                    print(f"Token expiré pour {gmail}, rafraîchissement...")
                    new_token, new_expires_at = refresh_access_token(refresh_token)
                    if new_token:
                        update_access_token(chat_id, new_token, new_expires_at)
                        token = new_token
                        print(f"Token rafraîchi pour {gmail}")
                    else:
                        print(f"Impossible de rafraîchir le token pour {gmail}, skip.")
                        continue

                messages = get_unread(token)

                for msg in messages:
                    msg_id               = msg["id"]
                    full                 = get_mail(token, msg_id)
                    subject, sender, attachments = extract(full)
                    category             = classify()

                    # ================= URGENT =================
                    if category == "urgent":
                        useless_block = format_useless()
                        text = (
                            f"🚨 URGENT\n"
                            f"Sujet: {subject}\n"
                            f"De: {sender}\n"
                            f"PJ: {attachments if attachments else 'Aucune'}"
                        )
                        if useless_block:
                            text += useless_block
                        send_message(chat_id, text)

                    # ================= MOYEN =================
                    elif category == "moyen":
                        date      = int(full.get("internalDate", 0)) / 1000
                        mail_date = datetime.fromtimestamp(date)

                        if datetime.now() - mail_date >= timedelta(days=2):
                            useless_block = format_useless()
                            text = (
                                f"⚠️ MOYEN\n"
                                f"Sujet: {subject}\n"
                                f"De: {sender}\n"
                                f"PJ: {attachments if attachments else 'Aucune'}"
                            )
                            if useless_block:
                                text += useless_block
                            send_message(chat_id, text)

                    # ================= INUTILE =================
                    else:
                        save_useless(msg_id, subject, sender, attachments)

            except Exception as e:
                print(f"Erreur [{gmail}]: {e}")

        time.sleep(30)

# =========================
# START
# =========================

if __name__ == "__main__":
    run()
