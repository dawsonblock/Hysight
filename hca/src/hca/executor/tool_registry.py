"""Registry of available tools with metadata and policy constraints."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, Optional, Type

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    ValidationError,
    field_validator,
    model_validator,
)

from hca.common.enums import ActionClass
from hca.common.types import ActionBinding, ActionCandidate
from hca.paths import REPO_ROOT, relative_run_storage_path, run_storage_path


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _is_within(base: Path, target: Path) -> bool:
    return target == base or base in target.parents


def _normalize_relative_path(
    value: str,
    *,
    default: Optional[str] = None,
) -> str:
    raw_value = value.strip()
    if not raw_value:
        if default is None:
            raise ValueError("path cannot be empty")
        raw_value = default

    normalized = PurePosixPath(raw_value.replace("\\", "/"))
    if normalized.is_absolute():
        raise ValueError("path must be relative")

    cleaned_parts = [
        part for part in normalized.parts if part not in {"", "."}
    ]
    if any(part == ".." for part in cleaned_parts):
        raise ValueError("path must stay within the bounded workspace")

    if not cleaned_parts:
        return "."
    return PurePosixPath(*cleaned_parts).as_posix()


def _resolve_repo_path(relative_path: str) -> tuple[Path, str]:
    normalized = _normalize_relative_path(relative_path, default=".")
    if normalized == ".":
        resolved = REPO_ROOT
    else:
        resolved = (REPO_ROOT / normalized).resolve()

    if not _is_within(REPO_ROOT, resolved):
        raise ValueError("path must stay within the repository root")

    return resolved, normalized


def _artifact_paths(
    run_id: str,
    requested_path: Optional[str],
    *,
    prefix: str,
    default_suffix: str,
) -> tuple[Path, Path]:
    if requested_path:
        artifact_path = Path(requested_path)
        if artifact_path.suffix == "":
            artifact_path = artifact_path.with_suffix(default_suffix)
    else:
        artifact_path = Path(f"{prefix}_{uuid.uuid4().hex}{default_suffix}")

    full_path = run_storage_path(run_id, "artifacts", *artifact_path.parts)
    relative_path = relative_run_storage_path(
        run_id,
        "artifacts",
        *artifact_path.parts,
    )
    return relative_path, full_path


class ToolArgsModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class EchoArgs(ToolArgsModel):
    text: StrictStr = Field(min_length=1)


class StoreNoteArgs(ToolArgsModel):
    note: StrictStr = Field(min_length=1)


class WriteArtifactArgs(ToolArgsModel):
    content: StrictStr = Field(min_length=1)
    path: Optional[StrictStr] = None

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: Optional[str]) -> Optional[str]:
        if value is None or not value.strip():
            return None
        return _normalize_relative_path(value)


class ListDirArgs(ToolArgsModel):
    path: StrictStr = "."

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        return _normalize_relative_path(value, default=".")


class ReadFileArgs(ToolArgsModel):
    path: StrictStr
    start_line: int = Field(default=1, ge=1)
    end_line: int = Field(default=200, ge=1)

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        return _normalize_relative_path(value)

    @model_validator(mode="after")
    def _validate_line_window(self) -> "ReadFileArgs":
        if self.end_line < self.start_line:
            raise ValueError(
                "end_line must be greater than or equal to start_line"
            )
        if (self.end_line - self.start_line) >= 400:
            raise ValueError("line window must stay under 400 lines")
        return self


class ToolValidationError(ValueError):
    def __init__(
        self,
        tool_name: str,
        *,
        missing_fields: Optional[list[str]] = None,
        invalid_fields: Optional[list[str]] = None,
        validation_errors: Optional[list[str]] = None,
    ) -> None:
        self.tool_name = tool_name
        self.missing_fields = _dedupe(missing_fields or [])
        self.invalid_fields = _dedupe(invalid_fields or [])
        self.validation_errors = _dedupe(validation_errors or [])

        message_parts: list[str] = []
        if self.missing_fields:
            message_parts.append(
                f"missing required fields: {', '.join(self.missing_fields)}"
            )
        if self.invalid_fields:
            message_parts.append(
                f"invalid fields: {', '.join(self.invalid_fields)}"
            )
        if self.validation_errors:
            message_parts.extend(self.validation_errors)

        if not message_parts:
            message_parts.append("invalid arguments")
        message = "; ".join(message_parts)
        super().__init__(
            f"Invalid arguments for tool '{tool_name}': {message}"
        )


class ToolMetadata(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str
    description: str
    prompt_signature: str
    func: Callable[[str, Dict[str, Any]], Dict[str, Any]]
    args_model: Type[ToolArgsModel]
    action_class: ActionClass
    requires_approval: bool
    reversibility: float = 1.0
    timeout: int = 30
    input_schema: Dict[str, Any] = Field(default_factory=dict)
    output_schema: Optional[Dict[str, Any]] = None
    artifact_behavior: Optional[str] = None
    side_effect_class: str = "none"

    def model_post_init(self, __context: Any) -> None:
        if not self.input_schema:
            self.input_schema = self.args_model.model_json_schema()

    def validate_arguments(self, args: Dict[str, Any]) -> Dict[str, Any]:
        normalized = self.args_model.model_validate(args)
        return normalized.model_dump(exclude_none=True)

    def required_fields(self) -> list[str]:
        return sorted(
            name
            for name, field in self.args_model.model_fields.items()
            if field.is_required()
        )


def _stable_json(payload: Any) -> str:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _fingerprint(payload: Any) -> str:
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def _policy_snapshot(tool: ToolMetadata) -> Dict[str, Any]:
    return {
        "tool_name": tool.name,
        "action_class": tool.action_class.value,
        "requires_approval": tool.requires_approval,
        "reversibility": tool.reversibility,
        "timeout": tool.timeout,
        "artifact_behavior": tool.artifact_behavior,
        "side_effect_class": tool.side_effect_class,
        "required_fields": tool.required_fields(),
    }


def _translate_validation_error(
    tool_name: str,
    exc: ValidationError,
) -> ToolValidationError:
    missing_fields: list[str] = []
    invalid_fields: list[str] = []
    validation_errors: list[str] = []

    for error in exc.errors():
        loc = error.get("loc", ())
        field_name = str(loc[-1]) if loc else ""
        error_type = str(error.get("type", ""))
        message = str(error.get("msg", "invalid value"))

        if error_type == "missing" and field_name:
            missing_fields.append(field_name)
            continue

        if field_name:
            invalid_fields.append(field_name)
            validation_errors.append(f"{field_name}: {message}")
        else:
            validation_errors.append(message)

    return ToolValidationError(
        tool_name,
        missing_fields=missing_fields,
        invalid_fields=invalid_fields,
        validation_errors=validation_errors,
    )


def _echo(run_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    return {"echo": args["text"]}


def _store_note(run_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    note = args["note"]
    path, full_path = _artifact_paths(
        run_id,
        None,
        prefix="note",
        default_suffix=".txt",
    )
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(note, encoding="utf-8")
    return {"path": str(path), "note": note}


def _write_artifact(run_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    content = args["content"]
    path, full_path = _artifact_paths(
        run_id,
        args.get("path"),
        prefix="artifact",
        default_suffix=".txt",
    )
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(content, encoding="utf-8")
    return {"path": str(path), "content": content}


def _list_dir(run_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    full_path, normalized_path = _resolve_repo_path(args["path"])
    if not full_path.exists():
        raise FileNotFoundError(f"Directory not found: {normalized_path}")
    if not full_path.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {normalized_path}")

    entries = [
        {
            "name": child.name,
            "kind": "directory" if child.is_dir() else "file",
        }
        for child in sorted(
            full_path.iterdir(),
            key=lambda child: (not child.is_dir(), child.name.lower()),
        )
    ]
    return {"path": normalized_path, "entries": entries}


def _read_file(run_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    full_path, normalized_path = _resolve_repo_path(args["path"])
    if not full_path.exists():
        raise FileNotFoundError(f"File not found: {normalized_path}")
    if not full_path.is_file():
        raise IsADirectoryError(f"Path is not a file: {normalized_path}")

    content = full_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    start_index = args["start_line"] - 1
    end_index = min(args["end_line"], len(lines))
    excerpt = "\n".join(lines[start_index:end_index])
    return {
        "path": normalized_path,
        "start_line": args["start_line"],
        "end_line": end_index,
        "total_lines": len(lines),
        "content": excerpt,
    }


_REGISTRY: Dict[str, ToolMetadata] = {
    "echo": ToolMetadata(
        name="echo",
        description="Return the provided text without side effects.",
        prompt_signature='{"text": "<message>"}',
        func=_echo,
        args_model=EchoArgs,
        action_class=ActionClass.low,
        requires_approval=False,
    ),
    "list_dir": ToolMetadata(
        name="list_dir",
        description="List entries from a repository-relative directory.",
        prompt_signature='{"path": "."}',
        func=_list_dir,
        args_model=ListDirArgs,
        action_class=ActionClass.low,
        requires_approval=False,
        side_effect_class="read_only",
    ),
    "read_file": ToolMetadata(
        name="read_file",
        description=(
            "Read a bounded line range from a repository-relative "
            "text file."
        ),
        prompt_signature=(
            '{"path": "README.md", "start_line": 1, '
            '"end_line": 80}'
        ),
        func=_read_file,
        args_model=ReadFileArgs,
        action_class=ActionClass.low,
        requires_approval=False,
        side_effect_class="read_only",
    ),
    "store_note": ToolMetadata(
        name="store_note",
        description="Persist a note inside run-scoped artifact storage.",
        prompt_signature='{"note": "<text to persist>"}',
        func=_store_note,
        args_model=StoreNoteArgs,
        action_class=ActionClass.medium,
        requires_approval=True,
        artifact_behavior="create_file",
        side_effect_class="file_write",
    ),
    "write_artifact": ToolMetadata(
        name="write_artifact",
        description="Write content to a bounded run artifact path.",
        prompt_signature=(
            '{"content": "<file body>", '
            '"path": "notes/output.txt"}'
        ),
        func=_write_artifact,
        args_model=WriteArtifactArgs,
        action_class=ActionClass.high,
        requires_approval=True,
        artifact_behavior="create_file",
        side_effect_class="file_write",
    ),
}


def get_tool(name: str) -> ToolMetadata:
    if name not in _REGISTRY:
        raise KeyError(f"Tool '{name}' not found in registry")
    return _REGISTRY[name]


def list_tools() -> Dict[str, ToolMetadata]:
    return _REGISTRY.copy()


def required_fields(name: str) -> list[str]:
    return get_tool(name).required_fields()


def validate_tool_arguments(
    name: str,
    arguments: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    tool = get_tool(name)
    if arguments is None:
        payload: Dict[str, Any] = {}
    elif isinstance(arguments, dict):
        payload = arguments
    else:
        raise ToolValidationError(
            name,
            validation_errors=["arguments must be an object"],
        )

    try:
        return tool.validate_arguments(payload)
    except ValidationError as exc:
        raise _translate_validation_error(name, exc) from exc


def build_action_binding(
    name: str,
    arguments: Optional[Dict[str, Any]],
    *,
    target: Optional[str] = None,
) -> ActionBinding:
    tool = get_tool(name)
    normalized_arguments = validate_tool_arguments(name, arguments)
    policy_snapshot = _policy_snapshot(tool)
    policy_fingerprint = _fingerprint(policy_snapshot)
    action_fingerprint = _fingerprint(
        {
            "tool_name": tool.name,
            "target": target,
            "normalized_arguments": normalized_arguments,
            "policy_fingerprint": policy_fingerprint,
        }
    )
    return ActionBinding(
        tool_name=tool.name,
        target=target,
        normalized_arguments=normalized_arguments,
        action_class=tool.action_class,
        requires_approval=tool.requires_approval,
        policy_snapshot=policy_snapshot,
        policy_fingerprint=policy_fingerprint,
        action_fingerprint=action_fingerprint,
    )


def canonicalize_action_candidate(
    candidate: ActionCandidate,
) -> ActionCandidate:
    binding = build_action_binding(
        candidate.kind,
        candidate.arguments,
        target=candidate.target,
    )
    return candidate.model_copy(
        update={
            "arguments": binding.normalized_arguments,
            "action_class": binding.action_class,
            "requires_approval": binding.requires_approval,
            "binding": binding,
        }
    )


def build_action_candidate(
    kind: Any,
    arguments: Optional[Dict[str, Any]],
    *,
    provenance: Optional[list[str]] = None,
    target: Optional[str] = None,
) -> ActionCandidate:
    if not isinstance(kind, str) or not kind:
        raise ToolValidationError(
            str(kind),
            validation_errors=["action kind must be a non-empty string"],
        )

    tool = get_tool(kind)
    binding = build_action_binding(kind, arguments, target=target)
    return ActionCandidate(
        kind=tool.name,
        target=target,
        arguments=binding.normalized_arguments,
        action_class=binding.action_class,
        binding=binding,
        reversibility=tool.reversibility,
        requires_approval=binding.requires_approval,
        provenance=provenance or [],
    )


def tool_prompt_catalog() -> str:
    lines = []
    for tool in sorted(_REGISTRY.values(), key=lambda item: item.name):
        approval = (
            "requires user approval"
            if tool.requires_approval
            else "no approval needed"
        )
        lines.append(
            f"  {tool.name:<15} {tool.prompt_signature:<60} [{approval}]"
        )
    return "\n".join(lines)
