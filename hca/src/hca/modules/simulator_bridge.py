"""Experimental simulator bridge stub.

This module is not part of the authoritative runtime path or proof surface.
"""

from hca.common.types import ModuleProposal, WorkspaceItem


class SimulatorBridge:
    name = "simulator_bridge"

    def propose(self, run_id: str) -> ModuleProposal:
        # For MVP, no simulated environment integration
        item = WorkspaceItem(
            source_module=self.name,
            kind="simulation",
            content="",
            salience=0.0,
            confidence=0.0,
            uncertainty=1.0,
            utility_estimate=0.0,
        )
        return ModuleProposal(
            source_module=self.name,
            candidate_items=[item],
            rationale="No simulation integration implemented.",
            confidence=0.0,
            novelty_score=0.0,
            estimated_value=0.0,
        )