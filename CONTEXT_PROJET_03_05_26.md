# 📬 Smart Mail Agent — Contexte complet du projet

> Dernière mise à jour : Mai 2026  
> Document de référence pour reprendre le projet à tout moment.

---

# 🎯 Objectif du projet

Créer un agent intelligent capable de :
- Surveiller une boîte Gmail
- Détecter les emails importants
- Notifier instantanément sur Telegram
- Filtrer automatiquement le bruit

---

# ✅ CE QUI EST FAIT ET FONCTIONNE

## 1. Authentification OAuth Google

- L'utilisateur envoie `/start user_id` au bot Telegram
- `collector.py` enregistre le `chat_id` + `user_id` via API HTTP vers Render
- Un lien OAuth Google est généré et envoyé à l'utilisateur
- L'utilisateur autorise l'accès Gmail
- Google redirige vers `https://smart-mail-server.onrender.com/callback`
- `serveur_auth.py` (sur Render) récupère `access_token`, `refresh_token`, email Gmail
- Les tokens sont stockés dans PostgreSQL sur Render
- Une notification Telegram confirme la connexion : `✅ Gmail connecté : email@gmail.com`

**Status : 100% fonctionnel ✅**

---

## 2. Base de données PostgreSQL sur Render

Migré depuis SQLite local vers PostgreSQL cloud.

### Tables créées :

**`users`**
| Champ | Type | Description |
|---|---|---|
| chat_id | TEXT (PK) | ID Telegram de l'utilisateur |
| user_id | TEXT | Identifiant choisi par l'utilisateur |

**`oauth_tokens`**
| Champ | Type | Description |
|---|---|---|
| chat_id | TEXT | ID Telegram |
| user_id | TEXT | Identifiant utilisateur |
| gmail | TEXT | Adresse Gmail connectée |
| access_token | TEXT | Token d'accès Gmail |
| refresh_token | TEXT | Token de renouvellement |
| expires_at | BIGINT | Timestamp UNIX d'expiration du token |
| created_at | TIMESTAMP | Date de création |

**`useless_mails`**
| Champ | Type | Description |
|---|---|---|
| msg_id | TEXT (PK) | ID Gmail du message |
| subject | TEXT | Sujet de l'email |
| sender | TEXT | Expéditeur |
| attachments | TEXT | Pièces jointes (séparées par virgule) |
| seen_at | TEXT | Date de marquage |

**Status : 100% fonctionnel ✅**

---

## 3. Serveur OAuth Flask sur Render (Web Service)

- URL publique : `https://smart-mail-server.onrender.com`
- Hébergé sur Render en tant que Web Service (plan gratuit)
- Tourne 24/7 (avec cold start possible après inactivité)

### Routes disponibles :

| Route | Méthode | Rôle |
|---|---|---|
| `/callback` | GET | Callback OAuth Google |
| `/add_user` | POST | Enregistrer un utilisateur Telegram |
| `/get_tokens` | GET | Récupérer tous les tokens OAuth |
| `/update_token` | POST | Mettre à jour un access_token après refresh |
| `/save_useless` | POST | Sauvegarder un mail inutile |
| `/get_useless` | GET | Récupérer les mails inutiles |
| `/clear_useless` | POST | Supprimer tous les mails inutiles |

**Status : 100% fonctionnel ✅**

---

## 4. Gestion automatique du refresh_token

- Implémentée dans `main.py`
- Le token est rafraîchi automatiquement s'il expire dans moins de 5 minutes
- Appel à `https://oauth2.googleapis.com/token` avec `grant_type=refresh_token`
- Le nouveau `access_token` et `expires_at` sont mis à jour en DB

**Status : 100% fonctionnel ✅**

---

## 5. Analyse des emails et notifications Telegram

Boucle toutes les 30 secondes :

1. Récupère tous les comptes depuis PostgreSQL
2. Vérifie/rafraîchit les tokens si nécessaire
3. Récupère les emails non lus via Gmail API
4. Pour chaque email : extrait sujet, expéditeur, pièces jointes
5. Classe l'email (voir classification ci-dessous)
6. Envoie les notifications Telegram selon la catégorie

