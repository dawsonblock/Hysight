import "@/App.css";
import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import HCAChat from "@/components/HCAChat";
import MemoryBrowser from "@/components/MemoryBrowser";
import OperatorConsole from "@/components/OperatorConsole";
import AutonomyWorkspace from "@/features/autonomy/AutonomyWorkspace";
import { Toaster } from "@/components/ui/toaster";

const SELECTED_RUN_STORAGE_KEY = "hysight:selected-run-id";
const ACTIVE_VIEW_STORAGE_KEY = "hysight:active-view";
const SELECTED_RUN_QUERY_PARAM = "run";
const ACTIVE_VIEW_QUERY_PARAM = "view";

const WORKSPACE_VIEWS = [
  {
    id: "assist",
    label: "Assist",
    description: "Start a live goal and keep the main task in front of you.",
  },
  {
    id: "runs",
    label: "Runs",
    description: "Review replay, approvals, and artifacts without chat noise.",
  },
  {
    id: "memory",
    label: "Memory",
    description: "Search retained context, facts, traces, and procedures.",
  },
  {
    id: "autonomy",
    label: "Autonomy",
    description: "Inspect the bounded autonomy supervisor, agents, schedules, and escalations.",
  },
];

const GUIDE_ITEMS = [
  {
    title: "Start with one goal",
    description:
      "Use Assist when you want the cleanest path: enter a goal, watch the live run, and act only when approval is requested.",
  },
  {
    title: "Review the bounded replay",
    description:
      "Open Runs when you need a fuller answer to what happened, what was approved, and which artifacts were written.",
  },
  {
    title: "Reuse remembered context",
    description:
      "Open Memory to inspect stored traces, facts, and procedures before starting another run or cleaning up stale records.",
  },
  {
    title: "Operate the control plane",
    description:
      "Open Autonomy to inspect bounded operator-style control state, manage agents and schedules, and jump back into replay when a run needs review.",
  },
];

function isValidWorkspaceView(value) {
  return WORKSPACE_VIEWS.some((view) => view.id === value);
}

function readSelectedRunFromUrl() {
  try {
    return new URLSearchParams(window.location.search).get(
      SELECTED_RUN_QUERY_PARAM
    );
  } catch {
    return null;
  }
}

function readStoredSelectedRun() {
  try {
    return window.localStorage.getItem(SELECTED_RUN_STORAGE_KEY);
  } catch {
    return null;
  }
}

function readInitialSelectedRun() {
  return readSelectedRunFromUrl() || readStoredSelectedRun();
}

function readActiveViewFromUrl() {
  try {
    const view = new URLSearchParams(window.location.search).get(
      ACTIVE_VIEW_QUERY_PARAM
    );
    return isValidWorkspaceView(view) ? view : null;
  } catch {
    return null;
  }
}

function readStoredActiveView() {
  try {
    const view = window.localStorage.getItem(ACTIVE_VIEW_STORAGE_KEY);
    return isValidWorkspaceView(view) ? view : null;
  } catch {
    return null;
  }
}

function readInitialActiveView() {
  return readActiveViewFromUrl() || readStoredActiveView() || "assist";
}

function WorkspaceNav({ activeView, onChange }) {
  return (
    <nav aria-label="Workspace views" className="shell-nav">
      {WORKSPACE_VIEWS.map((view) => {
        const isActive = activeView === view.id;
        return (
          <button
            key={view.id}
            aria-pressed={isActive}
            className={`shell-navButton${isActive ? " is-active" : ""}`}
            onClick={() => onChange(view.id)}
            type="button"
          >
            <span className="shell-navLabel">{view.label}</span>
            <span className="shell-navDescription">{view.description}</span>
          </button>
        );
      })}
    </nav>
  );
}

function GuideCard({ index, title, description }) {
  return (
    <article className="shell-guideCard">
      <div className="shell-guideIndex">0{index}</div>
      <h2 className="shell-guideTitle">{title}</h2>
      <p className="shell-guideDescription">{description}</p>
    </article>
  );
}

