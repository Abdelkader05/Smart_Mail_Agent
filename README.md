# 📬 Smart Mail Agent

Système automatisé qui connecte un compte Gmail à Telegram pour analyser les emails non lus et envoyer des notifications intelligentes.

---

# ⚙️ Architecture générale

Le projet est composé de 3 modules principaux :

- `collector.py` → gestion Telegram + inscription utilisateur + OAuth
- `main.py` → analyse des emails Gmail + notifications
- `init_db.py` → création et gestion de la base SQLite
- `config.py` → configuration globale (API, OAuth, tokens)

---

# 🔁 Flow complet du système

## 1. Connexion utilisateur (Telegram → OAuth)

1. L’utilisateur envoie :
        /start user_id

2. Le bot :
- enregistre `chat_id + user_id`
- génère un lien OAuth Google
- envoie le lien à l’utilisateur

3. L’utilisateur autorise l’accès Gmail

4. Google redirige vers :
        /callback?code=...&state=user_id

5. Le serveur récupère :
- access_token
- refresh_token
- email Gmail connecté

6. Tout est stocké dans la base `oauth_tokens`

---

## 2. Analyse des emails (main.py)

Toutes les 30 secondes :

1. Récupère tous les comptes connectés
2. Récupère les emails NON LUS Gmail
3. Pour chaque email :
   - extrait sujet, expéditeur, pièces jointes
   - le classe aléatoirement :
     - urgent
     - moyen
     - inutile

---

# 📊 Logique de classification

## 🚨 URGENT
- Notification immédiate Telegram
- Contient :
  - sujet
  - expéditeur
  - pièces jointes
- Ajoute aussi les emails "inutiles" accumulés

---

## ⚠️ MOYEN
- Vérifie l’âge du mail
- Si ≥ 2 jours :
  - envoie notification Telegram
  - ajoute les "inutiles"
- Sinon : ignoré

---

## ❌ INUTILE
- Aucun message Telegram immédiat
- Stocké en base SQLite
- Contient :
  - sujet
  - expéditeur
  - pièces jointes
  - date de marquage

---

## 📦 INUTILES (historique)

Les mails inutiles sont :
- stockés dans `useless_mails`
- regroupés et envoyés lors d’un mail urgent ou moyen
- puis supprimés après envoi

---

# 🗄️ Base de données

## users
| champ | description |
|------|-------------|
| chat_id | ID Telegram |
| user_id | identifiant utilisateur |

---

## oauth_tokens
| champ | description |
|------|-------------|
| chat_id | utilisateur Telegram |
| user_id | ID interne |
| gmail | compte Gmail connecté |
| access_token | token API |
| refresh_token | token renouvellement |
| expires_in | durée token |

---

## useless_mails
| champ | description |
|------|-------------|
| msg_id | ID Gmail |
| subject | sujet |
| sender | expéditeur |
| attachments | pièces jointes |
| seen_at | date de marquage |

---

# 📡 API utilisées

- Telegram Bot API
- Gmail API (OAuth Google)
- SQLite (local storage)

---

# 🧠 Technologies

- Python
- Flask (OAuth callback)
- Requests
- SQLite
- Google OAuth2

---

# 🔐 Authentification

Le système utilise OAuth2 Google :

- scope : `gmail.readonly`
- accès sécurisé
- refresh token pour accès long terme

---

# ⏱️ Execution

### 1. Lancer le bot Telegram

python collector.py

### 2. Lancer le serveur OAuth

python serveur_auth.py

### 3. Lancer l’agent email

python main.py


---

# ⚠️ Limitations actuelles

- classification des emails est aléatoire (V1)
- pas encore d’IA réelle
- refresh token non géré automatiquement
- optimisation Gmail API limitée

---

# 🚀 Améliorations futures

- classification intelligente (IA ou scoring)
- résumé automatique des emails
- gestion multi-comptes Gmail
- dashboard web
- optimisation des requêtes Gmail

---

# 📌 Objectif du projet

Créer un agent intelligent capable de :

- surveiller une boîte Gmail
- détecter les emails importants
- notifier instantanément sur Telegram
- filtrer automatiquement le bruit