"""Registry of available tools with metadata and policy constraints."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, Iterator, Optional, Type

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictStr,
    ValidationError,
    field_validator,
    model_validator,
)

from hca.common.enums import ActionClass, ApprovalDecision
from hca.common.types import ActionBinding, ActionCandidate
from hca.executor.sandbox import (
    CommandPolicyError,
    allowlisted_commands,
    run_in_sandbox,
)
from hca.storage import load_run
from hca.storage.approvals import (
    get_consumption,
    get_grant,
    get_latest_decision,
    get_request,
    iter_records as iter_approval_records,
)
from hca.storage.artifacts import iter_artifacts
from hca.storage.event_log import iter_events
from hca.storage.receipts import iter_receipts
from hca.paths import REPO_ROOT, relative_run_storage_path, run_storage_path


_READ_FILE_MAX_LINE_WINDOW = 400
_READ_TEXT_MAX_LINE_WINDOW = 400
_GLOB_MAX_RESULTS = 200
_GLOB_MAX_ROOT_RESULTS = 200
_SEARCH_MAX_RESULTS = 100
_SEARCH_MAX_FILES = 80
_SEARCH_MAX_TOTAL_BYTES = 2_000_000
_SEARCH_MAX_FILE_BYTES = 512_000
_STAT_HASH_MAX_BYTES = 1_000_000
_PATCH_MAX_FILE_BYTES = 1_000_000
_PATCH_DIFF_PREVIEW_CHARS = 12_000
_INVESTIGATION_CONTEXT_RADIUS = 2
_INVESTIGATION_MAX_MATCHES = 8
_SEARCH_IGNORED_PREFIXES = (
    PurePosixPath(".git"),
    PurePosixPath("frontend/build"),
    PurePosixPath("memvid/target"),
    PurePosixPath("memvid_service/target"),
    PurePosixPath("storage/runs"),
)
_SEARCH_IGNORED_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    "target",
}


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


def _normalize_glob_pattern(
    value: str,
    *,
    default: str = "**/*",
) -> str:
    raw_value = value.strip()
    if not raw_value:
        raw_value = default

    normalized = PurePosixPath(raw_value.replace("\\", "/"))
    if normalized.is_absolute():
        raise ValueError("pattern must be relative")

    cleaned_parts = [
        part for part in normalized.parts if part not in {"", "."}
    ]
    if any(part == ".." for part in cleaned_parts):
        raise ValueError("pattern must stay within the bounded workspace")

    if not cleaned_parts:
        return default
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


def _combine_scope_and_pattern(scope: str, pattern: str) -> str:
    normalized_scope = _normalize_relative_path(scope, default=".")
    normalized_pattern = _normalize_glob_pattern(pattern)
    if normalized_scope == ".":
        return normalized_pattern
    return PurePosixPath(normalized_scope, normalized_pattern).as_posix()


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


def _relative_repo_path(path: Path) -> str:
    if path == REPO_ROOT:
        return "."
    return path.relative_to(REPO_ROOT).as_posix()


def _should_skip_workspace_path(relative_path: str) -> bool:
    if relative_path == ".":
        return False

    posix_path = PurePosixPath(relative_path)
    if any(part in _SEARCH_IGNORED_DIR_NAMES for part in posix_path.parts):
        return True

    return any(
        posix_path == prefix or prefix in posix_path.parents
        for prefix in _SEARCH_IGNORED_PREFIXES
    )


def _iter_workspace_matches(
    pattern: str,
    *,
    scope: str = ".",
) -> Iterator[tuple[Path, str]]:
    seen: set[str] = set()
    combined_pattern = _combine_scope_and_pattern(scope, pattern)
    for path in sorted(REPO_ROOT.glob(combined_pattern)):
        resolved = path.resolve()
        if not _is_within(REPO_ROOT, resolved):
            continue

        relative_path = _relative_repo_path(resolved)
        if relative_path in seen or _should_skip_workspace_path(relative_path):
            continue

        seen.add(relative_path)
        yield resolved, relative_path


def _is_probably_text_file(path: Path) -> bool:
    try:
        with open(path, "rb") as handle:
            probe = handle.read(4096)
    except OSError:
        return False
    return b"\x00" not in probe


def _sha256_text(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _read_text_file(full_path: Path) -> str:
    if not _is_probably_text_file(full_path):
        raise ValueError("path must refer to a text file")
    return full_path.read_text(encoding="utf-8", errors="ignore")


def _read_text_range_payload(
    full_path: Path,
    normalized_path: str,
    *,
    start_line: int,
    end_line: int,
) -> Dict[str, Any]:
    content = _read_text_file(full_path)
    lines = content.splitlines()
    start_index = start_line - 1
    end_index = min(end_line, len(lines))
    excerpt = "\n".join(lines[start_index:end_index])
    return {
        "path": normalized_path,
        "start_line": start_line,
        "end_line": end_index,
        "line_span": {"start": start_line, "end": end_index},
        "total_lines": len(lines),
        "selected_line_count": max(0, end_index - start_index),
        "content": excerpt,
        "text": excerpt,
        "truncated": end_line > len(lines),
    }


def _line_number_for_index(text: str, index: int) -> int:
    return text[:index].count("\n") + 1


def _changed_line_summary(
    original: str,
    old_text: str,
    new_text: str,
) -> list[Dict[str, int]]:
    start_index = original.index(old_text)
    start_line = _line_number_for_index(original, start_index)
    removed_lines = max(1, old_text.count("\n") + 1)
    added_lines = max(1, new_text.count("\n") + 1)
    return [
        {
            "start_line": start_line,
            "removed_lines": removed_lines,
            "added_lines": added_lines,
        }
    ]


def _write_atomic_text(path: Path, content: str) -> None:
    temp_path: Optional[str] = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            delete=False,
        ) as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
            temp_path = handle.name
        os.replace(temp_path, path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def _unified_diff(path: str, before: str, after: str) -> str:
    diff_lines = difflib.unified_diff(
        before.splitlines(),
        after.splitlines(),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        lineterm="",
        n=3,
    )
    return "\n".join(diff_lines)


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
        if (self.end_line - self.start_line) >= _READ_FILE_MAX_LINE_WINDOW:
            raise ValueError("line window must stay under 400 lines")
        return self


class ReadTextRangeArgs(ReadFileArgs):
    pass


class StatPathArgs(ToolArgsModel):
    path: StrictStr = "."

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        return _normalize_relative_path(value, default=".")


class GlobWorkspaceArgs(ToolArgsModel):
    root: StrictStr = "."
    pattern: StrictStr = "**/*"
    max_results: int = Field(default=50, ge=1, le=_GLOB_MAX_RESULTS)

    @field_validator("root")
    @classmethod
    def _validate_root(cls, value: str) -> str:
        return _normalize_relative_path(value, default=".")

    @field_validator("pattern")
    @classmethod
    def _validate_pattern(cls, value: str) -> str:
        return _normalize_glob_pattern(value)


class SearchWorkspaceArgs(ToolArgsModel):
    query: StrictStr = Field(min_length=1)
    root: StrictStr = "."
    path_glob: StrictStr = "**/*"
    case_sensitive: bool = False
    max_results: int = Field(default=20, ge=1, le=_SEARCH_MAX_RESULTS)
    max_files: int = Field(default=40, ge=1, le=_SEARCH_MAX_FILES)
    max_total_bytes: int = Field(
        default=512_000,
        ge=1,
        le=_SEARCH_MAX_TOTAL_BYTES,
    )

    @field_validator("root")
    @classmethod
    def _validate_root(cls, value: str) -> str:
        return _normalize_relative_path(value, default=".")

    @field_validator("path_glob")
    @classmethod
    def _validate_path_glob(cls, value: str) -> str:
        return _normalize_glob_pattern(value)


class ReplaceInFileArgs(ToolArgsModel):
    path: StrictStr
    old_text: StrictStr = Field(min_length=1)
    new_text: StrictStr = ""
    apply: bool = False
    expected_hash: Optional[StrictStr] = None

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        return _normalize_relative_path(value)

    @field_validator("expected_hash")
    @classmethod
    def _validate_expected_hash(
        cls, value: Optional[str]
    ) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip().lower()
        if len(normalized) != 64 or any(
            character not in "0123456789abcdef" for character in normalized
        ):
            raise ValueError("expected_hash must be a sha256 hex digest")
        return normalized


class PatchTextFileArgs(ReplaceInFileArgs):
    diff_path: Optional[StrictStr] = None

    @field_validator("diff_path")
    @classmethod
    def _validate_diff_path(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None or not value.strip():
            return None
        return _normalize_relative_path(value)


class CreateRunReportArgs(ToolArgsModel):
    path: Optional[StrictStr] = None

    @field_validator("path")
    @classmethod
    def _validate_path(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None or not value.strip():
            return None
        return _normalize_relative_path(value)


class InvestigateWorkspaceIssueArgs(ToolArgsModel):
    query: StrictStr = Field(min_length=1)
    root: StrictStr = "."
    path_glob: StrictStr = "**/*"
    context_radius: int = Field(
        default=_INVESTIGATION_CONTEXT_RADIUS,
        ge=0,
        le=8,
    )
    max_matches: int = Field(default=6, ge=1, le=_INVESTIGATION_MAX_MATCHES)
    report_path: Optional[StrictStr] = None

    @field_validator("root")
    @classmethod
    def _validate_root(cls, value: str) -> str:
        return _normalize_relative_path(value, default=".")

    @field_validator("path_glob")
    @classmethod
    def _validate_path_glob(cls, value: str) -> str:
        return _normalize_glob_pattern(value)

    @field_validator("report_path")
    @classmethod
    def _validate_report_path(
        cls,
        value: Optional[str],
    ) -> Optional[str]:
        if value is None or not value.strip():
            return None
        return _normalize_relative_path(value)


class RunCommandArgs(ToolArgsModel):
    argv: list[StrictStr]
    cwd: StrictStr = "."
    timeout_seconds: int = Field(default=10, ge=1, le=20)

    @field_validator("argv")
    @classmethod
    def _validate_argv(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("argv must contain at least one element")

        normalized = [entry.strip() for entry in value]
        if any(not entry for entry in normalized):
            raise ValueError("argv entries cannot be empty")
        return normalized

    @field_validator("cwd")
    @classmethod
    def _validate_cwd(cls, value: str) -> str:
        return _normalize_relative_path(value, default=".")


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
    path_scope: str = "none"
    max_results: Optional[int] = None
    max_output_chars: Optional[int] = None
    command_allowlist: list[str] = Field(default_factory=list)
    expected_progress: float = 0.0
    expected_uncertainty_reduction: float = 0.0
    risk: float = 0.0
    cost: float = 0.0
    user_interruption_burden: float = 0.0

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
        "path_scope": tool.path_scope,
        "max_results": tool.max_results,
        "max_output_chars": tool.max_output_chars,
        "command_allowlist": tool.command_allowlist,
        "expected_progress": tool.expected_progress,
        "expected_uncertainty_reduction": (
            tool.expected_uncertainty_reduction
        ),
        "risk": tool.risk,
        "cost": tool.cost,
        "user_interruption_burden": tool.user_interruption_burden,
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

    return _read_text_range_payload(
        full_path,
        normalized_path,
        start_line=args["start_line"],
        end_line=args["end_line"],
    )


def _read_text_range(run_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    return _read_file(run_id, args)


def _stat_path(run_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    full_path, normalized_path = _resolve_repo_path(args["path"])
    if not full_path.exists():
        return {"path": normalized_path, "exists": False}

    stat_result = full_path.stat()
    payload: Dict[str, Any] = {
        "path": normalized_path,
        "exists": True,
        "kind": "directory" if full_path.is_dir() else "file",
        "size_bytes": stat_result.st_size,
        "modified_at": datetime.fromtimestamp(
            stat_result.st_mtime,
            tz=timezone.utc,
        ).isoformat(),
    }
    if full_path.is_file():
        payload["is_text"] = _is_probably_text_file(full_path)
        if payload["is_text"]:
            payload["line_count"] = len(
                full_path.read_text(
                    encoding="utf-8",
                    errors="ignore",
                ).splitlines()
            )
        if stat_result.st_size <= _STAT_HASH_MAX_BYTES:
            payload["sha256"] = hashlib.sha256(
                full_path.read_bytes()
            ).hexdigest()
    return payload


def _glob_workspace(run_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    entries = []
    truncated = False
    for full_path, relative_path in _iter_workspace_matches(
        args["pattern"],
        scope=args.get("root", "."),
    ):
        entries.append(
            {
                "path": relative_path,
                "kind": "directory" if full_path.is_dir() else "file",
            }
        )
        if len(entries) >= args["max_results"]:
            truncated = True
            break

    return {
        "root": args.get("root", "."),
        "pattern": args["pattern"],
        "searched_scope": _combine_scope_and_pattern(
            args.get("root", "."),
            args["pattern"],
        ),
        "entries": entries,
        "returned": len(entries),
        "truncated": truncated,
        "budgets": {"max_results": args["max_results"]},
    }


def _search_workspace(run_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    query = args["query"]
    case_sensitive = args.get("case_sensitive", False)
    needle = query if case_sensitive else query.lower()

    matches = []
    scanned_files = 0
    scanned_bytes = 0
    skipped_files = 0
    skipped_binary_files = 0
    skipped_oversized_files = 0
    per_file_counts: Dict[str, int] = {}
    truncation_reasons: list[str] = []

    for full_path, relative_path in _iter_workspace_matches(
        args["path_glob"],
        scope=args.get("root", "."),
    ):
        if not full_path.is_file():
            continue
        file_size = full_path.stat().st_size
        if scanned_files >= args["max_files"]:
            truncation_reasons.append("max_files")
            break
        if file_size > _SEARCH_MAX_FILE_BYTES:
            skipped_files += 1
            skipped_oversized_files += 1
            continue
        if scanned_bytes + file_size > args["max_total_bytes"]:
            truncation_reasons.append("max_total_bytes")
            break
        if not _is_probably_text_file(full_path):
            skipped_files += 1
            skipped_binary_files += 1
            continue

        scanned_files += 1
        scanned_bytes += file_size
        file_match_count = 0
        with open(full_path, "r", encoding="utf-8", errors="ignore") as handle:
            for line_number, line in enumerate(handle, start=1):
                haystack = line if case_sensitive else line.lower()
                if needle not in haystack:
                    continue
                file_match_count += 1
                matches.append(
                    {
                        "path": relative_path,
                        "line_number": line_number,
                        "preview": line.rstrip("\n"),
                    }
                )
                if len(matches) >= args["max_results"]:
                    truncation_reasons.append("max_results")
                    break
        if file_match_count:
            per_file_counts[relative_path] = file_match_count
        if truncation_reasons:
            break

    return {
        "query": query,
        "root": args.get("root", "."),
        "path_glob": args["path_glob"],
        "searched_scope": _combine_scope_and_pattern(
            args.get("root", "."),
            args["path_glob"],
        ),
        "matches": matches,
        "returned": len(matches),
        "returned_match_count": len(matches),
        "total_match_count": sum(per_file_counts.values()),
        "per_file_match_counts": [
            {"path": path, "match_count": count}
            for path, count in sorted(per_file_counts.items())
        ],
        "truncated": bool(truncation_reasons),
        "truncation_reasons": truncation_reasons,
        "scanned_files": scanned_files,
        "scanned_bytes": scanned_bytes,
        "skipped_files": skipped_files,
        "skipped_binary_files": skipped_binary_files,
        "skipped_oversized_files": skipped_oversized_files,
        "budgets": {
            "max_results": args["max_results"],
            "max_files": args["max_files"],
            "max_total_bytes": args["max_total_bytes"],
        },
    }


def _patch_text_file(run_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    full_path, normalized_path = _resolve_repo_path(args["path"])
    if not full_path.exists():
        raise FileNotFoundError(f"File not found: {normalized_path}")
    if not full_path.is_file():
        raise IsADirectoryError(f"Path is not a file: {normalized_path}")
    if full_path.stat().st_size > _PATCH_MAX_FILE_BYTES:
        raise ValueError("target file exceeds bounded patch size")

    original = _read_text_file(full_path)
    before_hash = _sha256_text(original)
    occurrences = original.count(args["old_text"])
    if occurrences == 0:
        raise ValueError("old_text was not found in the target file")
    if occurrences > 1:
        raise ValueError(
            "old_text matched multiple locations; replacement must be "
            "unambiguous"
        )

    updated = original.replace(args["old_text"], args["new_text"], 1)
    if updated == original:
        raise ValueError("patch operation produced no changes")
    after_hash = _sha256_text(updated)
    diff_text = _unified_diff(normalized_path, original, updated)
    changed_lines = _changed_line_summary(
        original,
        args["old_text"],
        args["new_text"],
    )

    applied = False
    if args.get("apply"):
        expected_hash = args.get("expected_hash")
        if not expected_hash:
            raise ValueError("expected_hash is required when apply=true")
        if expected_hash != before_hash:
            raise ValueError(
                "expected_hash does not match the current file state"
            )
        _write_atomic_text(full_path, updated)
        applied = True

    diff_relative_path, diff_full_path = _artifact_paths(
        run_id,
        args.get("diff_path"),
        prefix="patch_diff",
        default_suffix=".diff",
    )
    diff_full_path.parent.mkdir(parents=True, exist_ok=True)
    diff_full_path.write_text(diff_text or "(no diff)\n", encoding="utf-8")

    result: Dict[str, Any] = {
        "path": normalized_path,
        "operation": "replace",
        "occurrence_count": occurrences,
        "before_hash": before_hash,
        "after_hash": after_hash,
        "changed_lines": changed_lines,
        "mutation_summary": {
            "target_path": normalized_path,
            "applied": applied,
            "occurrence_count": occurrences,
        },
        "diff_preview": diff_text[:_PATCH_DIFF_PREVIEW_CHARS],
        "diff_artifact_path": str(diff_relative_path),
        "applied": applied,
    }
    result["_artifact_records"] = [
        {
            "path": str(diff_relative_path),
            "kind": "patch_diff",
            "metadata": {
                "target_path": normalized_path,
                "before_hash": before_hash,
                "after_hash": after_hash,
            },
        }
    ]
    if applied:
        result["_side_effects"] = [f"modified:{normalized_path}"]
    return result


def _replace_in_file(run_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    return _patch_text_file(run_id, args)


def _approval_status_for_report(run_id: str, approval_id: str) -> str:
    request = get_request(run_id, approval_id)
    decision = get_latest_decision(run_id, approval_id)
    grant = get_grant(run_id, approval_id)
    consumption = get_consumption(run_id, approval_id)
    if consumption is not None:
        return "consumed"
    if (
        decision is not None
        and decision.decision == ApprovalDecision.denied
    ):
        return "denied"
    if grant is not None or (
        decision is not None
        and decision.decision == ApprovalDecision.granted
    ):
        return "granted"
    if request is not None:
        return "pending"
    return "missing"


def _memory_outcomes_from_events(
    events: list[Dict[str, Any]],
) -> Dict[str, Any]:
    episodic_writes = 0
    external_writes = 0
    external_failures: list[Dict[str, Any]] = []
    for event in events:
        event_type = event.get("event_type")
        payload = event.get("payload")
        if event_type == "episodic_memory_written":
            episodic_writes += 1
        elif event_type == "external_memory_written":
            external_writes += 1
        elif event_type == "external_memory_write_failed" and isinstance(
            payload, dict
        ):
            external_failures.append(payload)
    return {
        "episodic_memory_writes": episodic_writes,
        "external_memory_writes": external_writes,
        "external_memory_failures": len(external_failures),
        "external_memory_failure_details": external_failures,
    }


def _create_run_report(run_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    context = load_run(run_id)
    events = list(iter_events(run_id))
    receipts = list(iter_receipts(run_id))
    artifacts = list(iter_artifacts(run_id))

    approval_ids = []
    for record in iter_approval_records(run_id):
        approval_id = record.get("approval_id")
        if isinstance(approval_id, str) and approval_id not in approval_ids:
            approval_ids.append(approval_id)

    approvals = []
    for approval_id in approval_ids:
        request = get_request(run_id, approval_id)
        decision = get_latest_decision(run_id, approval_id)
        grant = get_grant(run_id, approval_id)
        consumption = get_consumption(run_id, approval_id)
        approvals.append(
            {
                "approval_id": approval_id,
                "status": _approval_status_for_report(run_id, approval_id),
                "request": (
                    request.model_dump(mode="json") if request else None
                ),
                "decision": (
                    decision.model_dump(mode="json") if decision else None
                ),
                "grant": grant.model_dump(mode="json") if grant else None,
                "consumption": (
                    consumption.model_dump(mode="json")
                    if consumption
                    else None
                ),
            }
        )

    final_status = (
        context.state.value
        if context is not None
        else (
            events[-1].get("next_state")
            if events and events[-1].get("next_state")
            else "unknown"
        )
    )
    memory_outcomes = _memory_outcomes_from_events(events)
    action_records = [
        {
            "action_id": receipt.get("action_id"),
            "action_kind": receipt.get("action_kind"),
            "status": receipt.get("status"),
            "approval_id": receipt.get("approval_id"),
            "validation_status": receipt.get("validation_status"),
            "validated_arguments": receipt.get("validated_arguments"),
            "artifacts": receipt.get("artifacts") or [],
            "side_effects": receipt.get("side_effects") or [],
            "error": receipt.get("error"),
        }
        for receipt in receipts
    ]
    report = {
        "run_id": run_id,
        "final_status": final_status,
        "actions_executed": action_records,
        "approvals_used": approvals,
        "artifacts_produced": artifacts,
        "memory_outcomes": memory_outcomes,
        "event_count": len(events),
        "receipt_count": len(receipts),
    }

    relative_path, full_path = _artifact_paths(
        run_id,
        args.get("path"),
        prefix="run_report",
        default_suffix=".json",
    )
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return {
        "path": str(relative_path),
        "run_id": run_id,
        "final_status": final_status,
        "action_count": len(action_records),
        "approval_count": len(approvals),
        "artifact_count": len(artifacts),
        "memory_outcomes": memory_outcomes,
    }


def _investigate_workspace_issue(
    run_id: str,
    args: Dict[str, Any],
) -> Dict[str, Any]:
    search_result = _search_workspace(
        run_id,
        {
            "query": args["query"],
            "root": args.get("root", "."),
            "path_glob": args["path_glob"],
            "case_sensitive": False,
            "max_results": args["max_matches"],
            "max_files": min(args["max_matches"] * 6, _SEARCH_MAX_FILES),
            "max_total_bytes": min(512_000, _SEARCH_MAX_TOTAL_BYTES),
        },
    )
    evidence = []
    for match in search_result["matches"][: args["max_matches"]]:
        full_path, normalized_path = _resolve_repo_path(match["path"])
        start_line = max(1, match["line_number"] - args["context_radius"])
        end_line = match["line_number"] + args["context_radius"]
        excerpt = _read_text_range_payload(
            full_path,
            normalized_path,
            start_line=start_line,
            end_line=end_line,
        )
        evidence.append(
            {
                "path": normalized_path,
                "line_number": match["line_number"],
                "preview": match["preview"],
                "line_span": excerpt["line_span"],
                "excerpt": excerpt["text"],
            }
        )

    report = {
        "run_id": run_id,
        "query": args["query"],
        "root": args.get("root", "."),
        "path_glob": args["path_glob"],
        "search_summary": search_result,
        "evidence": evidence,
    }
    relative_path, full_path = _artifact_paths(
        run_id,
        args.get("report_path"),
        prefix="investigation",
        default_suffix=".json",
    )
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_text(
        json.dumps(report, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return {
        "path": str(relative_path),
        "query": args["query"],
        "match_count": len(search_result["matches"]),
        "files_with_matches": len(search_result["per_file_match_counts"]),
        "searched_scope": search_result["searched_scope"],
        "returned_evidence_count": len(evidence),
    }


def _run_command(run_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    cwd_full_path, normalized_cwd = _resolve_repo_path(args["cwd"])
    try:
        result = run_in_sandbox(
            args["argv"],
            cwd=cwd_full_path,
            repo_root=REPO_ROOT,
            timeout_seconds=args["timeout_seconds"],
            max_output_chars=12_000,
        )
    except CommandPolicyError as exc:
        raise ValueError(str(exc)) from exc

    return {
        "argv": result["argv"],
        "cwd": normalized_cwd,
        "returncode": result["returncode"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "ok": result["ok"],
        "truncated": result["truncated"],
        "duration_seconds": result["duration_seconds"],
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
        path_scope="repo_root",
        expected_progress=0.2,
        expected_uncertainty_reduction=0.5,
        cost=0.05,
    ),
    "read_text_range": ToolMetadata(
        name="read_text_range",
        description=(
            "Read a bounded line range from a repository-relative text "
            "file."
        ),
        prompt_signature=(
            '{"path": "README.md", "start_line": 1, '
            '"end_line": 80}'
        ),
        func=_read_text_range,
        args_model=ReadTextRangeArgs,
        action_class=ActionClass.low,
        requires_approval=False,
        side_effect_class="read_only",
        path_scope="repo_root",
        expected_progress=0.2,
        expected_uncertainty_reduction=0.75,
        cost=0.05,
    ),
    "read_file": ToolMetadata(
        name="read_file",
        description=(
            "Legacy alias for read_text_range. Reads a bounded line range "
            "from a repository-relative text file."
        ),
        prompt_signature=(
            '{"path": "README.md", "start_line": 1, '
            '"end_line": 80}'
        ),
        func=_read_text_range,
        args_model=ReadTextRangeArgs,
        action_class=ActionClass.low,
        requires_approval=False,
        side_effect_class="read_only",
        path_scope="repo_root",
        expected_progress=0.2,
        expected_uncertainty_reduction=0.75,
        cost=0.05,
    ),
    "stat_path": ToolMetadata(
        name="stat_path",
        description="Return bounded metadata for a repository-relative path.",
        prompt_signature='{"path": "hca/src/hca/common/enums.py"}',
        func=_stat_path,
        args_model=StatPathArgs,
        action_class=ActionClass.low,
        requires_approval=False,
        side_effect_class="read_only",
        path_scope="repo_root",
        expected_progress=0.1,
        expected_uncertainty_reduction=0.4,
        cost=0.03,
    ),
    "glob_workspace": ToolMetadata(
        name="glob_workspace",
        description=(
            "List bounded workspace paths matching a relative glob "
            "pattern."
        ),
        prompt_signature=(
            '{"root": "hca", "pattern": "**/*.py", '
            '"max_results": 50}'
        ),
        func=_glob_workspace,
        args_model=GlobWorkspaceArgs,
        action_class=ActionClass.low,
        requires_approval=False,
        side_effect_class="read_only",
        path_scope="repo_root",
        max_results=_GLOB_MAX_RESULTS,
        expected_progress=0.15,
        expected_uncertainty_reduction=0.65,
        cost=0.05,
    ),
    "search_workspace": ToolMetadata(
        name="search_workspace",
        description="Search bounded repository text files for a query string.",
        prompt_signature=(
            '{"query": "RuntimeState", "root": "hca", '
            '"path_glob": "**/*.py", "max_results": 20}'
        ),
        func=_search_workspace,
        args_model=SearchWorkspaceArgs,
        action_class=ActionClass.low,
        requires_approval=False,
        side_effect_class="read_only",
        path_scope="repo_root",
        max_results=_SEARCH_MAX_RESULTS,
        expected_progress=0.2,
        expected_uncertainty_reduction=0.9,
        cost=0.08,
    ),
    "investigate_workspace_issue": ToolMetadata(
        name="investigate_workspace_issue",
        description=(
            "Search bounded workspace files, gather targeted code ranges, "
            "and emit a structured investigation artifact."
        ),
        prompt_signature=(
            '{"query": "ActionBinding", "root": "hca", '
            '"path_glob": "**/*.py", "max_matches": 6}'
        ),
        func=_investigate_workspace_issue,
        args_model=InvestigateWorkspaceIssueArgs,
        action_class=ActionClass.low,
        requires_approval=False,
        artifact_behavior="create_file",
        side_effect_class="artifact_write",
        path_scope="repo_root",
        max_results=_INVESTIGATION_MAX_MATCHES,
        expected_progress=0.35,
        expected_uncertainty_reduction=0.95,
        cost=0.12,
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
        path_scope="run_artifacts",
        expected_progress=0.35,
        expected_uncertainty_reduction=0.2,
        risk=0.12,
        cost=0.08,
        user_interruption_burden=0.2,
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
        path_scope="run_artifacts",
        expected_progress=0.4,
        expected_uncertainty_reduction=0.1,
        risk=0.2,
        cost=0.12,
        user_interruption_burden=0.2,
    ),
    "create_run_report": ToolMetadata(
        name="create_run_report",
        description=(
            "Create a deterministic run evidence report artifact from "
            "events, receipts, approvals, artifacts, and memory outcomes."
        ),
        prompt_signature='{"path": "reports/run-summary.json"}',
        func=_create_run_report,
        args_model=CreateRunReportArgs,
        action_class=ActionClass.low,
        requires_approval=False,
        artifact_behavior="create_file",
        side_effect_class="artifact_write",
        path_scope="run_artifacts",
        expected_progress=0.3,
        expected_uncertainty_reduction=0.4,
        cost=0.05,
    ),
    "patch_text_file": ToolMetadata(
        name="patch_text_file",
        description=(
            "Preview or apply an exact bounded text mutation with a hash "
            "guard and diff artifact output."
        ),
        prompt_signature=(
            '{"path": "README.md", "old_text": "old", '
            '"new_text": "new", "apply": false}'
        ),
        func=_patch_text_file,
        args_model=PatchTextFileArgs,
        action_class=ActionClass.high,
        requires_approval=True,
        side_effect_class="file_write",
        path_scope="repo_root",
        expected_progress=0.75,
        expected_uncertainty_reduction=0.15,
        risk=0.45,
        cost=0.18,
        user_interruption_burden=0.25,
    ),
    "replace_in_file": ToolMetadata(
        name="replace_in_file",
        description=(
            "Legacy alias for patch_text_file. Preview or apply an exact "
            "single replacement in a repository file using a hash guard."
        ),
        prompt_signature=(
            '{"path": "README.md", "old_text": "old", '
            '"new_text": "new", "apply": false}'
        ),
        func=_patch_text_file,
        args_model=PatchTextFileArgs,
        action_class=ActionClass.high,
        requires_approval=True,
        side_effect_class="file_write",
        path_scope="repo_root",
        expected_progress=0.75,
        expected_uncertainty_reduction=0.15,
        risk=0.45,
        cost=0.18,
        user_interruption_burden=0.25,
    ),
    "run_command": ToolMetadata(
        name="run_command",
        description=(
            "Run an allowlisted local command without a shell in a bounded "
            "repository-relative working directory."
        ),
        prompt_signature=(
            '{"argv": ["pytest", "-q"], "cwd": ".", '
            '"timeout_seconds": 10}'
        ),
        func=_run_command,
        args_model=RunCommandArgs,
        action_class=ActionClass.high,
        requires_approval=True,
        timeout=20,
        side_effect_class="command_exec",
        path_scope="repo_root",
        max_output_chars=12_000,
        command_allowlist=allowlisted_commands(),
        expected_progress=0.45,
        expected_uncertainty_reduction=0.55,
        risk=0.3,
        cost=0.25,
        user_interruption_burden=0.15,
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


def _augment_patch_binding_arguments(
    name: str,
    arguments: Dict[str, Any],
) -> Dict[str, Any]:
    if name not in {"patch_text_file", "replace_in_file"}:
        return arguments
    if not arguments.get("apply") or arguments.get("expected_hash"):
        return arguments

    full_path, normalized_path = _resolve_repo_path(arguments["path"])
    if not full_path.exists() or not full_path.is_file():
        raise ToolValidationError(
            name,
            validation_errors=[
                f"path must reference an existing file: {normalized_path}"
            ],
        )
    if full_path.stat().st_size > _PATCH_MAX_FILE_BYTES:
        raise ToolValidationError(
            name,
            validation_errors=["target file exceeds bounded patch size"],
        )
    if not _is_probably_text_file(full_path):
        raise ToolValidationError(
            name,
            validation_errors=["path must refer to a text file"],
        )

    original = full_path.read_text(encoding="utf-8", errors="ignore")
    updated_arguments = dict(arguments)
    updated_arguments["path"] = normalized_path
    updated_arguments["expected_hash"] = _sha256_text(original)
    return updated_arguments


def build_action_binding(
    name: str,
    arguments: Optional[Dict[str, Any]],
    *,
    target: Optional[str] = None,
) -> ActionBinding:
    tool = get_tool(name)
    normalized_arguments = validate_tool_arguments(name, arguments)
    normalized_arguments = _augment_patch_binding_arguments(
        name,
        normalized_arguments,
    )
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
    tool = get_tool(candidate.kind)
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
            "reversibility": tool.reversibility,
            "expected_progress": tool.expected_progress,
            "expected_uncertainty_reduction": (
                tool.expected_uncertainty_reduction
            ),
            "risk": tool.risk,
            "cost": tool.cost,
            "user_interruption_burden": tool.user_interruption_burden,
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
        expected_progress=tool.expected_progress,
        expected_uncertainty_reduction=(
            tool.expected_uncertainty_reduction
        ),
        risk=tool.risk,
        cost=tool.cost,
        user_interruption_burden=tool.user_interruption_burden,
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