function App() {
  const [memOpen, setMemOpen] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState(readInitialSelectedRun);
  const [activeView, setActiveView] = useState(readInitialActiveView);
  const [operatorRefreshToken, setOperatorRefreshToken] = useState(0);

  const activeViewMeta =
    WORKSPACE_VIEWS.find((view) => view.id === activeView) || WORKSPACE_VIEWS[0];

  useEffect(() => {
    try {
      if (selectedRunId) {
        window.localStorage.setItem(SELECTED_RUN_STORAGE_KEY, selectedRunId);
      } else {
        window.localStorage.removeItem(SELECTED_RUN_STORAGE_KEY);
      }

      window.localStorage.setItem(ACTIVE_VIEW_STORAGE_KEY, activeView);

      const params = new URLSearchParams(window.location.search);
      if (selectedRunId) {
        params.set(SELECTED_RUN_QUERY_PARAM, selectedRunId);
      } else {
        params.delete(SELECTED_RUN_QUERY_PARAM);
      }

      if (activeView === "assist") {
        params.delete(ACTIVE_VIEW_QUERY_PARAM);
      } else {
        params.set(ACTIVE_VIEW_QUERY_PARAM, activeView);
      }

      const query = params.toString();
      const nextUrl = `${window.location.pathname}${
        query ? `?${query}` : ""
      }${window.location.hash}`;
      window.history.replaceState(window.history.state, "", nextUrl);
    } catch {
      // Ignore storage failures so the shell still renders in restricted modes.
    }
  }, [activeView, selectedRunId]);

  useEffect(() => {
    const handlePopState = () => {
      setSelectedRunId(readInitialSelectedRun());
      setActiveView(readInitialActiveView());
    };

    window.addEventListener("popstate", handlePopState);
    return () => {
      window.removeEventListener("popstate", handlePopState);
    };
  }, []);

  const handleSelectRun = (runId) => {
    setSelectedRunId(runId);
    if (runId && runId === selectedRunId) {
      setOperatorRefreshToken((currentValue) => currentValue + 1);
    }
  };

  const handleRunObserved = (runId) => {
    if (!runId) {
      return;
    }

    setSelectedRunId(runId);
    setOperatorRefreshToken((currentValue) => currentValue + 1);
  };

  const handleChangeView = (nextView) => {
    setActiveView(nextView);
    if (nextView === "memory") {
      setMemOpen(false);
    }
  };

  const handleOpenRunFromAutonomy = (runId) => {
    handleSelectRun(runId);
    setActiveView("runs");
  };

  const renderWorkspace = () => {
    if (activeView === "runs") {
      return (
        <section className="workspace-column workspace-column--full">
          <div className="workspace-context">
            <div>
              <div className="workspace-eyebrow">Replay-first review</div>
              <h2 className="workspace-title">Inspect runs without competing panels.</h2>
              <p className="workspace-description">
                Runs gives replay, approvals, subsystem health, and artifacts a
                dedicated workspace so new users can understand one run at a time.
              </p>
            </div>
          </div>
          <div className="workspace-surface workspace-surface--full">
            <OperatorConsole
              selectedRunId={selectedRunId}
              onSelectRun={handleSelectRun}
              refreshToken={operatorRefreshToken}
              onRunObserved={handleRunObserved}
            />
          </div>
        </section>
      );
    }

    if (activeView === "memory") {
      return (
        <section className="workspace-column workspace-column--full">
          <div className="workspace-context">
            <div>
              <div className="workspace-eyebrow">Retained context</div>
              <h2 className="workspace-title">Search what the system kept.</h2>
              <p className="workspace-description">
                Review stored facts, traces, and procedures in a dedicated
                workspace instead of a transient drawer.
              </p>
            </div>
          </div>
          <div className="workspace-surface workspace-surface--memory">
            <MemoryBrowser
              open
              title="Memory workspace"
              subtitle="Search, inspect, and clean up retained context."
              variant="embedded"
            />
          </div>
        </section>
      );
    }

    if (activeView === "autonomy") {
      return (
        <section className="workspace-column workspace-column--full">
          <div className="workspace-context">
            <div>
              <div className="workspace-eyebrow">Autonomy control plane</div>
              <h2 className="workspace-title">Inspect bounded autonomy without leaving operator replay.</h2>
              <p className="workspace-description">
                Use this workspace to inspect supervisor state, control kill-switch behavior,
                manage agents and schedules, and link active autonomous work back into the
                ordinary Runs surface.
              </p>
            </div>
          </div>
          <div className="workspace-surface workspace-surface--full">
            <AutonomyWorkspace
              onOpenRun={handleOpenRunFromAutonomy}
              selectedRunId={selectedRunId}
            />
          </div>
        </section>
      );
    }

    return (
      <>
        <section className="workspace-column workspace-column--primary">
          <div className="workspace-context">
            <div>
              <div className="workspace-eyebrow">Start here</div>
              <h2 className="workspace-title">Run a goal with the live agent in front.</h2>
              <p className="workspace-description">
                Assist keeps the live goal, streamed state changes, and approval
                moments focused on the main task.
              </p>
            </div>
          </div>
          <div className="workspace-surface workspace-surface--chat">
            <HCAChat
              memPanelOpen={memOpen}
              onToggleMemPanel={() => setMemOpen((value) => !value)}
              onRunObserved={handleRunObserved}
            />
          </div>
        </section>

        <aside className="workspace-column workspace-column--secondary">
          <div className="workspace-context workspace-context--compact">
            <div>
              <div className="workspace-eyebrow">Contextual review</div>
              <h2 className="workspace-title">Keep the latest replay close by.</h2>
              <p className="workspace-description">
                Use the side panel for fast awareness, then switch to Runs when
                you need deeper replay or artifact review.
              </p>
            </div>
            <button
              className="workspace-linkButton"
              onClick={() => handleChangeView("runs")}
              type="button"
            >
              Open the full Runs workspace
            </button>
          </div>
          <div className="workspace-surface workspace-surface--secondary">
            <OperatorConsole
              selectedRunId={selectedRunId}
              onSelectRun={handleSelectRun}
              refreshToken={operatorRefreshToken}
              onRunObserved={handleRunObserved}
            />
          </div>
        </aside>
      </>
    );
  };

  return (
    <BrowserRouter>
      <div className={`App app-shell app-shell--${activeView}`}>
        <div className="app-shell__frame">
          <header className="shell-header">
            <div className="shell-headerCard shell-headerCard--hero">
              <div className="shell-eyebrow">Hysight operator workspace</div>
              <h1 className="shell-title">Guide the agent without losing control.</h1>
              <p className="shell-subtitle">
                Start in Assist for live goals, switch to Runs for replay-backed
                inspection, open Memory when you need retained context, and use
                Autonomy for the bounded control plane.
              </p>
            </div>

            <div className="shell-headerCard shell-headerCard--status">
              <div className="shell-statusLabel">Current focus</div>
              <div className="shell-statusValue">{activeViewMeta.label}</div>
              <p className="shell-statusDescription">
                {activeViewMeta.description}
              </p>
              <div className="shell-statusMeta">
                {selectedRunId
                  ? `Selected run: ${selectedRunId}`
                  : "Selected run: none yet"}
              </div>
            </div>
          </header>

          <section className="shell-guideGrid" aria-label="How to use this workspace">
            {GUIDE_ITEMS.map((item, index) => (
              <GuideCard
                key={item.title}
                description={item.description}
                index={index + 1}
                title={item.title}
              />
            ))}
          </section>

          <div className="shell-toolbar">
            <WorkspaceNav activeView={activeView} onChange={handleChangeView} />
            {activeView !== "memory" && (
              <button
                className="shell-toolbarButton"
                onClick={() => setMemOpen(true)}
                type="button"
              >
                Open quick memory drawer
              </button>
            )}
          </div>

          <div className={`shell-workspace shell-workspace--${activeView}`}>
            <Routes>
              <Route path="/" element={renderWorkspace()} />
            </Routes>
          </div>
        </div>

        {activeView !== "memory" && (
          <MemoryBrowser open={memOpen} onClose={() => setMemOpen(false)} />
        )}
        <Toaster />
      </div>
    </BrowserRouter>
  );
}

export default App;
