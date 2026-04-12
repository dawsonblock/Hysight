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

    @staticmethod
    def _record_tool_artifact(
        run_id: str,
        *,
        candidate: ActionCandidate,
        path: str,
        kind: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        artifact_id = hashlib.md5(
            f"{candidate.action_id}:{path}:{kind}".encode()
        ).hexdigest()
        payload: Dict[str, Any] = metadata.copy() if metadata else {}
        payload.setdefault("args", candidate.arguments)
        if candidate.binding is not None:
            payload.setdefault(
                "binding",
                candidate.binding.model_dump(mode="json"),
            )
        art_record = ArtifactRecord(
            artifact_id=artifact_id,
            run_id=run_id,
            action_id=candidate.action_id,
            kind=kind,
            path=path,
            metadata=payload,
        )
        append_artifact(run_id, art_record.model_dump(mode="json"))
        return path

    def execute(
        self,
        run_id: str,
        candidate: ActionCandidate,
        approved: bool = False,
        approval_id: Optional[str] = None,
    ) -> ExecutionReceipt:
        """Execute the given action and return a receipt."""
        started_at = datetime.now(timezone.utc)
        validation_status = "validated"
        validated_arguments: Optional[Dict[str, Any]] = None

        try:
            candidate = canonicalize_action_candidate(candidate)
            tool_info = get_tool(candidate.kind)
            normalized_arguments = candidate.arguments
            validated_arguments = dict(normalized_arguments)

            if tool_info.requires_approval and not approved:
                raise PermissionError(
                    "Action "
                    f"'{candidate.kind}' requires explicit approval context"
                )

            raw_outputs = tool_info.func(run_id, normalized_arguments)
            side_effects: Optional[list[str]] = None
            artifacts: list[str] = []
            outputs = raw_outputs
            if isinstance(raw_outputs, dict):
                outputs = dict(raw_outputs)
                raw_side_effects = outputs.pop("_side_effects", None)
                if raw_side_effects:
                    side_effects = [str(effect) for effect in raw_side_effects]

                raw_artifacts = outputs.pop("_artifacts", None)
                if raw_artifacts:
                    artifacts.extend(str(path) for path in raw_artifacts)

                raw_artifact_records = outputs.pop(
                    "_artifact_records",
                    None,
                )
                if raw_artifact_records:
                    for record in raw_artifact_records:
                        if not isinstance(record, dict):
                            continue
                        path = record.get("path")
                        kind = record.get("kind") or candidate.kind
                        if not isinstance(path, str) or not path:
                            continue
                        artifacts.append(
                            self._record_tool_artifact(
                                run_id,
                                candidate=candidate,
                                path=path,
                                kind=str(kind),
                                metadata=(
                                    record.get("metadata")
                                    if isinstance(
                                        record.get("metadata"), dict
                                    )
                                    else None
                                ),
                            )
                        )

            status = ReceiptStatus.success
            error = None

            if (
                tool_info.artifact_behavior == "create_file"
                and outputs
                and "path" in outputs
            ):
                artifact_path = outputs["path"]
                artifacts.append(
                    self._record_tool_artifact(
                        run_id,
                        candidate=candidate,
                        path=artifact_path,
                        kind=candidate.kind,
                    )
                )

            if artifacts:
                artifacts = list(dict.fromkeys(artifacts))

        except Exception as exc:
            outputs = None
            status = ReceiptStatus.failure
            error = str(exc)
            artifacts = []
            side_effects = None
            validation_status = "failed"

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
            validation_status=validation_status,
            validated_arguments=validated_arguments,
            started_at=started_at,
            finished_at=finished_at,
            outputs=outputs,
            side_effects=side_effects,
            artifacts=(
                artifacts if status == ReceiptStatus.success else None
            ),
            error=error,
            audit_hash=audit_hash,
        )

        receipts_storage.append_receipt(
            run_id,
            receipt.model_dump(mode="json"),
        )
        return receipt
