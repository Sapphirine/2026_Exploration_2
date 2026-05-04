from pathlib import Path

import evoresearcher.memory.store as store_module
from evoresearcher.memory.store import JSONMemoryStore
from evoresearcher.schemas import MemoryEntry


class FakeVector:
    def __init__(self, values):
        self.values = values

    def __matmul__(self, other):
        return sum(a * b for a, b in zip(self.values, other.values, strict=True))


class FakeEmbeddingModel:
    def encode(self, texts, normalize_embeddings=True):
        vectors = []
        for text in texts:
            lowered = text.lower()
            if "moe" in lowered or "mixture of experts" in lowered:
                vectors.append(FakeVector([1.0, 0.0]))
            else:
                vectors.append(FakeVector([0.0, 1.0]))
        return vectors


def make_entry(entry_id: str, summary: str, goal: str, details: str) -> MemoryEntry:
    return MemoryEntry(
        entry_id=entry_id,
        kind="proposal_pattern",
        summary=summary,
        goal=goal,
        details=details,
        tags=["test"],
        created_at=f"2026-01-01T00:00:0{entry_id}+00:00",
    )


def test_embedding_query_is_preferred(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(
        store_module,
        "_get_sentence_transformer_model",
        lambda model_name: FakeEmbeddingModel(),
    )
    store = JSONMemoryStore(tmp_path / "memory.json")
    store.save(
        [
            make_entry("1", "MoE routing", "Improve MoE efficiency", "Sparse routing and dispatch."),
            make_entry("2", "Social policy", "Study welfare delivery", "Programs for the ultra-poor."),
        ]
    )
    hits = store.query("Need a proposal for mixture of experts efficiency", top_k=1)
    assert hits[0].summary == "MoE routing"
    assert store.last_query_backend == "embedding"


def test_lexical_fallback_is_used_when_embedding_fails(tmp_path: Path, monkeypatch):
    def broken_model(model_name):
        raise RuntimeError("embedding backend unavailable")

    monkeypatch.setattr(store_module, "_get_sentence_transformer_model", broken_model)
    store = JSONMemoryStore(tmp_path / "memory.json")
    store.save(
        [
            make_entry("1", "MoE routing", "Improve MoE efficiency", "Sparse routing and dispatch."),
            make_entry("2", "Social policy", "Study welfare delivery", "Programs for the ultra-poor."),
        ]
    )
    hits = store.query("Improve MoE efficiency", top_k=1)
    assert hits[0].summary == "MoE routing"
    assert store.last_query_backend == "lexical"
