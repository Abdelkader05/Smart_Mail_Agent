"""
Reset de la base SQLite locale.

Usage:
    python -m scripts.reset_db            -> menu interactif
    python -m scripts.reset_db --all      -> supprime tout
    python -m scripts.reset_db --useless  -> vide useless_mails
    python -m scripts.reset_db --tokens   -> vide oauth_tokens
    python -m scripts.reset_db --users    -> vide users
    python -m scripts.reset_db --processed -> vide processed_mails
    python -m scripts.reset_db --analysis -> vide mail_analysis
"""

import sys

from src.db import clear_all, clear_tokens, clear_users, clear_useless_mails, get_conn, init_db


def clear_processed_mails():
    with get_conn() as conn:
        conn.execute("DELETE FROM processed_mails")


def clear_mail_analysis():
    with get_conn() as conn:
        conn.execute("DELETE FROM mail_analysis")


def interactive_menu():
    print("\n=== RESET BASE LOCALE ===")
    print("1. Vider useless_mails uniquement")
    print("2. Vider oauth_tokens uniquement")
    print("3. Vider users uniquement")
    print("4. Vider processed_mails uniquement")
    print("5. Vider mail_analysis uniquement")
    print("6. TOUT vider (users + tokens + useless + processed + analysis)")
    print("7. Annuler")
    print("=========================")
    return input("Choix (1-7) : ").strip()


def main():
    init_db()
    args = sys.argv[1:]

    if "--all" in args:
        confirm = input("Supprimer TOUTES les donnees locales ? (oui/non) : ").strip().lower()
        if confirm == "oui":
            clear_all()
            print("Base locale entierement videe.")
        else:
            print("Annule.")

    elif "--useless" in args:
        clear_useless_mails()
        print("useless_mails videe.")

    elif "--tokens" in args:
        clear_tokens()
        print("oauth_tokens videe.")

    elif "--users" in args:
        clear_users()
        print("users videe.")

    elif "--processed" in args:
        clear_processed_mails()
        print("processed_mails videe.")

    elif "--analysis" in args:
        clear_mail_analysis()
        print("mail_analysis videe.")

    else:
        choice = interactive_menu()
        if choice == "1":
            clear_useless_mails()
            print("useless_mails videe.")
        elif choice == "2":
            clear_tokens()
            print("oauth_tokens videe.")
        elif choice == "3":
            clear_users()
            print("users videe.")
        elif choice == "4":
            clear_processed_mails()
            print("processed_mails videe.")
        elif choice == "5":
            clear_mail_analysis()
            print("mail_analysis videe.")
        elif choice == "6":
            confirm = input("Supprimer TOUTES les donnees locales ? (oui/non) : ").strip().lower()
            if confirm == "oui":
                clear_all()
                print("Base locale entierement videe.")
            else:
                print("Annule.")
        else:
            print("Annule.")


if __name__ == "__main__":
    main()
