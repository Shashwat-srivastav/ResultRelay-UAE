import { useEffect, useMemo, useRef, useState } from "react";
import { api, currentOwner } from "../api/client";
import {
  Banner, Chip, CLAIM_TONE, Empty, Panel, Skeleton, Spinner, StateBadge, fmtTime, statusTone, useAsync,
} from "../ui";
import { deadline, roleLabel } from "../labels";
import { ChainBeam, Provenance } from "../components";
import "../styles/scenarios.css";
import type { Run, Step } from "../types";

/** The number is a check/citation heuristic (audit finding M-1): say so where it is rendered. */
function supportTooltip(a: Step["agents"][number]): string {
  const basis =
    a.data && typeof a.data.confidence_basis === "string"
      ? a.data.confidence_basis
      : "derived: checks, citations, unresolved questions (heuristic)";
  return (
    "Support score in [0,1] - a heuristic from the number of checks performed, citations available " +
    "and questions left open. It is not a probability and not model certainty. Basis: " + basis
  );
}

export default function Simulator() {
  const scen = useAsync<any>(() => api.scenarios(), []);
  const [scenarioId, setScenarioId] = useState<string>("");
  const [config, setConfig] = useState<string>("resultrelay");
  const [run, setRun] = useState<Run | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [total, setTotal] = useState(0);
  const [focus, setFocus] = useState<number | null>(null);
  const runRef = useRef<string | null>(null);

  useEffect(() => {
    if (!scenarioId && scen.data?.scenarios?.length) {
      setScenarioId(scen.data.scenarios[0].scenario_id);
    }
  }, [scen.data, scenarioId]);

  const selectedScenario = useMemo(
    () => (scen.data?.scenarios ?? []).find((s: any) => s.scenario_id === scenarioId),
    [scen.data, scenarioId]
  );

  async function start() {
    setBusy(true);
    setErr(null);
    setSteps([]);
    setDone(false);
    setFocus(null);
    try {
      const res = await api.startRun(scenarioId, config);
      runRef.current = res.run.run_id;
      setRun(res.run);
      setTotal(res.events_remaining);
    } catch (e: any) {
      setErr(String(e.message ?? e));
    } finally {
      setBusy(false);
    }
  }

  async function step() {
    if (!runRef.current) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await api.stepRun(runRef.current);
      setRun(res.run);
      if (res.step) setSteps((s) => [...s, res.step]);
      setDone(res.done);
      if (res.progress) setTotal(res.progress.total);
    } catch (e: any) {
      setErr(String(e.message ?? e));
    } finally {
      setBusy(false);
    }
  }

  async function play() {
    if (!runRef.current) return;
    setBusy(true);
    setErr(null);
    try {
      const res = await api.playRun(runRef.current);
      setRun(res.run);
      setSteps(res.run.steps ?? []);
      setDone(true);
    } catch (e: any) {
      setErr(String(e.message ?? e));
    } finally {
      setBusy(false);
    }
  }

  async function downloadBundle() {
    if (!runRef.current) return;
    const bundle = await api.auditBundle(runRef.current);
    const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${runRef.current}-bundle.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  const owner = run ? currentOwner(run.escalations as any) : null;
  const dl = owner ? deadline(owner.due_at, steps.length ? steps[steps.length - 1].at : null) : null;
  const chainStates = run ? (steps.length ? steps.map((x) => x.resulting_state) : [run.state]) : [];
  const progress = total ? Math.min(100, (steps.length / total) * 100) : 0;

  return (
    <div className="stack">
      <Panel title="Run a scenario" hint="a fixed list of events, released in order">
        <div className="grid cols-4" style={{ alignItems: "end" }}>
          <div className="field" style={{ gridColumn: "span 2" }}>
            <label htmlFor="scenario">Scenario</label>
            {scen.loading ? (
              <Skeleton height={34} />
            ) : (
              <select id="scenario" value={scenarioId} onChange={(e) => setScenarioId(e.target.value)} disabled={busy}>
                {(scen.data?.scenarios ?? []).map((s: any) => (
                  <option key={s.scenario_id} value={s.scenario_id}>
                    {s.scenario_id} — {s.title} ({s.step_count} events)
                  </option>
                ))}
              </select>
            )}
          </div>
          <div className="field">
            <label htmlFor="config">Configuration</label>
            {scen.loading ? (
              <Skeleton height={34} />
            ) : (
              <select id="config" value={config} onChange={(e) => setConfig(e.target.value)} disabled={busy}>
                {Object.entries(scen.data?.configurations ?? {}).map(([k, v]: any) => (
                  <option key={k} value={k}>
                    {v.label}
                  </option>
                ))}
              </select>
            )}
          </div>
          <div className="row">
            <button className="btn primary" onClick={start} disabled={busy || !scenarioId}>
              {busy && !run ? <Spinner /> : "Start run"}
            </button>
          </div>
        </div>

        {scenarioId && (
          <div className="sim-prov">
            <Provenance scenarioId={scenarioId} provenance={selectedScenario?.provenance} size="strip" />
          </div>
        )}
        {selectedScenario && (
          <div style={{ marginTop: 12 }}>
            <div className="small">{selectedScenario.summary}</div>
            <div className="row-wrap" style={{ marginTop: 8 }}>
              <Chip tone="neutral">{selectedScenario.case_scope}</Chip>
              {selectedScenario.variant_of && <Chip tone="info">variant of {selectedScenario.variant_of}</Chip>}
              {scen.data?.configurations?.[config] && (
                <span className="tiny muted">{scen.data.configurations[config].description}</span>
              )}
            </div>
          </div>
        )}
      </Panel>

      {err && <Banner tone="bad">{err}</Banner>}

      {run && (
        <>
          <div className="grid split-8-4">
            <div data-video="case-state">
            <Panel
              title="Case state"
              hint={`${run.case_id} · ${run.configuration}`}
              action={
                <div className="row">
                  <button className="btn small" onClick={step} disabled={busy || done}>
                    {busy ? <Spinner /> : "Step"}
                  </button>
                  <button className="btn small" onClick={play} disabled={busy || done}>
                    Run to end
                  </button>
                  <button className="btn small ghost" onClick={downloadBundle} disabled={busy}>
                    Export bundle
                  </button>
                </div>
              }
            >
              <div className="row-wrap" style={{ marginBottom: 10 }}>
                <StateBadge code={run.state} role={owner?.role} size="lg" />
                <span className="small muted">{run.state_description}</span>
              </div>
              <div style={{ marginBottom: 12 }}>
                <ChainBeam states={chainStates} role={owner?.role} />
              </div>
              <div style={{ height: 6, background: "#eef1f4", borderRadius: 3, overflow: "hidden" }}>
                <div
                  style={{
                    width: `${progress}%`, height: "100%", background: "var(--accent)",
                    transition: "width 0.25s ease",
                  }}
                />
              </div>
              <div className="spread" style={{ marginTop: 6 }}>
                <span className="tiny muted">{steps.length} of {total} events released</span>
                {done && <Chip tone="ok">run complete</Chip>}
              </div>

              <div className="owner-card-wrap" data-video="owner-now" style={{ marginTop: 14 }}>
                <div className={`owner-card${owner ? "" : " none"}`}>
                  <div className="k">Owner now</div>
                  {owner ? (
                    <>
                      <div className="who">{roleLabel(owner.role)}, tier {owner.tier}</div>
                      <div className="small">
                        {dl ? <span className={dl.overdue ? "over" : ""}>{dl.text}</span> : null}
                        {owner.reason ? (
                          <span className="muted">{dl ? " · " : ""}{owner.reason.split(":")[0]}</span>
                        ) : null}
                      </div>
                    </>
                  ) : (
                    <div className="small muted">Nobody holds this case yet. Release events to see who is handed it.</div>
                  )}
                </div>
              </div>

              <div className="layer-grid" style={{ marginTop: 14 }}>
                <div className="layer-card">
                  <div className="k">Current revision</div>
                  <div className="v mono">{run.current_revision_id ?? "—"}</div>
                </div>
                <div className="layer-card">
                  <div className="k">Delivery</div>
                  <div className="v">
                    {run.attempts.length === 0
                      ? "nothing attempted"
                      : `${run.attempts.filter((a) => a.delivered).length} delivered / ${run.attempts.length} attempts`}
                  </div>
                </div>
                <div className="layer-card">
                  <div className="k">Acknowledgement</div>
                  <div className="v">
                    {run.acknowledgments.length === 0
                      ? "none"
                      : run.acknowledgments.map((a) => a.result_revision_id).join(", ")}
                  </div>
                </div>
                <div className="layer-card">
                  <div className="k">Open questions</div>
                  <div className="v">
                    {run.open_questions.length === 0 ? (
                      "none"
                    ) : (
                      <ul style={{ margin: "4px 0 0", paddingLeft: 16 }}>
                        {run.open_questions.slice(0, 4).map((q, i) => (
                          <li key={i} style={{ marginBottom: 4 }}>{q.replace(/^policy gap surfaced at step (\d+): /, "Step $1 gap: ")}</li>
                        ))}
                        {run.open_questions.length > 4 ? <li className="muted">and {run.open_questions.length - 4} more in the trace</li> : null}
                      </ul>
                    )}
                  </div>
                </div>
                <div className="layer-card">
                  <div className="k">Audit chain</div>
                  <div className="v">
                    <Chip tone={run.audit_chain_valid ? "ok" : "bad"}>
                      {run.audit_chain_valid ? `valid, ${run.audit.length} entries` : "broken"}
                    </Chip>
                  </div>
                </div>
              </div>

              {run.blocking_conditions.length > 0 && (
                <div style={{ marginTop: 12 }}>
                  <Banner tone="warn">
                    <span>
                      <strong>Blocking conditions:</strong> {run.blocking_conditions.join(", ")}. The case may not
                      close while these are open.
                    </span>
                  </Banner>
                </div>
              )}
            </Panel>
            </div>

            <div data-video="channel-status">
            <Panel title="Channel status" hint="transport layer, per run" flush>
              <div className="table-wrap" style={{ maxHeight: 300 }}>
                <table>
                  <tbody>
                    {run.channels.map((c) => (
                      <tr key={c.channel_id}>
                        <td>
                          <div className="mono small">{c.channel_id}</div>
                          <div className="tiny muted">
                            {c.kind}
                            {c.primary ? " · primary" : ""}
                          </div>
                        </td>
                        <td style={{ textAlign: "right" }}>
                          <Chip tone={c.status === "UP" ? "ok" : c.status === "DEGRADED" ? "warn" : "bad"}>{c.status === "UP" ? "Up" : c.status === "DEGRADED" ? "Degraded" : "Down"}</Chip>
                          {c.note && <div className="tiny muted" style={{ marginTop: 3 }}>{c.note}</div>}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Panel>
            </div>
          </div>

          <Panel title="Released events" hint={`${steps.length} processed`} flush>
            {steps.length === 0 && <Empty>Press “Step” to release the first event.</Empty>}
            <div className="panel-body">
              <div className="stack">
                {steps.map((s) => (
                  <StepCard key={s.step} s={s} open={focus === s.step} onToggle={() => setFocus(focus === s.step ? null : s.step)} />
                ))}
              </div>
            </div>
          </Panel>
        </>
      )}
    </div>
  );
}

function StepCard({ s, open, onToggle }: { s: Step; open: boolean; onToggle: () => void }) {
  const gate = s.gate;
  const blocked = gate && !gate.permitted;
  return (
    <div
      className="panel"
      style={{
        boxShadow: "none",
        borderColor: blocked ? "#f2d3d1" : s.transitions.some((t) => t.status === "APPLIED") ? "var(--line)" : "var(--line)",
      }}
    >
      <div className="panel-head" style={{ cursor: "pointer" }} onClick={onToggle}>
        <div className="row" style={{ minWidth: 0 }}>
          <span className="mono tiny muted" style={{ width: 26 }}>{String(s.step).padStart(2, "0")}</span>
          <Chip tone="info">{s.kind}</Chip>
          <span className="small">{s.event.summary}</span>
        </div>
        <div className="row" style={{ flex: "none" }}>
          <span className="mono tiny muted">{fmtTime(s.at)}</span>
          {s.transitions.map((t, i) => (
            <StateBadge key={i} code={t.resulting_state} />
          ))}
          <span className="muted">{open ? "▾" : "▸"}</span>
        </div>
      </div>

      <div className="panel-body" style={{ paddingTop: 12 }}>
        <div className="row-wrap" style={{ marginBottom: 10 }}>
          <StateBadge code={s.prior_state} size="md" />
          <span className="muted">→</span>
          <StateBadge code={s.resulting_state} />
          {s.proposed_action && (
            <>
              <span className="muted tiny">proposed</span>
              <Chip tone="neutral">{s.proposed_action}</Chip>
            </>
          )}
          {s.enforced_action && s.enforced_action !== s.proposed_action && (
            <>
              <span className="muted tiny">enforced</span>
              <Chip tone="warn">{s.enforced_action}</Chip>
            </>
          )}
          {s.human_intervention && (
            <Chip tone="warn" title={s.human_intervention.reason}>
              human: {s.human_intervention.role ?? "review"}
            </Chip>
          )}
        </div>

        {s.legacy_conflation && (
          <div style={{ marginBottom: 10 }}>
            <Banner tone="warn">
              <span>
                <strong>Baseline behaviour, recorded not hidden:</strong> {s.legacy_conflation}
              </span>
            </Banner>
          </div>
        )}

        {gate && (
          <div style={{ marginBottom: 10 }}>
            <div className={`banner ${gate.permitted ? "ok" : "bad"}`} style={{ flexDirection: "column", gap: 6 }}>
              <div className="spread" style={{ width: "100%" }}>
                <strong>
                  Gate: {gate.permitted ? "permitted" : "blocked"}
                  {gate.invariant ? ` · ${gate.invariant}` : ""}
                </strong>
                <span className="mono tiny">{gate.enforced_action}</span>
              </div>
              <div style={{ fontSize: 12 }}>{gate.reason}</div>
              {gate.policy_refs.length > 0 && (
                <div className="tiny mono" style={{ opacity: 0.85 }}>refs: {gate.policy_refs.join(" · ")}</div>
              )}
              {gate.conditions_checked.length > 0 && (
                <div className="tiny" style={{ opacity: 0.85 }}>checked: {gate.conditions_checked.join(" · ")}</div>
              )}
            </div>
          </div>
        )}

        {s.agents.length > 0 && (
          <div className="grid cols-2" style={{ marginBottom: 10 }}>
            {s.agents.map((a) => (
              <div key={a.agent_id} className="panel" style={{ boxShadow: "none", background: "#fbfcfd" }}>
                <div className="panel-head" style={{ padding: "8px 12px", background: "transparent" }}>
                  <div className="row">
                    <h3 style={{ fontSize: 12.5 }}>{a.agent_id}</h3>
                    <Chip tone={statusTone(a.assessment_status)}>{a.assessment_status}</Chip>
                  </div>
                  <span className="tiny muted" title={supportTooltip(a)}>
                    support {a.confidence.toFixed(2)} (heuristic)
                  </span>
                </div>
                <div className="panel-body" style={{ padding: "10px 12px" }}>
                  <div className="row-wrap" style={{ marginBottom: 6 }}>
                    <span className="tiny muted">recommends</span>
                    <Chip tone={a.requires_human_review ? "warn" : "neutral"}>{a.recommended_action}</Chip>
                    {a.requires_human_review && <Chip tone="warn">needs human</Chip>}
                  </div>
                  <div className="small" style={{ marginBottom: 8 }}>{a.concise_rationale}</div>
                  {a.applicable_sources.length > 0 && (
                    <div className="stack" style={{ gap: 4 }}>
                      {a.applicable_sources.slice(0, open ? 10 : 3).map((src, i) => (
                        <div key={i} className="row-wrap" style={{ gap: 5 }}>
                          <Chip tone={CLAIM_TONE[src.claim_type] ?? "neutral"}>{src.claim_type}</Chip>
                          <span className="mono tiny">
                            {src.source_id} {src.section} p.{src.page}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                  {a.conditions_unresolved.length > 0 && (
                    <div className="tiny" style={{ color: "var(--warn)", marginTop: 6 }}>
                      unresolved: {a.conditions_unresolved.join(" · ")}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {open && (
          <div className="stack">
            {s.proposed_action && s.proposal_trace && s.proposal_trace.length > 0 && (
              <div>
                <h3 style={{ fontSize: 12, marginBottom: 4 }}>Why this action was proposed</h3>
                <ul className="small muted" style={{ margin: 0, paddingLeft: 18 }}>
                  {s.proposal_trace.map((t, i) => (
                    <li key={i}>{t}</li>
                  ))}
                </ul>
              </div>
            )}

            {s.retrieved_evidence.length > 0 && (
              <div>
                <h3 style={{ fontSize: 12, marginBottom: 4 }}>Retrieved evidence</h3>
                <div className="stack" style={{ gap: 6 }}>
                  {s.retrieved_evidence.map((e, i) => (
                    <div key={i}>
                      <div className="row-wrap" style={{ gap: 6 }}>
                        <Chip tone={CLAIM_TONE[e.claim_type] ?? "neutral"}>{e.claim_type}</Chip>
                        <span className="mono tiny">
                          {e.source_id} · {e.section} · printed p.{e.page} · via {e.agent_id}
                        </span>
                      </div>
                      {e.quote && <div className="quote" style={{ marginTop: 4 }}>{e.quote}</div>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {s.transitions.length > 0 && (
              <div>
                <h3 style={{ fontSize: 12, marginBottom: 4 }}>Transitions</h3>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Event</th>
                        <th>From → To</th>
                        <th>Status</th>
                        <th>Reason</th>
                      </tr>
                    </thead>
                    <tbody>
                      {s.transitions.map((t, i) => (
                        <tr key={i}>
                          <td className="mono tiny">{t.trigger_event}</td>
                          <td className="mono tiny">{t.prior_state} → {t.resulting_state}</td>
                          <td><Chip tone={statusTone(t.status)}>{t.status}</Chip></td>
                          <td className="small">{t.reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {s.actions_performed.length > 0 && (
              <div>
                <h3 style={{ fontSize: 12, marginBottom: 4 }}>Actions performed</h3>
                <div className="stack" style={{ gap: 4 }}>
                  {s.actions_performed.map((a, i) => (
                    <div key={i} className="quote">
                      {Object.entries(a)
                        .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
                        .join("  ")}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {Object.keys(s.information_available ?? {}).length > 0 && (
              <div>
                <h3 style={{ fontSize: 12, marginBottom: 4 }}>Per-agent information availability</h3>
                <div className="layer-grid">
                  {Object.entries(s.information_available).map(([agent, info]) => (
                    <div key={agent} className="layer-card">
                      <div className="k">{agent}</div>
                      <div className="v tiny muted">
                        {Object.entries(info)
                          .filter(([, v]) => v === true || (typeof v === "number" && v > 0))
                          .map(([k]) => k)
                          .join(", ") || "no information available"}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {s.unresolved_questions.length > 0 && (
              <div>
                <h3 style={{ fontSize: 12, marginBottom: 4 }}>Open questions carried forward</h3>
                <ul className="small muted" style={{ margin: 0, paddingLeft: 18 }}>
                  {s.unresolved_questions.map((q, i) => (
                    <li key={i}>{q}</li>
                  ))}
                </ul>
              </div>
            )}

            {s.audit_findings.length > 0 && (
              <div>
                <h3 style={{ fontSize: 12, marginBottom: 4 }}>Audit findings</h3>
                <ul className="small" style={{ margin: 0, paddingLeft: 18 }}>
                  {s.audit_findings.map((f, i) => (
                    <li key={i}>{f}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
