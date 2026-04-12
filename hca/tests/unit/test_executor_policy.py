# mypy: ignore-errors
# pyright: reportMissingImports=false, reportMissingTypeStubs=false

from hca.executor.executor import Executor
from hca.executor.tool_registry import build_action_candidate
from hca.common.types import ActionCandidate
from hca.common.enums import ActionClass, ReceiptStatus
from hca.paths import run_storage_path


def test_unsupported_tool():
    executor = Executor()
    candidate = ActionCandidate(kind="magic_tool", arguments={})
    receipt = executor.execute("test_run", candidate)
    assert receipt.status == ReceiptStatus.failure
    # get_tool raises KeyError, executor catches it and puts it in error
    assert "magic_tool" in receipt.error


def test_approval_required_rejection():
    executor = Executor()
    # store_note requires approval
    candidate = ActionCandidate(
        kind="store_note",
        arguments={"note": "secret"},
    )
    receipt = executor.execute("test_run", candidate, approved=False)
    assert receipt.status == ReceiptStatus.failure
    assert "requires explicit approval context" in receipt.error


def test_successful_allowed_execution():
    executor = Executor()
    candidate = ActionCandidate(kind="echo", arguments={"text": "hello"})
    receipt = executor.execute(
        "test_run",
        candidate,
        approved=False,
    )  # echo doesn't need approval
    assert receipt.status == ReceiptStatus.success
    assert receipt.outputs["echo"] == "hello"


def test_build_action_candidate_uses_registry_policy():
    candidate = build_action_candidate(
        "store_note",
        {"note": "remember this"},
    )
    assert candidate.requires_approval is True
    assert candidate.action_class == ActionClass.medium


def test_executor_rejects_invalid_fields():
    executor = Executor()
    candidate = ActionCandidate(
        kind="echo",
        arguments={"text": "hello", "path": "oops.txt"},
    )
    receipt = executor.execute("test_run", candidate)
    assert receipt.status == ReceiptStatus.failure
    assert "invalid fields: path" in receipt.error


def test_executor_lists_repo_directory():
    executor = Executor()
    candidate = ActionCandidate(kind="list_dir", arguments={"path": "."})
    receipt = executor.execute("test_run", candidate)
    assert receipt.status == ReceiptStatus.success
    assert any(
        entry["name"] == "README.md"
        for entry in receipt.outputs["entries"]
    )


def test_executor_reads_repo_file():
    executor = Executor()
    candidate = ActionCandidate(
        kind="read_file",
        arguments={
            "path": "README.md",
            "start_line": 1,
            "end_line": 5,
        },
    )
    receipt = executor.execute("test_run", candidate)
    assert receipt.status == ReceiptStatus.success
    assert receipt.outputs["path"] == "README.md"
    assert receipt.outputs["content"]


def test_receipt_preserves_validated_arguments_and_binding():
    executor = Executor()
    candidate = ActionCandidate(
        kind="list_dir",
        arguments={"path": "./"},
    )

    receipt = executor.execute("test_run", candidate)

    assert receipt.status == ReceiptStatus.success
    assert receipt.validation_status == "validated"
    assert receipt.validated_arguments == {"path": "."}
    assert receipt.binding is not None
    assert receipt.binding.action_fingerprint
    assert receipt.binding.policy_fingerprint


def test_write_artifact_uses_bounded_requested_path(monkeypatch, tmp_path):
    monkeypatch.setenv("HCA_STORAGE_ROOT", str(tmp_path))

    executor = Executor()
    candidate = ActionCandidate(
        kind="write_artifact",
        arguments={"content": "artifact body", "path": "notes/summary.txt"},
    )
    receipt = executor.execute("test_run", candidate, approved=True)

    assert receipt.status == ReceiptStatus.success
    assert receipt.outputs["path"].endswith("notes/summary.txt")
    assert run_storage_path(
        "test_run",
        "artifacts",
        "notes",
        "summary.txt",
    ).exists()


if __name__ == "__main__":
    test_unsupported_tool()
    print("test_unsupported_tool passed")
    test_approval_required_rejection()
    print("test_approval_required_rejection passed")
    test_successful_allowed_execution()
    print("test_successful_allowed_execution passed")
