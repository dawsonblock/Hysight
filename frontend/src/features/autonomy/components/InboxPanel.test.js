import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import InboxPanel from "@/features/autonomy/components/InboxPanel";

const INBOX_ITEM_FIXTURE = {
  item_id: "item-1",
  agent_id: "agent-1",
  goal: "Check PR queue",
  payload: { source: "operator" },
  status: "queued",
  created_at: "2026-04-21T09:58:00Z",
  claimed_at: null,
};

function renderInboxPanel(overrides = {}) {
  const props = {
    actionKey: "",
    agents: [{ agent_id: "agent-1", name: "Release supervisor" }],
    formError: null,
    inboxForm: { agentId: "", goal: "", payload: "{}" },
    inboxItems: [],
    onCancel: jest.fn(),
    onCreateInboxItem: jest.fn((event) => event.preventDefault()),
    onInboxFormChange: jest.fn(),
    resourceError: null,
    ...overrides,
  };
  render(<InboxPanel {...props} />);
  return props;
}

test("shows empty state when no inbox items returned", () => {
  renderInboxPanel();
  expect(screen.getByText("No inbox items returned.")).toBeInTheDocument();
});

test("shows resource error when provided", () => {
  renderInboxPanel({ resourceError: "Inbox degraded" });
  expect(screen.getByText("Inbox degraded")).toBeInTheDocument();
});

test("Cancel button calls onCancel for an active item", async () => {
  const user = userEvent.setup();
  const props = renderInboxPanel({ inboxItems: [INBOX_ITEM_FIXTURE] });

  expect(screen.getByText("item-1")).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Cancel" }));
  expect(props.onCancel).toHaveBeenCalledWith(INBOX_ITEM_FIXTURE);
});

test("Cancel button is disabled when item is already cancelled", () => {
  renderInboxPanel({
    inboxItems: [{ ...INBOX_ITEM_FIXTURE, status: "cancelled" }],
  });
  expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
});
