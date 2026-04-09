# HCA Project Roadmap

This roadmap tracks the development of the Hybrid Cognitive Agent.

## Phase 0: Packaging and Foundation (COMPLETED)
- [x] Refactor repository into a canonical `src/hca` layout.
- [x] Implement absolute imports for better modularity.
- [x] Establish a functional smoke test suite.

## Phase 1: Human-in-the-Loop (COMPLETED)
- [x] Implement real approval storage with request/grant/consumption tracking.
- [x] Implement `pause` and `resume` logic in the runtime.
- [x] Support asynchronous approval tokens.

## Phase 2: Observability and Replay (COMPLETED)
- [x] Implement stateful reconstruction from event logs and snapshots.
- [x] Add a `replay` CLI for auditing and debugging.
- [x] Standardize event schemas across the runtime.
- [x] **Trace Integrity**: UTC timestamps and event ordering for all logs.
- [x] **Event-Based Replay**: Full reconstruction of run state from raw event logs.

## Phase 3: Execution and Policy (COMPLETED)
- [x] Implement a metadata-rich tool registry.
- [x] Harden the executor with policy enforcement.
- [x] Automate artifact recording and audit hashing.
- [x] **Policy Enforcement**: Executor-level validation of inputs and approval context.

## Phase 4: Cognitive Control (COMPLETED)
- [x] Make the Global Workspace operative with bounded recurrence.
- [x] Implement real contradiction detection in the Meta Monitor.
- [x] Connect monitor signals to runtime control flow.
- [x] **Authoritative State Machine**: Enforcement of legal state transitions.
- [x] **Grounded Cognition**: Real perception-plan-critique-execute loop with grounded stubs.
- [x] **Bounded Replanning**: Controllable recursion for resolving workspace conflicts.

## Phase 5: Memory and Knowledge (COMPLETED)
- [x] Implement multi-store retrieval with keyword search.
- [x] Add contradiction detection for new memory commits.

## Phase 6: Evaluation and Metrics (COMPLETED)
- [x] Implement real evaluation harnesses for metacognition and success rates.
- [x] Standardize metrics reporting.

## Phase 7: Future Work (PLANNED)
- [ ] Implement vector-based semantic search.
- [ ] Add support for multi-agent coordination.
- [ ] Develop a web-based dashboard for monitoring and approvals.
- [ ] Integrate with LLM-based reasoning for complex task decomposition.

## Phase 8: Operational Refinement (v4 - COMPLETED)
- [x] Harden replay with stateful reconstruction of denials and expirations.
- [x] Implement memory staleness scores and retrieval-time contradiction checks.
- [x] Operationalize workspace recurrence with real module-based revision and confidence-based pruning.
- [x] Complete API surface with FastAPI, including state reconstruction and approval management.
- [x] Expand Meta Monitor with broader detections for stale memory and missing info.
- [x] Update documentation and tests to match grounded reality.
