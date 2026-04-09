"""Broadcast workspace content to all registered modules."""

from __future__ import annotations

from typing import Any, Dict, List

from hca.workspace.workspace import Workspace


def _normalize_payload(
    source_module: str, payload: Any
) -> List[Dict[str, Any]]:
    if payload is None:
        return []
    payloads = payload if isinstance(payload, list) else [payload]
    normalized: List[Dict[str, Any]] = []
    for entry in payloads:
        if not isinstance(entry, dict):
            continue
        normalized.append(
            {
                "source_module": source_module,
                "revised_proposals": entry.get("revised_proposals", []),
                "confidence_adjustments": entry.get(
                    "confidence_adjustments", []
                ),
                "critique_items": entry.get("critique_items", []),
            }
        )
    return normalized


def broadcast(
    workspace: Workspace, subscribers: List[Any]
) -> List[Dict[str, Any]]:
    """Broadcast current workspace items to subscriber modules.
    This allows modules to update their internal state based on
    workspace content.
    """
    items = workspace.broadcast()
    revision_payloads: List[Dict[str, Any]] = []
    ordered_subscribers = sorted(
        subscribers,
        key=lambda subscriber: getattr(
            subscriber, "name", subscriber.__class__.__name__
        ),
    )
    for sub in ordered_subscribers:
        callback = getattr(sub, "on_broadcast", getattr(sub, "update", None))
        if callable(callback):
            payload = callback(items)
            revision_payloads.extend(
                _normalize_payload(
                    getattr(sub, "name", sub.__class__.__name__),
                    payload,
                )
            )
    revision_payloads.sort(
        key=lambda payload: (
            payload["source_module"],
            len(payload["revised_proposals"]),
            len(payload["confidence_adjustments"]),
            len(payload["critique_items"]),
        )
    )
    return revision_payloads
