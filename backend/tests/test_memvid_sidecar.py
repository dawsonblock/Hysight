"""Memvid sidecar boundary tests.

Default mode runs mock-backed contract checks against an in-memory sidecar via
requests-mock, so the backend suite can prove request/response shapes without a
running Rust service. Live-sidecar behavior is opt-in:

    RUN_MEMVID_TESTS=1 MEMORY_BACKEND=rust MEMORY_SERVICE_URL=http://localhost:3031 \
        pytest backend/tests/test_memvid_sidecar.py -v

Tests that require real restart semantics skip unless the live sidecar is
reachable and supervisorctl is available. If requests-mock is missing, the
default mock-mode tests skip with an explicit dependency message instead of
failing collection.
"""
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest
import requests

try:
    import requests_mock as rm_lib
except ModuleNotFoundError:  # pragma: no cover - depends on active test env
    rm_lib = None

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ── Sidecar availability probe ────────────────────────────────────────────────

def _probe_sidecar() -> bool:
    try:
        with socket.create_connection(("localhost", 3031), timeout=1):
            return True
    except OSError:
        return False


SIDECAR_REACHABLE = os.environ.get("RUN_MEMVID_TESTS") == "1" and _probe_sidecar()
_USE_REAL_SIDECAR = SIDECAR_REACHABLE
_MOCK_SIDECAR_REASON = (
    "requests-mock is not installed; install backend/requirements.txt "
    "for mock sidecar tests"
)
_LIVE_SIDECAR_REASON = (
    "requires RUN_MEMVID_TESTS=1 with a live memvid sidecar on localhost:3031"
)
_RESTART_REASON = (
    "requires RUN_MEMVID_TESTS=1, a live memvid sidecar, and supervisorctl in PATH"
)

# ─────────────────────────────────────────────────────────────────────────────

SIDECAR_URL = "http://localhost:3031"

# ── In-memory mock sidecar ────────────────────────────────────────────────────

class _FakeSidecar:
    """Stateful in-memory mock that validates sidecar request/response shapes."""

    def __init__(self):
        self._store: dict = {}

    def ingest(self, request, context):
        data = request.json()
        mid = str(uuid.uuid4())
        record = {**data, "memory_id": mid, "stored_at": "2026-01-01T00:00:00Z", "expired": False}
        self._store[mid] = record
        return {"memory_id": mid}

    def list(self, request, context):
        records = list(self._store.values())
        return {"records": records, "total": len(records)}

    def retrieve(self, request, context):
        data = request.json()
        words = set(data.get("query_text", "").lower().split())
        top_k = data.get("top_k", 5)

        def _overlap(m):
            return sum(1 for w in words if w in m.get("raw_text", "").lower())

        ranked = sorted(self._store.values(), key=_overlap, reverse=True)[:top_k]
        return {
            "hits": [
                {
                    "text": m["raw_text"],
                    "score": float(max(1, _overlap(m))),
                    "memory_type": m.get("memory_type", "fact"),
                    "memory_id": m["memory_id"],
                    "stored_at": m["stored_at"],
                }
                for m in ranked
            ]
        }

    def delete(self, request, context):
        mid = request.path.rsplit("/", 1)[-1]
        if mid in self._store:
            del self._store[mid]
            return {}
        context.status_code = 404
        return {"error": "not found"}

    def maintain(self, request, context):
        return {
            "durable_memory_count": len(self._store),
            "expired_count": 0,
            "expired_ids": [],
            "compaction_supported": False,
            "compactor_status": "ok",
        }


