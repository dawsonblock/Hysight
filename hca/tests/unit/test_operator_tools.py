"""Focused coverage for bounded operator-grade tools."""

# mypy: ignore-errors
# pyright: reportMissingImports=false, reportMissingTypeStubs=false

import json
from pathlib import Path

import pytest

import hca.executor.tool_registry as tool_registry
import hca.modules.planner as planner_module
from hca.common.enums import ReceiptStatus
from hca.common.types import ActionCandidate, RunContext
from hca.executor.executor import Executor
from hca.paths import relative_run_storage_path, run_storage_path
from hca.runtime.runtime import Runtime


def _write_file(root: Path, relative_path: str, content: str) -> None:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _artifact_full_path(run_id: str, relative_path: str) -> Path:
    parts = Path(relative_path).parts
    artifact_parts = (
        parts[4:]
        if len(parts) >= 5
        else (Path(relative_path).name,)
    )
    return run_storage_path(run_id, "artifacts", *artifact_parts)


@pytest.mark.parametrize(
    ("tool_name", "arguments"),
    [
        (
            "read_text_range",
            {"path": "../escape.txt", "start_line": 1, "end_line": 2},
        ),
        (
            "glob_workspace",
            {"root": "../escape", "pattern": "**/*", "max_results": 5},
        ),
        (
            "search_workspace",
            {"query": "needle", "root": "../escape", "path_glob": "**/*"},
        ),
        (
            "patch_text_file",
            {"path": "../escape.txt", "old_text": "a", "new_text": "b"},
        ),
        ("create_run_report", {"path": "../escape.json"}),
        (
            "investigate_workspace_issue",
            {"query": "needle", "root": "../escape", "path_glob": "**/*"},
        ),
    ],
)
def test_new_tools_reject_invalid_args(tool_name, arguments):
    executor = Executor()
    receipt = executor.execute(
        "test_run",
        ActionCandidate(kind=tool_name, arguments=arguments),
        approved=True,
    )

    assert receipt.status == ReceiptStatus.failure
    assert receipt.validation_status == "failed"


def test_stat_and_glob_workspace_use_repo_root_bounds(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_registry, "REPO_ROOT", tmp_path)
    _write_file(tmp_path, "src/example.py", "print('hello')\n")

    executor = Executor()

    stat_receipt = executor.execute(
        "test_run",
        ActionCandidate(
            kind="stat_path",
            arguments={"path": "src/example.py"},
        ),
    )
    assert stat_receipt.status == ReceiptStatus.success
    assert stat_receipt.validation_status == "validated"
    assert stat_receipt.validated_arguments == {"path": "src/example.py"}
    assert stat_receipt.outputs["exists"] is True
    assert stat_receipt.outputs["kind"] == "file"
    assert stat_receipt.outputs["sha256"]

    glob_receipt = executor.execute(
        "test_run",
        ActionCandidate(
            kind="glob_workspace",
            arguments={
                "root": "src",
                "pattern": "**/*.py",
                "max_results": 10,
            },
        ),
    )
    assert glob_receipt.status == ReceiptStatus.success
    assert glob_receipt.outputs["entries"] == [
        {"path": "src/example.py", "kind": "file"}
    ]


def test_read_text_range_reads_bounded_lines(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_registry, "REPO_ROOT", tmp_path)
    _write_file(tmp_path, "notes/todo.txt", "one\ntwo\nthree\nfour\n")

    executor = Executor()
    receipt = executor.execute(
        "test_run",
        ActionCandidate(
            kind="read_text_range",
            arguments={
                "path": "notes/todo.txt",
                "start_line": 2,
                "end_line": 3,
            },
        ),
    )

    assert receipt.status == ReceiptStatus.success
    assert receipt.outputs["text"] == "two\nthree"
    assert receipt.outputs["line_span"] == {"start": 2, "end": 3}


def test_read_text_range_rejects_binary(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_registry, "REPO_ROOT", tmp_path)
    path = tmp_path / "bin" / "blob.dat"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x00\x01needle\x02")

    executor = Executor()
    receipt = executor.execute(
        "test_run",
        ActionCandidate(
            kind="read_text_range",
            arguments={"path": "bin/blob.dat", "start_line": 1, "end_line": 2},
        ),
    )

    assert receipt.status == ReceiptStatus.failure
    assert "text file" in receipt.error


