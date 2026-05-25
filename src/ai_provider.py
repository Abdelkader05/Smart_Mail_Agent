import json

import requests

from src.classifier import classify_email
from src.config import (
    AI_ENABLED,
    AI_MAX_EMAIL_CHARS,
    AI_PROVIDER,
    AI_TIMEOUT,
    LOCAL_OPENAI_API_KEY,
    LOCAL_OPENAI_BASE_URL,
    LOCAL_OPENAI_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OPENAI_API_KEY,
    OPENAI_MODEL,
)


REQUIRED_KEYS = {
    "category",
    "importance_score",
    "summary",
    "reason",
    "suggested_action",
    "deadline_detected",
    "requires_reply",
    "confidence",
}

ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": ["urgent", "moyen", "inutile"]},
        "importance_score": {"type": "integer"},
        "summary": {"type": "string"},
        "reason": {"type": "string"},
        "suggested_action": {"type": "string"},
        "deadline_detected": {"type": ["string", "null"]},
        "requires_reply": {"type": "boolean"},
        "confidence": {"type": "integer"},
    },
    "required": sorted(REQUIRED_KEYS),
    "additionalProperties": False,
}


def analyze_email_with_ai(email_data):
    fallback = fallback_analysis(email_data)

    if not AI_ENABLED or AI_PROVIDER == "rules":
        return fallback

    try:
        if AI_PROVIDER == "openai":
            result = analyze_with_openai_cloud(email_data)
        elif AI_PROVIDER == "ollama":
            result = analyze_with_ollama(email_data)
        elif AI_PROVIDER == "local_openai":
            result = analyze_with_local_openai(email_data)
        else:
            print(f"IA indisponible: provider inconnu ({AI_PROVIDER}). Fallback regles.")
            return fallback

        return normalize_analysis(result, fallback, AI_PROVIDER)
    except Exception as exc:
        print(f"IA indisponible: {AI_PROVIDER} {exc.__class__.__name__}. Fallback regles.")
        return fallback


def fallback_analysis(email_data):
    result = classify_email(
        email_data.get("subject", ""),
        email_data.get("sender", ""),
        email_data.get("attachments", []),
        email_data.get("mail_date"),
        email_data.get("snippet", ""),
        email_data.get("body", ""),
    )
    result["provider"] = "rules"
    return result


def analyze_with_openai_cloud(email_data):
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY manquante")

    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY, timeout=AI_TIMEOUT)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=build_messages(email_data),
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "email_analysis",
                "strict": True,
                "schema": ANALYSIS_SCHEMA,
            },
        },
        timeout=AI_TIMEOUT,
    )
    return json.loads(response.choices[0].message.content)


def analyze_with_ollama(email_data):
    response = requests.post(
        f"{OLLAMA_BASE_URL.rstrip('/')}/api/chat",
        json={
            "model": OLLAMA_MODEL,
            "messages": build_messages(email_data),
            "stream": False,
            "format": "json",
        },
        timeout=AI_TIMEOUT,
    )
    response.raise_for_status()
    content = response.json().get("message", {}).get("content", "")
    return parse_json_content(content)


def analyze_with_local_openai(email_data):
    headers = {"Content-Type": "application/json"}
    if LOCAL_OPENAI_API_KEY:
        headers["Authorization"] = f"Bearer {LOCAL_OPENAI_API_KEY}"

    response = requests.post(
        f"{LOCAL_OPENAI_BASE_URL.rstrip('/')}/chat/completions",
        headers=headers,
        json={
            "model": LOCAL_OPENAI_MODEL,
            "messages": build_messages(email_data),
            "temperature": 0,
            "response_format": {"type": "json_object"},
        },
        timeout=AI_TIMEOUT,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return parse_json_content(content)


def build_messages(email_data):
    return [
        {
            "role": "system",
            "content": (
                "Tu es un assistant email personnel. Analyse l'email en francais. "
                "Retourne uniquement un JSON valide avec ces champs exacts: "
                "category, importance_score, summary, reason, suggested_action, "
                "deadline_detected, requires_reply, confidence. "
                "category doit etre urgent, moyen ou inutile."
            ),
        },
        {"role": "user", "content": build_prompt(email_data)},
    ]


def build_prompt(email_data):
    body = (email_data.get("body") or "")[:AI_MAX_EMAIL_CHARS]
    attachments = email_data.get("attachments") or []
    return (
        "Analyse cet email pour decider s'il faut notifier l'utilisateur.\n"
        "Retour attendu: JSON strict uniquement.\n"
        f"Sujet: {email_data.get('subject') or ''}\n"
        f"Expediteur: {email_data.get('sender') or ''}\n"
        f"Date: {email_data.get('date') or ''}\n"
        f"Snippet Gmail: {email_data.get('snippet') or ''}\n"
        f"Pieces jointes: {', '.join(attachments) if attachments else 'Aucune'}\n"
        f"Corps limite:\n{body}"
    )


def parse_json_content(content):
    if not content:
        raise ValueError("reponse vide")

    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:].strip()
    return json.loads(content)


def normalize_analysis(data, fallback, provider):
    if not isinstance(data, dict):
        raise ValueError("analysis is not an object")
    if not REQUIRED_KEYS.issubset(data):
        raise ValueError("analysis missing required keys")

    normalized = dict(fallback)
    normalized.update(data)

    if normalized.get("category") not in {"urgent", "moyen", "inutile"}:
        raise ValueError("invalid category")

    normalized["importance_score"] = clamp_int(normalized.get("importance_score"), 0, 100)
    normalized["confidence"] = clamp_int(normalized.get("confidence"), 0, 100)
    normalized["summary"] = str(normalized.get("summary") or fallback["summary"])[:500]
    normalized["reason"] = str(normalized.get("reason") or fallback["reason"])[:500]
    normalized["suggested_action"] = str(
        normalized.get("suggested_action") or fallback["suggested_action"]
    )[:500]
    normalized["deadline_detected"] = normalized.get("deadline_detected") or None
    normalized["requires_reply"] = bool(normalized.get("requires_reply"))
    normalized["provider"] = provider
    return normalized


def clamp_int(value, minimum, maximum):
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = minimum
    return max(minimum, min(maximum, value))
