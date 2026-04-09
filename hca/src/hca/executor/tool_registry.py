"""Registry of available tools with metadata and policy constraints."""

from typing import Callable, Dict, Any, Optional
from pydantic import BaseModel, Field
from hca.common.enums import ActionClass

class ToolMetadata(BaseModel):
    name: str
    func: Callable[[str, Dict[str, Any]], Dict[str, Any]]
    action_class: ActionClass
    requires_approval: bool
    reversibility: float = 1.0
    timeout: int = 30
    input_schema: Optional[Dict[str, Any]] = None
    output_schema: Optional[Dict[str, Any]] = None
    artifact_behavior: Optional[str] = None

# Tool implementations
def _echo(run_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    text = args.get("text", "")
    return {"echo": text}

def _store_note(run_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    from pathlib import Path
    import uuid
    
    note = args.get("note", "")
    file_id = uuid.uuid4().hex
    path = f"storage/runs/{run_id}/artifacts/note_{file_id}.txt"
    full_path = Path(path)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(note)
    
    return {"path": str(path), "note": note}

def _write_artifact(run_id: str, args: Dict[str, Any]) -> Dict[str, Any]:
    from pathlib import Path
    import uuid
    content = args.get("content", "")
    file_id = uuid.uuid4().hex
    path = f"storage/runs/{run_id}/artifacts/artifact_{file_id}.txt"
    full_path = Path(path)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(full_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    return {"path": str(path), "content": content}

_REGISTRY: Dict[str, ToolMetadata] = {
    "echo": ToolMetadata(
        name="echo",
        func=_echo,
        action_class=ActionClass.low,
        requires_approval=False,
        input_schema={"text": "string"}
    ),
    "store_note": ToolMetadata(
        name="store_note",
        func=_store_note,
        action_class=ActionClass.medium,
        requires_approval=True,
        input_schema={"note": "string"},
        artifact_behavior="create_file"
    ),
    "write_artifact": ToolMetadata(
        name="write_artifact",
        func=_write_artifact,
        action_class=ActionClass.high,
        requires_approval=True,
        input_schema={"content": "string"},
        artifact_behavior="create_file"
    ),
}

def get_tool(name: str) -> ToolMetadata:
    if name not in _REGISTRY:
        raise KeyError(f"Tool '{name}' not found in registry")
    return _REGISTRY[name]

def list_tools() -> Dict[str, ToolMetadata]:
    return _REGISTRY.copy()
