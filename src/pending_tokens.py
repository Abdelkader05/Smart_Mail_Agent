import json
import os
import tempfile
import uuid

from src.config import PENDING_TOKENS_PATH


def _ensure_parent_dir():
    parent = os.path.dirname(PENDING_TOKENS_PATH)
    if parent:
        os.makedirs(parent, exist_ok=True)


def load_pending_tokens():
    if not os.path.exists(PENDING_TOKENS_PATH):
        return []

    with open(PENDING_TOKENS_PATH, "r", encoding="utf-8") as handle:
        try:
            data = json.load(handle)
        except json.JSONDecodeError:
            return []

    if not isinstance(data, list):
        return []
    return data


def save_pending_tokens(tokens):
    _ensure_parent_dir()
    parent = os.path.dirname(PENDING_TOKENS_PATH) or "."
    fd, tmp_path = tempfile.mkstemp(prefix="pending_tokens_", suffix=".json", dir=parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(tokens, handle)
        os.replace(tmp_path, PENDING_TOKENS_PATH)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def append_pending_token(token):
    tokens = load_pending_tokens()
    token = dict(token)
    token.setdefault("id", uuid.uuid4().hex)
    tokens.append(token)
    save_pending_tokens(tokens)


def get_unconsumed_tokens():
    tokens = load_pending_tokens()
    return [token for token in tokens if not token.get("consumed")]


def ack_pending_tokens(token_ids):
    wanted = {str(token_id) for token_id in token_ids if token_id}
    if not wanted:
        return 0

    tokens = load_pending_tokens()
    remaining = [token for token in tokens if str(token.get("id")) not in wanted]
    removed = len(tokens) - len(remaining)
    save_pending_tokens(remaining)
    return removed
