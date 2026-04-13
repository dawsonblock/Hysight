import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import OperatorConsole from "@/components/OperatorConsole";
import {
  getRunArtifactDetail,
  getRunSummary,
  listRunArtifacts,
  listRunEvents,
  listRuns,
  toErrorMessage,
} from "@/lib/api";

jest.mock("@/lib/api", () => ({
  getRunArtifactDetail: jest.fn(),
  getRunSummary: jest.fn(),
  listRunArtifacts: jest.fn(),
  listRunEvents: jest.fn(),
  listRuns: jest.fn(),
  toErrorMessage: jest.fn((error, fallback) => error?.message || fallback),
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

function renderConsole(activeTab = null) {
  if (activeTab) {
    window.localStorage.setItem("hysight:operator-tab", activeTab);
  }

  return render(
    <OperatorConsole
      selectedRunId="run-completed"
      onSelectRun={jest.fn()}
      refreshToken={0}
    />
  );
}

beforeEach(() => {
  window.localStorage.clear();
  listRuns.mockResolvedValue({ records: RUN_RECORDS, total: 2 });
  getRunSummary.mockResolvedValue(RUN_DETAIL);
  listRunEvents.mockResolvedValue(RUN_EVENTS);
  listRunArtifacts.mockResolvedValue(RUN_ARTIFACTS);
  getRunArtifactDetail.mockImplementation(async (_runId, artifactId) => {
    return artifactId === "artifact-2"
      ? RUN_TRACE_ARTIFACT_DETAIL
      : RUN_ARTIFACT_DETAIL;
  });
  toErrorMessage.mockImplementation((error, fallback) => error?.message || fallback);
});

afterEach(() => {
  jest.clearAllMocks();
});

test("renders replay-backed overview fields and filters the run list", async () => {
  const user = userEvent.setup();

  renderConsole();

  expect(await screen.findByText("Planning")).toBeInTheDocument();
  expect(screen.getByText("Perception")).toBeInTheDocument();
  expect(screen.getByText("Critique")).toBeInTheDocument();
  expect(screen.getByText("Workflow steps")).toBeInTheDocument();
  expect(screen.getByText("Needs approval follow-up")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Completed" }));

  expect(screen.queryByText("Needs approval follow-up")).not.toBeInTheDocument();
  expect(screen.getAllByText("Successful retrieval").length).toBeGreaterThan(0);
});

test("restores the events tab and filters event inspection results", async () => {
  const user = userEvent.setup();

  renderConsole("events");

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

  renderConsole("artifacts");

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