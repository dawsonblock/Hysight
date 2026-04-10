"""
Python MemoryController satisfying the HCA ↔ MemVid contract.

Drop-in replaceable with the Rust HTTP service via env vars:
  MEMORY_BACKEND=rust
  MEMORY_SERVICE_URL=http://localhost:3031
"""
from __future__ import annotations

import json
import logging
import math
import os
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .types import CandidateMemory, MaintenanceReport, RetrievalHit, RetrievalQuery

_BACKEND = os.environ.get("MEMORY_BACKEND", "python")
_SERVICE_URL = os.environ.get("MEMORY_SERVICE_URL", "")
_log = logging.getLogger(__name__)

# ── Lazy-loaded fastembed model ───────────────────────────────────────────────

_embedding_model = None


def _embed(text: str) -> Optional[List[float]]:
    """Return a 384-dim embedding vector, or None if fastembed is unavailable."""
    global _embedding_model
    try:
        if _embedding_model is None:
            from fastembed import TextEmbedding  # type: ignore
            _embedding_model = TextEmbedding("BAAI/bge-small-en-v1.5")
        vecs = list(_embedding_model.embed([text]))
        return vecs[0].tolist()
    except Exception as exc:
        _log.debug("Embedding skipped: %s", exc)
        return None


class MemoryController:
    """
    In-process Python implementation of the memory contract.

    Satisfies the three contract endpoints:
      ingest   → POST /memory/ingest
      retrieve → POST /memory/retrieve
      maintain → POST /memory/maintain

    When MEMORY_BACKEND=rust + MEMORY_SERVICE_URL is set, every call is
    forwarded to the Rust memvid HTTP sidecar instead (transparent swap).
    """

    def __init__(self, storage_dir: Optional[str] = None) -> None:
        self._records: List[Dict[str, Any]] = []
        self._storage_dir = storage_dir
        if storage_dir:
            Path(storage_dir).mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    # ── persistence helpers ───────────────────────────────────────────────────

    def _disk_path(self) -> Optional[Path]:
        return Path(self._storage_dir) / "memories.jsonl" if self._storage_dir else None

    def _load_from_disk(self) -> None:
        path = self._disk_path()
        if path is None or not path.exists():
            return
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        self._records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass

    def _append_to_disk(self, record: Dict[str, Any]) -> None:
        path = self._disk_path()
        if path is None:
            return
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, default=str) + "\n")

    # ── BM25-lite scoring ─────────────────────────────────────────────────────

    @staticmethod
    def _bm25(query: str, text: str) -> float:
        k1, b, avg = 1.5, 0.75, 10.0
        q_terms = query.lower().split()
        d_terms = text.lower().split()
        if not q_terms or not d_terms:
            return 0.0
        tf_map: Dict[str, int] = defaultdict(int)
        for t in d_terms:
            tf_map[t] += 1
        score = 0.0
        for term in q_terms:
            tf = tf_map[term]
            if tf == 0:
                continue
            # BM25 TF component (no corpus IDF — uses term overlap as signal)
            numer = tf * (k1 + 1)
            denom = tf + k1 * (1 - b + b * len(d_terms) / avg)
            score += numer / denom
        return max(0.0, score)

    # ── public contract methods ───────────────────────────────────────────────

    def ingest(self, candidate: CandidateMemory) -> Optional[str]:
        """Store a candidate memory. Returns assigned memory_id."""
        if _BACKEND == "rust" and _SERVICE_URL:
            return self._rust_ingest(candidate)
        memory_id = str(uuid.uuid4())
        record: Dict[str, Any] = {
            "memory_id": memory_id,
            "raw_text": candidate.raw_text,
            "memory_type": candidate.memory_type,
            "memory_layer": "trace",
            "entity": candidate.entity,
            "slot": candidate.slot,
            "value": candidate.value,
            "confidence": candidate.confidence,
            "salience": candidate.salience,
            "scope": candidate.scope,
            "run_id": candidate.run_id,
            "workflow_key": candidate.workflow_key,
            "tags": candidate.tags,
            "metadata": candidate.metadata,
            "source": candidate.source.model_dump(),
            "stored_at": datetime.now(timezone.utc).isoformat(),
            "expired": False,
        }
        self._records.append(record)
        self._append_to_disk(record)
        return memory_id

    def retrieve(self, query: RetrievalQuery) -> List[RetrievalHit]:
        """Retrieve memories matching query using BM25 scoring."""
        if _BACKEND == "rust" and _SERVICE_URL:
            return self._rust_retrieve(query)
        candidates = [
            r for r in self._records
            if (not r.get("expired") or query.include_expired)
            and (query.memory_layer is None or r.get("memory_layer") == query.memory_layer)
            and (query.scope is None or r.get("scope") == query.scope)
            and (query.run_id is None or r.get("run_id") == query.run_id)
        ]
        scored = [
            (self._bm25(query.query_text, r["raw_text"]), r)
            for r in candidates
        ]
        scored = [(s, r) for s, r in scored if s > 0.0]
        scored.sort(key=lambda x: x[0], reverse=True)
        hits = []
        for score, rec in scored[: query.top_k]:
            stored_raw = rec.get("stored_at", datetime.now(timezone.utc).isoformat())
            stored_at = (
                datetime.fromisoformat(stored_raw)
                if isinstance(stored_raw, str)
                else stored_raw
            )
            hits.append(
                RetrievalHit(
                    memory_id=rec.get("memory_id"),
                    memory_layer=rec.get("memory_layer", "trace"),
                    memory_type=rec.get("memory_type"),
                    entity=rec.get("entity"),
                    slot=rec.get("slot"),
                    value=rec.get("value"),
                    text=rec.get("raw_text", ""),
                    score=score,
                    confidence=rec.get("confidence", 0.5),
                    stored_at=stored_at,
                    expired=rec.get("expired", False),
                    metadata=rec.get("metadata", {}),
                )
            )
        return hits

    def list_records(
        self,
        memory_type: Optional[str] = None,
        scope: Optional[str] = None,
        include_expired: bool = False,
        limit: int = 50,
        offset: int = 0,
    ):
        """Return paginated list of records, newest first. Returns (records, total)."""
        if _BACKEND == "rust" and _SERVICE_URL:
            return self._rust_list(memory_type, scope, include_expired, limit, offset)
        filtered = [
            r for r in self._records
            if (include_expired or not r.get("expired"))
            and (memory_type is None or r.get("memory_type") == memory_type)
            and (scope is None or r.get("scope") == scope)
        ]
        filtered.sort(key=lambda r: r.get("stored_at", ""), reverse=True)
        return filtered[offset : offset + limit], len(filtered)

    def delete_record(self, memory_id: str) -> bool:
        """Mark a record as expired (soft delete). Returns True if found."""
        if _BACKEND == "rust" and _SERVICE_URL:
            return self._rust_delete(memory_id)
        before = len(self._records)
        self._records = [r for r in self._records if r.get("memory_id") != memory_id]
        deleted = len(self._records) < before
        if deleted and self._storage_dir:
            self._rewrite_disk()
        return deleted

    def _rewrite_disk(self) -> None:
        path = self._disk_path()
        if path is None:
            return
        with open(path, "w", encoding="utf-8") as f:
            for rec in self._records:
                f.write(json.dumps(rec, default=str) + "\n")

    def maintain(self) -> MaintenanceReport:
        """Expire stale records and return maintenance stats."""
        if _BACKEND == "rust" and _SERVICE_URL:
            return self._rust_maintain()
        now = datetime.now(timezone.utc)
        expired_ids: List[str] = []
        durable = 0
        for rec in self._records:
            if rec.get("expired"):
                expired_ids.append(rec["memory_id"])
                continue
            stored_raw = rec.get("stored_at")
            if stored_raw:
                try:
                    age = now - datetime.fromisoformat(stored_raw)
                    if age > timedelta(days=7):
                        rec["expired"] = True
                        expired_ids.append(rec["memory_id"])
                        continue
                except Exception:
                    pass
            if rec.get("memory_type") in {"fact", "episode", "preference", "goalstate", "procedure"}:
                durable += 1
        return MaintenanceReport(
            durable_memory_count=durable,
            expired_count=len(expired_ids),
            expired_ids=expired_ids,
            compaction_supported=False,
            compactor_status="unsupported_python_backend",
        )

    # ── Rust HTTP delegation ──────────────────────────────────────────────────

    def _rust_ingest(self, candidate: CandidateMemory) -> Optional[str]:
        import httpx
        r = httpx.post(f"{_SERVICE_URL}/memory/ingest", json=candidate.model_dump(mode="json"), timeout=10)
        r.raise_for_status()
        return r.json().get("memory_id")

    def _rust_retrieve(self, query: RetrievalQuery) -> List[RetrievalHit]:
        import httpx
        r = httpx.post(f"{_SERVICE_URL}/memory/retrieve", json=query.model_dump(mode="json"), timeout=10)
        r.raise_for_status()
        return [RetrievalHit.model_validate(h) for h in r.json().get("hits", [])]

    def _rust_maintain(self) -> MaintenanceReport:
        import httpx
        r = httpx.post(f"{_SERVICE_URL}/memory/maintain", json={}, timeout=10)
        r.raise_for_status()
        return MaintenanceReport.model_validate(r.json())

    def _rust_list(self, memory_type, scope, include_expired, limit, offset):
        import httpx
        params = {"limit": limit, "offset": offset, "include_expired": str(include_expired).lower()}
        if memory_type:
            params["memory_type"] = memory_type
        if scope:
            params["scope"] = scope
        r = httpx.get(f"{_SERVICE_URL}/memory/list", params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        return data.get("records", []), data.get("total", 0)

    def _rust_delete(self, memory_id: str) -> bool:
        import httpx
        r = httpx.delete(f"{_SERVICE_URL}/memory/{memory_id}", timeout=10)
        r.raise_for_status()
        return r.json().get("deleted", False)
