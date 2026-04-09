import pytest
from hca.executor.executor import Executor
from hca.common.types import ActionCandidate
from hca.common.enums import ReceiptStatus

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
    candidate = ActionCandidate(kind="store_note", arguments={"note": "secret"})
    receipt = executor.execute("test_run", candidate, approved=False)
    assert receipt.status == ReceiptStatus.failure
    assert "requires explicit approval context" in receipt.error

def test_successful_allowed_execution():
    executor = Executor()
    candidate = ActionCandidate(kind="echo", arguments={"text": "hello"})
    receipt = executor.execute("test_run", candidate, approved=False) # echo doesn't need approval
    assert receipt.status == ReceiptStatus.success
    assert receipt.outputs["echo"] == "hello"

if __name__ == "__main__":
    test_unsupported_tool()
    print("test_unsupported_tool passed")
    test_approval_required_rejection()
    print("test_approval_required_rejection passed")
    test_successful_allowed_execution()
    print("test_successful_allowed_execution passed")
