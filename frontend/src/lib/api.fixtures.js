export const APPROVAL_BINDING_FIXTURE = {
  tool_name: "store_note",
  target: "storage/memory/operator-note.md",
  action_class: "memory_write",
  requires_approval: true,
  policy_snapshot: {
    requires_approval: true,
    retention: "operator_review",
  },
  policy_fingerprint: "policy-store-note",
  action_fingerprint: "action-store-note",
};

export const PENDING_APPROVAL_FIXTURE = {
  approval_id: "approval-1",
  status: "pending",
  expired: false,
  request: {
    approval_id: "approval-1",
    action_id: "action-approval-1",
    action_kind: "store_note",
    action_class: "memory_write",
    binding: APPROVAL_BINDING_FIXTURE,
    reason: "Write access is gated for operator review.",
    requested_at: "2026-04-13T15:10:00Z",
    expires_at: null,
  },
  decision: null,
  grant: null,
  consumption: null,
  corruption_count: 0,
};

export const SUBSYSTEMS_FIXTURE = {
  status: "degraded",
  database: {
    enabled: false,
    status: "disabled",
    detail:
      "Mongo-backed /api/status persistence is disabled because MONGO_URL and DB_NAME are unset. Replay-backed HCA and memory routes remain available without Mongo.",
  },
  memory: {
    backend: "python",
    uses_sidecar: false,
    status: "healthy",
    detail: "Python in-process memory controller is the active local memory authority",
    service_url: null,
  },
  storage: {
    status: "writable",
    detail: "HCA storage root and memory storage are writable",
    root: "/tmp/hca",
    memory_dir: "/tmp/hca/memory",
  },
  llm: {
    status: "missing",
    detail:
      "EMERGENT_LLM_KEY is missing; LLM-backed modules will fall back when possible",
  },
};

export const RUN_SUMMARY_FIXTURE = {
  run_id: "run-completed",
  goal: "Successful retrieval",
  state: "completed",
  created_at: "2026-04-13T15:00:00Z",
  updated_at: "2026-04-13T15:05:00Z",
  plan: {
    strategy: "information_retrieval_strategy",
    action: "retrieve_memory",
    planning_mode: "planner",
    confidence: 0.88,
    memory_context_used: true,
    memory_retrieval_status: "hit",
    memory_retrieval_error: null,
    rationale: "Prior release context is available.",
  },
  perception: {
    intent_class: "lookup_request",
    intent: "Find the latest release notes",
    perception_mode: "classifier",
    fallback_reason: null,
    llm_attempted: true,
  },
  critique: {
    verdict: "approved",
    alignment: 0.93,
    feasibility: 0.86,
    safety: 0.98,
    confidence_delta: 0.08,
    llm_powered: true,
    fallback_reason: null,
    issues: ["Response should mention the source artifact."],
    rationale: "Retrieval is safe and well scoped.",
  },
  action_taken: {
    kind: "retrieve_memory",
    arguments: { scope: "release-notes" },
    action_id: "action-1",
    requires_approval: false,
  },
  action_result: {
    status: "success",
    outputs: {},
    artifacts: [],
    error: null,
  },
  approval_id: null,
  approval: null,
  last_approval_decision: null,
  latest_receipt: { status: "success" },
  artifacts: [{ artifact_id: "artifact-1" }, { artifact_id: "artifact-2" }],
  artifacts_count: 2,
  memory_counts: { retrieved: 2 },
  memory_outcomes: { retrieval: ["release-notes", "summary"] },
  active_workflow: {
    workflow_class: "RetrievalWorkflow",
    strategy: "information_retrieval_strategy",
    workflow_id: "wf-1",
  },
  workflow_budget: { consumed_steps: 2, max_steps: 4 },
  workflow_checkpoint: { current_step_id: "return_result", current_step_index: 1 },
  workflow_step_history: [
    {
      step_id: "fetch",
      step_key: "fetch_memory",
      tool_name: "memvid",
      status: "completed",
      action_id: "action-1",
      touched_paths: ["storage/memory/release.json"],
    },
  ],
  workflow_artifacts: [{ artifact_id: "artifact-1" }],
  workflow_outcome: {
    terminal_event: "run_completed",
    reason: "answer returned",
    workflow_step_id: null,
    next_step_id: null,
  },
  discrepancies: [],
  memory_hits: [
    {
      text: "Release summaries should cite the most recent approved notes.",
      score: 0.92,
      memory_type: "procedure",
      stored_at: "2026-04-13T14:58:00Z",
    },
  ],
  key_events: [
    {
      type: "approval_requested",
      actor: "planner",
      timestamp: "2026-04-13T15:02:00Z",
      summary: "Action needs approval",
    },
  ],
  event_count: 8,
  metrics: {
    run_duration_ms: 4321,
    tool_latency: { count: 2, total_ms: 310, max_ms: 180, last_ms: 130 },
    memory_retrieval_latency: { count: 1, total_ms: 80, max_ms: 80, last_ms: 80 },
    memory_commit_latency: { count: 0, total_ms: 0, max_ms: 0, last_ms: null },
  },
};

