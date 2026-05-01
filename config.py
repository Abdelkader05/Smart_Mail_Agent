TELEGRAM_CHAT_ID = "TON_CHAT_ID"
CLAUDE_API_KEY = "TA_CLE"

TELEGRAM_TOKEN = "8626140879:AAHIkIKLrpVTGZa4vKu2muP64uccm2mzRvk"          # TELEGRAM_TOKEN du bot Telegram
JSON_FILE = "accounts.json"     # Fichier contenant id + emails

bd_file = "database.db"     # Fichier contenant id + emails

from urllib.parse import urlencode

CLIENT_ID = "488628652749-53djmg2406q7550v1sgvdlpp4rerramn.apps.googleusercontent.com"
CLIENT_SECRET = "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"
REDIRECT_URI = "http://localhost:8000/callback"

def generate_auth_url(user_id):
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/gmail.readonly",
        "access_type": "offline",
        "prompt": "consent",
        "state": user_id
    }

    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)