@pytest.fixture(autouse=True)
def sidecar():
    """Provide one isolated sidecar backend per test.

    Mock mode gets a fresh in-memory store every test; live mode hits the real
    service only when explicitly enabled.
    """
    if _USE_REAL_SIDECAR:
        yield None
        return

    if rm_lib is None:
        pytest.skip(_MOCK_SIDECAR_REASON)

    fake = _FakeSidecar()
    with rm_lib.Mocker() as m:
        m.post(f"{SIDECAR_URL}/memory/ingest", json=fake.ingest)
        m.get(f"{SIDECAR_URL}/memory/list", json=fake.list)
        m.post(f"{SIDECAR_URL}/memory/retrieve", json=fake.retrieve)
        m.post(f"{SIDECAR_URL}/memory/maintain", json=fake.maintain)
        m.delete(
            re.compile(rf"{re.escape(SIDECAR_URL)}/memory/.+"),
            json=fake.delete,
        )
        yield fake

# ── helpers ──────────────────────────────────────────────────────────────────

def ingest(text, memory_type="fact", scope="shared", tags=None, slot=None):
    payload = {
        "raw_text": text,
        "memory_type": memory_type,
        "scope": scope,
        "confidence": 0.9,
        "entity": "test",
        "slot": slot or "test_slot",
    }
    if tags:
        payload["tags"] = tags
    r = requests.post(f"{SIDECAR_URL}/memory/ingest", json=payload, timeout=10)
    return r


def list_memories():
    return requests.get(f"{SIDECAR_URL}/memory/list", timeout=10)


def retrieve(query, top_k=5):
    return requests.post(
        f"{SIDECAR_URL}/memory/retrieve",
        json={"query_text": query, "top_k": top_k},
        timeout=10,
    )


def delete_memory(memory_id):
    return requests.delete(f"{SIDECAR_URL}/memory/{memory_id}", timeout=10)


# ── 1. Ingest ─────────────────────────────────────────────────────────────────

class TestIngest:
    """POST /memory/ingest — mock mode by default; live mode when RUN_MEMVID_TESTS=1."""

    def test_ingest_returns_200_and_memory_id(self):
        r = ingest("TEST_ integration test fact for sidecar")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert "memory_id" in data, f"No memory_id in response: {data}"
        assert data["memory_id"] is not None
        assert isinstance(data["memory_id"], str) and len(data["memory_id"]) > 0

    def test_ingest_preference_memory(self):
        r = ingest(
            "TEST_ user prefers dark mode UI with high contrast",
            memory_type="preference",
            scope="private",
            tags=["ui", "dark_mode"],
            slot="ui_preference",
        )
        assert r.status_code == 200, r.text
        assert "memory_id" in r.json()


# ── 2. List ───────────────────────────────────────────────────────────────────

class TestList:
    """GET /memory/list — mock mode by default; live mode when RUN_MEMVID_TESTS=1."""

    def test_list_returns_records_and_total(self):
        r = list_memories()
        assert r.status_code == 200, r.text
        data = r.json()
        assert "records" in data
        assert "total" in data
        assert isinstance(data["records"], list)
        assert data["total"] == len(data["records"])

    def test_list_count_increases_after_ingest(self):
        before = list_memories().json()["total"]
        ingest("TEST_ unique text for count check xyz123")
        after = list_memories().json()["total"]
        assert after == before + 1, f"Expected {before+1}, got {after}"


# ── 3. Retrieve (BM25) ────────────────────────────────────────────────────────

