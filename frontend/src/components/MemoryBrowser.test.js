import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MemoryBrowser from "@/components/MemoryBrowser";
import {
  deleteMemoryRecord,
  listMemories,
  toErrorMessage,
} from "@/lib/api";

jest.mock("@/lib/api", () => ({
  deleteMemoryRecord: jest.fn(),
  listMemories: jest.fn(),
  toErrorMessage: jest.fn((error, fallback) => error?.message || fallback),
}));

const MEMORY_RESPONSE = {
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

beforeEach(() => {
  listMemories.mockResolvedValue(MEMORY_RESPONSE);
  deleteMemoryRecord.mockResolvedValue({ deleted: true, memory_id: "memory-1" });
  toErrorMessage.mockImplementation((error, fallback) => error?.message || fallback);
});

afterEach(() => {
  jest.clearAllMocks();
});

test("shows a selected memory inspector and closes on Escape", async () => {
  const user = userEvent.setup();
  const onClose = jest.fn();

  render(<MemoryBrowser open onClose={onClose} />);

  expect(await screen.findByText("Selected Record")).toBeInTheDocument();
  expect(
    screen.getAllByText(
      "Release summaries should always mention the approval state and the artifact path."
    ).length
  ).toBeGreaterThan(0);

  await user.click(screen.getByText(/Database credentials rotate every 30 days/i));

  expect(
    screen.getAllByText(
      "Database credentials rotate every 30 days and need a reminder record."
    ).length
  ).toBeGreaterThan(0);

  fireEvent.keyDown(window, { key: "Escape" });
  expect(onClose).toHaveBeenCalled();
});