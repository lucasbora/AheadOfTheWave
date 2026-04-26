import React from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { Toaster } from "sonner";
import TopNav from "./components/TopNav";
import Dashboard from "./pages/Dashboard";
import Compare from "./pages/Compare";
import Heatmap from "./pages/Heatmap";
import FinlandOracle from "./pages/FinlandOracle";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <TopNav />
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/compare" element={<Compare />} />
          <Route path="/heatmap" element={<Heatmap />} />
          <Route path="/finland" element={<FinlandOracle />} />
        </Routes>
        <Toaster
          position="bottom-right"
          theme="dark"
          toastOptions={{
            style: {
              background: "#0B101D",
              border: "1px solid #1E2535",
              color: "#fff",
              borderRadius: 0,
              fontFamily: "Geist Mono, monospace",
              fontSize: 12,
            },
          }}
        />
      </BrowserRouter>
    </div>
  );
}

export default App;
