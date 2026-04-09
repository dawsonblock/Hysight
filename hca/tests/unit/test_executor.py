from hca.executor.executor import Executor
from hca.common.types import ActionCandidate


def test_executor_echo():
    ex = Executor()
    action = ActionCandidate(
        kind="echo",
        arguments={"text": "hello"},
        expected_progress=0.5,
        expected_uncertainty_reduction=0.2,
        reversibility=1.0,
        risk=0.0,
        cost=0.0,
        user_interruption_burden=0.0,
        policy_alignment=1.0,
    )
    receipt = ex.execute("test_run", action)
    assert receipt.status.value == "success"
    assert receipt.outputs["echo"] == "hello"