def test_search_workspace_finds_structured_matches(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_registry, "REPO_ROOT", tmp_path)
    _write_file(tmp_path, "docs/notes.txt", "alpha\nneedle value\nomega\n")
    _write_file(tmp_path, "src/app.py", "print('needle value')\n")
    binary_path = tmp_path / "src" / "raw.bin"
    binary_path.write_bytes(b"\x00needle value\x00")

    executor = Executor()
    receipt = executor.execute(
        "test_run",
        ActionCandidate(
            kind="search_workspace",
            arguments={
                "query": "needle value",
                "path_glob": "**/*",
                "max_results": 5,
                "max_files": 10,
                "max_total_bytes": 100_000,
            },
        ),
    )

    assert receipt.status == ReceiptStatus.success
    assert receipt.outputs["returned"] == 2
    assert receipt.outputs["total_match_count"] == 2
    assert receipt.outputs["per_file_match_counts"] == [
        {"path": "docs/notes.txt", "match_count": 1},
        {"path": "src/app.py", "match_count": 1},
    ]
    assert receipt.outputs["skipped_binary_files"] == 1
    assert receipt.outputs["matches"][0]["preview"] == "needle value"


def test_search_workspace_enforces_file_budget(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_registry, "REPO_ROOT", tmp_path)
    _write_file(tmp_path, "a.txt", "needle\n")
    _write_file(tmp_path, "b.txt", "needle\n")
    _write_file(tmp_path, "c.txt", "needle\n")

    executor = Executor()
    receipt = executor.execute(
        "test_run",
        ActionCandidate(
            kind="search_workspace",
            arguments={
                "query": "needle",
                "path_glob": "**/*.txt",
                "max_results": 10,
                "max_files": 1,
                "max_total_bytes": 100_000,
            },
        ),
    )

    assert receipt.status == ReceiptStatus.success
    assert receipt.outputs["truncated"] is True
    assert receipt.outputs["truncation_reasons"] == ["max_files"]


def test_search_workspace_recovers_from_natural_language_query(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(tool_registry, "REPO_ROOT", tmp_path)
    _write_file(tmp_path, "contract/api.py", "class RuntimeState: pass\n")

    executor = Executor()
    receipt = executor.execute(
        "test_run",
        ActionCandidate(
            kind="search_workspace",
            arguments={
                "query": "search the repo for RuntimeState in contract/api.py",
                "path_glob": "**/*",
                "max_results": 5,
                "max_files": 10,
                "max_total_bytes": 100_000,
            },
        ),
    )

    assert receipt.status == ReceiptStatus.success
    assert receipt.outputs["returned"] == 1
    assert receipt.outputs["matches"][0]["path"] == "contract/api.py"
    assert receipt.outputs["recovered"] is True
    assert receipt.outputs["effective_query"] == "RuntimeState"
    assert receipt.outputs["effective_path_glob"] == "contract/api.py"
    assert any(
        attempt["query"] == "RuntimeState"
        for attempt in receipt.outputs["search_attempts"]
    )


def test_patch_text_file_preview_and_apply(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_registry, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))
    _write_file(tmp_path, "notes/todo.txt", "hello world\n")

    executor = Executor()

    preview_receipt = executor.execute(
        "test_run",
        ActionCandidate(
            kind="patch_text_file",
            arguments={
                "path": "notes/todo.txt",
                "old_text": "world",
                "new_text": "mars",
                "apply": False,
            },
        ),
        approved=True,
    )
    assert preview_receipt.status == ReceiptStatus.success
    assert preview_receipt.outputs["applied"] is False
    assert "-hello world" in preview_receipt.outputs["diff_preview"]
    assert preview_receipt.artifacts == [
        preview_receipt.outputs["diff_artifact_path"]
    ]
    assert preview_receipt.mutation_result is not None
    assert preview_receipt.mutation_result.status == "preview"
    assert preview_receipt.mutation_result.before_hash == (
        preview_receipt.outputs["before_hash"]
    )
    assert preview_receipt.mutation_result.after_hash == (
        preview_receipt.outputs["after_hash"]
    )
    assert preview_receipt.artifact_summaries is not None
    assert preview_receipt.artifact_summaries[0].artifact_type.value == (
        "patch_diff"
    )
    preview_diff = _artifact_full_path(
        "test_run",
        preview_receipt.outputs["diff_artifact_path"],
    )
    assert preview_diff.exists()
    assert (tmp_path / "notes/todo.txt").read_text(encoding="utf-8") == (
        "hello world\n"
    )

    apply_receipt = executor.execute(
        "test_run",
        ActionCandidate(
            kind="patch_text_file",
            arguments={
                "path": "notes/todo.txt",
                "old_text": "world",
                "new_text": "mars",
                "apply": True,
                "expected_hash": preview_receipt.outputs["before_hash"],
            },
        ),
        approved=True,
    )
    assert apply_receipt.status == ReceiptStatus.success
    assert apply_receipt.outputs["applied"] is True
    assert apply_receipt.side_effects == ["modified:notes/todo.txt"]
    assert apply_receipt.artifacts == [
        apply_receipt.outputs["diff_artifact_path"]
    ]
    assert apply_receipt.mutation_result is not None
    assert apply_receipt.mutation_result.status == "applied"
    assert apply_receipt.mutation_result.artifact_path == (
        apply_receipt.outputs["diff_artifact_path"]
    )
    assert (tmp_path / "notes/todo.txt").read_text(encoding="utf-8") == (
        "hello mars\n"
    )


