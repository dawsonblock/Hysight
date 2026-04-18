"""Live sidecar parity tests for the rust-backed memory authority.

These tests stay out of the default baseline proof surface. They compare the
public MemoryController contract across the local python backend and a real
sidecar, and they verify explicit failure semantics when the sidecar restarts
or disappears.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.server import create_app
from memory_service import CandidateMemory, RetrievalQuery
from memory_service.config import MemorySettings
from memory_service.controller import MemoryController
pytestmark = [pytest.mark.integration, pytest.mark.live]


def _tail_log(path: Path, *, lines: int = 40) -> str:
    if not path.exists():
        return "sidecar log file does not exist"
    content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(content[-lines:])


def _wait_for_health(service_url: str, *, timeout_seconds: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            response = requests.get(f"{service_url}/health", timeout=1)
        except requests.RequestException:
            time.sleep(0.25)
            continue
        if response.status_code == 200:
            return True
        time.sleep(0.25)
    return False


def _pick_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as candidate:
        candidate.bind(("127.0.0.1", 0))
        candidate.listen(1)
        return int(candidate.getsockname()[1])


def _sidecar_command() -> list[str]:
    release_binary = ROOT / "memvid_service" / "target" / "release" / "memvid-sidecar"
    if release_binary.exists():
        return [str(release_binary)]
    return [
        "cargo",
        "run",
        "--manifest-path",
        "memvid_service/Cargo.toml",
        "--release",
    ]


@dataclass
class ManagedSidecar:
    port: int
    data_dir: Path
    log_path: Path
    process: subprocess.Popen[str] | None = None
    _log_handle: object | None = field(default=None, init=False, repr=False)

    @property
    def service_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def start(self) -> None:
        if self.process is not None and self.process.poll() is None:
            return

        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_handle = self.log_path.open("a", encoding="utf-8")
        env = dict(os.environ)
        env["MEMORY_SERVICE_PORT"] = str(self.port)
        env["MEMORY_DATA_DIR"] = str(self.data_dir)
        self.process = subprocess.Popen(
            _sidecar_command(),
            cwd=ROOT,
            env=env,
            stdout=self._log_handle,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        if not _wait_for_health(self.service_url):
            self.stop()
            raise RuntimeError(
                "Managed sidecar did not become healthy.\n"
                f"{_tail_log(self.log_path)}"
            )

    def stop(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        self.process = None
        if self._log_handle is not None:
            self._log_handle.close()
            self._log_handle = None

    def restart(self) -> None:
        self.stop()
        self.start()


@pytest.fixture()
def managed_sidecar(tmp_path):
    if not shutil.which("cargo") and not (
        ROOT / "memvid_service" / "target" / "release" / "memvid-sidecar"
    ).exists():
        pytest.skip("requires cargo or a prebuilt memvid-sidecar binary")

    sidecar = ManagedSidecar(
        port=_pick_free_port(),
        data_dir=tmp_path / "sidecar-data",
        log_path=tmp_path / "sidecar.log",
    )
    sidecar.start()
    try:
        yield sidecar
    finally:
        sidecar.stop()


@pytest.fixture()
def rust_app_client(managed_sidecar, tmp_path, monkeypatch):
    storage_root = tmp_path / "storage"
    monkeypatch.setenv("MEMORY_BACKEND", "rust")
    monkeypatch.setenv("MEMORY_SERVICE_URL", managed_sidecar.service_url)
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("MEMORY_STORAGE_DIR", str(storage_root / "memory"))
    monkeypatch.delenv("MONGO_URL", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    import memory_service.singleton as memory_singleton

    memory_singleton._controller = None
    with TestClient(create_app()) as client:
        yield client
    memory_singleton._controller = None


def _local_controller(tmp_path, monkeypatch) -> MemoryController:
    storage_root = tmp_path / "local-storage"
    memory_dir = storage_root / "memory"
    monkeypatch.setenv("MEMORY_BACKEND", "python")
    monkeypatch.delenv("MEMORY_SERVICE_URL", raising=False)
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("MEMORY_STORAGE_DIR", str(memory_dir))
    return MemoryController(storage_dir=str(memory_dir))


def _rust_controller(service_url: str, storage_dir: Path) -> MemoryController:
    return MemoryController(
        settings=MemorySettings(
            backend="rust",
            storage_dir=storage_dir,
            service_url=service_url,
        )
    )


def test_live_sidecar_controller_matches_local_memory_contract(
    managed_sidecar,
    tmp_path,
    monkeypatch,
):
    local_controller = _local_controller(tmp_path, monkeypatch)
    rust_controller = _rust_controller(
        managed_sidecar.service_url,
        tmp_path / "unused-rust-storage",
    )

    local_memory_id = local_controller.ingest(
        CandidateMemory(
            raw_text="sidecar parity alpha text",
            memory_type="fact",
            scope="shared",
        )
    )
    rust_memory_id = rust_controller.ingest(
        CandidateMemory(
            raw_text="sidecar parity alpha text",
            memory_type="fact",
            scope="shared",
        )
    )

    local_records, local_total = local_controller.list_records()
    rust_records, rust_total = rust_controller.list_records()
    assert local_total == 1
    assert rust_total == 1
    assert local_records[0].text == rust_records[0].text == "sidecar parity alpha text"

    local_hits = local_controller.retrieve(
        RetrievalQuery(query_text="parity alpha", top_k=5)
    )
    rust_hits = rust_controller.retrieve(
        RetrievalQuery(query_text="parity alpha", top_k=5)
    )
    assert [hit.text for hit in local_hits] == ["sidecar parity alpha text"]
    assert [hit.text for hit in rust_hits] == ["sidecar parity alpha text"]

    local_report = local_controller.maintain()
    rust_report = rust_controller.maintain()
    assert local_report.durable_memory_count == rust_report.durable_memory_count == 1
    assert local_report.expired_count == rust_report.expired_count == 0
    assert local_report.expired_ids == rust_report.expired_ids == []
    assert local_report.compaction_supported is rust_report.compaction_supported is False

    assert local_controller.delete_record(local_memory_id) is True
    assert rust_controller.delete_record(rust_memory_id) is True
    assert local_controller.delete_record("00000000-0000-0000-0000-000000000000") is False
    assert rust_controller.delete_record("00000000-0000-0000-0000-000000000000") is False


def test_rust_backend_delete_missing_matches_local_404(app_client, rust_app_client):
    local_response = app_client.delete("/api/hca/memory/nonexistent-id")
    rust_response = rust_app_client.delete("/api/hca/memory/nonexistent-id")

    assert local_response.status_code == 404
    assert rust_response.status_code == 404
    assert rust_response.json() == local_response.json()


def test_managed_live_sidecar_persists_ingest_and_delete_across_restart(
    managed_sidecar,
    tmp_path,
):
    controller = _rust_controller(
        managed_sidecar.service_url,
        tmp_path / "unused-rust-storage",
    )

    memory_id = controller.ingest(
        CandidateMemory(
            raw_text="restart parity text",
            memory_type="fact",
            scope="shared",
        )
    )

    managed_sidecar.restart()
    reloaded = _rust_controller(
        managed_sidecar.service_url,
        tmp_path / "unused-rust-storage",
    )
    records_after_restart, total_after_restart = reloaded.list_records()
    assert total_after_restart == 1
    assert [record.memory_id for record in records_after_restart] == [memory_id]

    assert reloaded.delete_record(memory_id) is True

    managed_sidecar.restart()
    after_delete_restart = _rust_controller(
        managed_sidecar.service_url,
        tmp_path / "unused-rust-storage",
    )
    final_records, final_total = after_delete_restart.list_records()
    assert final_total == 0
    assert final_records == []


def test_rust_backend_routes_fail_explicitly_and_recover_after_sidecar_restart(
    rust_app_client,
    managed_sidecar,
):
    healthy_response = rust_app_client.get("/api/hca/memory/list")
    assert healthy_response.status_code == 200

    managed_sidecar.stop()

    for _ in range(3):
        unavailable_response = rust_app_client.get("/api/hca/memory/list")
        assert unavailable_response.status_code == 503
        detail = unavailable_response.json()["detail"]
        assert "Rust memory sidecar is configured as the active memory authority" in detail
        assert "/api/subsystems" in detail

    managed_sidecar.start()
    recovered_response = rust_app_client.get("/api/hca/memory/list")
    assert recovered_response.status_code == 200
