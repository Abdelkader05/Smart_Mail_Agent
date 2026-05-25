from datetime import datetime

from src.config import IMPORTANT_SENDERS, URGENT_KEYWORDS, USELESS_KEYWORDS


def _contains_any(text, keywords):
    lowered = (text or "").lower()
    return [keyword for keyword in keywords if keyword in lowered]


def classify_email(subject, sender, attachments=None, mail_date=None, snippet="", body=""):
    attachments = attachments or []
    score = 20
    reasons = []
    searchable_text = " ".join([subject or "", sender or "", snippet or "", body or ""])

    subject_matches = _contains_any(searchable_text, URGENT_KEYWORDS)
    if subject_matches:
        score += 55
        reasons.append("mot-cle urgent: " + ", ".join(subject_matches[:3]))

    sender_lower = (sender or "").lower()
    important_matches = [item for item in IMPORTANT_SENDERS if item in sender_lower]
    if important_matches:
        score += 35
        reasons.append("expediteur important")

    useless_matches = _contains_any(searchable_text, USELESS_KEYWORDS)
    if useless_matches:
        score -= 35
        reasons.append("signal faible: " + ", ".join(useless_matches[:3]))

    if attachments:
        score += 10
        reasons.append("piece jointe presente")

    if mail_date:
        age_days = (datetime.now() - mail_date).days
        if age_days >= 2:
            score += 20
            reasons.append(f"anciennete {age_days} jour(s)")

    score = max(0, min(100, score))

    if score >= 70:
        category = "urgent"
    elif score >= 35:
        category = "moyen"
    else:
        category = "inutile"

    summary = (snippet or subject or "Email sans sujet").strip()
    if len(summary) > 220:
        summary = summary[:217].rstrip() + "..."
    reason = "; ".join(reasons) if reasons else "score par defaut"

    return {
        "category": category,
        "importance_score": score,
        "summary": summary,
        "reason": reason,
        "suggested_action": _suggest_action(category),
        "deadline_detected": None,
        "requires_reply": category in {"urgent", "moyen"},
        "confidence": 60 if reasons else 45,
    }


def _suggest_action(category):
    if category == "urgent":
        return "Lire et traiter rapidement."
    if category == "moyen":
        return "Verifier quand tu as un moment."
    return "Aucune action immediate."