def test_patch_text_file_rejects_hash_mismatch(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_registry, "REPO_ROOT", tmp_path)
    _write_file(tmp_path, "notes/todo.txt", "hello world\n")

    executor = Executor()
    receipt = executor.execute(
        "test_run",
        ActionCandidate(
            kind="patch_text_file",
            arguments={
                "path": "notes/todo.txt",
                "old_text": "world",
                "new_text": "mars",
                "apply": True,
                "expected_hash": "0" * 64,
            },
        ),
        approved=True,
    )

    assert receipt.status == ReceiptStatus.failure
    assert "expected_hash does not match" in receipt.error


def test_patch_text_file_rejects_binary_target(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_registry, "REPO_ROOT", tmp_path)
    binary_path = tmp_path / "notes" / "blob.bin"
    binary_path.parent.mkdir(parents=True, exist_ok=True)
    binary_path.write_bytes(b"\x00\x01binary")

    executor = Executor()
    receipt = executor.execute(
        "test_run",
        ActionCandidate(
            kind="patch_text_file",
            arguments={
                "path": "notes/blob.bin",
                "old_text": "binary",
                "new_text": "text",
                "apply": False,
            },
        ),
        approved=True,
    )

    assert receipt.status == ReceiptStatus.failure
    assert "text file" in receipt.error


def test_patch_text_file_rejects_oversized_target(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_registry, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(tool_registry, "_PATCH_MAX_FILE_BYTES", 8)
    _write_file(tmp_path, "notes/todo.txt", "0123456789")

    executor = Executor()
    receipt = executor.execute(
        "test_run",
        ActionCandidate(
            kind="patch_text_file",
            arguments={
                "path": "notes/todo.txt",
                "old_text": "0",
                "new_text": "x",
                "apply": False,
            },
        ),
        approved=True,
    )

    assert receipt.status == ReceiptStatus.failure
    assert "bounded patch size" in receipt.error


def test_investigate_workspace_issue_writes_report(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_registry, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))
    _write_file(tmp_path, "contract/api.py", "class RuntimeState: pass\n")

    executor = Executor()
    receipt = executor.execute(
        "test_run",
        ActionCandidate(
            kind="investigate_workspace_issue",
            arguments={
                "query": "RuntimeState",
                "root": "contract",
                "path_glob": "**/*.py",
                "max_matches": 4,
            },
        ),
    )

    assert receipt.status == ReceiptStatus.success
    assert receipt.artifacts == [receipt.outputs["path"]]
    report_path = _artifact_full_path("test_run", receipt.outputs["path"])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["query"] == "RuntimeState"
    assert report["evidence"][0]["path"] == "contract/api.py"


def test_investigate_workspace_issue_preserves_search_recovery(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(tool_registry, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))
    _write_file(tmp_path, "contract/api.py", "class RuntimeState: pass\n")

    executor = Executor()
    receipt = executor.execute(
        "test_run",
        ActionCandidate(
            kind="investigate_workspace_issue",
            arguments={
                "query": "search the repo for RuntimeState in contract/api.py",
                "root": ".",
                "path_glob": "**/*.py",
                "max_matches": 4,
            },
        ),
    )

    assert receipt.status == ReceiptStatus.success
    report_path = _artifact_full_path("test_run", receipt.outputs["path"])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["search_summary"]["recovered"] is True
    assert report["search_summary"]["effective_query"] == "RuntimeState"
    assert report["evidence"][0]["path"] == "contract/api.py"


