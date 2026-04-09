import "@/App.css";
import { useState } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import HCAChat from "@/components/HCAChat";
import MemoryBrowser from "@/components/MemoryBrowser";

function App() {
  const [memOpen, setMemOpen] = useState(false);

  return (
    <div className="App" style={{ display: "flex", height: "100vh", overflow: "hidden", background: "#f8fafc" }}>
      <BrowserRouter>
        <Routes>
          <Route
            path="/"
            element={
              <HCAChat
                memPanelOpen={memOpen}
                onToggleMemPanel={() => setMemOpen((v) => !v)}
              />
            }
          />
        </Routes>
      </BrowserRouter>

      {/* Memory browser slides in from right */}
      <MemoryBrowser open={memOpen} onClose={() => setMemOpen(false)} />
    </div>
  );
}

export default App;
