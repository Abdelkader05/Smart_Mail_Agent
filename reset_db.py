"""
reset_db.py — Vide les données via l'API Flask sur Render.

Usage :
    python reset_db.py            → Menu interactif
    python reset_db.py --all      → Supprime TOUT (users + tokens + useless_mails)
    python reset_db.py --useless  → Vide uniquement la table useless_mails
    python reset_db.py --tokens   → Vide uniquement les tokens OAuth
    python reset_db.py --users    → Vide uniquement les utilisateurs Telegram
"""

import sys
import requests
from config import SERVER_URL

# =========================
# APPELS API
# =========================

def clear_useless_mails():
    r = requests.post(f"{SERVER_URL}/clear_useless", timeout=10)
    if r.status_code == 200:
        print("✅ useless_mails vidée")
    else:
        print(f"❌ Erreur useless_mails : {r.status_code} {r.text}")

def clear_tokens():
    r = requests.post(f"{SERVER_URL}/clear_tokens", timeout=10)
    if r.status_code == 200:
        print("✅ oauth_tokens vidée")
    else:
        print(f"❌ Erreur oauth_tokens : {r.status_code} {r.text}")

def clear_users():
    r = requests.post(f"{SERVER_URL}/clear_users", timeout=10)
    if r.status_code == 200:
        print("✅ users vidée")
    else:
        print(f"❌ Erreur users : {r.status_code} {r.text}")

def clear_all():
    clear_useless_mails()
    clear_tokens()
    clear_users()
    print("🗑️  Base de données entièrement vidée.")

# =========================
# MENU INTERACTIF
# =========================

def interactive_menu():
    print("\n=== RESET BASE DE DONNÉES ===")
    print("1. Vider useless_mails uniquement")
    print("2. Vider oauth_tokens uniquement")
    print("3. Vider users uniquement")
    print("4. TOUT vider (users + tokens + useless_mails)")
    print("5. Annuler")
    print("=============================")
    return input("Choix (1-5) : ").strip()

# =========================
# MAIN
# =========================

def main():
    args = sys.argv[1:]

    if "--all" in args:
        confirm = input("⚠️  Supprimer TOUTES les données ? (oui/non) : ").strip().lower()
        if confirm == "oui":
            clear_all()
        else:
            print("Annulé.")

    elif "--useless" in args:
        clear_useless_mails()

    elif "--tokens" in args:
        clear_tokens()

    elif "--users" in args:
        clear_users()

    else:
        choice = interactive_menu()
        if choice == "1":
            clear_useless_mails()
        elif choice == "2":
            clear_tokens()
        elif choice == "3":
            clear_users()
        elif choice == "4":
            confirm = input("⚠️  Supprimer TOUTES les données ? (oui/non) : ").strip().lower()
            if confirm == "oui":
                clear_all()
            else:
                print("Annulé.")
        else:
            print("Annulé.")

if __name__ == "__main__":
    main()
