import requests
import random
import time
from datetime import datetime, timedelta
from config import TELEGRAM_TOKEN, SERVER_URL, CLIENT_ID, CLIENT_SECRET

# =========================
# DÉDUPLICATION EN MÉMOIRE
# =========================
# Set global : contient tous les msg_id déjà traités depuis le lancement
processed_ids = set()

# =========================
# TELEGRAM
# =========================

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": text})

# =========================
# API SERVEUR
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
    return data["access_token"], int(time.time()) + int(data.get("expires_in", 3600))

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
# INIT : marquer les emails existants comme déjà vus
# =========================

def preload_existing_emails(token, gmail):
    """
    Au démarrage, récupère tous les emails non lus actuels et les ajoute
    dans processed_ids SANS envoyer de notification.
    Seuls les emails arrivant APRÈS ce moment seront notifiés.
    """
    try:
        messages = get_unread(token)
        count = 0
        for msg in messages:
            msg_id = msg["id"]
            if msg_id not in processed_ids:
                processed_ids.add(msg_id)
                count += 1
        if count > 0:
            print(f"[{gmail}] {count} email(s) existant(s) ignorés (déjà présents au démarrage)")
    except Exception as e:
        print(f"[{gmail}] Erreur preload : {e}")

# =========================
# MAIN LOOP
# =========================

def run():
    print("Agent Gmail démarré...")
    first_run = True  # Indique si c'est le premier passage

    while True:
        try:
            accounts = get_accounts()
        except Exception as e:
            print(f"Erreur get_accounts : {e}")
            time.sleep(30)
            continue

        for account in accounts:
            chat_id       = account["chat_id"]
            gmail         = account["gmail"]
            token         = account["access_token"]
            refresh_token = account["refresh_token"]
            expires_at    = account["expires_at"]

            try:
                # Refresh token si nécessaire
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

                # Premier passage : marquer les emails existants sans notifier
                if first_run:
                    preload_existing_emails(token, gmail)
                    continue  # On ne traite rien lors du premier passage

                # Passages suivants : traiter uniquement les nouveaux emails
                messages = get_unread(token)

                for msg in messages:
                    msg_id = msg["id"]

                    # Déjà traité → on skip
                    if msg_id in processed_ids:
                        continue

                    # Nouveau mail → on le marque immédiatement
                    processed_ids.add(msg_id)

                    full                         = get_mail(token, msg_id)
                    subject, sender, attachments = extract(full)
                    category                     = classify()

                    if category == "urgent":
                        useless_block = format_useless()
                        text = f"🚨 URGENT\nSujet: {subject}\nDe: {sender}\nPJ: {attachments if attachments else 'Aucune'}"
                        if useless_block:
                            text += useless_block
                        send_message(chat_id, text)

                    elif category == "moyen":
                        date      = int(full.get("internalDate", 0)) / 1000
                        mail_date = datetime.fromtimestamp(date)
                        if datetime.now() - mail_date >= timedelta(days=2):
                            useless_block = format_useless()
                            text = f"⚠️ MOYEN\nSujet: {subject}\nDe: {sender}\nPJ: {attachments if attachments else 'Aucune'}"
                            if useless_block:
                                text += useless_block
                            send_message(chat_id, text)

                    else:
                        save_useless(msg_id, subject, sender, attachments)

            except Exception as e:
                print(f"Erreur [{gmail}]: {e}")

        # Après le premier tour complet sur tous les comptes, on passe en mode normal
        if first_run:
            print("Initialisation terminée. Surveillance des nouveaux emails...")
            first_run = False

        time.sleep(30)

# =========================
# START
# =========================

if __name__ == "__main__":
    run()
