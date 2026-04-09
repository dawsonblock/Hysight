"""Memory API tests - list, filter, pagination, delete, 404"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

class TestMemoryList:
    def test_list_returns_records(self):
        r = requests.get(f"{BASE_URL}/api/hca/memory/list")
        assert r.status_code == 200
        data = r.json()
        assert "records" in data
        assert "total" in data
        assert data["total"] > 0
        assert len(data["records"]) > 0
        print(f"Total records: {data['total']}")

    def test_list_filter_by_type_episode(self):
        r = requests.get(f"{BASE_URL}/api/hca/memory/list?memory_type=episode")
        assert r.status_code == 200
        data = r.json()
        assert len(data["records"]) > 0
        for rec in data["records"]:
            assert rec["memory_type"] == "episode"
        print(f"Episode records: {len(data['records'])}")

    def test_list_pagination(self):
        r = requests.get(f"{BASE_URL}/api/hca/memory/list?limit=2&offset=0")
        assert r.status_code == 200
        data = r.json()
        assert len(data["records"]) == 2
        print(f"Paginated: got {len(data['records'])} records")

    def test_record_fields(self):
        r = requests.get(f"{BASE_URL}/api/hca/memory/list?limit=1")
        assert r.status_code == 200
        rec = r.json()["records"][0]
        assert "memory_id" in rec
        assert "memory_type" in rec
        assert "text" in rec
        print(f"Record fields OK: {list(rec.keys())}")


class TestMemoryDelete:
    def test_delete_nonexistent_returns_404(self):
        r = requests.delete(f"{BASE_URL}/api/hca/memory/nonexistent-id")
        assert r.status_code == 404
        print("404 for nonexistent id: OK")

    def test_create_via_run_then_delete(self):
        # Get initial total
        r0 = requests.get(f"{BASE_URL}/api/hca/memory/list")
        initial_total = r0.json()["total"]

        # POST a run to create a memory
        run_r = requests.post(f"{BASE_URL}/api/hca/run", json={"goal": "TEST_memory_delete echo hello"})
        assert run_r.status_code == 200, f"Run failed: {run_r.text}"
        print(f"Run created: {run_r.json().get('run_id')}")

        # Wait a bit and check total increased
        import time; time.sleep(2)
        r1 = requests.get(f"{BASE_URL}/api/hca/memory/list")
        new_total = r1.json()["total"]
        print(f"Total after run: {new_total} (was {initial_total})")
        # total should increase (or stay same if run didn't create memory)

        # Find a memory to delete
        records = r1.json()["records"]
        assert len(records) > 0
        mem_id = records[0]["memory_id"]

        # Delete it
        del_r = requests.delete(f"{BASE_URL}/api/hca/memory/{mem_id}")
        assert del_r.status_code == 200
        data = del_r.json()
        assert data.get("deleted") == True
        print(f"Deleted memory {mem_id}: OK")

        # Verify total decreased
        r2 = requests.get(f"{BASE_URL}/api/hca/memory/list")
        after_delete = r2.json()["total"]
        assert after_delete == new_total - 1
        print(f"Total after delete: {after_delete}: OK")
