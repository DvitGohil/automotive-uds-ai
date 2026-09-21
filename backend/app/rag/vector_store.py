"""
Local, private vector store (FAISS). One collection per project, persisted
to disk under settings.VECTOR_DB_PATH/<collection_name>/. No external/network
vector service — keeps storage local as required by the project architecture.
"""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from app.core.config import settings


@dataclass
class VectorRecord:
    id: str  # e.g. chunk_id — stable identity for upsert/dedup
    vector: list[float]
    content_hash: str  # used to detect unchanged content and skip re-indexing
    metadata: dict = field(default_factory=dict)


@dataclass
class SearchResult:
    id: str
    score: float
    metadata: dict


@dataclass
class UpsertSummary:
    added: int = 0
    updated: int = 0
    skipped: int = 0


class VectorStoreError(Exception):
    pass


class VectorStore:
    def __init__(self, collection_name: str, dimension: int, base_path: Optional[str] = None):
        import faiss  # lazy import: keeps this module importable without faiss for non-vector code paths

        self._faiss = faiss
        self.collection_name = collection_name
        self.dimension = dimension
        self.base_path = Path(base_path or settings.VECTOR_DB_PATH) / collection_name
        self.index_path = self.base_path / "index.faiss"
        self.meta_path = self.base_path / "metadata.json"
        self._load_or_init()

    def _load_or_init(self) -> None:
        self.base_path.mkdir(parents=True, exist_ok=True)
        if self.index_path.exists() and self.meta_path.exists():
            self.index = self._faiss.read_index(str(self.index_path))
            self.meta = json.loads(self.meta_path.read_text())
        else:
            self.index = self._faiss.IndexIDMap2(self._faiss.IndexFlatIP(self.dimension))
            self.meta = {"records": {}, "id_map": {}, "next_id": 1}

    def _save(self) -> None:
        self._faiss.write_index(self.index, str(self.index_path))
        self.meta_path.write_text(json.dumps(self.meta))

    def _assign_int_id(self, record_id: str) -> int:
        if record_id in self.meta["id_map"]:
            return self.meta["id_map"][record_id]
        new_id = self.meta["next_id"]
        self.meta["id_map"][record_id] = new_id
        self.meta["next_id"] = new_id + 1
        return new_id

    def upsert(self, records: list[VectorRecord]) -> UpsertSummary:
        summary = UpsertSummary()
        for record in records:
            if len(record.vector) != self.dimension:
                raise VectorStoreError(
                    f"Vector dimension mismatch for id={record.id!r}: "
                    f"got {len(record.vector)}, expected {self.dimension}"
                )

            existing = self.meta["records"].get(record.id)
            if existing is not None and existing.get("content_hash") == record.content_hash:
                summary.skipped += 1
                continue  # unchanged content — avoid unnecessary duplicate/re-indexing work

            int_id = self._assign_int_id(record.id)
            if existing is not None:
                self.index.remove_ids(np.array([int_id], dtype="int64"))
                summary.updated += 1
            else:
                summary.added += 1

            vector = np.array([record.vector], dtype="float32")
            self._faiss.normalize_L2(vector)
            self.index.add_with_ids(vector, np.array([int_id], dtype="int64"))
            self.meta["records"][record.id] = {
                "int_id": int_id,
                "content_hash": record.content_hash,
                "metadata": record.metadata,
            }

        self._save()
        return summary

    def search(self, query_vector: list[float], top_k: int = 5) -> list[SearchResult]:
        if len(query_vector) != self.dimension:
            raise VectorStoreError(
                f"Query vector dimension mismatch: got {len(query_vector)}, expected {self.dimension}"
            )
        if self.index.ntotal == 0:
            return []

        vector = np.array([query_vector], dtype="float32")
        self._faiss.normalize_L2(vector)
        k = min(top_k, self.index.ntotal)
        scores, ids = self.index.search(vector, k)

        int_to_record_id = {v["int_id"]: k for k, v in self.meta["records"].items()}
        results: list[SearchResult] = []
        for score, int_id in zip(scores[0], ids[0]):
            if int_id == -1:
                continue
            record_id = int_to_record_id.get(int(int_id))
            if record_id is None:
                continue
            record = self.meta["records"][record_id]
            results.append(SearchResult(id=record_id, score=float(score), metadata=record["metadata"]))
        return results

    def count(self) -> int:
        return self.index.ntotal


def get_vector_store(collection_name: str, dimension: int) -> VectorStore:
    return VectorStore(collection_name=collection_name, dimension=dimension)