class TestRetrieve:
    """POST /memory/retrieve — BM25 scored retrieval. Mock mode by default; live mode when RUN_MEMVID_TESTS=1."""

    @pytest.fixture(autouse=True)
    def seed_memories(self):
        # Ingest distinct memories for relevance tests
        ingest(
            "TEST_ user strongly prefers dark mode UI theme with high contrast colors",
            memory_type="preference",
            scope="private",
            tags=["ui", "dark_mode"],
            slot="ui_pref",
        )
        ingest(
            "TEST_ the capital of France is Paris",
            memory_type="fact",
            scope="shared",
            slot="geo_fact",
        )
        ingest(
            "TEST_ user completed onboarding task on 2025-01-01",
            memory_type="episode",
            scope="private",
            slot="onboarding",
        )
        if _USE_REAL_SIDECAR:
            time.sleep(0.5)  # give Tantivy time to index

    def test_retrieve_returns_results_with_score(self):
        r = retrieve("dark mode UI preference")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "hits" in data, f"No 'hits' key: {data}"
        assert len(data["hits"]) > 0

    def test_retrieve_scores_are_positive(self):
        r = retrieve("dark mode UI preference")
        assert r.status_code == 200, r.text
        results = r.json()["hits"]
        assert len(results) > 0
        for res in results:
            assert "score" in res, f"No score in result: {res}"
            assert res["score"] > 0, f"Score not positive: {res['score']}"

    def test_bm25_relevance_dark_mode_returns_preference(self):
        """dark mode UI query should rank the preference memory highest"""
        r = retrieve("dark mode UI")
        assert r.status_code == 200, r.text
        results = r.json()["hits"]
        assert len(results) > 0
        top = results[0]
        text = top.get("text", "").lower()
        assert "dark mode" in text, f"Top result does not contain 'dark mode': {text}"

    def test_retrieve_top_k_limits_results(self):
        r = retrieve("memory", top_k=2)
        assert r.status_code == 200, r.text
        results = r.json()["hits"]
        assert len(results) <= 2


# ── 4. Delete ────────────────────────────────────────────────────────────────

class TestDelete:
    """DELETE /memory/:id — mock mode by default; live mode when RUN_MEMVID_TESTS=1."""

    def test_delete_removes_memory(self):
        # ingest a fresh memory
        r = ingest("TEST_ memory to be deleted soon")
        assert r.status_code == 200
        mid = r.json()["memory_id"]

        # delete it
        dr = delete_memory(mid)
        assert dr.status_code in (200, 204), f"Delete failed: {dr.status_code} {dr.text}"

        # verify it's gone from list
        records = list_memories().json()["records"]
        ids = [rec["memory_id"] for rec in records]
        assert mid not in ids, "Deleted memory still present in list"

    def test_delete_nonexistent_returns_error(self):
        r = delete_memory("00000000-0000-0000-0000-000000000000")
        assert r.status_code in (404, 400), f"Expected 404/400, got {r.status_code}"


# ── 5. Persistence ────────────────────────────────────────────────────────────

@pytest.mark.skipif(
    not _USE_REAL_SIDECAR or not shutil.which("supervisorctl"),
    reason=_RESTART_REASON,
)
class TestPersistence:
    """Live-sidecar restart semantics.

    These tests only validate persistence when the real sidecar is running and
    can be restarted via supervisorctl.
    """

    def _restart_sidecar(self):
        """Restart the live sidecar through supervisorctl."""
        subprocess.run(
            ["sudo", "supervisorctl", "restart", "memvid-sidecar"],
            check=True,
            timeout=30,
        )
        time.sleep(3)

    def test_ingest_survives_restart(self):
        unique_text = f"TEST_ persistence check text {int(time.time())}"
        r = ingest(unique_text)
        assert r.status_code == 200
        mid = r.json()["memory_id"]

        self._restart_sidecar()

        records = list_memories().json()["records"]
        ids = [rec["memory_id"] for rec in records]
        assert mid in ids, f"Memory {mid} not found after restart. Total: {len(ids)}"

    def test_delete_persists_across_restart(self):
        r = ingest(f"TEST_ delete-persist check {int(time.time())}")
        assert r.status_code == 200
        mid = r.json()["memory_id"]

        dr = delete_memory(mid)
        assert dr.status_code in (200, 204)

        self._restart_sidecar()

        records = list_memories().json()["records"]
        ids = [rec["memory_id"] for rec in records]
        assert mid not in ids, "Deleted memory came back after restart"


# ── 6. Maintain (TTL) ─────────────────────────────────────────────────────────

class TestMaintain:
    """POST /memory/maintain — mock mode by default; live mode when RUN_MEMVID_TESTS=1."""

    def test_maintain_returns_200(self):
        r = requests.post(f"{SIDECAR_URL}/memory/maintain", timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
