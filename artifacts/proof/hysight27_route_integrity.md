# Hysight-main 27 route-to-runtime integrity

## Verdict

**Result: PASS on this revision (`aad7d10251c53b2b97c989dd3b750124d93d74fe`).**

No route-level bypass of the normal run authority path was found during this audit.

## Evidence

1. **Canonical HCA route remains the ordinary runtime path**
   - `backend/server_hca_routes.py` uses `run_goal(...)` for `/api/hca/run` and the same replay-backed summary/event views for reads.
   - No autonomy-only shortcut execution path was introduced in the HCA routes.

2. **Autonomy HTTP routes do not execute tools directly**
   - `backend/server_autonomy_routes.py` only manages supervisor state, status, schedules, inbox, kill switch, and `tick()`.
   - The route layer delegates to `get_supervisor()` and storage helpers; it does not call the executor or tool registry directly.

3. **Autonomous work is converted into an ordinary HCA run**
   - `hca/src/hca/autonomy/supervisor.py::launch_run()` calls `runtime.create_autonomous_run(...)`.
   - `hca/src/hca/runtime/runtime.py::create_autonomous_run()` persists a normal `RunContext`, sets `autonomy_agent_id`, `autonomy_trigger_id`, and `autonomy_mode`, and writes a standard `run_created` event.

4. **Observation stays replay-backed**
   - `observe_run()` reloads the existing run via `load_run(run_id)` and `read_events(run_id)`.
   - Checkpoints are written through `storage.save_checkpoint(...)`, and all autonomy decisions are emitted onto the normal event log via `append_event(...)`.

## Fresh proof support from this run

- The prerequisite autonomy proof passed fresh: **50 passed, 0 skipped**.
- That proof includes ordinary-run metadata and restart/dedupe coverage, which matches the code-path inspection above.

## Conclusion

For this exact revision, autonomy still respects **one execution authority**:
ordinary HCA runs are created through the runtime, autonomy metadata is attached to those runs, and the replay/event-log surface remains the system of record.