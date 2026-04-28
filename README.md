# Smart_Mail_Agent
Agent automatique qui analyse plusieurs boîtes Gmail, détecte les emails importants et envoie des notifications intelligentes sur Telegram, tout en évitant le spam.

🚀 Objectif

Gagner du temps en automatisant la gestion des emails :

Lire plusieurs comptes Gmail
Identifier les mails importants
Ignorer les emails inutiles
Regrouper les informations pertinentes
Envoyer des notifications utiles (pas trop fréquentes)
⚙️ Fonctionnalités
📥 Lecture multi-comptes
Support de plusieurs adresses Gmail
Ajout / suppression facile via fichier de configuration
🧠 Analyse intelligente
Classification des emails en :
IMPORTANT
MOYEN
INUTILE
Basée sur une IA externe (ex : Mistral AI ou Anthropic)
🔕 Anti-spam intelligent
Notification immédiate uniquement pour les mails importants
Regroupement des mails moyens en résumé
Aucun message pour les emails inutiles
📊 Résumé automatique

Exemple :

📊 Résumé (2 jours)

IMPORTANT:
- Convocation entretien
- Facture EDF

MOYEN:
- 3 mails administratifs

INUTILE:
- 12 promotions ignorées
🧾 Gestion automatique
Marque les mails inutiles comme lus
Stocke l’historique des emails
Évite les doublons
🧠 Mémoire (contexte utilisateur)
Conservation des anciens emails importants
Amélioration progressive de la classification
🏗️ Architecture
GitHub Actions (toutes les 4h)
        ↓
Script Python
        ↓
Lecture Gmail (IMAP)
        ↓
Analyse IA
        ↓
Base de données (SQLite)
        ↓
Notification Telegram
🛠️ Technologies utilisées
Python
IMAP (Gmail)
GitHub Actions (automatisation)
SQLite (stockage)
Telegram (notifications)
API IA (au choix) :
Mistral AI
Anthropic
OpenAI
📁 Structure du projet
project/
│
├── main.py
├── accounts.json
├── database.db
│
├── gmail/
├── ai/
├── memory/
├── notifier/
⚡ Installation
1. Cloner le projet
git clone <repo>
cd project
2. Installer les dépendances
pip install -r requirements.txt
3. Configurer les comptes Gmail

Créer accounts.json :

{
  "accounts": [
    {
      "email": "example@gmail.com",
      "app_password": "xxxx",
      "active": true
    }
  ]
}
4. Configurer Telegram
Créer un bot avec BotFather
Récupérer :
TOKEN
CHAT_ID
5. Configurer l’IA

Ajouter ta clé API dans le code ou via variables d’environnement.

🔁 Automatisation

Le script est exécuté automatiquement via GitHub Actions toutes les 4 heures.

📈 Évolutions prévues
Réponse automatique aux emails
Priorisation avancée
Dashboard web
Apprentissage personnalisé
Support d’autres services mail
⚠️ Limites
Dépend des APIs (IA, Gmail)
Risque d’erreurs de classification
Nécessite une configuration initiale
📌 Conclusion

Ce projet permet de transformer la gestion des emails en un système automatisé, intelligent et non intrusif, en utilisant des outils simples et peu coûteux.
