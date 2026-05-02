import psycopg2

DATABASE_URL = "postgresql://smart_mail_db_user:zdIcyzdx0KEqGUqDZU1HZ69lc0n2MmsI@dpg-d7r5ug9kh4rs73eldvjg-a.frankfurt-postgres.render.com/smart_mail_db"

print("Connexion...")
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    chat_id TEXT PRIMARY KEY,
    user_id TEXT
)
""")

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

cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
tables = cursor.fetchall()

cursor.close()
conn.close()

print("Connexion réussie !")
print("Tables créées :")
for t in tables:
    print(f"  - {t[0]}")