"""Deterministic, tenant-scoped chunk identity primitives."""

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from typing import Iterable


CHUNK_REF_PREFIX = "chk_"


def canonicalize_chunk_text(text: str) -> str:
    """Normalize representation without applying language-specific rewriting."""
    normalized = unicodedata.normalize("NFC", text)
    return re.sub(r"\s+", " ", normalized).strip()


def exact_chunk_hash(text: str) -> str:
    return hashlib.sha256(canonicalize_chunk_text(text).encode("utf-8")).hexdigest()


def build_chunk_ref(
    *,
    api_key_id: int,
    file_id: str,
    chunking_strategy: str,
    chunking_version: str,
    chunking_parameters: dict[str, int],
    exact_hash: str,
    duplicate_ordinal: int,
) -> str:
    """Build an opaque stable ref for one logical occurrence of a chunk.

    Tenant identity is included in the digest, but never exposed directly.
    Duplicate ordinal distinguishes repeated identical chunks in the same file.
    """
    if duplicate_ordinal < 0:
        raise ValueError("duplicate_ordinal must be non-negative")
    identity = {
        "tenant": str(api_key_id),
        "file": file_id,
        "strategy": chunking_strategy,
        "strategy_version": chunking_version,
        "parameters": chunking_parameters,
        "content_hash": exact_hash,
        "duplicate_ordinal": duplicate_ordinal,
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"{CHUNK_REF_PREFIX}{digest}"


def assign_chunk_refs(
    texts: Iterable[str],
    *,
    api_key_id: int,
    file_id: str,
    chunking_strategy: str,
    chunking_version: str,
    chunking_parameters: dict[str, int],
) -> list[tuple[str, str]]:
    """Return `(chunk_ref, exact_hash)` in source order."""
    occurrences: defaultdict[str, int] = defaultdict(int)
    identities = []
    for text in texts:
        content_hash = exact_chunk_hash(text)
        duplicate_ordinal = occurrences[content_hash]
        occurrences[content_hash] += 1
        identities.append(
            (
                build_chunk_ref(
                    api_key_id=api_key_id,
                    file_id=file_id,
                    chunking_strategy=chunking_strategy,
                    chunking_version=chunking_version,
                    chunking_parameters=chunking_parameters,
                    exact_hash=content_hash,
                    duplicate_ordinal=duplicate_ordinal,
                ),
                content_hash,
            )
        )
    return identities
