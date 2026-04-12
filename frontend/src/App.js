import "@/App.css";
import { useState } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import HCAChat from "@/components/HCAChat";
import MemoryBrowser from "@/components/MemoryBrowser";
import OperatorConsole from "@/components/OperatorConsole";

function App() {
  const [memOpen, setMemOpen] = useState(false);
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [operatorRefreshToken, setOperatorRefreshToken] = useState(0);

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
