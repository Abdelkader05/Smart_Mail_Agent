import sqlite3
from config import bd_file

def create_table():
    conn = sqlite3.connect(bd_file)
    cursor = conn.cursor()

    # USER TELEGRAM
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        chat_id INTEGER PRIMARY KEY,
        user_id TEXT
    )
    """)

    # TOKENS OAUTH + GMAIL
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS oauth_tokens (
        chat_id INTEGER,
        user_id TEXT,
        gmail TEXT,
        access_token TEXT,
        refresh_token TEXT,
        expires_in INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS useless_mails (
    msg_id TEXT PRIMARY KEY,
    subject TEXT,
    sender TEXT,
    attachments TEXT,
    seen_at TEXT
);
    """)
    conn.commit()
    conn.close()