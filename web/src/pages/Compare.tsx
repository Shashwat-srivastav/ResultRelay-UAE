import { useState } from "react";
import { api } from "../api/client";
import { Banner, Chip, Empty, Panel, Spinner, fmtTime, useAsync } from "../ui";

const CONFIGS = [
  { id: "resultrelay", label: "ResultRelay (policy-governed)" },
  { id: "retrieval_only", label: "Citation-only RAG" },
  { id: "static_rules", label: "Conventional rules" },
  { id: "policy_blind", label: "Policy-blind" },
];

/**
 * One scenario, two configurations, same seed. This is the screen that makes the claim checkable:
 * the difference between the two columns is the policy layer, because nothing else differs.
 */
export default function Compare() {
  const scenarios = useAsync<{ scenarios: any[] }>(() => api.scenarios(), []);
  const [scenario, setScenario] = useState<string>("S6-jurisdiction-conflict");
  const [left, setLeft] = useState("resultrelay");
  const [right, setRight] = useState("retrieval_only");
  const [busy, setBusy] = useState(false);
  const [runs, setRuns] = useState<Record<string, any> | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function runBoth() {
    setBusy(true);
    setError(null);
    setRuns(null);
    try {
      const out: Record<string, any> = {};
      for (const cfg of [left, right]) {
        const started = await api.startRun(scenario, cfg);
        const runId = started.run.run_id;
        await api.playRun(runId);
        out[cfg] = { runtime: await api.getRun(runId), trace: await api.trace(runId) };
      }
      setRuns(out);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  const list = scenarios.data?.scenarios ?? [];
  const diff = runs && runs[left] && runs[right]
    ? {
        state: runs[left].runtime.state !== runs[right].runtime.state,
        citations: citedBinding(runs[left].trace) !== citedBinding(runs[right].trace),
        foreign: foreignCitations(runs[right].trace).length > 0 || foreignCitations(runs[left].trace).length > 0,
      }
    : null;

  return (
    <div className="stack">
      <Banner tone="info">
        <span>
          The same synthetic scenario is executed twice, once per configuration, from the same seed. Any difference
          in the two columns is attributable to the policy layer, because the scenario, the transport plan and the
          event order are identical.
        </span>
      </Banner>

      <Panel title="Run a comparison">
        <div className="row" style={{ gap: 10, flexWrap: "wrap" }}>
          <select value={scenario} onChange={(e) => setScenario(e.target.value)} style={{ width: 340 }} aria-label="scenario">
            {list.map((s: any) => (
              <option key={s.scenario_id} value={s.scenario_id}>
                {s.scenario_id}
              </option>
            ))}
          </select>
          <select value={left} onChange={(e) => setLeft(e.target.value)} style={{ width: 250 }} aria-label="left configuration">
            {CONFIGS.map((c) => (
              <option key={c.id} value={c.id}>{c.label}</option>
            ))}
          </select>
          <span className="muted">vs</span>
          <select value={right} onChange={(e) => setRight(e.target.value)} style={{ width: 250 }} aria-label="right configuration">
            {CONFIGS.map((c) => (
              <option key={c.id} value={c.id}>{c.label}</option>
            ))}
          </select>
          <button className="btn" onClick={runBoth} disabled={busy || left === right}>
            {busy ? <Spinner /> : "Run both"}
          </button>
        </div>
        {left === right && <div className="tiny muted">Pick two different configurations.</div>}
        {error && <Empty>{error}</Empty>}
      </Panel>

      {runs && diff && (
        <>
        <div className="row" style={{ alignItems: "flex-start", gap: 16, flexWrap: "wrap" }}>
          {[left, right].map((cfg) => {
            const r = runs[cfg];
            const finalState = r.runtime.state;
            const differs = cfg === left ? null : runs[left].runtime.state !== finalState;
            return (
              <div key={cfg} style={{ flex: "1 1 400px", minWidth: 340 }}>
              <Panel
                title={CONFIGS.find((c) => c.id === cfg)?.label ?? cfg}
                hint={
                  cfg === right
                    ? diff && diff.state
                      ? "different final state"
                      : diff?.citations
                        ? "same final state — different citations"
                        : "identical on both dimensions"
                    : undefined
                }
              >
                <div className="stack" style={{ gap: 8 }}>
                  <div className="row" style={{ gap: 8 }}>
                    <Chip tone={finalState.includes("ACKNOWLEDGED") || finalState === "COMMUNICATION_DOCUMENTED" ? "ok" : "warn"}>
                      {finalState}
                    </Chip>
                    <span className="tiny muted">{r.runtime.attempts.length} attempt(s)</span>
                  </div>

                  <div className="tiny">
                    <span className="muted">citations used</span>
                    <div className="mono">{citedBinding(r.trace) || "none"}</div>
                    {foreignCitations(r.trace).length > 0 && (
                      <div style={{ marginTop: 4 }}>
                        <Chip tone="warn">outside the case jurisdiction</Chip>{" "}
                        <span className="mono">{foreignCitations(r.trace).join(", ")}</span>
                      </div>
                    )}
                  </div>

                  <div className="tiny">
                    <span className="muted">gate refusals</span>
                    <div>{blockedSteps(r.trace)}</div>
                  </div>

                  <div className="tiny">
                    <span className="muted">final steps</span>
                    {r.trace.steps.slice(-3).map((s: any) => (
                      <div key={s.step} className="mono">
                        #{s.step} {fmtTime(s.at)} → {s["6_resulting_state"]}
                        {s["4_gate"].invariant ? ` [${s["4_gate"].invariant}]` : ""}
                      </div>
                    ))}
                  </div>
                </div>
              </Panel>
              </div>
            );
          })}
        </div>
        </>
      )}

      {runs && diff && diff.foreign && (
        <Banner tone="warn">
          <span>
            One column grounded its reasoning in material from outside the case jurisdiction. A Dubai case may be
            informed by another emirate's standard or by an international body, but neither can underwrite an action
            — which is exactly what the policy layer is for.
          </span>
        </Banner>
      )}

      {runs && diff && !diff.state && !diff.citations && (
        <Banner tone="info">
          <span>
            These two configurations reached the same outcome on this scenario. That is a real result, not a
            failure of the comparison: it means this scenario does not discriminate between them.
          </span>
        </Banner>
      )}
    </div>
  );
}

/** Citations whose source is not AE-DU or AE-FED — material that cannot bind a Dubai case. */
function foreignCitations(trace: any): string[] {
  const out = new Set<string>();
  for (const step of trace.steps)
    for (const e of step["2_evidence"] ?? []) {
      const id = String(e.source_id ?? "");
      if (id && !["S1", "U1", "U2", "U3", "U4", "U5"].includes(id)) out.add(`${id} ${e.section ?? ""}`.trim());
    }
  return [...out].sort();
}

function citedBinding(trace: any): string {
  const ids = new Set<string>();
  for (const step of trace.steps)
    for (const p of step["3_proposals"] ?? [])
      for (const c of p.citations ?? []) ids.add(String(c));
  return [...ids].sort().join(", ");
}

function blockedSteps(trace: any): string {
  const blocked = trace.steps.filter((s: any) => s["4_gate"]?.permitted === false);
  if (!blocked.length) return "none";
  return blocked
    .map((s: any) => `#${s.step} ${s["4_gate"].invariant ?? "blocked"}`)
    .join(" · ");
}
