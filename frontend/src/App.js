import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import HCAChat from "@/components/HCAChat";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<HCAChat />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;
