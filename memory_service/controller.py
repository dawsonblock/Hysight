"""
Python MemoryController satisfying the HCA ↔ MemVid contract.

Drop-in replaceable with the Rust HTTP service via env vars:
  MEMORY_BACKEND=rust
  MEMORY_SERVICE_URL=http://localhost:3031
"""
from __future__ import annotations

import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from .config import (
    MemorySettings,
    probe_memory_service,
    validate_memory_backend_startup,
)
from .types import (
    CandidateMemory,
    MaintenanceReport,
    MemoryListItem,
    MemoryListResponse,
    RetrievalHit,
    RetrievalQuery,
    RetrievalResponse,
)

_log = logging.getLogger(__name__)


class MemoryBackendError(RuntimeError):
    """Raised when the configured memory backend cannot serve a request."""


def _coerce_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    return datetime.now(timezone.utc)


def _safe_parse_stored_at(record: Dict[str, Any]) -> datetime:
    try:
        return _coerce_datetime(record.get("stored_at"))
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


def _normalize_list_item(record: Dict[str, Any]) -> MemoryListItem:
    return MemoryListItem(
        memory_id=str(record.get("memory_id", "")),
        memory_layer=str(record.get("memory_layer") or "trace"),
        memory_type=record.get("memory_type", "trace"),
        text=record.get("text") or record.get("raw_text") or "",
        scope=record.get("scope", "private"),
        confidence=record.get("confidence", 0.5),
        stored_at=_safe_parse_stored_at(record),
        expired=bool(record.get("expired", False)),
        run_id=record.get("run_id"),
    )