def test_create_run_report_materializes_prior_run(monkeypatch, tmp_path):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))

    runtime = Runtime()
    run_id = runtime.run("echo hello")

    executor = Executor()
    receipt = executor.execute(
        run_id,
        ActionCandidate(kind="create_run_report", arguments={}),
    )

    assert receipt.status == ReceiptStatus.success
    report_path = _artifact_full_path(run_id, receipt.outputs["path"])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["run_id"] == run_id
    assert report["final_status"] == "completed"
    assert len(report["actions_executed"]) == 1


def test_summarize_search_results_writes_artifact(monkeypatch, tmp_path):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))

    executor = Executor()
    receipt = executor.execute(
        "test_run",
        ActionCandidate(
            kind="summarize_search_results",
            arguments={
                "query": "RuntimeState",
                "search_result": {
                    "searched_scope": "hca",
                    "returned": 1,
                    "total_match_count": 1,
                    "matches": [
                        {
                            "path": "hca/src/hca/common/enums.py",
                            "line_number": 6,
                            "preview": "class RuntimeState(str, Enum):",
                        }
                    ],
                },
                "excerpt": {
                    "path": "hca/src/hca/common/enums.py",
                    "text": "class RuntimeState(str, Enum):",
                },
            },
        ),
    )

    assert receipt.status == ReceiptStatus.success
    assert receipt.artifacts == [receipt.outputs["path"]]
    report_path = _artifact_full_path("test_run", receipt.outputs["path"])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["query"] == "RuntimeState"
    assert report["top_matches"][0]["path"] == "hca/src/hca/common/enums.py"


def test_create_diff_report_writes_certification_artifact(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))

    executor = Executor()
    receipt = executor.execute(
        "test_run",
        ActionCandidate(
            kind="create_diff_report",
            arguments={
                "target_path": "notes/todo.txt",
                "before_hash": "1" * 64,
                "after_hash": "2" * 64,
                "changed_lines": [
                    {
                        "start_line": 1,
                        "removed_lines": 1,
                        "added_lines": 1,
                    }
                ],
                "diff_artifact_path": (
                    relative_run_storage_path(
                        "test_run",
                        "artifacts",
                        "patch.diff",
                    ).as_posix()
                ),
                "approval_id": "approval-1",
            },
        ),
    )

    assert receipt.status == ReceiptStatus.success
    report_path = _artifact_full_path("test_run", receipt.outputs["path"])
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["target_path"] == "notes/todo.txt"
    assert report["certified_mutation"] is True


def test_planner_fallback_emits_registered_tool(monkeypatch):
    planner = planner_module.Planner()
    monkeypatch.setattr(
        planner_module,
        "load_run",
        lambda run_id: RunContext(run_id=run_id, goal="create run report"),
    )

    proposal = planner.propose("run-planner")
    action = next(
        item.content["action"]
        for item in proposal.candidate_items
        if item.kind == "action_suggestion"
    )

    assert action in tool_registry.list_tools()


def test_run_command_executes_pytest(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_registry, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))
    _write_file(
        tmp_path,
        "test_sample.py",
        "def test_ok():\n    assert 2 + 2 == 4\n",
    )

    executor = Executor()
    receipt = executor.execute(
        "test_run",
        ActionCandidate(
            kind="run_command",
            arguments={
                "argv": ["pytest", "-q", "test_sample.py"],
                "cwd": ".",
                "timeout_seconds": 10,
            },
        ),
        approved=True,
    )

    assert receipt.status == ReceiptStatus.success
    assert receipt.outputs["ok"] is True
    assert receipt.outputs["returncode"] == 0
    assert "1 passed" in (
        receipt.outputs["stdout"] + receipt.outputs["stderr"]
    )


def test_run_command_nonzero_exit_preserves_artifact(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(tool_registry, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))
    _write_file(
        tmp_path,
        "test_sample.py",
        "def test_fail():\n    assert False\n",
    )

    executor = Executor()
    receipt = executor.execute(
        "test_run",
        ActionCandidate(
            kind="run_command",
            arguments={
                "argv": ["pytest", "-q", "test_sample.py"],
                "cwd": ".",
                "timeout_seconds": 10,
            },
        ),
        approved=True,
    )

    assert receipt.status == ReceiptStatus.failure
    assert receipt.validation_status == "validated"
    assert receipt.outputs["ok"] is False
    assert receipt.artifacts == [receipt.outputs["artifact_path"]]
    command_artifact = _artifact_full_path(
        "test_run",
        receipt.outputs["artifact_path"],
    )
    assert command_artifact.exists()
    payload = json.loads(command_artifact.read_text(encoding="utf-8"))
    assert payload["returncode"] != 0


