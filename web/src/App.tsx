import { useState } from "react";
import { NavLink, Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api } from "./api/client";
import { Tooltip } from "./ui";
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
    group: "Work",
    items: [
      { to: "/", label: "Overview", exact: true },
      { to: "/cases", label: "Cases" },
      { to: "/trace", label: "Decision trace" },
    ],
  },
  {
    group: "Test",
    items: [
      { to: "/simulator", label: "Scenarios" },
      { to: "/compare", label: "Side-by-side" },
    ],
  },
  {
    group: "Evidence",
    items: [
      { to: "/standards", label: "Rules & gaps" },
      { to: "/evaluation", label: "Evaluation" },
      { to: "/audit", label: "Audit chain" },
    ],
  },
];

const TITLES: Record<string, { title: string; purpose: string }> = {
  "/": { title: "Overview", purpose: "Which critical results need a person now, and where every other one is." },
  "/cases": { title: "Cases", purpose: "Every case, where it is, and who holds it." },
  "/simulator": { title: "Scenarios", purpose: "Replay a published incident event by event, or against a weaker system." },
  "/compare": { title: "Side-by-side", purpose: "The same scenario under two configurations, so you can see what each control changes." },
  "/trace": { title: "Decision trace", purpose: "For each step: the evidence retrieved, what the agents said, what code checked, and what the gate allowed." },
  "/standards": { title: "Rules and gaps", purpose: "The clauses behind each decision, whether they bind in Dubai, and where the rules say nothing." },
  "/evaluation": { title: "Evaluation", purpose: "12 scenarios × 12 configurations: which end safely, and which control made the difference." },
  "/audit": { title: "Audit chain", purpose: "Every decision, hash-linked and re-checked when you open it." },
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
  const navigate = useNavigate();
  const [touring, setTouring] = useState(false);
  const [tourErr, setTourErr] = useState(false);

  /** Latest S9 council run, or start and play one, then open the trace at the handoff step. */
  async function tour() {
    setTouring(true);
    setTourErr(false);
    try {
      const runs = await api.listTraces().catch(() => [] as any[]);
      const hit = [...(runs ?? [])].reverse().find((x: any) =>
        /S9/.test(String(x.scenario_id ?? "")) && x.configuration === "resultrelay_council");
      let id: string | undefined = hit?.run_id;
      if (!id) {
        const started = await api.startRun("S9-reply-from-someone-else", "resultrelay_council");
        id = started.run.run_id as string;
        await api.playRun(id);
      }
      navigate(`/trace?run=${encodeURIComponent(id)}&step=5`);
    } catch {
      setTourErr(true);
    } finally {
      setTouring(false);
    }
  }
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
            <div className="brand-sub">Critical lab results</div>
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
          <strong style={{ color: "var(--ink)", fontWeight: 600 }}>Demonstration build.</strong>
          <div style={{ marginTop: 4 }}>
            Synthetic patients; identities invented. No hospital system or live messaging is connected. Clock: simulated, GST.
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
          <div className="row" style={{ gap: 12, flex: "none" }}>
            <button className="btn small primary" onClick={tour} disabled={touring} data-video="tour">
              {touring ? "Opening…" : tourErr ? "Tour failed, retry" : "Start here: 3-minute tour"}
            </button>
            <Tooltip content="No live network, hospital system or patient data. Identities are invented." focusable>
              <span className="data-flag">Scenarios from published incidents · identities invented</span>
            </Tooltip>
          </div>
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
