# 🚀 Smart Mail Agent — Évolution prévue (NON IMPLÉMENTÉE)

> ⚠️ **Statut** : Cette section décrit une architecture **validée et planifiée** mais **pas encore développée ni testée**.
> Elle est documentée ici comme feuille de route pour la prochaine phase du projet.

---

## 🎯 Objectif principal de l'évolution

Supprimer la dépendance au PC local pour le traitement des emails (`src/main.py` et `src/serveur_auth.py`), tout en restant **100% gratuit**, en déployant les composants serveurs sur **Render**.

---

## 🔴 Problèmes de l'architecture actuelle

| Problème | Détail |
|---|---|
| `src/main.py` tourne en local | Le PC doit rester allumé pour que le système fonctionne |
| `src/serveur_auth.py` tourne en local | Le callback OAuth n'est pas accessible depuis internet sans tunnel (ngrok, etc.) |
| SQLite en local | Non partageable entre services, non persistante sur Render |
| Refresh token non géré | Si le token expire, le système s'arrête silencieusement |
| Classification aléatoire | Pas de vraie logique d'analyse (V1 temporaire) |

---

## 🏗️ Nouvelle architecture cible (3 blocs)

```
┌─────────────────────────────────────────────────────────────┐
│                        RENDER (cloud)                       │
│                                                             │
│  ┌──────────────────────┐   ┌──────────────────────────┐   │
│  │  Web Service (Flask) │   │  Background Worker       │   │
│  │  serveur_auth.py     │   │  main.py                 │   │
│  │                      │   │                          │   │
│  │  - /callback OAuth   │   │  - Boucle emails (30s)   │   │
│  │  - /add_user (API)   │   │  - Gmail API             │   │
│  │  - /get_tokens (API) │   │  - Classification        │   │
│  │  - /clear_useless    │   │  - Notif Telegram        │   │
│  └──────────┬───────────┘   └────────────┬─────────────┘   │
│             │                            │                  │
│             └──────────┬─────────────────┘                  │
│                        │                                    │
│               ┌────────▼────────┐                           │
│               │  PostgreSQL     │                           │
│               │  (Render DB)    │                           │
│               │                 │                           │
│               │  - users        │                           │
│               │  - oauth_tokens │                           │
│               │  - useless_mails│                           │
│               └─────────────────┘                           │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────┐
│       PC LOCAL              │
│                             │
│  collector.py               │
│  - Bot Telegram             │
│  - /start → enregistrement  │
│  - Génère lien OAuth        │
│  - Appelle API Render       │
│    (plus SQLite local)      │
└─────────────────────────────┘
```

---

## 📦 Détail des changements fichier par fichier

### 1. `src/serveur_auth.py` → déplacé sur Render (Web Service)

**Avant :** tourne en local, callback OAuth inaccessible sans tunnel.

**Après :** hébergé sur Render, accessible via URL publique :
```
https://ton-app.onrender.com/callback
```

**Changements à apporter :**
- Remplacer la connexion SQLite par PostgreSQL (`psycopg2`)
- Stocker `access_token`, `refresh_token`, `gmail`, `expires_at` en DB distante
- Ajouter des routes API internes (voir section dédiée ci-dessous)
- Lire `DATABASE_URL` depuis les variables d'environnement Render

---

### 2. `src/main.py` → déplacé sur Render (Background Worker)

**Avant :** tourne en local dans un terminal, dépend du PC.

**Après :** tourne en continu sur Render, indépendamment du PC.

**Changements à apporter :**
- Connexion PostgreSQL au lieu de SQLite
- Ajout d'une gestion robuste des erreurs (`try/except` sur chaque étape)
- Ajout de la gestion automatique du `refresh_token` (voir section dédiée)
- Boucle `while True` avec `sleep(30)` inchangée dans sa logique

