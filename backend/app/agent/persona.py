"""Keeps the assistant's persona: the model never shows its own name. Pure code.

Input:  the final `answer` text and the `model_id` ("vendor/crouton-alpha").
Output: apply_persona(answer, model_id) -> (answer, replaced terms): the model's own
        display name, derived from its id, is rewritten to PERSONA_NAME ("Axel").

The name is the last path segment of the id split on - _ space or dot. Tokens with
digits (versions) and generic words are dropped. It needs a multi-token name, or one
distinctive token of 4+ letters; otherwise nothing is rewritten.
"""

from __future__ import annotations

import re

PERSONA_NAME = "Axel"
# Tokens of a model id that are not a distinctive name (so never rewritten).
_GENERIC_TOKENS = frozenset(
    {"free", "chat", "instruct", "preview", "beta", "latest", "turbo", "mini", "base",
     "online", "thinking", "exp", "experimental", "large", "small", "medium"}
)  # fmt: skip


def _model_name_pattern(model_id: str) -> re.Pattern[str] | None:
    """Regex for the model's own display name, or None when it has no distinctive one."""
    segment = model_id.rsplit("/", 1)[-1].split(":")[0]
    tokens = [
        t for t in re.split(r"[-_ .]+", segment)
        if t.isalpha() and t.lower() not in _GENERIC_TOKENS
    ]  # fmt: skip
    if not tokens or (len(tokens) == 1 and len(tokens[0]) < 4):
        return None
    body = r"[-_ ]?".join(re.escape(t) for t in tokens)
    return re.compile(rf"(?<![A-Za-z0-9]){body}(?![A-Za-z0-9])", re.IGNORECASE)


def apply_persona(answer: str, model_id: str) -> tuple[str, list[str]]:
    """Replace the model's own name with Axel. Returns (answer, replaced terms)."""
    pattern = _model_name_pattern(model_id or "")
    if pattern is None:
        return answer, []
    found = [m.group(0) for m in pattern.finditer(answer)]
    return (pattern.sub(PERSONA_NAME, answer), found) if found else (answer, [])
