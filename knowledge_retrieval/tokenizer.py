"""Token estimation utilities with tiktoken integration and resilient fallback."""

from __future__ import annotations

import re
from typing import Optional

_TIKTOKEN_ENCODER = None
_TIKTOKEN_INITIALIZED = False


def _get_encoder():
    global _TIKTOKEN_ENCODER, _TIKTOKEN_INITIALIZED
    if not _TIKTOKEN_INITIALIZED:
        try:
            import tiktoken
            _TIKTOKEN_ENCODER = tiktoken.get_encoding("cl100k_base")
        except Exception:
            _TIKTOKEN_ENCODER = None
        _TIKTOKEN_INITIALIZED = True
    return _TIKTOKEN_ENCODER


def estimate_tokens(text: str) -> int:
    """Estimates the token count of a given string.
    
    Uses tiktoken cl100k_base if available; falls back to standard heuristic:
    ~4 characters per token for English text, handling whitespace and punctuation.
    """
    if not text:
        return 0
    encoder = _get_encoder()
    if encoder is not None:
        try:
            return len(encoder.encode(text, disallowed_special=()))
        except Exception:
            pass
    
    # Fallback heuristic:
    # 1 token is roughly 4 characters or 0.75 words.
    words = len(re.findall(r"\w+", text))
    chars = len(text)
    heuristic = max(1, int((words * 1.3 + chars / 4.0) / 2))
    return heuristic
