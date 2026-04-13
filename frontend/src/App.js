import "@/App.css";
import { useEffect, useState } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import HCAChat from "@/components/HCAChat";
import MemoryBrowser from "@/components/MemoryBrowser";
import OperatorConsole from "@/components/OperatorConsole";

const SELECTED_RUN_STORAGE_KEY = "hysight:selected-run-id";

function readStoredSelectedRun() {
  try {
    return window.localStorage.getItem(SELECTED_RUN_STORAGE_KEY);
  } catch {
    return null;
  }
}

function App() {
  const [memOpen, setMemOpen] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState(readStoredSelectedRun);
  const [operatorRefreshToken, setOperatorRefreshToken] = useState(0);

  useEffect(() => {
    try {
      if (selectedRunId) {
        window.localStorage.setItem(SELECTED_RUN_STORAGE_KEY, selectedRunId);
        return;
      }

      window.localStorage.removeItem(SELECTED_RUN_STORAGE_KEY);
    } catch {
      // Ignore storage failures so the shell still renders in restricted modes.
    }
  }, [selectedRunId]);

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
            onSelectRun={setSelectedRunId}
            refreshToken={operatorRefreshToken}
          />
        </div>

        <MemoryBrowser open={memOpen} onClose={() => setMemOpen(false)} />
      </div>
    </BrowserRouter>
  );
}

export default App;