def _normalize_hit(record: Dict[str, Any], score: float) -> RetrievalHit:
    return RetrievalHit(
        memory_id=record.get("memory_id"),
        belief_id=record.get("belief_id"),
        memory_layer=record.get("memory_layer", "trace"),
        memory_type=record.get("memory_type"),
        entity=record.get("entity"),
        slot=record.get("slot"),
        value=record.get("value"),
        text=record.get("text") or record.get("raw_text") or "",
        score=score,
        confidence=record.get("confidence", 0.5),
        stored_at=_safe_parse_stored_at(record),
        expired=bool(record.get("expired", False)),
        metadata=record.get("metadata", {}),
    )


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

    def __init__(
        self,
        storage_dir: Optional[str] = None,
        settings: Optional[MemorySettings] = None,
    ) -> None:
        self._settings = settings or validate_memory_backend_startup()
        if storage_dir is not None:
            self._settings = MemorySettings(
                backend=self._settings.backend,
                storage_dir=Path(storage_dir),
                service_url=self._settings.service_url,
            )
        if self._settings.uses_sidecar:
            probe_memory_service(self._settings)
        self._records: List[Dict[str, Any]] = []
        self._storage_dir = str(self._settings.storage_dir)
        if not self._settings.uses_sidecar:
            self._settings.storage_dir.mkdir(parents=True, exist_ok=True)
            self._load_from_disk()

    # Persistence helpers.

    def _disk_path(self) -> Optional[Path]:
        if not self._storage_dir:
            return None
        return Path(self._storage_dir) / "memories.jsonl"

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

    # BM25-lite scoring.

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

    # Public contract methods.

    def ingest(self, candidate: CandidateMemory) -> Optional[str]:
        """Store a candidate memory. Returns assigned memory_id."""
        if self._settings.uses_sidecar:
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
        if self._settings.uses_sidecar:
            return self._rust_retrieve(query)
        candidates = [
            r for r in self._records
            if (not r.get("expired") or query.include_expired)
            and (
                query.memory_layer is None
                or r.get("memory_layer") == query.memory_layer
            )
            and (query.scope is None or r.get("scope") == query.scope)
            and (query.run_id is None or r.get("run_id") == query.run_id)
        ]
        scored = [
            (self._bm25(query.query_text, r["raw_text"]), r)
            for r in candidates
        ]
        scored = [(s, r) for s, r in scored if s > 0.0]
        scored.sort(key=lambda x: x[0], reverse=True)
        hits: List[RetrievalHit] = []
        for score, rec in scored[: query.top_k]:
            hits.append(_normalize_hit(rec, score))
        return hits

    def list_records(
        self,
        memory_type: Optional[str] = None,
        scope: Optional[str] = None,
        include_expired: bool = False,
        limit: int = 50,
        offset: int = 0,
    ):
        """Return a paginated list of records, newest first."""
        if self._settings.uses_sidecar:
            return self._rust_list(
                memory_type,
                scope,
                include_expired,
                limit,
                offset,
            )
        filtered = [
            r for r in self._records
            if (include_expired or not r.get("expired"))
            and (memory_type is None or r.get("memory_type") == memory_type)
            and (scope is None or r.get("scope") == scope)
        ]
        filtered.sort(key=lambda r: r.get("stored_at", ""), reverse=True)
        records = [
            _normalize_list_item(r)
            for r in filtered[offset: offset + limit]
        ]
        return records, len(filtered)

    def delete_record(self, memory_id: str) -> bool:
        """Delete a record by ID. Returns True if found."""
        if self._settings.uses_sidecar:
            return self._rust_delete(memory_id)
        before = len(self._records)
        self._records = [
            r for r in self._records if r.get("memory_id") != memory_id
        ]
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
        if self._settings.uses_sidecar:
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
                except (TypeError, ValueError):
                    pass
            if rec.get("memory_type") in {
                "fact",
                "episode",
                "preference",
                "goalstate",
                "procedure",
            }:
                durable += 1
        return MaintenanceReport(
            durable_memory_count=durable,
            expired_count=len(expired_ids),
            expired_ids=expired_ids,
            compaction_supported=False,
            compactor_status="unsupported_python_backend",
        )

    # Rust HTTP delegation.

    def _request(self, method: str, path: str, **kwargs: Any):
        try:
            import httpx
        except ImportError as exc:  # pragma: no cover - dependency validation
            raise MemoryBackendError(
                "httpx must be installed when MEMORY_BACKEND=rust"
            ) from exc

        try:
            response = httpx.request(
                method,
                self._settings.endpoint(path),
                timeout=10,
                **kwargs,
            )
            response.raise_for_status()
            return response
        except httpx.HTTPError as exc:
            raise MemoryBackendError(
                f"Rust memory backend request failed: {exc}"
            ) from exc

    @staticmethod
    def _parse_json_response(response) -> Dict[str, Any]:
        try:
            return response.json()
        except ValueError as exc:
            raise MemoryBackendError(
                "Rust memory backend returned invalid JSON"
            ) from exc

    def _rust_ingest(self, candidate: CandidateMemory) -> Optional[str]:
        response = self._request(
            "POST",
            "/memory/ingest",
            json=candidate.model_dump(mode="json"),
        )
        return self._parse_json_response(response).get("memory_id")

    def _rust_retrieve(self, query: RetrievalQuery) -> List[RetrievalHit]:
        response = self._request(
            "POST",
            "/memory/retrieve",
            json=query.model_dump(mode="json"),
        )
        payload = self._parse_json_response(response)
        try:
            return RetrievalResponse.model_validate(payload).hits
        except ValidationError as exc:
            raise MemoryBackendError(
                "Rust memory backend returned an invalid retrieve payload"
            ) from exc

    def _rust_maintain(self) -> MaintenanceReport:
        response = self._request("POST", "/memory/maintain", json={})
        try:
            return MaintenanceReport.model_validate(
                self._parse_json_response(response)
            )
        except ValidationError as exc:
            raise MemoryBackendError(
                "Rust memory backend returned an invalid maintenance payload"
            ) from exc

    def _rust_list(self, memory_type, scope, include_expired, limit, offset):
        params = {
            "limit": limit,
            "offset": offset,
            "include_expired": str(include_expired).lower(),
        }
        if memory_type:
            params["memory_type"] = memory_type
        if scope:
            params["scope"] = scope
        response = self._request("GET", "/memory/list", params=params)
        payload = self._parse_json_response(response)
        try:
            list_response = MemoryListResponse.model_validate(
                {
                    "records": [
                        _normalize_list_item(record).model_dump(mode="json")
                        for record in payload.get("records", [])
                    ],
                    "total": payload.get("total", 0),
                }
            )
        except ValidationError as exc:
            raise MemoryBackendError(
                "Rust memory backend returned an invalid list payload"
            ) from exc
        return list_response.records, list_response.total

    def _rust_delete(self, memory_id: str) -> bool:
        response = self._request("DELETE", f"/memory/{memory_id}")
        return bool(self._parse_json_response(response).get("deleted", False))
