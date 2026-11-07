import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import CaseTimeline from "./pages/CaseTimeline";
import Simulator from "./pages/Simulator";
import StandardsMapping from "./pages/StandardsMapping";
import Evaluation from "./pages/Evaluation";
import Audit from "./pages/Audit";
import Trace from "./pages/Trace";
import Compare from "./pages/Compare";

const NAV = [
  {
    group: "Operate",
    items: [
      { to: "/", label: "Console", exact: true },
      { to: "/cases", label: "Case timeline" },
      { to: "/simulator", label: "Simulator" },
      { to: "/compare", label: "Side-by-side" },
      { to: "/trace", label: "Decision trace" },
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

const TITLES: Record<string, { title: string; purpose: string }> = {
  "/": { title: "Console", purpose: "Where every critical result is on its way to a person, and which ones need someone now." },
  "/cases": { title: "Case timeline", purpose: "Every event, revision and transition of one case, in order." },
  "/simulator": { title: "Simulator", purpose: "Release a scenario's events one at a time and watch each decision." },
  "/compare": { title: "Side-by-side", purpose: "The same scenario under two configurations, so you can see what each control changes." },
  "/trace": { title: "Decision trace", purpose: "For each step: the evidence retrieved, what the agents said, what code checked, and what the gate allowed." },
  "/standards": { title: "Standards and gaps", purpose: "The policy clauses the system cites, and where the rules say nothing." },
  "/evaluation": { title: "Evaluation", purpose: "Twelve scenarios in twelve configurations: which ones end safely." },
  "/audit": { title: "Audit trail", purpose: "The hash-chained record of every case, re-verified when you open it." },
};

function Logo() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden>
      <path d="M4 7h9a4 4 0 0 1 0 8H9" stroke="#ffffff" strokeWidth="2.2" strokeLinecap="round" />
      <path d="M11 11l-4 4 4 4" stroke="#ffffff" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export default function App() {
  const loc = useLocation();
  const meta = TITLES[loc.pathname] ?? TITLES["/"];

  return (
    <div className="shell">
      <a className="skip-link" href="#main">Skip to content</a>
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark">
            <Logo />
          </span>
          <div>
            <div className="brand-name">ResultRelay</div>
            <div className="brand-sub">Result communication</div>
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
                {it.label}
              </NavLink>
            ))}
          </nav>
        ))}

        <div className="sidebar-foot">
          <strong style={{ color: "var(--ink)", fontWeight: 600 }}>Demonstration build</strong>
          <div style={{ marginTop: 4 }}>
            Synthetic patients and results only. No hospital system or live messaging is connected.
          </div>
          <div className="shell-status">
            <div className="row-s"><span>Synthetic data</span><b>yes</b></div>
            <div className="row-s"><span>Live network</span><b>none</b></div>
            <div className="row-s"><span>Version</span><b className="mono">0.1.0</b></div>
          </div>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div className="topbar-title">
            <h1>{meta.title}</h1>
            <p className="purpose">{meta.purpose}</p>
          </div>
          <span className="data-flag" title="No live network, hospital system or patient data">
            Synthetic data, offline
          </span>
        </header>

        <main className="content" id="main">
          <div key={loc.pathname}>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/cases" element={<CaseTimeline />} />
            <Route path="/simulator" element={<Simulator />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="/trace" element={<Trace />} />
            <Route path="/standards" element={<StandardsMapping />} />
            <Route path="/evaluation" element={<Evaluation />} />
            <Route path="/audit" element={<Audit />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          </div>
        </main>
      </div>
    </div>
  );
}
