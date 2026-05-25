import time

import requests

from src.config import API_SECRET, AUTH_SERVER_URL, TELEGRAM_TOKEN, generate_auth_url
from src.db import init_db, save_user


def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"timeout": 10}
    if offset:
        params["offset"] = offset
    return requests.get(url, params=params, timeout=15).json()


def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": text}, timeout=10)


def register_user_on_auth_server(chat_id, user_id):
    headers = {}
    if API_SECRET:
        headers["X-API-Key"] = API_SECRET

    try:
        response = requests.post(
            f"{AUTH_SERVER_URL}/register_user",
            json={"chat_id": str(chat_id), "user_id": str(user_id)},
            headers=headers,
            timeout=10,
        )
        if response.status_code != 200:
            print(f"Erreur register_user : {response.status_code} {response.text}")
    except Exception as exc:
        print(f"Serveur auth indisponible, le state OAuth garde quand meme le chat_id : {exc}")


def run():
    init_db()
    offset = None
    print("Bot Telegram demarre...")

    while True:
        try:
            data = get_updates(offset)
        except Exception as exc:
            print(f"Erreur getUpdates Telegram : {exc}")
            time.sleep(5)
            continue

        for update in data.get("result", []):
            offset = update["update_id"] + 1

            if "message" not in update:
                continue

            msg = update["message"]
            chat_id = msg["chat"]["id"]
            text = msg.get("text", "")

            if text.startswith("/start"):
                parts = text.split()

                if len(parts) == 2:
                    user_id = parts[1]
                    save_user(chat_id, user_id)
                    register_user_on_auth_server(chat_id, user_id)

                    try:
                        auth_url = generate_auth_url(user_id, chat_id)
                    except RuntimeError as exc:
                        print(f"Erreur configuration OAuth : {exc}")
                        send_message(chat_id, "Configuration OAuth incomplete. Verifie API_SECRET ou STATE_SECRET.")
                        continue

                    send_message(chat_id, "Autorise l'acces Gmail :")
                    send_message(chat_id, auth_url)
                else:
                    send_message(chat_id, "Utilise : /start user_id")

        time.sleep(5)


if __name__ == "__main__":
    run()
