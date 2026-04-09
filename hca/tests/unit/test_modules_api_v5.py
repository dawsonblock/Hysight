import os
import shutil
from hca.common.types import WorkspaceItem, RunContext
from hca.modules.perception_text import TextPerception
from hca.modules.planner import Planner
from hca.storage.runs import save_run

def setup_module():
    if os.path.exists("storage/runs/test_modules_v5"):
        shutil.rmtree("storage/runs/test_modules_v5")

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
