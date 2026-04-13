import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

jest.mock("react-router-dom", () => ({
  __esModule: true,
  BrowserRouter: function MockBrowserRouter({ children }) {
    return <>{children}</>;
  },
  Routes: function MockRoutes({ children }) {
    return <>{children}</>;
  },
  Route: function MockRoute({ element }) {
    return element;
  },
}), { virtual: true });

jest.mock("@/components/HCAChat", () => ({
  __esModule: true,
  default: function MockHCAChat({ onRunObserved, onToggleMemPanel }) {
    return (
      <div>
        <button onClick={() => onRunObserved("run-observed")}>Observe run</button>
        <button onClick={onToggleMemPanel}>Toggle memory</button>
      </div>
    );
  },
}));

jest.mock("@/components/OperatorConsole", () => ({
  __esModule: true,
  default: function MockOperatorConsole({ selectedRunId, onSelectRun, refreshToken }) {
    return (
      <div>
        <div data-testid="selected-run-id">{selectedRunId || "none"}</div>
        <div data-testid="refresh-token">{String(refreshToken)}</div>
        <button onClick={() => onSelectRun("run-next")}>Select next run</button>
      </div>
    );
  },
}));

jest.mock("@/components/MemoryBrowser", () => ({
  __esModule: true,
  default: function MockMemoryBrowser({ open, onClose }) {
    return open ? <button onClick={onClose}>Close memory</button> : null;
  },
}));

jest.mock("@/components/ui/toaster", () => ({
  __esModule: true,
  Toaster: function MockToaster() {
    return null;
  },
}));

const App = require("@/App").default;

beforeEach(() => {
  window.localStorage.clear();
  window.history.pushState({}, "", "/?run=run-from-url");
});

afterEach(() => {
  window.history.pushState({}, "", "/");
});

test("initializes from the run query parameter and keeps URL plus storage in sync", async () => {
  const user = userEvent.setup();

  render(<App />);

  expect(screen.getByTestId("selected-run-id")).toHaveTextContent("run-from-url");

  await user.click(screen.getByRole("button", { name: "Select next run" }));

  await waitFor(() => {
    expect(screen.getByTestId("selected-run-id")).toHaveTextContent("run-next");
    expect(window.location.search).toContain("run=run-next");
    expect(window.localStorage.getItem("hysight:selected-run-id")).toBe("run-next");
  });

  await user.click(screen.getByRole("button", { name: "Observe run" }));

  await waitFor(() => {
    expect(screen.getByTestId("selected-run-id")).toHaveTextContent("run-observed");
    expect(screen.getByTestId("refresh-token")).toHaveTextContent("1");
    expect(window.location.search).toContain("run=run-observed");
  });
});