import requests
import sqlite3
import time
from config import *
import init_db

conn = sqlite3.connect(bd_file)
cursor = conn.cursor()

def save_user(chat_id, user_id):
    cursor.execute("""
    INSERT OR REPLACE INTO users (chat_id, user_id)
    VALUES (?, ?)
    """, (chat_id, user_id))
    conn.commit()

def get_updates(offset=None):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates"
    params = {"timeout": 10}
    if offset:
        params["offset"] = offset
    return requests.get(url, params=params).json()

def send_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    requests.post(url, data={"chat_id": chat_id, "text": text})

def run():
    offset = None

    while True:
        data = get_updates(offset)

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

                    auth_url = generate_auth_url(user_id)

                    send_message(chat_id, "Autorise l'accès Gmail :")
                    send_message(chat_id, auth_url)

                else:
                    send_message(chat_id, "Utilise : /start user_id")

        time.sleep(5)

if __name__ == "__main__":
    init_db.create_table()
    run()