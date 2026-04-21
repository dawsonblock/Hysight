import { render, screen } from "@testing-library/react";
import SelectedRunPanel from "@/features/autonomy/components/SelectedRunPanel";

const RUN_SUMMARY_FIXTURE = {
  run_id: "run-abc123",
  state: "active",
  goal: "Explore the dataset and produce a report.",
};

function renderSelectedRunPanel(overrides = {}) {
  const props = {
    selectedRunSummary: RUN_SUMMARY_FIXTURE,
    ...overrides,
  };
  const { container } = render(<SelectedRunPanel {...props} />);
  return { props, container };
}

test("renders nothing when selectedRunSummary is null", () => {
  const { container } = renderSelectedRunPanel({ selectedRunSummary: null });
  expect(container).toBeEmptyDOMElement();
});

test("renders run_id when summary is provided", () => {
  renderSelectedRunPanel();
  expect(screen.getByText("run-abc123")).toBeInTheDocument();
});

test("renders formatted state label", () => {
  renderSelectedRunPanel();
  expect(screen.getByText("Active")).toBeInTheDocument();
});

test("renders goal text", () => {
  renderSelectedRunPanel();
  expect(
    screen.getByText("Explore the dataset and produce a report.")
  ).toBeInTheDocument();
});
