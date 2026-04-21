import { render, screen } from "@testing-library/react";
import StyleStatePanel from "@/features/autonomy/components/StyleStatePanel";

const AGENT_FIXTURE = { agent_id: "agent-1", name: "Release supervisor", style_profile_id: "default" };

const AUTONOMY_STATUS_FIXTURE = {
  current_attention_mode: "focused",
  hyperfocus_steps_used: 3,
  reanchor_due: false,
  interrupt_queue_length: 1,
  last_reanchor_summary: null,
};

const CHECKPOINT_FIXTURE = {
  style_profile_id: "drift-aware",
  current_attention_mode: "hyperfocus",
  hyperfocus_steps_used: 3,
  novelty_budget_remaining: 7,
  last_reanchor_summary: null,
};

function renderStyleStatePanel(overrides = {}) {
  const props = {
    agents: [AGENT_FIXTURE],
    autonomyStatus: AUTONOMY_STATUS_FIXTURE,
    latestCheckpointByAgent: { "agent-1": CHECKPOINT_FIXTURE },
    ...overrides,
  };
  render(<StyleStatePanel {...props} />);
  return props;
}

test("shows empty state when no agents available", () => {
  renderStyleStatePanel({ agents: [] });
  expect(screen.getByText("No agents available for style inspection.")).toBeInTheDocument();
});

test("renders Current attention mode label from autonomyStatus", () => {
  renderStyleStatePanel();
  expect(screen.getByText("Current attention mode")).toBeInTheDocument();
  expect(screen.getByText("Focused")).toBeInTheDocument();
});

test("renders agent row with style_profile_id from latest checkpoint", () => {
  renderStyleStatePanel();
  expect(screen.getByText("Release supervisor")).toBeInTheDocument();
  expect(screen.getByText("drift-aware")).toBeInTheDocument();
});

test("renders agent row with fallback style_profile_id from agent when no checkpoint", () => {
  renderStyleStatePanel({ latestCheckpointByAgent: {} });
  expect(screen.getByText("default")).toBeInTheDocument();
});
