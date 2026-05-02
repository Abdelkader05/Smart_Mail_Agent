from flask import Flask, request, jsonify
import requests
import psycopg2
import time
import os
from config import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, TELEGRAM_TOKEN, DATABASE_URL

app = Flask(__name__)

# =========================
# DEBUG
# =========================
print("=== CONFIG CHARGÉE ===")
print(f"CLIENT_ID     : {'OK' if CLIENT_ID else '❌ MANQUANT'}")
print(f"CLIENT_SECRET : {'OK' if CLIENT_SECRET else '❌ MANQUANT'}")
print(f"REDIRECT_URI  : {REDIRECT_URI}")
print(f"DATABASE_URL  : {'OK' if DATABASE_URL else '❌ MANQUANT'}")
print(f"TELEGRAM_TOKEN: {'OK' if TELEGRAM_TOKEN else '❌ MANQUANT'}")
print("======================")

# =========================
# CONNEXION DB
# =========================

def get_conn():
    return psycopg2.connect(DATABASE_URL)

# =========================
# UTILS
# =========================

def get_chat_id(user_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT chat_id FROM users WHERE user_id = %s", (user_id,))
    result = cur.fetchone()
    cur.close()
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
    conn = get_conn()
    cur = conn.cursor()
    expires_at = int(time.time()) + int(tokens.get("expires_in", 3600))
    cur.execute("""
        INSERT INTO oauth_tokens (chat_id, user_id, gmail, access_token, refresh_token, expires_at)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """, (
        chat_id, user_id, gmail,
        tokens.get("access_token"),
        tokens.get("refresh_token"),
        expires_at
    ))
    conn.commit()
    cur.close()
    conn.close()

# =========================
# ROUTE OAUTH CALLBACK
# =========================

@app.route("/callback")
def callback():
    code    = request.args.get("code")
    user_id = request.args.get("state")

    if not code or not user_id:
        return "Erreur OAuth : paramètres manquants", 400

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
        return f"Erreur token Google : {tokens}", 400

    gmail   = get_gmail_address(access_token)
    chat_id = get_chat_id(user_id)

    if chat_id:
        save_tokens(chat_id, user_id, gmail, tokens)
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": chat_id, "text": f"✅ Gmail connecté : {gmail}"}
        )
        return "Connexion réussie ! Tu peux fermer cette page.", 200

    return "Erreur : utilisateur introuvable", 404

# =========================
# ROUTE API — Ajouter un utilisateur
# =========================

@app.route("/add_user", methods=["POST"])
def add_user():
    body    = request.get_json()
    chat_id = body.get("chat_id")
    user_id = body.get("user_id")

    if not chat_id or not user_id:
        return jsonify({"error": "chat_id et user_id requis"}), 400

    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO users (chat_id, user_id)
        VALUES (%s, %s)
        ON CONFLICT (chat_id) DO UPDATE SET user_id = EXCLUDED.user_id
    """, (str(chat_id), str(user_id)))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"status": "ok"}), 200

# =========================
# ROUTE API — Récupérer tous les tokens
# =========================

@app.route("/get_tokens", methods=["GET"])
def get_tokens():
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT chat_id, gmail, access_token, refresh_token, expires_at FROM oauth_tokens")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    result = [
        {
            "chat_id":       row[0],
            "gmail":         row[1],
            "access_token":  row[2],
            "refresh_token": row[3],
            "expires_at":    row[4]
        }
        for row in rows
    ]
    return jsonify(result), 200

# =========================
# ROUTE API — Mettre à jour le access_token après refresh
# =========================

@app.route("/update_token", methods=["POST"])
def update_token():
    body = request.get_json()
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        UPDATE oauth_tokens
        SET access_token = %s, expires_at = %s
        WHERE chat_id = %s
    """, (
        body.get("access_token"),
        body.get("expires_at"),
        body.get("chat_id")
    ))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"status": "ok"}), 200

# =========================
# ROUTE API — Sauvegarder un mail inutile
# =========================

@app.route("/save_useless", methods=["POST"])
def save_useless():
    body = request.get_json()
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("""
        INSERT INTO useless_mails (msg_id, subject, sender, attachments, seen_at)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (msg_id) DO NOTHING
    """, (
        body.get("msg_id"),
        body.get("subject"),
        body.get("sender"),
        body.get("attachments"),
        body.get("seen_at")
    ))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"status": "ok"}), 200

# =========================
# ROUTE API — Récupérer les mails inutiles
# =========================

@app.route("/get_useless", methods=["GET"])
def get_useless():
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("SELECT subject, sender, attachments, seen_at FROM useless_mails")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    result = [
        {"subject": r[0], "sender": r[1], "attachments": r[2], "seen_at": r[3]}
        for r in rows
    ]
    return jsonify(result), 200

# =========================
# ROUTE API — Supprimer les mails inutiles
# =========================

@app.route("/clear_useless", methods=["POST"])
def clear_useless():
    conn = get_conn()
    cur  = conn.cursor()
    cur.execute("DELETE FROM useless_mails")
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({"status": "cleared"}), 200

# =========================
# START
# =========================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
