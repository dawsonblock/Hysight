import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AgentsPanel from "@/features/autonomy/components/AgentsPanel";

function renderAgentsPanel(overrides = {}) {
  const props = {
    actionKey: "",
    activeRunCountByAgent: { "agent-1": 1 },
    agentForm: {
      name: "",
      description: "",
      styleProfileId: "conservative_operator",
      enabled: true,
      maxStepsPerRun: "50",
      maxRunsPerAgent: "25",
      maxParallelRuns: "1",
      maxRetriesPerStep: "2",
      maxRunDurationSeconds: "900",
      deadmanTimeoutSeconds: "1800",
      allowMemoryWrites: true,
      allowExternalWrites: false,
      autoResumeAfterApproval: false,
    },
    agents: [
      {
        agent_id: "agent-1",
        name: "Release supervisor",
        status: "active",
        style_profile_id: "conservative_operator",
      },
    ],
    autonomyStatus: {
      novelty_budget_remaining: 4,
    },
    budgetByAgent: {
      "agent-1": {
        total_steps_observed: 11,
        total_retries_used: 1,
      },
    },
    escalationCountByAgent: { "agent-1": 1 },
    formError: "",
    latestCheckpointByAgent: {
      "agent-1": {
        current_attention_mode: "hyperfocus_review",
        novelty_budget_remaining: 3,
        reanchor_due: true,
        interrupt_queue_length: 2,
        last_reanchor_summary: { summary: "Re-anchor preserved focus." },
      },
    },
    onAgentFormChange: jest.fn(),
    onCreateAgent: jest.fn((event) => event.preventDefault()),
    onPause: jest.fn(),
    onResume: jest.fn(),
    onStop: jest.fn(),
    resourceError: "",
    ...overrides,
  };

  render(<AgentsPanel {...props} />);

  return props;
}

test("renders agent controls and routes pause and stop actions", async () => {
  const user = userEvent.setup();
  const props = renderAgentsPanel();

  expect(screen.getByRole("button", { name: "Resume" })).toBeDisabled();

  await user.click(screen.getByRole("button", { name: "Pause" }));
  await user.click(screen.getByRole("button", { name: "Stop" }));

  expect(props.onPause).toHaveBeenCalledWith(expect.objectContaining({ agent_id: "agent-1" }));
  expect(props.onStop).toHaveBeenCalledWith(expect.objectContaining({ agent_id: "agent-1" }));
});

test("submits the create-agent form through the parent handler", async () => {
  const user = userEvent.setup();
  const props = renderAgentsPanel();

  await user.click(screen.getByRole("button", { name: "Create agent" }));

  expect(props.onCreateAgent).toHaveBeenCalled();
});