import os
import sqlite3
from contextlib import contextmanager

from src.config import LOCAL_DB_PATH


@contextmanager
def get_conn():
    db_dir = os.path.dirname(LOCAL_DB_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(LOCAL_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                chat_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS oauth_tokens (
                chat_id TEXT PRIMARY KEY,
                user_id TEXT,
                gmail TEXT,
                access_token TEXT,
                refresh_token TEXT,
                expires_at INTEGER,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS useless_mails (
                msg_id TEXT PRIMARY KEY,
                subject TEXT,
                sender TEXT,
                attachments TEXT,
                seen_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_mails (
                msg_id TEXT PRIMARY KEY,
                gmail TEXT,
                category TEXT,
                processed_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS mail_analysis (
                msg_id TEXT PRIMARY KEY,
                gmail TEXT,
                category TEXT,
                importance_score INTEGER,
                summary TEXT,
                reason TEXT,
                suggested_action TEXT,
                deadline_detected TEXT,
                requires_reply INTEGER,
                confidence INTEGER,
                provider TEXT,
                analyzed_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_type TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        ensure_column(conn, "mail_analysis", "provider", "TEXT")


def ensure_column(conn, table, column, column_type):
    columns = [row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")


def save_user(chat_id, user_id):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO users (chat_id, user_id)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET user_id = excluded.user_id
        """, (str(chat_id), str(user_id)))


def upsert_token(token):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO oauth_tokens (
                chat_id, user_id, gmail, access_token, refresh_token, expires_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id) DO UPDATE SET
                user_id = excluded.user_id,
                gmail = excluded.gmail,
                access_token = excluded.access_token,
                refresh_token = COALESCE(excluded.refresh_token, oauth_tokens.refresh_token),
                expires_at = excluded.expires_at,
                updated_at = CURRENT_TIMESTAMP
        """, (
            str(token.get("chat_id")),
            token.get("user_id"),
            token.get("gmail"),
            token.get("access_token"),
            token.get("refresh_token"),
            token.get("expires_at"),
        ))


def get_accounts():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT chat_id, user_id, gmail, access_token, refresh_token, expires_at
            FROM oauth_tokens
            WHERE access_token IS NOT NULL AND refresh_token IS NOT NULL
        """).fetchall()
        return [dict(row) for row in rows]


def update_access_token(chat_id, access_token, expires_at):
    with get_conn() as conn:
        conn.execute("""
            UPDATE oauth_tokens
            SET access_token = ?, expires_at = ?, updated_at = CURRENT_TIMESTAMP
            WHERE chat_id = ?
        """, (access_token, expires_at, str(chat_id)))


def save_useless_mail(msg_id, subject, sender, attachments, seen_at):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO useless_mails (msg_id, subject, sender, attachments, seen_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(msg_id) DO NOTHING
        """, (msg_id, subject, sender, attachments, seen_at))


def get_useless_mails():
    with get_conn() as conn:
        rows = conn.execute("""
            SELECT subject, sender, attachments, seen_at
            FROM useless_mails
            ORDER BY seen_at ASC
        """).fetchall()
        return [dict(row) for row in rows]


def clear_useless_mails():
    with get_conn() as conn:
        conn.execute("DELETE FROM useless_mails")


def is_mail_processed(msg_id):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM processed_mails WHERE msg_id = ?",
            (msg_id,),
        ).fetchone()
        return row is not None


def mark_mail_processed(msg_id, gmail, category="preloaded"):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO processed_mails (msg_id, gmail, category)
            VALUES (?, ?, ?)
            ON CONFLICT(msg_id) DO NOTHING
        """, (msg_id, gmail, category))


def save_mail_analysis(msg_id, gmail, analysis):
    with get_conn() as conn:
        conn.execute("""
            INSERT INTO mail_analysis (
                msg_id, gmail, category, importance_score, summary, reason,
                suggested_action, deadline_detected, requires_reply, confidence, provider
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(msg_id) DO UPDATE SET
                gmail = excluded.gmail,
                category = excluded.category,
                importance_score = excluded.importance_score,
                summary = excluded.summary,
                reason = excluded.reason,
                suggested_action = excluded.suggested_action,
                deadline_detected = excluded.deadline_detected,
                requires_reply = excluded.requires_reply,
                confidence = excluded.confidence,
                provider = excluded.provider,
                analyzed_at = CURRENT_TIMESTAMP
        """, (
            msg_id,
            gmail,
            analysis.get("category"),
            analysis.get("importance_score"),
            analysis.get("summary"),
            analysis.get("reason"),
            analysis.get("suggested_action"),
            analysis.get("deadline_detected"),
            1 if analysis.get("requires_reply") else 0,
            analysis.get("confidence"),
            analysis.get("provider", analysis.get("source", "unknown")),
        ))


def get_mail_analysis(msg_id):
    with get_conn() as conn:
        row = conn.execute("""
            SELECT category, importance_score, summary, reason, suggested_action,
                   deadline_detected, requires_reply, confidence, provider
            FROM mail_analysis
            WHERE msg_id = ?
        """, (msg_id,)).fetchone()
        if not row:
            return None
        data = dict(row)
        data["requires_reply"] = bool(data["requires_reply"])
        return data


def clear_tokens():
    with get_conn() as conn:
        conn.execute("DELETE FROM oauth_tokens")


def clear_users():
    with get_conn() as conn:
        conn.execute("DELETE FROM users")


def clear_all():
    with get_conn() as conn:
        conn.execute("DELETE FROM useless_mails")
        conn.execute("DELETE FROM mail_analysis")
        conn.execute("DELETE FROM processed_mails")
        conn.execute("DELETE FROM user_rules")
        conn.execute("DELETE FROM oauth_tokens")
        conn.execute("DELETE FROM users")
