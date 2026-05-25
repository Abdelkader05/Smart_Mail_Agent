# Smart Mail Agent - Contexte projet a jour

Derniere mise a jour: 2026-05-25

Ce document decrit l'etat reel du projet apres les tests locaux. Les anciens fichiers de contexte dans `docs/` sont conserves comme historique, mais ils mentionnent encore des etapes PostgreSQL/Render ou une classification aleatoire qui ne representent plus l'architecture actuelle.

## Objectif

Smart Mail Agent est un assistant email personnel qui connecte Gmail a Telegram pour:

- surveiller les emails non lus;
- analyser leur contenu;
- classer les emails en `urgent`, `moyen` ou `inutile`;
- resumer les emails importants;
- expliquer le classement;
- proposer une action utile;
- notifier l'utilisateur sur Telegram;
- filtrer et regrouper les emails inutiles.

## Architecture actuelle

Architecture hybride simple:

- Local: bot Telegram, agent Gmail, base SQLite, scripts init/reset.
- Render: serveur Flask OAuth uniquement, utilise pour le callback public Google.
- IA: configurable avec OpenAI cloud, Ollama local, endpoint local compatible OpenAI, ou fallback par regles.

Render ne contient pas la base principale et ne notifie pas Telegram.

## Structure des fichiers

```text
Smart_Mail_Agent/
+-- src/
|   +-- collector.py        # Bot Telegram local
|   +-- main.py             # Agent Gmail local
|   +-- serveur_auth.py     # Pont OAuth Render
|   +-- config.py           # Config env, secrets, state OAuth signe
|   +-- db.py               # Acces SQLite local
|   +-- pending_tokens.py   # File temporaire JSON cote Render
|   +-- ai_provider.py      # Interface IA: openai, ollama, local_openai, rules
|   +-- ai_analyzer.py      # Alias compatible vers ai_provider
|   +-- classifier.py       # Fallback par regles
+-- scripts/
|   +-- init_db.py          # Initialise/migre SQLite
|   +-- reset_db.py         # Reset partiel/total SQLite
+-- docs/                   # Documentation et contextes
+-- data/                   # Bases locales et archive SQLite
+-- README.md               # Documentation principale a jour
+-- README_v2.md            # Redirection vers README.md
+-- requirements.txt
```

## Responsabilites des modules

`src/collector.py`

- Ecoute Telegram avec `getUpdates`.
- Gere `/start user_id`.
- Enregistre `chat_id + user_id` en SQLite locale.
- Genere une URL OAuth Google avec state signe.
- Envoie le lien OAuth a l'utilisateur.

`src/main.py`

- Synchronise les tokens OAuth en attente depuis Render.
- Ack les tokens seulement apres sauvegarde locale.
- Rafraichit les access tokens Gmail.
- Recupere les emails Gmail non lus.
- Extrait sujet, expediteur, date, snippet, corps texte/html nettoye et pieces jointes.
- Appelle `analyze_email_with_ai(email_data)`.
- Stocke l'analyse dans SQLite.
- Deduplique les emails via `processed_mails`.
- Envoie les notifications Telegram.

`src/serveur_auth.py`

- Recoit `/callback` depuis Google.
- Verifie le state OAuth signe.
- Echange le code OAuth contre les tokens Google.
- Recupere l'adresse Gmail.
- Stocke temporairement les tokens dans `PENDING_TOKENS_PATH`.
- Expose `/pending_tokens` et `/ack_tokens` pour le local.

`src/db.py`

- Gere la base SQLite locale.
- Cree les tables.
- Stocke utilisateurs, tokens, mails inutiles, mails traites, analyses IA et futures regles utilisateur.

`src/pending_tokens.py`

- Gere le stockage temporaire JSON cote Render.
- Ajoute un `id` aux tokens en attente.
- Permet la lecture sans suppression.
- Supprime seulement les tokens ack par le local.

`src/ai_provider.py`

- Interface stable: `analyze_email_with_ai(email_data) -> dict`.
- Supporte `openai`, `ollama`, `local_openai`, `rules`.
- Normalise les reponses.
- Fallback automatique vers les regles.

`src/classifier.py`

- Fallback par regles.
- Score selon mots-cles urgents, expediteurs importants, pieces jointes, anciennete et signaux faibles.

## Flow Telegram -> OAuth -> Gmail -> Telegram

