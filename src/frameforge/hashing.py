"""Stable content hashing for files and structured data."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

_CHUNK = 1 << 20


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hash_file(path: Path) -> str | None:
    """SHA-256 of a file's bytes, or None if it doesn't exist."""
    path = Path(path)
    if not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def hash_data(data: Any) -> str:
    """Hash JSON-serialisable data independent of key order and whitespace."""
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hash_bytes(canonical.encode("utf-8"))


def combine(*hashes: str | None) -> str:
    """Derive one cache key from several input hashes (order matters)."""
    return hash_data([h for h in hashes])
