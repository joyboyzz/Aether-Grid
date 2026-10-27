import React from "react";
import AuthGate from "./AuthGate";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import App from "./App";
import BuyerPortal from "./BuyerPortal";
import Analytics from "./Analytics";
import CarrierPortal from "./CarrierPortal";
import InsurancePortal from "./InsurancePortal";
import "./styles/index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <BrowserRouter>
      <div style={{background: "#422006", color: "#fef3c7", padding: "9px 18px", fontSize: 12, textAlign: "center"}}>
        SIMULATION / PROTOTYPE — software telemetry, heuristic shelf life, simulated escrow & insurance. No actual payments or physical rescue verified.
      </div>
      <AuthGate><Routes>
        <Route path="/buyer" element={<BuyerPortal/>}/>
        <Route path="/analytics" element={<Analytics/>}/>
        <Route path="/carrier" element={<CarrierPortal/>}/>
        <Route path="/insurance" element={<InsurancePortal/>}/>
        <Route path="/*" element={<App/>}/>
      </Routes></AuthGate>
    </BrowserRouter>
  </React.StrictMode>
);