### Logique de classification actuelle (V1 - ALÉATOIRE) :

> ⚠️ La classification est encore aléatoire (`random.choice`). Ce n'est pas une vraie IA.

| Catégorie | Comportement |
|---|---|
| 🚨 URGENT | Notification immédiate + bloc des mails inutiles accumulés |
| ⚠️ MOYEN | Notification si le mail a plus de 2 jours + bloc inutiles |
| ❌ INUTILE | Stocké en DB, envoyé groupé lors du prochain urgent/moyen |

**Status : Fonctionnel mais classification aléatoire ⚠️**

---

## 6. Variables d'environnement

Toutes les valeurs sensibles sont dans un fichier `.env` local (non commité sur GitHub).

```env
TELEGRAM_TOKEN=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
REDIRECT_URI=https://smart-mail-server.onrender.com/callback
SERVER_URL=https://smart-mail-server.onrender.com
DATABASE_URL=postgresql://...@dpg-....frankfurt-postgres.render.com/smart_mail_db
```

`config.py` utilise `python-dotenv` + `os.getenv()` pour lire ces valeurs.  
Sur Render, les variables sont définies directement dans le dashboard (pas de `.env`).

**Status : 100% fonctionnel ✅**

---

# 🏗️ Architecture actuelle

```
┌─────────────────────────────────────────────────────────────┐
│                        RENDER (cloud)                        │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Web Service — serveur_auth.py                       │   │
│  │  https://smart-mail-server.onrender.com              │   │
│  │                                                      │   │
│  │  /callback      → OAuth Google                       │   │
│  │  /add_user      → enregistrement utilisateur         │   │
│  │  /get_tokens    → lecture tokens                     │   │
│  │  /update_token  → refresh token                      │   │
│  │  /save_useless  → stockage mail inutile              │   │
│  │  /get_useless   → lecture mails inutiles             │   │
│  │  /clear_useless → suppression mails inutiles         │   │
│  └──────────────────────────┬───────────────────────────┘   │
│                             │                               │
│               ┌─────────────▼──────────────┐               │
│               │  PostgreSQL (Render DB)     │               │
│               │  users                     │               │
│               │  oauth_tokens              │               │
│               │  useless_mails             │               │
│               └────────────────────────────┘               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    PC LOCAL (doit être allumé)              │
│                                                             │
│  collector.py                    main.py                    │
│  - Bot Telegram                  - Boucle 30s              │
│  - /start → API Render           - Gmail API               │
│  - Génère lien OAuth             - Classification          │
│                                  - Notif Telegram          │
│                                  - Refresh token           │
│                                  - PostgreSQL direct       │
└─────────────────────────────────────────────────────────────┘
```

---

# ❌ CE QUI N'EST PAS ENCORE FAIT

## 1. `main.py` en cloud (24/7 sans PC)

**Problème rencontré :**
- Render Background Worker → plus de plan gratuit
- PythonAnywhere gratuit → bloque les connexions PostgreSQL ET les requêtes HTTPS externes
- Railway → non testé

**Solution identifiée (non implémentée) :**
- Oracle Cloud Free Tier : VPS gratuit à vie, aucune restriction réseau
- Alternative : héberger `main.py` sur Render en payant (~$7/mois)

**Status : ❌ Non implémenté — main.py tourne en local**

---

## 2. Classification intelligente des emails (V2)

**Problème actuel :**
La classification est 100% aléatoire (`random.choice(["urgent", "moyen", "inutile"])`).

**Solution prévue (non implémentée) :**
Remplacer le random par une vraie logique, par exemple :

Option A — Scoring par règles :
- Mots-clés dans le sujet : "urgent", "ASAP", "important" → urgent
- Expéditeurs connus/inconnus → pondération
- Présence de pièces jointes → boost score
- Heure d'envoi → pondération

Option B — Classification via API Claude :
- Envoyer sujet + expéditeur à Claude
- Récupérer la catégorie + un résumé en une phrase
- Coût : ~$0.001 par email

**Status : ❌ Non implémenté — classification aléatoire**

---

## 3. Résumé automatique des emails

**Objectif :**
Au lieu d'envoyer juste sujet + expéditeur, envoyer un résumé du contenu de l'email en 1-2 phrases.

