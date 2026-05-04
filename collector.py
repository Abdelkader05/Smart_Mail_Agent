import requests
import time
from config import TELEGRAM_TOKEN, SERVER_URL, generate_auth_url

# =========================
# TELEGRAM
# =========================

def get_updates(offset=None):
    url    = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"timeout": 10}
    if offset:
        params["offset"] = offset
    return requests.get(url, params=params).json()

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": text})

# =========================
# API SERVEUR
# =========================

def save_user(chat_id, user_id):
    try:
        r = requests.post(
            f"{SERVER_URL}/add_user",
            json={"chat_id": str(chat_id), "user_id": str(user_id)},
            timeout=10
        )
        if r.status_code != 200:
            print(f"Erreur save_user : {r.status_code} {r.text}")
    except Exception as e:
        print(f"Impossible de joindre le serveur : {e}")

# =========================
# BOUCLE PRINCIPALE
# =========================

def run():
    offset = None
    print("Bot Telegram démarré...")

    while True:
        data = get_updates(offset)

        for update in data.get("result", []):
            offset = update["update_id"] + 1

            if "message" not in update:
                continue

            msg     = update["message"]
            chat_id = msg["chat"]["id"]
            text    = msg.get("text", "")

            if text.startswith("/start"):
                parts = text.split()

                if len(parts) == 2:
                    user_id = parts[1]
                    save_user(chat_id, user_id)
                    auth_url = generate_auth_url(user_id)
                    send_message(chat_id, "Autorise l'accès Gmail :")
                    send_message(chat_id, auth_url)
                else:
                    send_message(chat_id, "Utilise : /start user_id")

        time.sleep(5)

# =========================
# START
# =========================

if __name__ == "__main__":
    run()  # Plus d'init_db ici, les tables existent déjà sur Render
