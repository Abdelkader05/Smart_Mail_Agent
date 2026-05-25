# Smart Mail Agent

Architecture hybride simple pour un projet personnel:

- local: bot Telegram, agent Gmail, base SQLite, init/reset;
- Render: serveur Flask OAuth Google uniquement, avec callback public stable.

## Structure

```text
Smart_Mail_Agent/
+-- src/
|   +-- collector.py        # Bot Telegram local
|   +-- main.py             # Agent Gmail local
|   +-- serveur_auth.py     # Pont OAuth a deployer sur Render
|   +-- config.py           # Config, secrets, state OAuth signe
|   +-- db.py               # Base SQLite locale
|   +-- pending_tokens.py   # File JSON temporaire cote Render
|   +-- ai_provider.py      # Abstraction IA: OpenAI, Ollama, local OpenAI, rules
|   +-- ai_analyzer.py      # Alias compatible vers ai_provider
|   +-- classifier.py       # Fallback par regles
+-- scripts/
|   +-- init_db.py          # Cree/migre la base locale
|   +-- reset_db.py         # Reset local
+-- docs/                   # Notes conservees
+-- data/                   # Bases locales ignorees par Git si necessaire
+-- README.md
+-- README_v2.md
```

## Flow

1. L'utilisateur envoie `/start user_id` au bot Telegram local.
2. `src.collector` enregistre `chat_id + user_id` dans SQLite.
3. Le bot genere une URL OAuth Google avec un `state` signe HMAC.
4. Google redirige vers Render sur `/callback`.
5. `src.serveur_auth` verifie le `state`, recupere les tokens Google et les stocke temporairement dans `PENDING_TOKENS_PATH`.
6. `src.main` poll `/pending_tokens`, recupere les tokens, les enregistre en SQLite, appelle `/ack_tokens`, puis notifie Telegram.
7. `src.main` surveille Gmail, extrait le contenu, analyse avec l'IA si active, deduplique via SQLite et envoie les notifications.

Render ne contient pas la base principale et ne notifie pas Telegram.

## Variables `.env`

Local:

```env
TELEGRAM_TOKEN=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
REDIRECT_URI=https://smart-mail-server.onrender.com/callback
AUTH_SERVER_URL=https://smart-mail-server.onrender.com
LOCAL_DB_PATH=data/smart_mail_agent.db

API_SECRET=un-secret-long
# Optionnel: si absent, STATE_SECRET reprend API_SECRET
STATE_SECRET=un-secret-long

TOKEN_POLL_INTERVAL=10
MAIL_POLL_INTERVAL=30

# IA
AI_ENABLED=true
# openai | ollama | local_openai | rules
AI_PROVIDER=openai

# OpenAI cloud
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini

# Ollama local
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# Endpoint local compatible OpenAI, ex: LM Studio
LOCAL_OPENAI_BASE_URL=http://localhost:1234/v1
LOCAL_OPENAI_API_KEY=local-key
LOCAL_OPENAI_MODEL=local-model

AI_TIMEOUT=20
AI_MAX_EMAIL_CHARS=6000

# Optionnel, separe par virgules
IMPORTANT_SENDERS=chef@exemple.com,client@exemple.com
URGENT_KEYWORDS=urgent,asap,important,critique,deadline
USELESS_KEYWORDS=newsletter,promo,publicite,unsubscribe
```

Render:

```env
APP_ENV=production
API_SECRET=le-meme-secret-que-local
STATE_SECRET=le-meme-secret-que-local
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
REDIRECT_URI=https://smart-mail-server.onrender.com/callback
PENDING_TOKENS_PATH=data/pending_tokens.json
```

En production/Render, `API_SECRET` est obligatoire. En dev local, il peut etre vide, mais les routes internes deviennent permissives et un warning est affiche.

## Commandes

Installer:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Preparer la configuration:

```bash
copy .env.example .env
```

Remplis `.env`, puis verifie que le projet est pret:

```bash
python -m scripts.check_setup
```

Pour generer un secret local solide:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Mets cette meme valeur dans `API_SECRET` et `STATE_SECRET` en local et sur Render.

Test hors-ligne rapide, sans appel Telegram/Gmail/OpenAI reel:

```bash
python -m scripts.smoke_test
```

Initialiser la base locale:

```bash
python -m scripts.init_db
```

Lancer le bot Telegram local:

```bash
python -m src.collector
```

Lancer l'agent Gmail local:

```bash
python -m src.main
```

Tester le serveur OAuth localement:

```bash
python -m src.serveur_auth
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

Deploy Render:

```bash
python -m src.serveur_auth
```

## Routes Render

| Route | Role |
|---|---|
| `GET /callback` | Callback OAuth Google. Verifie le `state` signe. |
| `GET /pending_tokens` | Donne au local les tokens non confirmes. Protege par `API_SECRET`. |
| `POST /ack_tokens` | Supprime les tokens confirmes apres sauvegarde locale. Protege par `API_SECRET`. |
| `POST /register_user` | Compatibilite/dev. Le vrai lien user/chat est dans le `state` signe. |
| `GET /health` | Statut simple du pont OAuth. |

`/pending_tokens` ne supprime pas immediatement. Le local confirme avec `/ack_tokens` seulement apres avoir ecrit les tokens dans SQLite, ce qui evite une perte si le local plante entre lecture et sauvegarde.

## Deduplication

La table locale `processed_mails` garde les `msg_id` deja vus ou traites. Au redemarrage, `src.main` verifie cette table avant toute notification, donc un email deja traite n'est pas renotifie.

## Analyse IA

`src/ai_provider.py` centralise l'analyse intelligente. `src.main` appelle une seule fonction stable:

```python
analyze_email_with_ai(email_data)
```

Cette fonction choisit le provider depuis `.env`, normalise la reponse et fallback automatiquement vers les regles. `src.main` lui transmet:

- sujet;
- expediteur;
- date;
- snippet Gmail;
- corps texte nettoye si disponible;
- pieces jointes.

Le corps envoye a l'IA est limite par `AI_MAX_EMAIL_CHARS` pour reduire les couts et les erreurs. Les tokens, secrets et contenus complets ne sont pas logges.

L'IA doit retourner une structure JSON stricte:

```python
{
    "category": "urgent|moyen|inutile",
    "importance_score": 0,
    "summary": "resume court en francais",
    "reason": "raison claire",
    "suggested_action": "action recommandee",
    "deadline_detected": None,
    "requires_reply": False,
    "confidence": 0,
}
```

Les resultats sont stockes localement dans `mail_analysis`:

- `msg_id`
- `gmail`
- `category`
- `importance_score`
- `summary`
- `reason`
- `suggested_action`
- `deadline_detected`
- `requires_reply`
- `confidence`
- `provider`
- `analyzed_at`

Cela evite de refaire une analyse IA inutilement.

## Fallback par regles

Si `AI_ENABLED=false`, si le provider est indisponible, si l'API timeout, si la cle manque, ou si le JSON est invalide, l'agent utilise `src/classifier.py`.

Le fallback applique un score par regles:

- mots-cles urgents;
- expediteurs importants;
- pieces jointes;
- anciennete;
- signaux faibles type newsletter/promo.

## Notifications Telegram

Les notifications utilisent le resultat IA ou fallback:

```text
URGENT - Score 92/100
Sujet: ...
De: ...
Resume: ...
Pourquoi: ...
Action: ...
Deadline: ...
Reponse requise: oui/non
Confiance: ...
PJ: ...
```

## Providers IA

Desactiver l'IA:

```env
AI_ENABLED=false
AI_PROVIDER=rules
```

OpenAI cloud:

```env
AI_ENABLED=true
AI_PROVIDER=openai
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4.1-mini
```

Ollama local:

```env
AI_ENABLED=true
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
```

LM Studio ou serveur compatible OpenAI:

```env
AI_ENABLED=true
AI_PROVIDER=local_openai
LOCAL_OPENAI_BASE_URL=http://localhost:1234/v1
LOCAL_OPENAI_API_KEY=local-key
LOCAL_OPENAI_MODEL=local-model
```

Le champ `provider` dans `mail_analysis` indique quelle couche a produit l'analyse: `openai`, `ollama`, `local_openai` ou `rules`.

## Apprentissage futur

La table `user_rules` prepare une future couche d'apprentissage utilisateur:

- expediteurs importants;
- mots-cles urgents;
- domaines ignores;
- preferences de notification.

Elle n'est pas encore pilotee par Telegram, mais la structure locale est prete.

## Cout et limites IA

- Chaque email analyse peut consommer des tokens OpenAI.
- `AI_MAX_EMAIL_CHARS` limite le contenu transmis.
- Les emails deja traites ne sont pas renotifies grace a `processed_mails`.
- Les analyses existantes sont stockees dans `mail_analysis`.
- En cas d'indisponibilite IA, l'agent continue avec le fallback par regles.

## Tests utiles

```bash
python -m py_compile src/config.py src/db.py src/pending_tokens.py src/classifier.py src/ai_provider.py src/ai_analyzer.py src/collector.py src/main.py src/serveur_auth.py scripts/init_db.py scripts/reset_db.py scripts/check_setup.py scripts/smoke_test.py
python -m scripts.check_setup
python -m scripts.smoke_test
python -m scripts.init_db
```