**Ce qu'il faudrait faire :**
- Extraire le corps de l'email (actuellement seuls sujet/expéditeur/PJ sont extraits)
- Envoyer le corps à l'API Claude
- Inclure le résumé dans la notification Telegram

**Status : ❌ Non implémenté**

---

## 4. Déduplication des emails

**Problème actuel :**
Si un email non lu est traité à chaque cycle de 30 secondes, il peut générer plusieurs notifications pour le même email.

**Solution prévue :**
- Ajouter une table `processed_mails` en DB
- Vérifier si `msg_id` a déjà été traité avant d'envoyer une notification
- Ou utiliser le label Gmail `UNREAD` et le retirer après traitement

**Status : ❌ Non implémenté — risque de doublons**

---

## 5. Sécurité de l'API interne

**Problème actuel :**
Les routes `/add_user`, `/get_tokens`, etc. sont publiques — n'importe qui connaissant l'URL peut les appeler.

**Solution prévue :**
Ajouter un header secret partagé :
```python
# Dans chaque route Flask
token = request.headers.get("X-API-Key")
if token != os.getenv("API_SECRET"):
    return jsonify({"error": "Unauthorized"}), 401
```

**Status : ❌ Non implémenté — API non sécurisée**

---

## 6. Gestion multi-comptes Gmail

**Objectif :**
Permettre à un même utilisateur Telegram de connecter plusieurs comptes Gmail.

**Status : ❌ Non prévu dans l'architecture actuelle**

---

## 7. Dashboard web

**Objectif :**
Interface web pour voir les emails traités, les statistiques, gérer les comptes.

**Status : ❌ Non prévu**

---

# 📁 Structure des fichiers

```
Smart_Mail_Agent/
├── main.py            → Boucle principale (local, accès PostgreSQL direct)
├── collector.py       → Bot Telegram (local, appels API vers Render)
├── serveur_auth.py    → Serveur Flask OAuth + API interne (Render)
├── config.py          → Config globale (os.getenv + dotenv)
├── init_db.py         → Création tables PostgreSQL
├── requirements.txt   → Dépendances Python
├── .env               → Variables sensibles (NON commité sur GitHub)
└── .gitignore         → Contient .env
```

---

# 🔧 Technologies utilisées

| Technologie | Rôle |
|---|---|
| Python 3 | Langage principal |
| Flask | Serveur OAuth + API interne |
| psycopg2 | Connexion PostgreSQL |
| python-dotenv | Lecture fichier .env |
| Telegram Bot API | Notifications utilisateur |
| Gmail API (OAuth2) | Lecture emails |
| PostgreSQL (Render) | Base de données cloud |
| Render Web Service | Hébergement serveur Flask |
| Google OAuth2 | Authentification Gmail |

---

# 🚀 Comment lancer le projet

### 1. Lancer le bot Telegram (PC)
```bash
python collector.py
```

### 2. Lancer l'agent email (PC)
```bash
python main.py
```

### 3. Le serveur OAuth tourne automatiquement sur Render
```
https://smart-mail-server.onrender.com
```

---

# ⚠️ Limitations connues

| Limitation | Impact | Solution |
|---|---|---|
| `main.py` tourne en local | Système s'arrête si PC éteint | Oracle Cloud Free Tier |
| Classification aléatoire | Notifications non pertinentes | Scoring ou API Claude |
| Pas de déduplication | Doublons possibles | Table `processed_mails` |
| API interne non sécurisée | Routes publiques accessibles | Header `X-API-Key` |
| Render cold start | Callback OAuth peut être lent | Normal sur plan gratuit |
| DB Render gratuite | Reset possible après 90j inactivité | Utiliser régulièrement |

---

# 📋 Prochaines étapes recommandées (par priorité)

1. **Déduplication** — éviter les doublons de notifications (rapide à implémenter)
2. **Sécuriser l'API** — ajouter `X-API-Key` sur les routes Flask
3. **Classification intelligente** — remplacer le random par des règles ou API Claude
4. **Résumé des emails** — extraire le corps + résumer avec Claude
5. **Hébergement `main.py`** — Oracle Cloud Free Tier pour 24/7
