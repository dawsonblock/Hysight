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
  default: function MockMemoryBrowser({ open, onClose, variant = "modal" }) {
    if (!open) {
      return null;
    }

    return (
      <div data-testid={`memory-browser-${variant}`}>
        {variant === "modal" && onClose ? (
          <button onClick={onClose}>Close memory</button>
        ) : null}
      </div>
    );
  },
}));

jest.mock("@/features/autonomy/AutonomyWorkspace", () => ({
  __esModule: true,
  default: function MockAutonomyWorkspace({ onOpenRun, selectedRunId }) {
    return (
      <div data-testid="autonomy-workspace">
        <div data-testid="autonomy-selected-run">{selectedRunId || "none"}</div>
        <button onClick={() => onOpenRun("run-from-autonomy")}>Open autonomy run</button>
      </div>
    );
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
  window.history.pushState({}, "", "/?run=run-from-url&view=runs");
});

afterEach(() => {
  window.history.pushState({}, "", "/");
});

test("keeps run selection synced while switching between all operator workspaces", async () => {
  const user = userEvent.setup();

  render(<App />);

  expect(screen.getByTestId("selected-run-id")).toHaveTextContent("run-from-url");
  expect(screen.getByRole("button", { name: /^Runs/ })).toHaveAttribute(
    "aria-pressed",
    "true"
  );

  await user.click(screen.getByRole("button", { name: /^Assist/ }));

  await waitFor(() => {
    expect(window.location.search).not.toContain("view=");
    expect(window.localStorage.getItem("hysight:active-view")).toBe("assist");
  });

  await user.click(screen.getByRole("button", { name: "Observe run" }));

  await waitFor(() => {
    expect(screen.getByTestId("selected-run-id")).toHaveTextContent("run-observed");
    expect(screen.getByTestId("refresh-token")).toHaveTextContent("1");
    expect(window.location.search).toContain("run=run-observed");
  });

  await user.click(screen.getByRole("button", { name: "Toggle memory" }));

  expect(screen.getByTestId("memory-browser-modal")).toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: "Close memory" }));

  expect(screen.queryByTestId("memory-browser-modal")).not.toBeInTheDocument();

  await user.click(screen.getByRole("button", { name: /^Memory/ }));

  await waitFor(() => {
    expect(screen.getByTestId("memory-browser-embedded")).toBeInTheDocument();
    expect(window.location.search).toContain("run=run-observed");
    expect(window.location.search).toContain("view=memory");
    expect(window.localStorage.getItem("hysight:active-view")).toBe("memory");
    expect(window.localStorage.getItem("hysight:selected-run-id")).toBe(
      "run-observed"
    );
  });

  await user.click(screen.getByRole("button", { name: /^Autonomy/ }));

  await waitFor(() => {
    expect(screen.getByTestId("autonomy-workspace")).toBeInTheDocument();
    expect(screen.getByTestId("autonomy-selected-run")).toHaveTextContent(
      "run-observed"
    );
    expect(window.location.search).toContain("view=autonomy");
  });

  await user.click(screen.getByRole("button", { name: "Open autonomy run" }));

  await waitFor(() => {
    expect(screen.getByTestId("selected-run-id")).toHaveTextContent(
      "run-from-autonomy"
    );
    expect(window.location.search).toContain("run=run-from-autonomy");
    expect(window.location.search).toContain("view=runs");
  });
});