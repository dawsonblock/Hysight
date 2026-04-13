import "@/App.css";
import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import HCAChat from "@/components/HCAChat";
import MemoryBrowser from "@/components/MemoryBrowser";
import OperatorConsole from "@/components/OperatorConsole";
import { Toaster } from "@/components/ui/toaster";

const SELECTED_RUN_STORAGE_KEY = "hysight:selected-run-id";
const SELECTED_RUN_QUERY_PARAM = "run";

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

function App() {
  const [memOpen, setMemOpen] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState(readInitialSelectedRun);
  const [operatorRefreshToken, setOperatorRefreshToken] = useState(0);

  useEffect(() => {
    try {
      if (selectedRunId) {
        window.localStorage.setItem(SELECTED_RUN_STORAGE_KEY, selectedRunId);
      } else {
        window.localStorage.removeItem(SELECTED_RUN_STORAGE_KEY);
      }

      const params = new URLSearchParams(window.location.search);
      if (selectedRunId) {
        params.set(SELECTED_RUN_QUERY_PARAM, selectedRunId);
      } else {
        params.delete(SELECTED_RUN_QUERY_PARAM);
      }

      const query = params.toString();
      const nextUrl = `${window.location.pathname}${
        query ? `?${query}` : ""
      }${window.location.hash}`;
      window.history.replaceState(window.history.state, "", nextUrl);
    } catch {
      // Ignore storage failures so the shell still renders in restricted modes.
    }
  }, [selectedRunId]);

  useEffect(() => {
    const handlePopState = () => {
      setSelectedRunId(readInitialSelectedRun());
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

  return (
    <BrowserRouter>
      <div className="App app-shell">
        <div className="app-main">
          <Routes>
            <Route
              path="/"
              element={
                <HCAChat
                  memPanelOpen={memOpen}
                  onToggleMemPanel={() => setMemOpen((v) => !v)}
                  onRunObserved={handleRunObserved}
                />
              }
            />
          </Routes>
        </div>

        <div className="app-operator">
          <OperatorConsole
            selectedRunId={selectedRunId}
            onSelectRun={handleSelectRun}
            refreshToken={operatorRefreshToken}
          />
        </div>

        <MemoryBrowser open={memOpen} onClose={() => setMemOpen(false)} />
        <Toaster />
      </div>
    </BrowserRouter>
  );
}

export default App;