export const RUN_AWAITING_SUMMARY_FIXTURE = {
  run_id: "run-awaiting",
  goal: "Needs approval follow-up",
  state: "awaiting_approval",
  created_at: "2026-04-13T15:09:00Z",
  updated_at: "2026-04-13T15:10:00Z",
  plan: {
    strategy: "artifact_authoring_strategy",
    action: "store_note",
    planning_mode: "rule_based_fallback",
    confidence: 0.55,
    memory_context_used: false,
    memory_retrieval_status: null,
    memory_retrieval_error: null,
    rationale: "The requested note should be stored after operator approval.",
  },
  perception: {
    intent_class: "store_note",
    intent: "store",
    perception_mode: "rule_based_fallback",
    fallback_reason: null,
    llm_attempted: true,
  },
  critique: {
    verdict: "revise",
    alignment: 0.7,
    feasibility: 0.8,
    safety: 0.9,
    confidence_delta: -0.05,
    llm_powered: false,
    fallback_reason: null,
    issues: ["Approval required before writing the note."],
    rationale: "Write access is gated for operator review.",
  },
  action_taken: {
    kind: "store_note",
    arguments: { note: "Needs approval follow-up" },
    action_id: "action-awaiting-1",
    requires_approval: true,
  },
  action_result: {
    status: null,
    outputs: null,
    artifacts: [],
    error: null,
  },
  approval_id: "approval-1",
  approval: PENDING_APPROVAL_FIXTURE,
  last_approval_decision: null,
  latest_receipt: null,
  artifacts: [],
  artifacts_count: 0,
  memory_counts: { episodic: 0 },
  memory_outcomes: { episodic_memory_writes: 0 },
  active_workflow: null,
  workflow_budget: null,
  workflow_checkpoint: null,
  workflow_step_history: [],
  workflow_artifacts: [],
  workflow_outcome: {
    terminal_event: null,
    reason: null,
    workflow_step_id: null,
    next_step_id: null,
  },
  discrepancies: [],
  memory_hits: [],
  key_events: [
    {
      type: "approval_requested",
      actor: "runtime",
      timestamp: "2026-04-13T15:10:00Z",
      summary: "Approval requested (id=approval-1)",
    },
  ],
  event_count: 6,
  metrics: {
    run_duration_ms: 1600,
    tool_latency: { count: 0, total_ms: 0, max_ms: 0, last_ms: null },
    memory_retrieval_latency: { count: 0, total_ms: 0, max_ms: 0, last_ms: null },
    memory_commit_latency: { count: 0, total_ms: 0, max_ms: 0, last_ms: null },
  },
};

export const RUN_APPROVED_SUMMARY_FIXTURE = {
  ...RUN_AWAITING_SUMMARY_FIXTURE,
  state: "completed",
  updated_at: "2026-04-13T15:12:00Z",
  approval: {
    ...PENDING_APPROVAL_FIXTURE,
    status: "granted",
    decision: {
      approval_id: "approval-1",
      decision: "granted",
      actor: "user",
      reason: "Approved by operator",
      binding: APPROVAL_BINDING_FIXTURE,
      decided_at: "2026-04-13T15:11:00Z",
      expires_at: null,
    },
    grant: {
      approval_id: "approval-1",
      token: "eval-token",
      actor: "user",
      binding: APPROVAL_BINDING_FIXTURE,
      granted_at: "2026-04-13T15:11:30Z",
      expires_at: null,
    },
  },
  last_approval_decision: "granted",
  action_result: {
    status: "success",
    outputs: { note_path: "storage/runs/run-awaiting/artifacts/note.txt" },
    artifacts: [],
    error: null,
  },
  latest_receipt: { status: "success" },
  artifacts: [{ artifact_id: "artifact-awaiting-1" }],
  artifacts_count: 1,
  event_count: 9,
  workflow_outcome: {
    terminal_event: "run_completed",
    reason: "note stored",
    workflow_step_id: null,
    next_step_id: null,
  },
};

