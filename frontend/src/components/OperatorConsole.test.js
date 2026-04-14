import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import OperatorConsole from "@/components/OperatorConsole";
import {
  decideRunApproval,
  getRunArtifactDetail,
  getRunSummary,
  listRunArtifacts,
  listRunEvents,
  listRuns,
  toErrorMessage,
} from "@/lib/api";
import { toast } from "@/hooks/use-toast";

jest.mock("@/lib/api", () => ({
  decideRunApproval: jest.fn(),
  getRunArtifactDetail: jest.fn(),
  getRunSummary: jest.fn(),
  listRunArtifacts: jest.fn(),
  listRunEvents: jest.fn(),
  listRuns: jest.fn(),
  toErrorMessage: jest.fn((error, fallback) => error?.message || fallback),
}));

jest.mock("@/hooks/use-toast", () => ({
  toast: jest.fn(),
}));

const RUN_RECORDS = [
  {
    run_id: "run-awaiting",
    goal: "Needs approval follow-up",
    state: "awaiting_approval",
    updated_at: "2026-04-13T15:10:00Z",
    plan: { strategy: "artifact_authoring_strategy" },
    event_count: 6,
    artifacts_count: 1,
  },
  {
    run_id: "run-completed",
    goal: "Successful retrieval",
    state: "completed",
    updated_at: "2026-04-13T15:05:00Z",
    plan: { strategy: "information_retrieval_strategy" },
    event_count: 8,
    artifacts_count: 2,
  },
];

const RUN_DETAIL = {
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
    rationale: "Prior release context is available.",
  },
  perception: {
    intent_class: "lookup_request",
    intent: "Find the latest release notes",
    perception_mode: "classifier",
    llm_attempted: true,
  },
  critique: {
    verdict: "approved",
    alignment: 0.93,
    feasibility: 0.86,
    safety: 0.98,
    confidence_delta: 0.08,
    llm_powered: true,
    issues: ["Response should mention the source artifact."],
    rationale: "Retrieval is safe and well scoped.",
  },
  action_taken: {
    kind: "retrieve_memory",
    arguments: { scope: "release-notes" },
    requires_approval: false,
  },
  action_result: {
    status: "success",
  },
  latest_receipt: { status: "success" },
  artifacts_count: 2,
  event_count: 8,
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
  metrics: {
    run_duration_ms: 4321,
    tool_latency: { count: 2, total_ms: 310, max_ms: 180, last_ms: 130 },
    memory_retrieval_latency: { count: 1, total_ms: 80, max_ms: 80, last_ms: 80 },
    memory_commit_latency: { count: 0, total_ms: 0, max_ms: 0, last_ms: null },
  },
};

const RUN_AWAITING_DETAIL = {
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
    rationale: "The requested note should be stored after operator approval.",
  },
  perception: {
    intent_class: "store_note",
    intent: "store",
    perception_mode: "rule_based_fallback",
    llm_attempted: true,
  },
  critique: {
    verdict: "revise",
    alignment: 0.7,
    feasibility: 0.8,
    safety: 0.9,
    confidence_delta: -0.05,
    llm_powered: false,
    issues: ["Approval required before writing the note."],
    rationale: "Write access is gated for operator review.",
  },
  action_taken: {
    kind: "store_note",
    arguments: { note: "Needs approval follow-up" },
    requires_approval: true,
  },
  action_result: { status: null, error: null },
  latest_receipt: null,
  approval_id: "approval-1",
  approval: { status: "pending" },
  last_approval_decision: null,
  artifacts_count: 0,
  event_count: 6,
  memory_counts: { episodic: 0 },
  memory_outcomes: { episodic_memory_writes: 0 },
  active_workflow: null,
  workflow_budget: null,
  workflow_checkpoint: null,
  workflow_step_history: [],
  workflow_artifacts: [],
  workflow_outcome: { terminal_event: null, reason: null, next_step_id: null },
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
  metrics: {
    run_duration_ms: 1600,
    tool_latency: { count: 0, total_ms: 0, max_ms: 0, last_ms: null },
    memory_retrieval_latency: { count: 0, total_ms: 0, max_ms: 0, last_ms: null },
    memory_commit_latency: { count: 0, total_ms: 0, max_ms: 0, last_ms: null },
  },
};

