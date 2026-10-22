import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import CaseTimeline from "./pages/CaseTimeline";
import Simulator from "./pages/Simulator";
import StandardsMapping from "./pages/StandardsMapping";
import Evaluation from "./pages/Evaluation";
import Audit from "./pages/Audit";

const NAV = [
  {
    group: "Operate",
    items: [
      { to: "/", label: "Console", exact: true },
      { to: "/cases", label: "Case timeline" },
      { to: "/simulator", label: "Simulator" },
    ],
  },
  {
    group: "Evidence",
    items: [
      { to: "/standards", label: "Standards & gaps" },
      { to: "/evaluation", label: "Evaluation" },
      { to: "/audit", label: "Audit trail" },
    ],
  },
];

const TITLES: Record<string, { kicker: string; title: string }> = {
  "/": { kicker: "Result communication", title: "Console" },
  "/cases": { kicker: "Case layer", title: "Case timeline" },
  "/simulator": { kicker: "Scenario runner", title: "Simulator" },
  "/standards": { kicker: "Evidence layer", title: "Standards & gaps" },
  "/evaluation": { kicker: "Evidence layer", title: "Evaluation" },
  "/audit": { kicker: "Audit layer", title: "Audit trail" },
};

function Logo() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M4 7h9a4 4 0 0 1 0 8H9" stroke="#eafffa" strokeWidth="2" strokeLinecap="round" />
      <path d="M11 11l-4 4 4 4" stroke="#8ef0dc" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx="19" cy="17" r="2.4" fill="#8ef0dc" />
    </svg>
  );
}

export default function App() {
  const loc = useLocation();
  const meta = TITLES[loc.pathname] ?? { kicker: "ResultRelay", title: "Console" };

  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            <Logo />
          </span>
          <div>
            <div className="brand-name">ResultRelay</div>
            <div className="brand-sub" style={{ whiteSpace: "nowrap" }}>Policy-governed relay</div>
          </div>
        </div>

        {NAV.map((g) => (
          <nav className="nav-group" key={g.group} aria-label={g.group}>
            <div className="nav-label">{g.group}</div>
            {g.items.map((it) => (
              <NavLink
                key={it.to}
                to={it.to}
                end={it.exact}
                className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}
              >
                <span className="dot" />
                {it.label}
              </NavLink>
            ))}
          </nav>
        ))}

        <div className="sidebar-foot">
          <strong style={{ color: "#8b98a4" }}>Demonstration build</strong>
          <div style={{ marginTop: 4 }}>
            Synthetic patients and results only. No EHR, messaging or LLM provider is connected.
          </div>
          <div style={{ marginTop: 8, fontFamily: "var(--mono)", fontSize: 10.5 }}>v0.1.0 · deterministic</div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="topbar-title">
            <span className="kicker">{meta.kicker}</span>
            <h1 style={{ fontSize: 19 }}>{meta.title}</h1>
          </div>
          <div className="row">
            <span className="chip outline" title="Every case in this build is synthetic">
              SYNTHETIC DATA
            </span>
            <span className="chip neutral" title="No live network, EHR or model provider">
              OFFLINE
            </span>
          </div>
        </header>

        <main className="content">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/cases" element={<CaseTimeline />} />
            <Route path="/simulator" element={<Simulator />} />
            <Route path="/standards" element={<StandardsMapping />} />
            <Route path="/evaluation" element={<Evaluation />} />
            <Route path="/audit" element={<Audit />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
