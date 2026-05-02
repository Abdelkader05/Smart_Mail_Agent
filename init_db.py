import psycopg2
import os
from config import DATABASE_URL

def create_table():
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()

    # USER TELEGRAM
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        chat_id TEXT PRIMARY KEY,
        user_id TEXT
    )
    """)

    # TOKENS OAUTH + GMAIL
    # expires_at = timestamp UNIX réel (plus fiable que expires_in)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS oauth_tokens (
        chat_id TEXT,
        user_id TEXT,
        gmail TEXT,
        access_token TEXT,
        refresh_token TEXT,
        expires_at BIGINT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # MAILS INUTILES
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS useless_mails (
        msg_id TEXT PRIMARY KEY,
        subject TEXT,
        sender TEXT,
        attachments TEXT,
        seen_at TEXT
    )
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("Tables PostgreSQL créées avec succès.")

if __name__ == "__main__":
    create_table()
