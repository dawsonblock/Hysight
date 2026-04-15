import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MemoryBrowser from "@/components/MemoryBrowser";
import { MEMORY_LIST_FIXTURE } from "@/lib/api.fixtures";
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

const MEMORY_RESPONSE = MEMORY_LIST_FIXTURE;

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

test("supports an embedded workspace mode without modal dismissal", async () => {
  const onClose = jest.fn();

  render(<MemoryBrowser open onClose={onClose} variant="embedded" />);

  expect(await screen.findByRole("region", { name: /memory store/i })).toBeInTheDocument();
  expect(screen.queryByTestId("memory-backdrop")).not.toBeInTheDocument();
  expect(screen.queryByTestId("close-memory-btn")).not.toBeInTheDocument();

  fireEvent.keyDown(window, { key: "Escape" });
  expect(onClose).not.toHaveBeenCalled();
});