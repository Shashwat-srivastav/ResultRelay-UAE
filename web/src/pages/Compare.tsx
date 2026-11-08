import { useState } from "react";
import { api, currentOwner } from "../api/client";
import { Banner, Empty, Panel, Spinner, StateBadge, fmtTime, useAsync } from "../ui";
import { Chip } from "../ui";
import { Provenance } from "../components";
import { lookup, roleLabel, scenarioKey } from "../labels";
import "../styles/scenarios.css";

const CONFIGS = [
  { id: "resultrelay_council", label: "ResultRelay + agent council" },
  { id: "resultrelay", label: "ResultRelay, rules only" },
  { id: "retrieval_only", label: "Citation-only RAG" },
  { id: "static_rules", label: "Conventional rules" },
  { id: "policy_blind", label: "Policy-blind" },
];
const CLOSED = ["COMMUNICATION_DOCUMENTED", "CORRECTED_RESULT_ACKNOWLEDGED"];
const SHORT: Record<string, string> = { resultrelay_council: "ResultRelay", resultrelay: "ResultRelay (rules only)" };

/** What a configuration did, in a clause: "closes the case", "hands it to the supervisor on duty", or its state label. */
function did(run: any): string {
  const st: string = run.runtime.state;
  if (CLOSED.includes(st)) return "closes the case";
  const owner = currentOwner(run.trace?.escalations);
  if (st.startsWith("ESCALATION") && owner) return `hands it to the ${roleLabel(owner.role).toLowerCase()}`;
  return `ends at \u201c${lookup("state", st, { role: owner?.role }).label}\u201d`;
}

/**
 * One scenario, two configurations, same seed. This is the screen that makes the claim checkable:
 * the difference between the two columns is the policy layer, because nothing else differs.
 */
export default function Compare() {
  const scenarios = useAsync<{ scenarios: any[] }>(() => api.scenarios(), []);
  const [scenario, setScenario] = useState<string>("S9-reply-from-someone-else");
  const [left, setLeft] = useState("policy_blind");
  const [right, setRight] = useState("resultrelay_council");
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

  const nameOf = (id: string) => SHORT[id] ?? CONFIGS.find((c) => c.id === id)?.label ?? id;
  const verdict = (() => {
    if (!runs || !runs[left] || !runs[right] || !diff) return "";
    const tail = scenarioKey(scenario) === "S9" && CLOSED.includes(runs[left].runtime.state) ? " on the daughter\u2019s reply" : "";
    if (!diff.state) return `${nameOf(left)} and ${nameOf(right)} reach the same outcome on this scenario: both ${did(runs[left])}.`;
    return `${nameOf(left)} ${did(runs[left])}${tail}; ${nameOf(right)} ${did(runs[right])}.`;
  })();

  return (
    <div className="stack">
      <Panel title="Run a comparison" hint="same scenario, same seed, two configurations">
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
        <div style={{ marginTop: 10 }}><Provenance scenarioId={scenario} size="strip" /></div>
        {error && <Empty>{error}</Empty>}
      </Panel>

      {runs && diff && (
        <>
        <div className={`verdict${diff.state ? "" : " same"}`} data-video="verdict">
          {verdict}
        </div>
        <div className="cmp-cols">
          {[left, right].map((cfg) => {
            const r = runs[cfg];
            const finalState = r.runtime.state;
            const differs = cfg === left ? null : runs[left].runtime.state !== finalState;
            return (
              <div key={cfg} data-video={cfg === left ? "result-left" : "result-right"}>
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
                    <StateBadge code={finalState} role={currentOwner(r.trace?.escalations)?.role} size="lg" />
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
