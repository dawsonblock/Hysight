from importlib import import_module
import shutil

from hca.common.types import RunContext
from hca.modules.perception_text import TextPerception
from hca.paths import run_storage_dir

save_run = import_module("hca.storage.runs").save_run


def setup_module():
    run_dir = run_storage_dir("test_modules_v5")
    if run_dir.exists():
        shutil.rmtree(run_dir)


def test_perception_grounding():
    run_id = "test_modules_v5"
    ctx = RunContext(run_id=run_id, goal="remember my keys are in the car")
    save_run(ctx)

    perc = TextPerception()
    proposal = perc.propose(run_id)
    assert len(proposal.candidate_items) == 1
    assert proposal.candidate_items[0].kind == "perceived_intent"
    assert proposal.candidate_items[0].content["intent"] == "store"


if __name__ == "__main__":
    setup_module()
    test_perception_grounding()
    print("test_perception_grounding passed")
