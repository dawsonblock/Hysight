import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import HCAChat from "@/components/HCAChat";
import {
  decideRunApproval,
  streamRun,
  toErrorMessage,
} from "@/lib/api";

jest.mock("react-markdown", () => ({ children }) => <div>{children}</div>);
jest.mock("remark-gfm", () => () => null);

jest.mock("@/lib/api", () => ({
  decideRunApproval: jest.fn(),
  getResponseErrorMessage: jest.fn(async () => "Request failed."),
  streamRun: jest.fn(),
  toErrorMessage: jest.fn((error, fallback) => error?.message || fallback),
}));

function createStreamResponse(chunks) {
  let index = 0;

  return {
    ok: true,
    body: {
      getReader() {
        return {
          read: jest.fn().mockImplementation(() => {
            if (index < chunks.length) {
              const value = Uint8Array.from(Buffer.from(chunks[index], "utf8"));
              index += 1;
              return Promise.resolve({ done: false, value });
            }

            return Promise.resolve({ done: true, value: undefined });
          }),
        };
      },
    },
  };
}

function sse(eventType, data) {
  return `event: ${eventType}\ndata: ${JSON.stringify(data)}\n\n`;
}

const DONE_SUMMARY = {
  run_id: "run-approval",
  goal: "Prepare release summary",
  state: "awaiting_approval",
  approval_id: "approval-1",
  approval: {
    approval_id: "approval-1",
    status: "pending",
    expired: false,
    request: {
      approval_id: "approval-1",
      action_id: "action-approval-1",
      action_kind: "write_artifact",
      action_class: "artifact_write",
      reason: "Operator review is required before writing release artifacts.",
      requested_at: "2026-04-13T15:00:30Z",
      binding: {
        tool_name: "write_artifact",
        target: "artifacts/release-summary.md",
        action_class: "artifact_write",
        requires_approval: true,
        policy_snapshot: {
          requires_approval: true,
          retention: "release-approval-policy",
        },
        policy_fingerprint: "policy-release-artifact",
        action_fingerprint: "action-release-summary",
      },
    },
    decision: null,
    grant: null,
    consumption: null,
    corruption_count: 0,
  },
  plan: {
    strategy: "artifact_authoring_strategy",
    action: "write_artifact",
    planning_mode: "planner",
    confidence: 0.81,
    memory_context_used: true,
    memory_retrieval_status: "hit",
    rationale: "A draft summary should be assembled before sending.",
    fallback_reason: "planner timeout fallback",
  },
  perception: {
    intent_class: "draft_request",
    intent: "Create a release summary",
    perception_mode: "classifier",
    llm_attempted: true,
  },
  critique: {
    verdict: "approved",
    alignment: 0.91,
    feasibility: 0.87,
    safety: 0.97,
    confidence_delta: 0.12,
    llm_powered: true,
    issues: ["Requires approval before writing the artifact."],
    rationale: "Drafting is safe, but write access is gated.",
  },
  active_workflow: {
    workflow_class: "ArtifactWorkflow",
    strategy: "artifact_authoring_strategy",
  },
  workflow_budget: { consumed_steps: 1, max_steps: 3 },
  workflow_checkpoint: { current_step_id: "draft", current_step_index: 0 },
  workflow_outcome: {
    terminal_event: "approval_requested",
    reason: "pending approval",
  },
  workflow_step_history: [
    { step_id: "draft", step_key: "draft_release", status: "completed" },
  ],
  action_taken: {
    kind: "write_artifact",
    requires_approval: true,
    arguments: {
      path: "artifacts/release-summary.md",
      title: "Release summary",
    },
  },
  memory_hits: [
    {
      text: "Previous release summaries use bullet highlights and cite approvals.",
      score: 0.91,
      memory_type: "procedure",
      stored_at: "2026-04-13T14:59:00Z",
    },
  ],
};

beforeEach(() => {
  decideRunApproval.mockResolvedValue({});
  toErrorMessage.mockImplementation((error, fallback) => error?.message || fallback);
});

afterEach(() => {
  jest.clearAllMocks();
});

test("renders the rich operator summary after a streamed run completes", async () => {
  const user = userEvent.setup();
  const onRunObserved = jest.fn();

  streamRun.mockResolvedValue(
    createStreamResponse([
      sse("status", { run_id: "run-approval" }) +
        sse("step", {
          event_type: "workflow_selected",
          label: "Workflow selected",
          timestamp: "2026-04-13T15:00:00Z",
        }) +
        sse("done", DONE_SUMMARY),
    ])
  );

  render(
    <HCAChat
      memPanelOpen={false}
      onToggleMemPanel={jest.fn()}
      onRunObserved={onRunObserved}
    />
  );

  expect(screen.getAllByText("Assist workspace").length).toBeGreaterThan(0);
  expect(screen.getByText("Goal composer")).toBeInTheDocument();

  await user.type(screen.getByTestId("goal-input"), "Prepare release summary");
  await user.click(screen.getByRole("button", { name: "Run goal" }));

  expect(await screen.findByText("AWAITING APPROVAL")).toBeInTheDocument();
  expect(screen.getByText("Run summary")).toBeInTheDocument();
  expect(screen.getByText("Approval required")).toBeInTheDocument();
  expect(
    screen.getAllByText("Operator review is required before writing release artifacts.").length
  ).toBeGreaterThan(0);
  expect(screen.getByText("policy policy-release-artifact")).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Deny" })).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: /Reasoning details/i }));

  expect(screen.getByText("PERCEPTION")).toBeInTheDocument();
  expect(screen.getByText("CRITIQUE")).toBeInTheDocument();
  expect(screen.getByText("WORKFLOW")).toBeInTheDocument();

  await waitFor(() => {
    expect(onRunObserved).toHaveBeenCalledWith("run-approval");
  });
});