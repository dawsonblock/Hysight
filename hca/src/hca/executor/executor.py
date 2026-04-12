"""Execution authority for the hybrid cognitive agent."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from hca.common.enums import ArtifactType, ReceiptStatus
from hca.common.types import (
    ActionCandidate,
    ArtifactRecord,
    ArtifactSummary,
    ExecutionReceipt,
    MutationResult,
)
from hca.storage import receipts as receipts_storage
from hca.storage.artifacts import append_artifact
from hca.executor.tool_registry import canonicalize_action_candidate, get_tool
from hca.paths import run_storage_path


class Executor:
    """Single execution authority. All side effects pass through here."""

    @staticmethod
    def _artifact_type_for_kind(kind: str) -> ArtifactType:
        mapping = {
            "investigate_workspace_issue": ArtifactType.investigation_summary,
            "summarize_search_results": ArtifactType.investigation_summary,
            "patch_diff": ArtifactType.patch_diff,
            "create_diff_report": ArtifactType.diff_report,
            "create_run_report": ArtifactType.run_report,
            "command_result": ArtifactType.command_result,
        }
        return mapping.get(kind, ArtifactType.generic_file)

    @staticmethod
    def _artifact_full_path(run_id: str, path: str) -> Path:
        parts = Path(path).parts
        if len(parts) >= 5 and parts[:4] == (
            "storage",
            "runs",
            run_id,
            "artifacts",
        ):
            return run_storage_path(run_id, "artifacts", *parts[4:])
        return run_storage_path(run_id, "artifacts", *parts)

    @classmethod
    def _artifact_hashes(
        cls,
        run_id: str,
        path: str,
        metadata: Dict[str, Any],
    ) -> Dict[str, str]:
        hashes: Dict[str, str] = {}
        raw_hashes = metadata.get("hashes")
        if isinstance(raw_hashes, dict):
            hashes.update(
                {
                    str(key): str(value)
                    for key, value in raw_hashes.items()
                    if value is not None
                }
            )

        full_path = cls._artifact_full_path(run_id, path)
        if full_path.exists() and full_path.is_file():
            hashes.setdefault(
                "artifact_sha256",
                hashlib.sha256(full_path.read_bytes()).hexdigest(),
            )
        return hashes

    @staticmethod
    def _record_tool_artifact(
        run_id: str,
        *,
        candidate: ActionCandidate,
        path: str,
        kind: str,
        approval_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ArtifactSummary:
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

        file_paths = [
            str(value)
            for value in payload.get("file_paths", [])
            if isinstance(value, str)
        ]
        hashes = Executor._artifact_hashes(run_id, path, payload)
        art_record = ArtifactRecord(
            artifact_id=artifact_id,
            run_id=run_id,
            action_id=candidate.action_id,
            kind=kind,
            path=path,
            source_action_ids=[candidate.action_id],
            file_paths=file_paths,
            hashes=hashes,
            approval_id=approval_id,
            workflow_id=candidate.workflow_id,
            metadata=payload,
        )
        append_artifact(run_id, art_record.model_dump(mode="json"))
        return ArtifactSummary(
            artifact_id=artifact_id,
            artifact_type=Executor._artifact_type_for_kind(kind),
            run_id=run_id,
            path=path,
            source_action_ids=[candidate.action_id],
            file_paths=file_paths,
            hashes=hashes,
            approval_id=approval_id,
            workflow_id=candidate.workflow_id,
        )

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
        touched_paths: Optional[list[str]] = None
        artifact_summaries: list[ArtifactSummary] = []
        mutation_result: Optional[MutationResult] = None

        try:
            candidate = canonicalize_action_candidate(candidate)
            tool_info = get_tool(candidate.kind)
            normalized_arguments = candidate.arguments
            validated_arguments = dict(normalized_arguments)

            if candidate.requires_approval and not approved:
                raise PermissionError(
                    "Action "
                    f"'{candidate.kind}' requires explicit approval context"
                )

            raw_outputs = tool_info.func(run_id, normalized_arguments)
            side_effects: Optional[list[str]] = None
            artifacts: list[str] = []
            outputs = raw_outputs
            failure_message: Optional[str] = None
            if isinstance(raw_outputs, dict):
                outputs = dict(raw_outputs)
                raw_side_effects = outputs.pop("_side_effects", None)
                if raw_side_effects:
                    side_effects = [str(effect) for effect in raw_side_effects]

                raw_touched_paths = outputs.pop("touched_paths", None)
                if raw_touched_paths:
                    touched_paths = [
                        str(path)
                        for path in raw_touched_paths
                        if isinstance(path, str)
                    ]

                raw_mutation_result = outputs.pop("mutation_result", None)
                if isinstance(raw_mutation_result, dict):
                    mutation_result = MutationResult.model_validate(
                        raw_mutation_result
                    )

                raw_failure_message = outputs.pop("_failure_message", None)
                if isinstance(raw_failure_message, str):
                    failure_message = raw_failure_message

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
                        summary = self._record_tool_artifact(
                            run_id,
                            candidate=candidate,
                            path=path,
                            kind=str(kind),
                            approval_id=approval_id,
                            metadata=(
                                record.get("metadata")
                                if isinstance(record.get("metadata"), dict)
                                else None
                            ),
                        )
                        artifacts.append(summary.path)
                        artifact_summaries.append(summary)

            status = ReceiptStatus.success
            error = None

            if (
                tool_info.artifact_behavior == "create_file"
                and outputs
                and "path" in outputs
            ):
                artifact_path = outputs["path"]
                summary = self._record_tool_artifact(
                    run_id,
                    candidate=candidate,
                    path=artifact_path,
                    kind=candidate.kind,
                    approval_id=approval_id,
                    metadata={
                        "file_paths": outputs.get("file_paths") or [],
                        "hashes": outputs.get("hashes") or {},
                    },
                )
                artifacts.append(summary.path)
                artifact_summaries.append(summary)

            if failure_message is not None:
                status = ReceiptStatus.failure
                error = failure_message

            if artifacts:
                artifacts = list(dict.fromkeys(artifacts))
            if artifact_summaries:
                deduped: Dict[str, ArtifactSummary] = {}
                for summary in artifact_summaries:
                    deduped[summary.path] = summary
                artifact_summaries = list(deduped.values())

        except Exception as exc:
            outputs = None
            status = ReceiptStatus.failure
            error = str(exc)
            artifacts = []
            side_effects = None
            validation_status = "failed"
            touched_paths = None
            artifact_summaries = []
            mutation_result = None

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
            workflow_id=candidate.workflow_id,
            workflow_step_id=candidate.workflow_step_id,
            started_at=started_at,
            finished_at=finished_at,
            outputs=outputs,
            side_effects=side_effects,
            touched_paths=touched_paths,
            artifacts=artifacts or None,
            artifact_summaries=artifact_summaries or None,
            mutation_result=mutation_result,
            error=error,
            audit_hash=audit_hash,
        )

        receipts_storage.append_receipt(
            run_id,
            receipt.model_dump(mode="json"),
        )
        return receipt
