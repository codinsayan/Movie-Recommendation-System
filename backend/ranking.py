"""S5C: versioned contracts, budgets and a bounded sparse feature cache for ranking.

Pipeline stages and where they live:
  retrieval  -> discovery.Discovery.candidates      (bounded TMDB candidate pool)
  encoding   -> FeatureStore.encode                 (sparse vectors, cached per movie)
  profile    -> Recommender._profile                (positive/negative/mood/external)
  scoring    -> Recommender.recommend               (sparse candidate @ dense profile)
  reranking  -> Recommender._mmr / _mmr_union       (only the bounded rerank pool)

Every stage is versioned by RANKING_CONTRACT plus the engine's feature_version, so
vectors from different vocabularies are never mixed or compared.
"""
from __future__ import annotations

from collections import OrderedDict
import hashlib
import os
from threading import Lock

import numpy as np
from scipy import sparse
from sklearn.preprocessing import normalize

from features import FEATURE_LANGUAGE, feature_text

RANKING_CONTRACT = "rank-v2"

# Per-request work limits. Growing caches or catalogues must never enlarge these.
RANKING_BUDGET = {
    "rerank_pool": 300,              # rows MMR may compare (k * 3, capped)
    "encode_batch": 64,              # documents per vectorizer call on cache misses
    "external_viewing": 20,          # watched titles outside the snapshot considered per request
    "feature_cache_entries": 4000,   # derived vectors kept in memory (LRU)
    "feature_cache_bytes": 16 * 1024 * 1024,
}
ENTRY_OVERHEAD = 256   # bytes per cache entry beyond its arrays (key, digest, bookkeeping)


def ranking_mode() -> str:
    """CINEMAGIC_RANKING=snapshot is the rollback path: no live candidates, snapshot ranking only."""
    return "snapshot" if os.environ.get("CINEMAGIC_RANKING", "").strip().lower() == "snapshot" else "dynamic"


def metadata_digest(document: str) -> str:
    return hashlib.sha256(document.encode("utf-8")).hexdigest()[:16]


class FeatureStore:
    """Sparse TF-IDF vectors for titles outside the snapshot, keyed by canonical identity.

    Key: (canonical key, metadata language, feature_version). Each entry stores the
    digest of the feature document it was built from, so changed metadata (for example
    a summary upgraded to full details) is re-encoded instead of reused. Entries are
    derived data: eviction only means a later request re-encodes from metadata.
    """

    def __init__(self, engine, budget=None):
        self.budget = {**RANKING_BUDGET, **(budget or {})}
        self._lock = Lock()
        self._entries: OrderedDict = OrderedDict()
        self.bytes = 0
        self.stats = {"hits": 0, "misses": 0, "reencoded": 0, "evictions": 0, "incompatible_dropped": 0}
        self.bind(engine)

    def bind(self, engine):
        """Attach to an engine; vectors from any other feature version are dropped, never reused."""
        with self._lock:
            self.engine = engine
            self.version = engine.feature_version
            stale = [key for key in self._entries if key[2] != self.version]
            for key in stale:
                self._drop(key)
            self.stats["incompatible_dropped"] += len(stale)

    def _drop(self, key):
        entry = self._entries.pop(key)
        self.bytes -= entry["bytes"]

    def _lookup(self, key, digest):
        entry = self._entries.get(key)
        if entry is None:
            return None, False
        if entry["digest"] != digest:
            return None, True       # same movie, different metadata: re-encode
        self._entries.move_to_end(key)
        return entry, False

    def _store(self, key, digest, row):
        indices = row.indices.astype(np.int32)
        values = row.data.astype(np.float64)
        size = indices.nbytes + values.nbytes + ENTRY_OVERHEAD
        if key in self._entries:
            self._drop(key)
        self._entries[key] = {"digest": digest, "indices": indices, "values": values, "bytes": size}
        self.bytes += size
        while self._entries and (len(self._entries) > self.budget["feature_cache_entries"]
                                 or self.bytes > self.budget["feature_cache_bytes"]):
            self._drop(next(iter(self._entries)))
            self.stats["evictions"] += 1

    def encode(self, movies, language=FEATURE_LANGUAGE):
        """Return (L2-normalised CSR matrix, per-request stats). Only cache misses hit the vectorizer."""
        width = len(self.engine.vectorizer.vocabulary_)
        documents = [feature_text(m) for m in movies]
        keys = [(f"{m.get('source', 'tmdb')}:{m['id']}", m.get("metadata_language") or language, self.version)
                for m in movies]
        digests = [metadata_digest(d) for d in documents]
        rows: list = [None] * len(movies)
        request = {"hits": 0, "misses": 0, "reencoded": 0, "batches": 0}
        missing = []
        with self._lock:
            for p, (key, digest) in enumerate(zip(keys, digests)):
                entry, changed = self._lookup(key, digest)
                if entry is not None:
                    rows[p] = (entry["indices"], entry["values"])
                    request["hits"] += 1
                else:
                    missing.append(p)
                    request["reencoded" if changed else "misses"] += 1
        batch = self.budget["encode_batch"]
        for start in range(0, len(missing), batch):
            chunk = missing[start:start + batch]
            # Fitted vocabulary only: unseen words are ignored, nothing is refit or appended.
            encoded = normalize(self.engine.vectorizer.transform([documents[p] for p in chunk])).tocsr()
            request["batches"] += 1
            with self._lock:
                for offset, p in enumerate(chunk):
                    row = encoded[offset]
                    self._store(keys[p], digests[p], row)
                    rows[p] = (row.indices.astype(np.int32), row.data.astype(np.float64))
        with self._lock:
            for name in ("hits", "misses", "reencoded"):
                self.stats[name] += request[name]
        indptr = np.cumsum([0] + [len(r[0]) for r in rows])
        data = np.concatenate([r[1] for r in rows]) if rows else np.zeros(0)
        indices = np.concatenate([r[0] for r in rows]) if rows else np.zeros(0, dtype=np.int32)
        matrix = sparse.csr_matrix((data, indices, indptr), shape=(len(movies), width))
        return matrix, request

    def snapshot(self):
        with self._lock:
            return {"entries": len(self._entries), "bytes": int(self.bytes), "feature_version": self.version,
                    "limits": {"entries": self.budget["feature_cache_entries"], "bytes": self.budget["feature_cache_bytes"]},
                    **self.stats}

    def clear(self):
        with self._lock:
            self._entries.clear()
            self.bytes = 0
