import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { Banner, Chip, Empty, Panel, Skeleton, fmtTime, stateTone, useAsync } from "../ui";
import { useReveal } from "../design/motion";

/**
 * The decision trace: what the system knew, what each agent proposed, what the gate decided and why.
 *
 * This is the answer to "show me the reasoning". It deliberately shows artefacts rather than prose:
 * a reviewer can check an artefact against the corpus and the audit chain; they cannot check a
 * paragraph of self-report. Raw model reasoning is not published, and in the shipped configuration
 * there is no model to reason.
 */
/** Shorten at a word boundary and say so, instead of cutting a word in half. */
function clip(text: string, max: number): string {
  if (text.length <= max) return text;
  const cut = text.slice(0, max);
  return cut.slice(0, cut.lastIndexOf(" ")) + "…";
}

export default function Trace() {
  const [params, setParams] = useSearchParams();
  const runParam = params.get("run");
  const stepParam = Number(params.get("step") ?? "1") || 1;

  const traces = useAsync<any[]>(() => api.listTraces(), []);
  const runs = traces.data ?? [];
  const active = runParam ?? runs[0]?.run_id ?? null;
  const trace = useAsync<any>(
    () => (active ? api.trace(active) : Promise.resolve(null)),
    [active]
  );

  const [open, setOpen] = useState<number | null>(stepParam);
  useEffect(() => setOpen(stepParam), [stepParam]);

  const steps = trace.data?.steps ?? [];
  const reveal = useReveal<HTMLDivElement>([trace.data, active], 0.03);
  const stepRefs = useRef<Record<number, HTMLDivElement | null>>({});


  function goTo(step: number) {
    setOpen(step);
    const next = new URLSearchParams(params);
    if (active) next.set("run", String(active));
    next.set("step", String(step));
    setParams(next, { replace: true });
    stepRefs.current[step]?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  return (
    <div className="stack" ref={reveal}>
      <div data-reveal>
        <Banner tone="info">
          <span>
            Every step is recorded as ordered artefacts — event, evidence, proposals, gate decision, transition,
            resulting state. The gate's decision is computed before any advisory input is read, so a proposal can be
            inspected, scored and overruled but never enforced.
          </span>
        </Banner>
      </div>

      <Panel
        title="Runs in this process"
        hint={runs.length ? `${runs.length} run(s)` : "none yet"}
        action={
          <select
            value={active ?? ""}
            onChange={(e) => {
              const next = new URLSearchParams(params);
              next.set("run", e.target.value);
              next.delete("step");
              setParams(next, { replace: true });
            }}
            style={{ width: 320 }}
            aria-label="run"
          >
            {(runs.length ? runs : [{ run_id: "", label: "run the simulator first" }]).map((r: any) => (
              <option key={r.run_id} value={r.run_id}>
                {r.label ?? `${r.run_id} · ${r.configuration ?? ""} · ${r.scenario_id ?? ""}`}
              </option>
            ))}
          </select>
        }
      >
        {traces.loading ? (
          <Skeleton />
        ) : !runs.length ? (
          <Empty>
            No runs in memory. Open the Simulator, start a scenario, then come back — traces are served from the
            live run, not reconstructed from the store.
          </Empty>
        ) : trace.loading ? (
          <Skeleton height={200} />
        ) : trace.error ? (
          <Empty>{String(trace.error)}</Empty>
        ) : trace.data ? (
          <div className="stack" style={{ gap: 12 }}>
            <div className="row tiny muted" style={{ gap: 12 }}>
              <span>{trace.data.configuration}</span>
              <span>case {trace.data.case_id}</span>
              <span title={trace.data.kb_index_sha256}>corpus {trace.data.kb_index_sha256?.slice(0, 12)}</span>
            </div>

            <div className="step-rail" role="tablist" aria-label="steps">
              {steps.map((s: any) => (
                <button
                  key={s.step}
                  role="tab"
                  className="step-pip"
                  aria-current={s.step === open ? "true" : undefined}
                  aria-selected={s.step === open}
                  onClick={() => goTo(s.step)}
                >
                  Step {s.step}{s["4_gate"]?.permitted ? "" : " refused"}
                </button>
              ))}
            </div>

            {steps.map((s: any) => {
              const isOpen = open === s.step;
              const gate = s["4_gate"];
              return (
                <div
                  key={s.step}
                  className="card"
                  style={{ padding: "12px 16px" }}
                  ref={(el) => {
                    stepRefs.current[s.step] = el;
                  }}
                  data-reveal
                >
                  <button
                    className="row"
                    onClick={() => goTo(s.step)}
                    aria-expanded={isOpen}
                    style={{
                      justifyContent: "space-between",
                      width: "100%",
                      background: "none",
                      border: 0,
                      padding: 0,
                      cursor: "pointer",
                      textAlign: "left",
                      color: "inherit",
                      font: "inherit",
                    }}
                  >
                    <span className="row" style={{ gap: 10 }}>
                      <strong>Step {s.step}</strong>
                      <span className="tiny muted">{fmtTime(s.at)}</span>
                      <Chip tone="neutral">{s["1_event"] ?? "event"}</Chip>
                    </span>
                    <span className="row" style={{ gap: 8 }}>
                      <Chip tone={gate.permitted ? "ok" : "bad"}>{gate.permitted ? "permitted" : "refused"}</Chip>
                      <Chip tone="info">{gate.enforced_action}</Chip>
                      <span className="btn small">{isOpen ? "Hide" : "Trace"}</span>
                    </span>
                  </button>

                  {isOpen && (
                    <div className="trace-grid">
                      <div className="tg-k">Evidence</div>
                      <div className="tg-v">
                        {(s["2_evidence"] ?? []).length === 0 ? (
                          <span className="muted">No clause matched above the relevance floor.</span>
                        ) : (
                          s["2_evidence"].slice(0, 4).map((e: any, i: number) => (
                            <div key={i} className="ev-line">
                              <span className="mono">{e.source_id} {e.section}, p.{e.page}</span>
                              <Chip tone={e.claim_type === "BINDING_REQUIREMENT" ? "ok" : "outline"}>{e.claim_type}</Chip>
                              <span>{e.quote?.slice(0, 160)}</span>
                            </div>
                          ))
                        )}
                      </div>

                      <div className="tg-k">Rule proposals</div>
                      <div className="tg-v">
                        {s["3_proposals"].map((p: any, i: number) => (
                          <div key={i} className="ev-line">
                            <span className="mono">{p.agent}</span>
                            <strong className="mono">{p.action}</strong>
                            <span className="muted">confidence {p.confidence}{p.citations?.length ? `, cites ${p.citations.join(", ")}` : ""}</span>
                          </div>
                        ))}
                      </div>

                      {s["3b_council"] ? (
                        <>
                          <div className="tg-k">
                            Agent council
                            <div className="tg-sub">advises; can only escalate</div>
                          </div>
                          <div className="tg-v">
                            {s["3b_council"].agents.map((a: any, i: number) => (
                              <div key={i} className="agent">
                                <div className="row-wrap">
                                  <strong>{a.role === "reviewer" ? "Adversarial reviewer" : a.role === "institution" ? "TDRA-lens analyst" : "Policy analyst"}</strong>
                                  <Chip tone={a.status === "DISPUTED" ? "bad" : "neutral"}>{a.status}</Chip>
                                </div>
                                <div className="mono answers">
                                  {Object.entries(a.answers)
                                    .filter(([k]) => k !== "rationale")
                                    .map(([k, v]) => `${k} ${typeof v === "number" ? (v as number).toFixed(2) : v}`)
                                    .join(",  ")}
                                </div>
                                {a.answers.rationale ? <div className="quote">{clip(String(a.answers.rationale).replace(/\*\*/g, ""), 280)}</div> : null}
                              </div>
                            ))}
                            {s["3b_council"].assurance
                              .filter((r: any) => r.outcome !== "ACCEPTED")
                              .map((r: any, i: number) => (
                                <div key={i} className="ev-line">
                                  <span>Assurance check on the {r.role}</span>
                                  <Chip tone={r.outcome === "CORRECTED" ? "warn" : r.outcome === "DISPUTED" || r.outcome === "OBJECTION_REJECTED" ? "bad" : "neutral"}>
                                    {r.outcome}
                                  </Chip>
                                  {(r.checks ?? []).length ? <span className="muted">{(r.checks ?? []).join("; ")}</span> : null}
                                </div>
                              ))}
                            <div className={`decision${s["3b_council"].decision === "ESCALATE" ? " escalate" : ""}`}>
                              <strong>Orchestrator: {s["3b_council"].decision === "ESCALATE" ? "escalate to a person" : "proceed"}</strong>
                              {s["3b_council"].escalation ? <div>{s["3b_council"].escalation}</div> : null}
                              {s["3b_council"].conflicts?.length ? (
                                <div className="tiny muted">Recorded differences: {s["3b_council"].conflicts.join("; ")}</div>
                              ) : null}
                            </div>
                          </div>
                        </>
                      ) : null}

                      <div className="tg-k">Gate</div>
                      <div className="tg-v">
                        <div>
                          {gate.reason}
                          {gate.invariant ? <> Invariant <strong className="mono">{gate.invariant}</strong>.</> : null}
                        </div>
                        {gate.conditions_checked.length ? (
                          <ul>
                            {gate.conditions_checked.map((c: string, i: number) => (
                              <li key={i} className="muted">{c}</li>
                            ))}
                          </ul>
                        ) : null}
                        {gate.advisory ? (
                          <div className="small" style={{ marginTop: 4 }}>
                            Adviser <Chip tone={gate.advisory.status === "ADVISORY_ONLY" ? "warn" : "neutral"}>{gate.advisory.status}</Chip>{" "}
                            {gate.advisory.candidate_action ? (
                              <>
                                proposed <strong>{gate.advisory.candidate_action}</strong>
                                {gate.advisory_overruled ? ", overruled by the gate" : ", agreed; agreement is not evidence"}
                              </>
                            ) : (
                              <span className="muted">{gate.advisory.reason}</span>
                            )}
                          </div>
                        ) : null}
                      </div>

                      <div className="tg-k">Transition</div>
                      <div className="tg-v">
                        {(s["5_transitions"] ?? []).map((t: any, i: number) => (
                          <div key={i} className="ev-line">
                            <Chip tone={t.status === "APPLIED" ? "ok" : t.status === "BLOCKED" ? "bad" : "neutral"}>{t.status}</Chip>
                            <span className="mono">{t.prior} → {t.resulting}</span>
                            <span className="muted">{t.reason?.slice(0, 160)}</span>
                          </div>
                        ))}
                        {!s["5_transitions"]?.length && <span className="muted">No transition attempted.</span>}
                      </div>

                      <div className="tg-k">Result</div>
                      <div className="tg-v">
                        <Chip tone={stateTone(s["6_resulting_state"])}>{s["6_resulting_state"]}</Chip>
                      </div>

                      {s.unresolved?.length ? (
                        <>
                          <div className="tg-k">Open questions</div>
                          <div className="tg-v">
                            <ul>
                              {s.unresolved.slice(0, 3).map((u: string, i: number) => (
                                <li key={i} className="muted">{u}</li>
                              ))}
                            </ul>
                          </div>
                        </>
                      ) : null}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        ) : null}
      </Panel>
    </div>
  );
}
