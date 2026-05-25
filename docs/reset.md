python -m scripts.reset_db              # menu interactif local
python -m scripts.reset_db --useless    # vide juste les mails inutiles locaux
python -m scripts.reset_db --tokens     # deconnecte les comptes Gmail en local
python -m scripts.reset_db --users      # supprime les utilisateurs Telegram locaux
python -m scripts.reset_db --processed  # vide l'historique des mails traites
python -m scripts.reset_db --analysis   # vide les analyses IA locales
python -m scripts.reset_db --all        # remet la DB locale a zero completement
