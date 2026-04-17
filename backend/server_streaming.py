import asyncio
import concurrent.futures
import json
import os
from typing import Any, Dict, Optional

from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend import server_bootstrap as _server_bootstrap  # noqa: F401
from hca.api.models import CreateRunRequest  # type: ignore[import-untyped]


_STREAM_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
    max_workers=max(4, min(16, os.cpu_count() or 1)),
    thread_name_prefix="hysight-stream",
)
_STREAM_POLL_INTERVAL_SECONDS = 0.3


_STREAM_LABELS: Dict[str, str] = {
    "run_created": "Run initialised",
    "module_proposed": "Module proposed",
    "meta_assessed": "Workspace assessed",
    "action_scored": "Actions scored",
    "action_selected": "Action selected",
    "approval_requested": "Approval required",
    "execution_started": "Executing action",
    "execution_finished": "Execution finished",
    "memory_written": "Memory written",
    "run_completed": "Run completed",
    "run_failed": "Run failed",
    "snapshot_saved": "Snapshot saved",
}


def _stream_label(event: Dict[str, Any]) -> str:
    event_type = event.get("event_type", "")
    actor = event.get("actor", "")
    payload = event.get("payload", {})
    base = str(_STREAM_LABELS.get(event_type, event_type.replace("_", " ")))
    if event_type == "module_proposed":
        source = payload.get("source_module") or actor
        candidate_items = payload.get("candidate_items", [])
        kinds = list({item.get("kind", "") for item in candidate_items if item.get("kind")})
        detail = f"{source}: {', '.join(kinds)}" if kinds else source
        return f"{base} — {detail}"
    if event_type == "action_selected":
        kind = payload.get("kind", "?")
        return f"{base}: {kind}"
    if event_type == "execution_finished":
        status = payload.get("status", "?")
        return f"{base} ({status})"
    if event_type == "approval_requested":
        return f"{base} — action needs your sign-off"
    return base


def _sse(event_type: str, data: Any) -> str:
    def _json_default(value: Any):
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        return str(value)

    payload = json.dumps(data, default=_json_default)
    return f"event: {event_type}\ndata: {payload}\n\n"


async def stream_hca_run(body: CreateRunRequest, extract_run_summary) -> StreamingResponse:
    result_holder: Dict[str, Any] = {
        "run_id": None,
        "done": False,
        "error": None,
    }

    def _execute():
        from hca.runtime.runtime import Runtime  # type: ignore

        class _StreamingRuntime(Runtime):
            def create_run(self, goal, user_id=None):
                context = super().create_run(goal, user_id)
                result_holder["run_id"] = context.run_id
                return context

        try:
            runtime = _StreamingRuntime()
            run_id = runtime.run(body.goal, user_id=body.user_id)
            result_holder["run_id"] = run_id
        except Exception as exc:
            result_holder["error"] = str(exc)
        finally:
            result_holder["done"] = True

    async def generate():
        from hca.storage.event_log import read_events  # type: ignore

        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(_STREAM_EXECUTOR, _execute)

        try:
            yield _sse("status", {"label": "Connecting to agent…", "step": 0})

            event_cursor = 0
            run_id: Optional[str] = None
            step = 1

            while not result_holder["done"]:
                await asyncio.sleep(_STREAM_POLL_INTERVAL_SECONDS)

                if not run_id and result_holder["run_id"]:
                    run_id = result_holder["run_id"]
                    yield _sse(
                        "status",
                        {
                            "label": "Pipeline running…",
                            "step": step,
                            "run_id": run_id,
                        },
                    )
                    step += 1

                if run_id:
                    events, event_cursor = read_events(
                        run_id,
                        offset=event_cursor,
                    )
                    for event in events:
                        yield _sse(
                            "step",
                            {
                                "step": step,
                                "event_id": event.get("event_id"),
                                "event_type": event.get("event_type"),
                                "label": _stream_label(event),
                                "actor": event.get("actor"),
                                "timestamp": event.get("timestamp"),
                                "payload": event.get("payload", {}),
                            },
                        )
                        step += 1

            await asyncio.wait_for(asyncio.wrap_future(future), timeout=5.0)

            if result_holder["error"]:
                yield _sse("error", {"label": result_holder["error"]})
                return

            run_id = result_holder["run_id"]
            if run_id:
                events, event_cursor = read_events(
                    run_id,
                    offset=event_cursor,
                )
                for event in events:
                    yield _sse(
                        "step",
                        {
                            "step": step,
                            "event_id": event.get("event_id"),
                            "event_type": event.get("event_type"),
                            "label": _stream_label(event),
                            "actor": event.get("actor"),
                            "timestamp": event.get("timestamp"),
                            "payload": event.get("payload", {}),
                        },
                    )
                    step += 1

                yield _sse("done", extract_run_summary(run_id))
            else:
                yield _sse("error", {"label": "Run failed to start."})
        finally:
            if not future.done():
                await asyncio.wrap_future(future)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )