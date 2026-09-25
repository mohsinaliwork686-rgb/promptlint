"""Token counting — exact with tiktoken when installed, heuristic otherwise."""

from __future__ import annotations

import re
from functools import lru_cache

_WORD_RE = re.compile(r"\w+|[^\w\s]")


@lru_cache(maxsize=8)
def _encoder(name: str):
    try:
        import tiktoken
    except ImportError:
        return None
    try:
        return tiktoken.get_encoding(name)
    except Exception:
        try:
            return tiktoken.encoding_for_model(name)
        except Exception:
            return None


def estimate_tokens(text: str, tokenizer: str = "heuristic") -> tuple[int, bool]:
    """Return ``(count, exact)``.

    ``exact`` is False when we fell back to the heuristic because tiktoken was
    not installed or the encoding name was not recognised.
    """
    if tokenizer and tokenizer != "heuristic":
        encoder = _encoder(tokenizer)
        if encoder is not None:
            return len(encoder.encode(text)), True
    return _heuristic(text), False


def _heuristic(text: str) -> int:
    """Approximate BPE: short words are one token, long words split every ~4 chars."""
    total = 0
    for piece in _WORD_RE.findall(text):
        total += 1 if len(piece) <= 4 else -(-len(piece) // 4)
    # Newlines and indentation carry tokens of their own.
    total += text.count("\n")
    return total