**Structure de la boucle (inchangée dans l'intention) :**
```
while True:
    récupérer tous les comptes depuis PostgreSQL
    pour chaque compte :
        vérifier si access_token expiré → refresh si besoin
        récupérer emails non lus Gmail
        pour chaque email :
            classifier (urgent / moyen / inutile)
            envoyer notification Telegram si nécessaire
            stocker inutiles en DB
    sleep(30s)
```

---

### 3. `src/collector.py` → reste en local, mais adapté

**Avant :** écrivait directement dans SQLite local.

**Après :** communique avec l'API Flask hébergée sur Render.

**Changements à apporter :**
- Supprimer toute import/utilisation de SQLite
- Remplacer les écritures en DB par des appels HTTP `POST` vers l'API Render

**Exemple de changement :**
```python
# AVANT
cursor.execute("INSERT INTO users VALUES (?, ?)", (chat_id, user_id))

# APRÈS
requests.post("https://ton-app.onrender.com/add_user", json={
    "chat_id": chat_id,
    "user_id": user_id
})
```

---

### 4. `scripts/init_db.py` → migration SQLite → PostgreSQL

**Avant :** crée des tables SQLite locales.

**Après :** crée des tables PostgreSQL sur Render.

**Dépendance à ajouter :**
```bash
pip install psycopg2-binary
```

**Connexion :**
```python
import psycopg2
import os

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
cursor = conn.cursor()
```

**Changements de schéma :**

| Champ | Avant (SQLite) | Après (PostgreSQL) |
|---|---|---|
| `expires_in` | durée en secondes | → remplacé par `expires_at` (timestamp UNIX réel) |
| Types | TEXT, INTEGER | identiques en PostgreSQL |

**Nouveau schéma SQL complet :**
```sql
CREATE TABLE IF NOT EXISTS users (
    chat_id TEXT PRIMARY KEY,
    user_id TEXT
);

CREATE TABLE IF NOT EXISTS oauth_tokens (
    chat_id TEXT,
    user_id TEXT,
    gmail TEXT,
    access_token TEXT,
    refresh_token TEXT,
    expires_at BIGINT
);

CREATE TABLE IF NOT EXISTS useless_mails (
    msg_id TEXT,
    subject TEXT,
    sender TEXT,
    attachments TEXT,
    seen_at TIMESTAMP
);
```

---

### 5. `config.py` → variables d'environnement

**Avant :** constantes écrites en dur dans le fichier.

**Après :** toutes les valeurs sensibles lues depuis l'environnement.

**Variables à définir sur Render :**
```
DATABASE_URL=postgres://user:password@host:port/dbname
TELEGRAM_TOKEN=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
REDIRECT_URI=https://ton-app.onrender.com/callback
```

---

## 🔌 Nouvelles routes API Flask (à créer dans `src/serveur_auth.py`)

Ces routes permettent à `src/collector.py` (local) d'interagir avec la DB distante sans accès direct.

| Route | Méthode | Rôle |
|---|---|---|
| `/callback` | GET | Callback OAuth Google (déjà existant) |
| `/add_user` | POST | Enregistrer un nouvel utilisateur Telegram |
| `/get_tokens` | GET | Récupérer tous les tokens OAuth actifs |
| `/clear_useless` | POST | Supprimer les mails inutiles après envoi |

**Exemple payload `/add_user` :**
```json
{
  "chat_id": "123456789",
  "user_id": "mon_user"
}
```

---

## 🔄 Gestion automatique du refresh_token (à implémenter)

C'est un point **critique** actuellement manquant. Sans ça, le système s'arrête dès l'expiration du token (généralement 1h).

**Logique à ajouter dans `src/main.py` :**
```python
import time

def is_token_expired(expires_at):
    return time.time() > expires_at

def refresh_access_token(refresh_token):
    response = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token"
    })
    data = response.json()
    return data["access_token"], time.time() + data["expires_in"]

# Dans la boucle principale :
if is_token_expired(account["expires_at"]):
    new_token, new_expires = refresh_access_token(account["refresh_token"])
    # Mettre à jour en DB PostgreSQL
```

---

## 🗄️ Pourquoi abandonner SQLite

| Critère | SQLite local | PostgreSQL Render |
|---|---|---|
| Partageable entre services | ❌ Non | ✅ Oui |
| Persistant sur Render | ❌ Reset possible | ✅ Oui |
| Accessible depuis le PC | ✅ Direct | ✅ Via API |
| Gratuit | ✅ | ✅ (plan gratuit Render) |
| Complexité | Faible | Moyenne |

SQLite ne peut pas être partagé entre `src/serveur_auth.py` et `src/main.py` si ces deux services tournent sur Render dans des environnements isolés. Et le filesystem de Render est éphémère (reset à chaque redémarrage), donc les données seraient perdues.

---

## ☁️ Déploiement Render prévu

### Service 1 : Web Service (Flask)
- **Fichier :** `src/serveur_auth.py`
- **Start command :** `python -m src.serveur_auth`
- **Port :** 5000 (ou variable `$PORT` de Render)
- **URL publique :** `https://ton-app.onrender.com`

### Service 2 : Background Worker
- **Fichier :** `src/main.py`
- **Start command :** `python -m src.main`
- **Pas de port exposé** (worker pur)

### Base de données
- **Type :** PostgreSQL
- **Plan :** Gratuit Render
- **Récupérer :** `DATABASE_URL` depuis le dashboard Render

### Fichiers de déploiement à créer
```
requirements.txt     ← liste toutes les dépendances Python
start.sh             ← (optionnel) script de démarrage
```

**`requirements.txt` minimum :**
```
requests
flask
psycopg2-binary
google-auth
google-auth-oauthlib
google-api-python-client
python-telegram-bot
```

---

## ⚠️ Contraintes Render (plan gratuit)

- Le Web Service peut se mettre en veille si inactif (cold start ~30s)
- Le Background Worker peut redémarrer sans préavis
- CPU et RAM limités
- Pas garanti 24/7 mais suffisant pour quelques utilisateurs
- La DB PostgreSQL gratuite a une limite de stockage (~1 Go)

---

## 🔁 Nouveau flow complet après implémentation

```
1. Utilisateur envoie /start sur Telegram
        ↓
2. collector.py (PC) génère lien OAuth
   + appelle POST /add_user sur Render
        ↓
3. Utilisateur clique le lien OAuth Google
        ↓
4. Google redirige vers https://ton-app.onrender.com/callback
        ↓
5. serveur_auth.py (Render) récupère tokens
   + stocke dans PostgreSQL (Render)
        ↓
6. main.py (Render, boucle continue) :
   - lit oauth_tokens depuis PostgreSQL
   - vérifie/refresh les tokens si expirés
   - interroge Gmail API
   - classe les emails
   - envoie notifications Telegram
   - stocke les inutiles en DB
        ↓
7. Tout fonctionne sans que le PC soit allumé ✅
```

---

## 📋 Ordre d'implémentation recommandé

1. **Créer la DB PostgreSQL sur Render** → récupérer `DATABASE_URL`
2. **Adapter `scripts/init_db.py`** → réécrire en PostgreSQL, créer les tables
3. **Adapter `src/serveur_auth.py`** → PostgreSQL + routes API
4. **Déployer Flask sur Render** (Web Service)
5. **Adapter `src/main.py`** → PostgreSQL + gestion refresh_token
6. **Déployer `src/main.py` sur Render** (Background Worker)
7. **Adapter `src/collector.py`** → remplacer SQLite par appels API
8. **Tester le flow complet** de bout en bout

---

## ✅ Résumé des avantages attendus

- Système autonome, fonctionne sans le PC
- Notifications Telegram continues 24/7
- Base de données unique et cohérente
- Tokens OAuth gérés automatiquement
- Architecture plus proche d'un vrai SaaS
- Toujours 100% gratuit

## ❌ Points de vigilance

- Plus de composants = plus de surface de bugs
- Render gratuit = redémarrages possibles (prévoir logs clairs)
- La DB PostgreSQL gratuite Render peut être supprimée après 90 jours d'inactivité
- L'API interne Flask n'a pas encore de sécurité (à sécuriser avec un token secret)
