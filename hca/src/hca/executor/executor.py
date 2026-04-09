"""Execution authority for the hybrid cognitive agent."""

from __future__ import annotations

import hashlib
import json
import time
from typing import Dict, Any, Tuple, Optional
from datetime import datetime, timezone

from hca.common.types import ActionCandidate, ExecutionReceipt, ArtifactRecord
from hca.common.enums import ReceiptStatus
from hca.storage import receipts as receipts_storage
from hca.storage.artifacts import append_artifact
from hca.executor.tool_registry import get_tool


class Executor:
    """Single execution authority. All side effects pass through here."""

    def execute(self, run_id: str, candidate: ActionCandidate, approved: bool = False) -> ExecutionReceipt:
        """Execute the given action and return a receipt."""
        started_at = datetime.now(timezone.utc)
        
        try:
            # 1. Resolve tool and enforce policy
            # get_tool will raise ValueError if tool is unknown
            tool_info = get_tool(candidate.kind)
            
            # 2. Validate required input fields
            # Simple check for MVP: check if required_args (if any) are present
            required_args = getattr(tool_info, "required_args", [])
            for arg in required_args:
                if arg not in candidate.arguments:
                    raise ValueError(f"Missing required argument: {arg}")
            
            # 3. Approval enforcement
            if tool_info.requires_approval and not approved:
                raise PermissionError(f"Action '{candidate.kind}' requires explicit approval context")

            # 4. Call tool function
            outputs = tool_info.func(run_id, candidate.arguments)
            status = ReceiptStatus.success
            error = None
            
            # 3. Handle artifacts if tool produced any
            artifacts = []
            if tool_info.artifact_behavior == "create_file" and outputs and "path" in outputs:
                artifact_path = outputs["path"]
                artifact_id = hashlib.md5(artifact_path.encode()).hexdigest()
                art_record = ArtifactRecord(
                    artifact_id=artifact_id,
                    run_id=run_id,
                    action_id=candidate.action_id,
                    kind=candidate.kind,
                    path=artifact_path,
                    metadata={"args": candidate.arguments}
                )
                append_artifact(run_id, art_record.model_dump(mode="json"))
                artifacts.append(artifact_path)
                
        except Exception as exc:
            outputs = None
            status = ReceiptStatus.failure
            error = str(exc)
            artifacts = None

        finished_at = datetime.now(timezone.utc)
        
        # 4. Compute deterministic audit hash
        audit_payload = {
            "action_id": candidate.action_id,
            "status": status.value,
            "outputs": outputs,
            "error": error
        }
        audit_str = json.dumps(audit_payload, sort_keys=True, default=str)
        audit_hash = hashlib.sha256(audit_str.encode()).hexdigest()
        
        receipt = ExecutionReceipt(
            action_id=candidate.action_id,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            outputs=outputs,
            artifacts=artifacts,
            error=error,
            audit_hash=audit_hash,
        )
        
        # 5. Persist receipt
        receipts_storage.append_receipt(run_id, receipt.model_dump(mode="json"))
        return receipt
