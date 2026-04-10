"""
External integration tests for the memvid Rust sidecar (port 3031) and
Python backend integration.

These tests are SKIPPED automatically when the sidecar is not reachable on
localhost:3031. They are NOT fakes — they require the real Rust service to be
running. To run them locally:

    MEMORY_BACKEND=rust MEMORY_SERVICE_URL=http://localhost:3031 pytest \
        backend/tests/test_memvid_sidecar.py -v

TestPersistence additionally requires supervisorctl and is only valid in a
managed deployment environment.

Tests covered: ingest, retrieve (BM25), list, delete, persistence, TTL maintain.
"""
import shutil
import socket
import subprocess
import time

import pytest
import requests
import os


# ── Sidecar availability probe ────────────────────────────────────────────────

def _probe_sidecar() -> bool:
    try:
        with socket.create_connection(("localhost", 3031), timeout=1):
            return True
    except OSError:
        return False


SIDECAR_REACHABLE = os.environ.get("RUN_MEMVID_TESTS") == "1" and _probe_sidecar()

pytestmark = pytest.mark.skipif(
    not SIDECAR_REACHABLE,
    reason="set RUN_MEMVID_TESTS=1 and start memvid sidecar on localhost:3031 to run",
)

# ─────────────────────────────────────────────────────────────────────────────

SIDECAR_URL = "http://localhost:3031"
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

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
    """POST /memory/ingest"""

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
    """GET /memory/list"""

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
    """POST /memory/retrieve - BM25 scored retrieval"""

    @pytest.fixture(autouse=True, scope="class")
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
    """DELETE /memory/:id"""

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
    not shutil.which("supervisorctl"),
    reason="requires supervisorctl in PATH",
)
class TestPersistence:
    """Ingest → restart sidecar → list (records must survive)"""

    def test_ingest_survives_restart(self):
        unique_text = f"TEST_ persistence check text {int(time.time())}"
        r = ingest(unique_text)
        assert r.status_code == 200
        mid = r.json()["memory_id"]

        # Restart sidecar
        subprocess.run(
            ["sudo", "supervisorctl", "restart", "memvid-sidecar"],
            check=True,
            timeout=30,
        )
        time.sleep(3)  # wait for it to come up

        records = list_memories().json()["records"]
        ids = [rec["memory_id"] for rec in records]
        assert mid in ids, f"Memory {mid} not found after restart. Total: {len(ids)}"

    def test_delete_persists_across_restart(self):
        r = ingest(f"TEST_ delete-persist check {int(time.time())}")
        assert r.status_code == 200
        mid = r.json()["memory_id"]

        dr = delete_memory(mid)
        assert dr.status_code in (200, 204)

        # Restart sidecar
        subprocess.run(
            ["sudo", "supervisorctl", "restart", "memvid-sidecar"],
            check=True,
            timeout=30,
        )
        time.sleep(3)

        records = list_memories().json()["records"]
        ids = [rec["memory_id"] for rec in records]
        assert mid not in ids, "Deleted memory came back after restart"


# ── 6. Maintain (TTL) ─────────────────────────────────────────────────────────

class TestMaintain:
    """POST /memory/maintain"""

    def test_maintain_returns_200(self):
        r = requests.post(f"{SIDECAR_URL}/memory/maintain", timeout=10)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"


# ── 7. Python backend → sidecar integration ───────────────────────────────────

class TestPythonBackendIntegration:
    """POST /api/hca/run - end-to-end through Python FastAPI"""

    def test_hca_run_returns_200(self):
        if not BASE_URL:
            pytest.skip("REACT_APP_BACKEND_URL not set")
        payload = {"goal": "What facts are stored in memory?"}
        r = requests.post(f"{BASE_URL}/api/hca/run", json=payload, timeout=30)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_hca_run_response_has_output(self):
        if not BASE_URL:
            pytest.skip("REACT_APP_BACKEND_URL not set")
        payload = {"goal": "Test memory recall"}
        r = requests.post(f"{BASE_URL}/api/hca/run", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data  # non-empty response