const RUN_APPROVED_DETAIL = {
  ...RUN_AWAITING_DETAIL,
  state: "completed",
  updated_at: "2026-04-13T15:12:00Z",
  approval: { status: "granted" },
  last_approval_decision: "granted",
  action_result: {
    status: "success",
    outputs: { note_path: "storage/runs/run-awaiting/artifacts/note.txt" },
    error: null,
  },
  latest_receipt: { status: "success" },
  artifacts_count: 1,
  event_count: 9,
  workflow_outcome: {
    terminal_event: "run_completed",
    reason: "note stored",
    next_step_id: null,
  },
};

const RUN_DENIED_DETAIL = {
  ...RUN_AWAITING_DETAIL,
  state: "halted",
  updated_at: "2026-04-13T15:11:00Z",
  approval: { status: "denied" },
  last_approval_decision: "denied",
  event_count: 7,
  workflow_outcome: {
    terminal_event: "approval_denied",
    reason: "operator denied request",
    next_step_id: null,
  },
};

const RUN_EVENTS = {
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

const RUN_ARTIFACTS = {
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

const RUN_ARTIFACT_DETAIL = {
  ...RUN_ARTIFACTS.records[0],
  content: "# Release Summary\n\n- Item one",
  size_bytes: 128,
  truncated: false,
};

const RUN_TRACE_ARTIFACT_DETAIL = {
  ...RUN_ARTIFACTS.records[1],
  content: '{"status":"ok"}',
  size_bytes: 64,
  truncated: false,
};

const RUN_AWAITING_EVENTS = {
  run_id: "run-awaiting",
  total: 1,
  records: [
    {
      event_id: "event-awaiting-1",
      run_id: "run-awaiting",
      event_type: "approval_requested",
      actor: "runtime",
      timestamp: "2026-04-13T15:10:00Z",
      summary: "Action needs approval",
      payload: { approval_id: "approval-1", reason: "write access" },
      prior_state: "running",
      next_state: "awaiting_approval",
      is_key_event: true,
    },
  ],
};

const RUN_AWAITING_ARTIFACTS = {
  run_id: "run-awaiting",
  total: 0,
  records: [],
};

function renderConsole({
  activeTab = null,
  selectedRunId = "run-completed",
  onRunObserved = jest.fn(),
} = {}) {
  if (activeTab) {
    window.localStorage.setItem("hysight:operator-tab", activeTab);
  }

  return render(
    <OperatorConsole
      selectedRunId={selectedRunId}
      onSelectRun={jest.fn()}
      refreshToken={0}
      onRunObserved={onRunObserved}
    />
  );
}

beforeEach(() => {
  window.localStorage.clear();
  decideRunApproval.mockReset();
  listRuns.mockResolvedValue({ records: RUN_RECORDS, total: 2 });
  getRunSummary.mockImplementation(async (runId) => {
    return runId === "run-awaiting" ? RUN_AWAITING_DETAIL : RUN_DETAIL;
  });
  listRunEvents.mockImplementation(async (runId) => {
    return runId === "run-awaiting" ? RUN_AWAITING_EVENTS : RUN_EVENTS;
  });
  listRunArtifacts.mockImplementation(async (runId) => {
    return runId === "run-awaiting" ? RUN_AWAITING_ARTIFACTS : RUN_ARTIFACTS;
  });
  getRunArtifactDetail.mockImplementation(async (_runId, artifactId) => {
    return artifactId === "artifact-2"
      ? RUN_TRACE_ARTIFACT_DETAIL
      : RUN_ARTIFACT_DETAIL;
  });
  toErrorMessage.mockImplementation((error, fallback) => error?.message || fallback);
  toast.mockReset();
});

afterEach(() => {
  jest.clearAllMocks();
});

test("renders replay-backed overview fields and filters the run list", async () => {
  const user = userEvent.setup();

  renderConsole();

  expect(await screen.findByText("Focused run")).toBeInTheDocument();
  expect(screen.getByText("Needs sign-off")).toBeInTheDocument();
  expect(await screen.findByText("Replay digest")).toBeInTheDocument();
  expect(await screen.findByText("Planning")).toBeInTheDocument();
  expect(screen.getByText("Perception")).toBeInTheDocument();
  expect(screen.getAllByText("Critique").length).toBeGreaterThan(0);
  expect(screen.getByText("Workflow steps")).toBeInTheDocument();
  expect(screen.getByText("Needs approval follow-up")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Completed" }));

  expect(screen.queryByText("Needs approval follow-up")).not.toBeInTheDocument();
  expect(screen.getAllByText("Successful retrieval").length).toBeGreaterThan(0);
});

test("restores the events tab and filters event inspection results", async () => {
  const user = userEvent.setup();

  renderConsole({ activeTab: "events" });

  expect(await screen.findByText("Key events")).toBeInTheDocument();
  const filterInput = await screen.findByPlaceholderText(
    "Filter by type, actor, summary, or payload"
  );

  expect(
    screen.getAllByRole("button", { name: /approval_requested/i }).length
  ).toBeGreaterThan(0);
  expect(screen.getByText("Selected event")).toBeInTheDocument();

  await user.type(filterInput, "approval");

  expect(screen.getAllByText("Action needs approval").length).toBeGreaterThan(0);
  expect(screen.queryByText("Workflow selected")).not.toBeInTheDocument();
});

test("filters artifacts and loads the selected artifact detail", async () => {
  const user = userEvent.setup();

  renderConsole({ activeTab: "artifacts" });

  expect(await screen.findByText("Previewable")).toBeInTheDocument();
  const artifactFilter = await screen.findByPlaceholderText(
    "Filter by kind, path, workflow, or action"
  );

  await waitFor(() => {
    expect(getRunArtifactDetail).toHaveBeenCalledWith("run-completed", "artifact-1");
  });

  expect(screen.getByText("Linked files")).toBeInTheDocument();

  await user.type(artifactFilter, "trace");

  await waitFor(() => {
    expect(screen.queryByText("artifacts/release-summary.md")).not.toBeInTheDocument();
    expect(screen.getAllByText("artifacts/retrieval-trace.json").length).toBeGreaterThan(0);
  });
});

test("allows approving a pending run directly from the replay console", async () => {
  const user = userEvent.setup();
  const onRunObserved = jest.fn();

  decideRunApproval.mockResolvedValue(RUN_APPROVED_DETAIL);

  renderConsole({ selectedRunId: "run-awaiting", onRunObserved });

  expect(await screen.findByTestId("operator-approve-btn")).toBeInTheDocument();
  expect(screen.getByTestId("operator-deny-btn")).toBeInTheDocument();

  await user.click(screen.getByTestId("operator-approve-btn"));

  await waitFor(() => {
    expect(decideRunApproval).toHaveBeenCalledWith(
      "run-awaiting",
      "approve",
      "approval-1"
    );
    expect(onRunObserved).toHaveBeenCalledWith("run-awaiting");
    expect(screen.queryByTestId("operator-approve-btn")).not.toBeInTheDocument();
  });
});

test("allows denying a pending run directly from the replay console", async () => {
  const user = userEvent.setup();
  const onRunObserved = jest.fn();

  decideRunApproval.mockResolvedValue(RUN_DENIED_DETAIL);

  renderConsole({ selectedRunId: "run-awaiting", onRunObserved });

  expect(await screen.findByTestId("operator-deny-btn")).toBeInTheDocument();

  await user.click(screen.getByTestId("operator-deny-btn"));

  await waitFor(() => {
    expect(decideRunApproval).toHaveBeenCalledWith(
      "run-awaiting",
      "deny",
      "approval-1"
    );
    expect(onRunObserved).toHaveBeenCalledWith("run-awaiting");
    expect(screen.queryByTestId("operator-deny-btn")).not.toBeInTheDocument();
  });
});