import { useEffect, useState } from "react";
import { API_BASE_URL } from "./api";
import UdsKnowledgePanel from "./components/UdsKnowledgePanel";
import RequestConstructionPanel from "./components/RequestConstructionPanel";
import PositiveTestsPanel from "./components/PositiveTestsPanel";
import NegativeTestsPanel from "./components/NegativeTestsPanel";
import ResponseValidationPanel from "./components/ResponseValidationPanel";
import AutomationTemplatesPanel from "./components/AutomationTemplatesPanel";
import AuditTraceabilityPanel from "./components/AuditTraceabilityPanel";

const TABS = [
  { id: "knowledge", label: "UDS Knowledge", Component: UdsKnowledgePanel },
  { id: "request", label: "Request Construction", Component: RequestConstructionPanel },
  { id: "positive", label: "Positive Tests", Component: PositiveTestsPanel },
  { id: "negative", label: "Negative Tests", Component: NegativeTestsPanel },
  { id: "response", label: "ECU Response Validation", Component: ResponseValidationPanel },
  { id: "templates", label: "Automation Templates", Component: AutomationTemplatesPanel },
  { id: "audit", label: "Audit & Traceability", Component: AuditTraceabilityPanel },
];

function App() {
  const [status, setStatus] = useState("checking backend...");
  const [activeTab, setActiveTab] = useState("knowledge");

  useEffect(() => {
    fetch(`${API_BASE_URL}/health`)
      .then((res) => res.json())
      .then((data) => setStatus(`Backend: ${data.status} (${data.app})`))
      .catch(() => setStatus("Backend unreachable"));
  }, []);

  const ActivePanel = TABS.find((t) => t.id === activeTab)?.Component;

  return (
    <div style={{ fontFamily: "var(--sans)", padding: "2rem", maxWidth: 900, margin: "0 auto" }}>
      <h1>UDS Diagnostics Assistant</h1>
      <p style={{ color: "var(--text)" }}>{status}</p>

      <nav style={{ display: "flex", flexWrap: "wrap", gap: "0.5rem", margin: "1rem 0", borderBottom: "1px solid var(--border)", paddingBottom: "0.75rem" }}>
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              background: activeTab === tab.id ? "var(--accent)" : "transparent",
              color: activeTab === tab.id ? "#fff" : "var(--text-h)",
              border: `1px solid ${activeTab === tab.id ? "var(--accent)" : "var(--border)"}`,
              borderRadius: 6,
              padding: "0.4rem 0.8rem",
              cursor: "pointer",
              fontSize: "0.85rem",
            }}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <main>{ActivePanel && <ActivePanel />}</main>
    </div>
  );
}

export default App;
