"""Execution authority for the hybrid cognitive agent."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from hca.common.types import ActionCandidate, ExecutionReceipt, ArtifactRecord
from hca.common.enums import ReceiptStatus
from hca.storage import receipts as receipts_storage
from hca.storage.artifacts import append_artifact
from hca.executor.tool_registry import canonicalize_action_candidate, get_tool


class Executor:
    """Single execution authority. All side effects pass through here."""

    def execute(
        self,
        run_id: str,
        candidate: ActionCandidate,
        approved: bool = False,
        approval_id: Optional[str] = None,
    ) -> ExecutionReceipt:
        """Execute the given action and return a receipt."""
        started_at = datetime.now(timezone.utc)

        try:
            candidate = canonicalize_action_candidate(candidate)
            tool_info = get_tool(candidate.kind)
            normalized_arguments = candidate.arguments

            if tool_info.requires_approval and not approved:
                raise PermissionError(
                    "Action "
                    f"'{candidate.kind}' requires explicit approval context"
                )

            outputs = tool_info.func(run_id, normalized_arguments)
            status = ReceiptStatus.success
            error = None

            artifacts = []
            if (
                tool_info.artifact_behavior == "create_file"
                and outputs
                and "path" in outputs
            ):
                artifact_path = outputs["path"]
                artifact_id = hashlib.md5(artifact_path.encode()).hexdigest()
                metadata: Dict[str, Any] = {"args": normalized_arguments}
                if candidate.binding is not None:
                    metadata["binding"] = candidate.binding.model_dump(
                        mode="json"
                    )
                art_record = ArtifactRecord(
                    artifact_id=artifact_id,
                    run_id=run_id,
                    action_id=candidate.action_id,
                    kind=candidate.kind,
                    path=artifact_path,
                    metadata=metadata,
                )
                append_artifact(run_id, art_record.model_dump(mode="json"))
                artifacts.append(artifact_path)

        except Exception as exc:
            outputs = None
            status = ReceiptStatus.failure
            error = str(exc)
            artifacts = None

        finished_at = datetime.now(timezone.utc)

        binding_payload = None
        if candidate.binding is not None:
            binding_payload = candidate.binding.model_dump(mode="json")

        audit_payload = {
            "action_id": candidate.action_id,
            "action_kind": candidate.kind,
            "approval_id": approval_id,
            "binding": binding_payload,
            "status": status.value,
            "outputs": outputs,
            "error": error,
        }
        audit_str = json.dumps(audit_payload, sort_keys=True, default=str)
        audit_hash = hashlib.sha256(audit_str.encode()).hexdigest()

        receipt = ExecutionReceipt(
            action_id=candidate.action_id,
            action_kind=candidate.kind,
            approval_id=approval_id,
            status=status,
            binding=candidate.binding,
            started_at=started_at,
            finished_at=finished_at,
            outputs=outputs,
            artifacts=artifacts,
            error=error,
            audit_hash=audit_hash,
        )

        receipts_storage.append_receipt(
            run_id,
            receipt.model_dump(mode="json"),
        )
        return receipt