1. L'utilisateur envoie `/start user_id` au bot Telegram local.
2. `collector.py` enregistre l'utilisateur dans SQLite.
3. `collector.py` genere une URL OAuth Google avec un state HMAC signe.
4. L'utilisateur autorise Gmail.
5. Google redirige vers Render `/callback`.
6. `serveur_auth.py` verifie le state, recupere les tokens Google et les stocke temporairement.
7. `main.py` appelle `/pending_tokens`.
8. `main.py` sauvegarde les tokens en SQLite.
9. `main.py` appelle `/ack_tokens` pour supprimer les tokens temporaires cote Render.
10. `main.py` notifie Telegram: Gmail connecte.
11. `main.py` surveille Gmail, analyse les emails et notifie selon la categorie.

## Base SQLite locale

Base active par defaut: `data/smart_mail_agent.db`.

Tables:

- `users`: `chat_id`, `user_id`.
- `oauth_tokens`: compte Gmail, access token, refresh token, expiration.
- `useless_mails`: emails classes inutiles a regrouper plus tard.
- `processed_mails`: deduplication persistante des emails vus/traites.
- `mail_analysis`: resultat IA ou fallback par email.
- `user_rules`: structure prevue pour l'apprentissage utilisateur.

`data/smart_mail_agent.db` est ignore par Git. `data/database.db` est l'ancienne base archivee.

## Serveur Render

Routes:

| Route | Role |
|---|---|
| `GET /health` | Statut simple et nombre de tokens en attente. |
| `GET /callback` | Callback OAuth Google avec state signe. |
| `POST /register_user` | Compatibilite/dev; le state signe contient deja les infos utiles. |
| `GET /pending_tokens` | Retourne les tokens non ack. Protege par `API_SECRET`. |
| `POST /ack_tokens` | Supprime les tokens ack apres sauvegarde locale. Protege par `API_SECRET`. |

Limites:

- `PENDING_TOKENS_PATH` est un fichier temporaire. Sur Render, le filesystem peut etre ephemere selon le plan et les redemarrages.
- Si Render redemarre avant que le local recupere un token, il peut etre necessaire de refaire `/start`.
- Le serveur Render ne doit pas contenir la base principale.

## Securite

- `API_SECRET` est obligatoire en production/Render.
- En dev local, `API_SECRET` peut etre vide, mais un warning explicite est affiche.
- `STATE_SECRET` signe le state OAuth; s'il est absent, il reprend `API_SECRET`.
- Le callback refuse un state manquant, modifie ou expire.
- Les routes sensibles `/pending_tokens` et `/ack_tokens` utilisent `X-API-Key`.
- Les tokens OAuth, refresh tokens et cles API ne doivent pas etre logges.

## Deduplication persistante

La deduplication utilise:

- cache memoire `processed_ids` pour limiter les requetes pendant l'execution;
- table SQLite `processed_mails` pour survivre aux redemarrages.

Au demarrage d'un compte, les emails deja non lus sont precharges comme `preloaded`, sans notification.

## Analyse IA et fallback

Interface unique:

```python
analyze_email_with_ai(email_data)
```

Retour normalise:

```python
{
    "category": "urgent|moyen|inutile",
    "importance_score": 0,
    "summary": "...",
    "reason": "...",
    "suggested_action": "...",
    "deadline_detected": None,
    "requires_reply": False,
    "confidence": 0,
    "provider": "openai|ollama|local_openai|rules",
}
```

Providers:

- `openai`: OpenAI cloud via SDK officiel.
- `ollama`: endpoint local `/api/chat`.
- `local_openai`: endpoint local compatible OpenAI `/chat/completions`.
- `rules`: classification locale par regles.

Fallback vers `rules` si:

- `AI_ENABLED=false`;
- provider inconnu;
- cle manquante;
- timeout;
- API indisponible;
- JSON invalide;
- reponse incomplete.

Le contenu envoye a l'IA est limite par `AI_MAX_EMAIL_CHARS`.

## Variables `.env`

Local:

```env
TELEGRAM_TOKEN=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
REDIRECT_URI=https://smart-mail-server.onrender.com/callback
AUTH_SERVER_URL=https://smart-mail-server.onrender.com
LOCAL_DB_PATH=data/smart_mail_agent.db

API_SECRET=...
STATE_SECRET=...
TOKEN_POLL_INTERVAL=10
MAIL_POLL_INTERVAL=30

AI_ENABLED=true
AI_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini

OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

LOCAL_OPENAI_BASE_URL=http://localhost:1234/v1
LOCAL_OPENAI_API_KEY=local-key
LOCAL_OPENAI_MODEL=local-model

AI_TIMEOUT=20
AI_MAX_EMAIL_CHARS=6000

IMPORTANT_SENDERS=
URGENT_KEYWORDS=urgent,asap,important,critique,deadline
USELESS_KEYWORDS=newsletter,promo,publicite,unsubscribe
```

