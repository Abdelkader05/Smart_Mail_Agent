import os
import time

import requests
from flask import Flask, jsonify, request

from src.config import CLIENT_ID, CLIENT_SECRET, REDIRECT_URI, verify_oauth_state
from src.pending_tokens import ack_pending_tokens, append_pending_token, get_unconsumed_tokens

app = Flask(__name__)


print("=== CONFIG AUTH SERVER ===")
print(f"CLIENT_ID     : {'OK' if CLIENT_ID else 'MANQUANT'}")
print(f"CLIENT_SECRET : {'OK' if CLIENT_SECRET else 'MANQUANT'}")
print(f"REDIRECT_URI  : {REDIRECT_URI}")
print("==========================")


def is_authorized():
    from src.config import API_SECRET

    if not API_SECRET:
        return True
    return request.headers.get("X-API-Key") == API_SECRET


def get_gmail_address(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(
        "https://gmail.googleapis.com/gmail/v1/users/me/profile",
        headers=headers,
        timeout=15,
    )
    return response.json().get("emailAddress")


@app.route("/health")
def health():
    return jsonify({"status": "ok", "pending_tokens": len(get_unconsumed_tokens())}), 200


@app.route("/register_user", methods=["POST"])
@app.route("/add_user", methods=["POST"])
def register_user():
    if not is_authorized():
        return jsonify({"error": "unauthorized"}), 401

    body = request.get_json() or {}
    if not body.get("chat_id") or not body.get("user_id"):
        return jsonify({"error": "chat_id et user_id requis"}), 400

    # Kept for backward compatibility. Signed OAuth state carries the real data.
    return jsonify({"status": "ok"}), 200


@app.route("/callback")
def callback():
    code = request.args.get("code")
    state = request.args.get("state")

    if not code or not state:
        return "Erreur OAuth : parametres manquants", 400

    try:
        state_data = verify_oauth_state(state)
    except ValueError as exc:
        return f"Erreur OAuth : {exc}", 400

    data = {
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    response = requests.post("https://oauth2.googleapis.com/token", data=data, timeout=15)
    tokens = response.json()

    access_token = tokens.get("access_token")
    if not access_token:
        return "Erreur token Google", 400

    gmail = get_gmail_address(access_token)
    expires_at = int(time.time()) + int(tokens.get("expires_in", 3600))

    append_pending_token({
        "chat_id": state_data["chat_id"],
        "user_id": state_data["user_id"],
        "gmail": gmail,
        "access_token": access_token,
        "refresh_token": tokens.get("refresh_token"),
        "expires_at": expires_at,
    })

    return "Connexion reussie ! Tu peux fermer cette page. L'agent local va synchroniser le compte.", 200


@app.route("/pending_tokens", methods=["GET"])
@app.route("/get_tokens", methods=["GET"])
def get_pending_tokens():
    if not is_authorized():
        return jsonify({"error": "unauthorized"}), 401

    return jsonify({"tokens": get_unconsumed_tokens()}), 200


@app.route("/ack_tokens", methods=["POST"])
def ack_tokens():
    if not is_authorized():
        return jsonify({"error": "unauthorized"}), 401

    body = request.get_json() or {}
    removed = ack_pending_tokens(body.get("token_ids", []))
    return jsonify({"status": "ok", "removed": removed}), 200


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port)