def test_run_command_rejects_disallowed_command(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_registry, "REPO_ROOT", tmp_path)

    executor = Executor()
    receipt = executor.execute(
        "test_run",
        ActionCandidate(
            kind="run_command",
            arguments={
                "argv": ["bash", "-lc", "pwd"],
                "cwd": ".",
                "timeout_seconds": 5,
            },
        ),
        approved=True,
    )

    assert receipt.status == ReceiptStatus.failure
    assert "not allowlisted" in receipt.error


def test_run_command_rejects_shell_metacharacters(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_registry, "REPO_ROOT", tmp_path)

    executor = Executor()
    receipt = executor.execute(
        "test_run",
        ActionCandidate(
            kind="run_command",
            arguments={
                "argv": ["pytest", "-q", "test_sample.py;echo hacked"],
                "cwd": ".",
                "timeout_seconds": 5,
            },
        ),
        approved=True,
    )

    assert receipt.status == ReceiptStatus.failure
    assert "shell metacharacters" in receipt.error


def test_run_command_rejects_dangerous_pytest_flags(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_registry, "REPO_ROOT", tmp_path)

    executor = Executor()
    receipt = executor.execute(
        "test_run",
        ActionCandidate(
            kind="run_command",
            arguments={
                "argv": ["pytest", "-q", "--rootdir=.."],
                "cwd": ".",
                "timeout_seconds": 5,
            },
        ),
        approved=True,
    )

    assert receipt.status == ReceiptStatus.failure
    assert "not allowed" in receipt.error


def test_run_command_rejects_cwd_escape(monkeypatch, tmp_path):
    monkeypatch.setattr(tool_registry, "REPO_ROOT", tmp_path)

    executor = Executor()
    receipt = executor.execute(
        "test_run",
        ActionCandidate(
            kind="run_command",
            arguments={
                "argv": ["pytest", "-q"],
                "cwd": "../outside",
                "timeout_seconds": 5,
            },
        ),
        approved=True,
    )

    assert receipt.status == ReceiptStatus.failure
    assert "bounded workspace" in receipt.error


def test_run_command_timeout_records_failure_artifact(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(tool_registry, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))
    _write_file(
        tmp_path,
        "test_slow.py",
        "import time\n\n"
        "def test_slow():\n"
        "    time.sleep(2)\n"
        "    assert True\n",
    )

    executor = Executor()
    receipt = executor.execute(
        "test_run",
        ActionCandidate(
            kind="run_command",
            arguments={
                "argv": ["pytest", "-q", "test_slow.py"],
                "cwd": ".",
                "timeout_seconds": 1,
            },
        ),
        approved=True,
    )

    assert receipt.status == ReceiptStatus.failure
    assert receipt.outputs["timed_out"] is True
    assert receipt.artifacts == [receipt.outputs["artifact_path"]]
    assert "timed out after 1s" in receipt.error
    payload = json.loads(
        _artifact_full_path(
            "test_run",
            receipt.outputs["artifact_path"],
        ).read_text(encoding="utf-8")
    )
    assert payload["timed_out"] is True
    assert payload["ok"] is False


def test_run_command_truncates_output_deterministically(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setattr(tool_registry, "REPO_ROOT", tmp_path)
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path / "storage"))
    _write_file(
        tmp_path,
        "test_loud.py",
        "def test_loud():\n"
        "    print('x' * 13050)\n"
        "    assert False\n",
    )

    executor = Executor()
    receipt = executor.execute(
        "test_run",
        ActionCandidate(
            kind="run_command",
            arguments={
                "argv": ["pytest", "-q", "-s", "test_loud.py"],
                "cwd": ".",
                "timeout_seconds": 10,
            },
        ),
        approved=True,
    )

    assert receipt.status == ReceiptStatus.failure
    assert receipt.outputs["truncated"] is True
    combined_output = (
        (receipt.outputs.get("stdout") or "")
        + (receipt.outputs.get("stderr") or "")
    )
    assert "...[truncated]..." in combined_output