Render:

```env
APP_ENV=production
API_SECRET=...
STATE_SECRET=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
REDIRECT_URI=https://smart-mail-server.onrender.com/callback
PENDING_TOKENS_PATH=data/pending_tokens.json
```

## Commandes utiles

Installer:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Initialiser la DB:

```bash
python -m scripts.init_db
```

Reset:

```bash
python -m scripts.reset_db
python -m scripts.reset_db --useless
python -m scripts.reset_db --tokens
python -m scripts.reset_db --users
python -m scripts.reset_db --processed
python -m scripts.reset_db --analysis
python -m scripts.reset_db --all
```

Lancer:

```bash
python -m src.collector
python -m src.main
python -m src.serveur_auth
```

Render start command:

```bash
python -m src.serveur_auth
```

Verification pre-test:

```bash
python -m scripts.check_setup
python -m scripts.smoke_test
```

## Tests effectues le 2026-05-25

Sans appels externes reels:

- Compilation de tous les fichiers Python: OK.
- Script `scripts.check_setup`: OK avec `API_SECRET` et `STATE_SECRET` renseignes.
- Script `scripts.smoke_test`: OK.
- Validation `API_SECRET` obligatoire en production: OK.
- Mode dev sans `API_SECRET` explicite: OK.
- State OAuth signe valide: OK.
- State modifie refuse: OK.
- State expire refuse: OK.
- Callback Flask refuse state invalide: OK.
- Callback Flask mocke avec token Google + profil Gmail: OK.
- `/pending_tokens` protege par `API_SECRET`: OK.
- `/ack_tokens` supprime les tokens confirmes: OK.
- Dev Flask sans `API_SECRET`: OK.
- Stockage pending tokens fichier absent/corrompu/append/ack: OK.
- SQLite temporaire: users, oauth_tokens, useless_mails, processed_mails, mail_analysis: OK.
- Reset partiel scripts: users/tokens/useless/processed/analysis: OK.
- Reset total avec input mocke: OK.
- Sync token Render -> SQLite locale mockee: OK.
- Notification locale "Gmail connecte" mockee: OK.
- Refresh access token mocke: OK.
- Bloc mails inutiles dans notification: OK.
- Format notification urgent/moyen: OK.
- Extraction Gmail HTML, snippet, date, PJ: OK.
- Classification urgent par mots-cles: OK.
- Classification inutile newsletter/promo: OK.
- Classification avec pieces jointes/anciennete: OK.
- Provider IA `rules`: OK.
- Provider IA `openai` mocke: OK.
- Provider IA `ollama` mocke: OK.
- Provider IA `local_openai` mocke: OK.
- Fallback IA sur timeout: OK.
- Fallback IA sur JSON invalide: OK.
- Limite de prompt IA via `AI_MAX_EMAIL_CHARS`: OK.
- Stockage DB du champ `provider`: OK.

Bug corrige pendant les tests:

- Le fallback classait `URGENT deadline` comme `moyen` car le score arrivait a 65/100. Le poids des mots-cles urgents est passe de +45 a +55, ce qui classe bien ce cas en `urgent`.
- Le cache memoire `processed_ids` pouvait marquer un email comme vu avant la fin du traitement. En cas d'erreur pendant `get_mail`, analyse, sauvegarde ou notification, l'email pouvait etre ignore jusqu'au redemarrage. Le cache est maintenant mis a jour seulement apres `mark_mail_processed`.

## Limites restantes

- Pas de test end-to-end reel Telegram/Gmail/OAuth effectue pour eviter messages et appels externes.
- Le `.env` local doit encore definir `API_SECRET` et `STATE_SECRET` avec la meme valeur que Render avant le test reel.
- `PENDING_TOKENS_PATH` reste une persistance simple par fichier; une DB persistante Render serait plus robuste.
- `user_rules` existe mais n'est pas encore alimentee par commandes Telegram.
- Le bot Telegram utilise polling `getUpdates`; pas de webhook.
- Le multi-compte Gmail par meme utilisateur est limite par `chat_id` comme cle primaire dans `oauth_tokens`.
- Les emails precharges au demarrage sont marques traites sans analyse; c'est volontaire pour eviter les anciennes notifications.

## Prochaines etapes recommandees

1. Ajouter des commandes Telegram simples pour ajuster `user_rules`.
2. Ajouter une commande locale de diagnostic des comptes connectes.
3. Ajouter une option explicite pour reanalyser un email deja stocke.
4. Envisager une persistance Render plus robuste pour pending tokens si l'usage augmente.
5. Ajouter des tests unitaires permanents dans un dossier `tests/`.
