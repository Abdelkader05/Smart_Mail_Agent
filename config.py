import os
from urllib.parse import urlencode

# =========================
# TELEGRAM
# =========================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")

# =========================
# GOOGLE OAUTH
# =========================
CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
REDIRECT_URI  = os.getenv("REDIRECT_URI", "http://localhost:8000/callback")
# En prod Render : REDIRECT_URI = "https://ton-app.onrender.com/callback"

# =========================
# BASE DE DONNÉES
# =========================
# En local pour tests : "postgresql://user:password@localhost:5432/maildb"
# En prod Render      : fourni automatiquement par Render dans DATABASE_URL
DATABASE_URL = os.getenv("DATABASE_URL", "")

# =========================
# URL interne du serveur Flask
# =========================
# En local : "http://localhost:8000"
# En prod  : "https://ton-app.onrender.com"
SERVER_URL = os.getenv("SERVER_URL", "http://localhost:8000")

# =========================
# GÉNÉRATION URL OAUTH
# =========================
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
