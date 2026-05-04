"""JSON memories with embedding retrieval and lexical fallback."""

from __future__ import annotations

from collections import Counter
from functools import lru_cache
from math import sqrt
from pathlib import Path
import logging
import json
import os
import re

from evoresearcher.schemas import MemoryEntry

LOGGER = logging.getLogger(__name__)
DEFAULT_MEMORY_EMBED_MODEL = os.getenv(
    "EVORESEARCHER_MEMORY_EMBED_MODEL",
    "all-MiniLM-L6-v2",
)


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _cosine(a: Counter[str], b: Counter[str]) -> float:
    shared = set(a) & set(b)
    num = sum(a[token] * b[token] for token in shared)
    denom = sqrt(sum(v * v for v in a.values())) * sqrt(sum(v * v for v in b.values()))
    return num / denom if denom else 0.0


def _entry_text(entry: MemoryEntry) -> str:
    return " ".join([entry.summary, entry.goal, entry.details, " ".join(entry.tags)])


@lru_cache(maxsize=2)
def _get_sentence_transformer_model(model_name: str):
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name, device="cpu")


class JSONMemoryStore:
    def __init__(self, path: Path, *, embed_model_name: str = DEFAULT_MEMORY_EMBED_MODEL):
        self.path = path
        self.embed_model_name = embed_model_name
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.last_query_backend = "lexical"

    def query(self, query: str, top_k: int = 3) -> list[MemoryEntry]:
        entries = self.load()
        if not entries:
            return []
        embedding_scored = self._embedding_scores(query, entries)
        if embedding_scored is not None:
            self.last_query_backend = "embedding"
            embedding_scored.sort(key=lambda item: (-item[1], item[0].created_at, item[0].entry_id))
            return [entry for entry, _ in embedding_scored[:top_k]]
        self.last_query_backend = "lexical"
        query_vec = Counter(_tokenize(query))
        scored: list[tuple[MemoryEntry, float]] = []
        for entry in entries:
            score = _cosine(query_vec, Counter(_tokenize(_entry_text(entry))))
            scored.append((entry, score))
        scored.sort(key=lambda item: (-item[1], item[0].created_at, item[0].entry_id))
        return [entry for entry, _ in scored[:top_k]]

    def add(self, entry: MemoryEntry) -> None:
        entries = self.load()
        entries.append(entry)
        self.save(entries)

    def load(self) -> list[MemoryEntry]:
        if not self.path.exists():
            return []
        return [MemoryEntry.model_validate(item) for item in json.loads(self.path.read_text())]

    def save(self, entries: list[MemoryEntry]) -> None:
        self.path.write_text(json.dumps([item.model_dump() for item in entries], indent=2))

    def _embedding_scores(
        self,
        query: str,
        entries: list[MemoryEntry],
    ) -> list[tuple[MemoryEntry, float]] | None:
        try:
            model = _get_sentence_transformer_model(self.embed_model_name)
            vectors = model.encode(
                [query, *[_entry_text(entry) for entry in entries]],
                normalize_embeddings=True,
            )
            query_vec = vectors[0]
            entry_vecs = vectors[1:]
            scored = []
            for entry, vec in zip(entries, entry_vecs, strict=False):
                score = float(query_vec @ vec)
                scored.append((entry, score))
            return scored
        except Exception as exc:
            LOGGER.warning("Falling back to lexical memory retrieval: %s", exc)
            return None
