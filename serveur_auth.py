from flask import Flask, request
import requests
import sqlite3
from config import *

app = Flask(__name__)

def get_chat_id(user_id):
    conn = sqlite3.connect(bd_file)
    cursor = conn.cursor()

    cursor.execute("SELECT chat_id FROM users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    conn.close()
    return result[0] if result else None

def get_gmail_address(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}

    r = requests.get(
        "https://gmail.googleapis.com/gmail/v1/users/me/profile",
        headers=headers
    )

    return r.json().get("emailAddress")

def save_tokens(chat_id, user_id, gmail, tokens):
    conn = sqlite3.connect(bd_file)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO oauth_tokens (chat_id, user_id, gmail, access_token, refresh_token, expires_in)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        chat_id,
        user_id,
        gmail,
        tokens.get("access_token"),
        tokens.get("refresh_token"),
        tokens.get("expires_in")
    ))

    conn.commit()
    conn.close()

@app.route("/callback")
def callback():
    code = request.args.get("code")
    user_id = request.args.get("state")

    if not code or not user_id:
        return "Erreur OAuth"

    # Échange code → token
    data = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code"
    }

    r = requests.post("https://oauth2.googleapis.com/token", data=data)
    tokens = r.json()

    access_token = tokens.get("access_token")

    if not access_token:
        return str(tokens)

    gmail = get_gmail_address(access_token)
    chat_id = get_chat_id(user_id)

    if chat_id:
        save_tokens(chat_id, user_id, gmail, tokens)

        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": chat_id, "text": f"Gmail connecté : {gmail}"}
        )

    return "Connexion réussie"

app.run(port=8000)