export const RUN_LIST_FIXTURE = {
  records: [RUN_AWAITING_SUMMARY_FIXTURE, RUN_SUMMARY_FIXTURE],
  total: 2,
};

export const RUN_EVENTS_FIXTURE = {
  run_id: "run-completed",
  total: 3,
  records: [
    {
      event_id: "event-1",
      run_id: "run-completed",
      event_type: "approval_requested",
      actor: "planner",
      timestamp: "2026-04-13T15:02:00Z",
      summary: "Action needs approval",
      payload: { approval_id: "approval-1", reason: "write access" },
      prior_state: "running",
      next_state: "awaiting_approval",
      is_key_event: true,
    },
    {
      event_id: "event-2",
      run_id: "run-completed",
      event_type: "workflow_selected",
      actor: "planner",
      timestamp: "2026-04-13T15:01:00Z",
      summary: "Workflow selected",
      payload: { workflow_class: "RetrievalWorkflow" },
      prior_state: "running",
      next_state: "running",
      is_key_event: false,
    },
    {
      event_id: "event-3",
      run_id: "run-completed",
      event_type: "run_completed",
      actor: "runtime",
      timestamp: "2026-04-13T15:05:00Z",
      summary: "Run completed",
      payload: { status: "success" },
      prior_state: "running",
      next_state: "completed",
      is_key_event: true,
    },
  ],
};

export const RUN_ARTIFACTS_FIXTURE = {
  run_id: "run-completed",
  total: 2,
  records: [
    {
      artifact_id: "artifact-1",
      run_id: "run-completed",
      action_id: "action-1",
      kind: "summary",
      path: "artifacts/release-summary.md",
      source_action_ids: ["action-1"],
      file_paths: ["artifacts/release-summary.md"],
      hashes: { sha256: "abc" },
      workflow_id: "wf-1",
      approval_id: null,
      metadata: { format: "markdown" },
      created_at: "2026-04-13T15:05:00Z",
      content_available: true,
    },
    {
      artifact_id: "artifact-2",
      run_id: "run-completed",
      action_id: "action-2",
      kind: "trace",
      path: "artifacts/retrieval-trace.json",
      source_action_ids: ["action-2"],
      file_paths: ["artifacts/retrieval-trace.json"],
      hashes: { sha256: "def" },
      workflow_id: "wf-1",
      approval_id: null,
      metadata: { format: "json" },
      created_at: "2026-04-13T15:04:00Z",
      content_available: true,
    },
  ],
};

export const RUN_ARTIFACT_DETAIL_FIXTURE = {
  ...RUN_ARTIFACTS_FIXTURE.records[0],
  content: "# Release Summary\n\n- Item one",
  size_bytes: 128,
  truncated: false,
};

export const RUN_TRACE_ARTIFACT_DETAIL_FIXTURE = {
  ...RUN_ARTIFACTS_FIXTURE.records[1],
  content: '{"status":"ok"}',
  size_bytes: 64,
  truncated: false,
};

export const MEMORY_LIST_FIXTURE = {
  total: 2,
  records: [
    {
      memory_id: "memory-1",
      memory_type: "procedure",
      run_id: "run-1",
      stored_at: "2026-04-13T14:00:00Z",
      text: "Release summaries should always mention the approval state and the artifact path.",
    },
    {
      memory_id: "memory-2",
      memory_type: "preference",
      run_id: "run-2",
      stored_at: "2026-04-13T14:05:00Z",
      text: "Database credentials rotate every 30 days and need a reminder record.",
    },
  ],
};

export const DELETE_MEMORY_FIXTURE = {
  deleted: true,
  memory_id: "memory-1",
};