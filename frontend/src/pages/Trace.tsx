import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { Banner, Chip, Empty, Panel, Skeleton, fmtTime, useAsync } from "../ui";
import { Pipeline3DLazy as Pipeline3D } from "../design/Pipeline3DLazy";
import { useReveal } from "../design/motion";

/**
 * The decision trace: what the system knew, what each agent proposed, what the gate decided and why.
 *
 * This is the answer to "show me the reasoning". It deliberately shows artefacts rather than prose:
 * a reviewer can check an artefact against the corpus and the audit chain; they cannot check a
 * paragraph of self-report. Raw model reasoning is not published, and in the shipped configuration
 * there is no model to reason.
 */
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

  const pipeline = useMemo(
    () =>
      steps.map((s: any) => ({
        label: `step ${s.step}`,
        permitted: Boolean(s["4_gate"]?.permitted),
        active: s.step === open,
      })),
    [steps, open]
  );

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

            {pipeline.some((s: { permitted: boolean }) => !s.permitted) && (
              <Pipeline3D steps={pipeline} onSelect={(i) => goTo(i + 1)} caption="this run, step by step — refused steps stop at the gate" />
            )}

            {/* Keyboard-parity navigation: the same jump the 3-D scene offers, in text. */}
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
                  {String(s.step).padStart(2, "0")} · {s["4_gate"]?.permitted ? "ok" : "blocked"}
                </button>
              ))}
            </div>

            {steps.map((s: any) => {
              const isOpen = open === s.step;
              const gate = s["4_gate"];
              return (
                <div
                  key={s.step}
                  className={`card${isOpen ? " panel-glow" : ""}`}
                  style={{ padding: 12 }}
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
                      <Chip tone={gate.permitted ? "ok" : "bad"}>{gate.permitted ? "permitted" : "blocked"}</Chip>
                      <Chip tone="info">{gate.enforced_action}</Chip>
                      <span className="btn small">{isOpen ? "Hide" : "Trace"}</span>
                    </span>
                  </button>

                  {isOpen && (
                    <div className="stack" style={{ gap: 10, marginTop: 10 }}>
                      <div>
                        <div className="tiny muted">1 · evidence retrieved</div>
                        {(s["2_evidence"] ?? []).length === 0 ? (
                          <div className="tiny muted">none — no clause matched above the relevance floor</div>
                        ) : (
                          s["2_evidence"].slice(0, 4).map((e: any, i: number) => (
                            <div key={i} className="tiny">
                              <span className="mono">{e.source_id} {e.section}</span> · p.{e.page} ·{" "}
                              <Chip tone="outline">{e.claim_type}</Chip> {e.quote?.slice(0, 120)}
                            </div>
                          ))
                        )}
                      </div>

                      <div>
                        <div className="tiny muted">2 · proposals</div>
                        {s["3_proposals"].map((p: any, i: number) => (
                          <div key={i} className="tiny">
                            <span className="mono">{p.agent}</span> → <strong>{p.action}</strong>{" "}
                            <span className="muted">
                              (confidence {p.confidence}; {p.confidence_basis ?? p.status})
                            </span>
                            {p.citations?.length ? <span className="muted"> · cites {p.citations.join(", ")}</span> : null}
                          </div>
                        ))}
                      </div>

                      <div>
                        <div className="tiny muted">3 · gate</div>
                        <div className="tiny">
                          {gate.reason}
                          {gate.invariant ? <> · invariant <strong>{gate.invariant}</strong></> : null}
                        </div>
                        {gate.conditions_checked.map((c: string, i: number) => (
                          <div key={i} className="tiny muted">
                            · {c}
                          </div>
                        ))}
                        {gate.advisory ? (
                          <div className="tiny" style={{ marginTop: 4 }}>
                            adviser: <Chip tone={gate.advisory.status === "ADVISORY_ONLY" ? "warn" : "neutral"}>{gate.advisory.status}</Chip>{" "}
                            {gate.advisory.candidate_action ? (
                              <>
                                proposed <strong>{gate.advisory.candidate_action}</strong>
                                {gate.advisory_overruled ? " — overruled by the gate" : " — agreed, but agreement is not evidence"}
                              </>
                            ) : (
                              <span className="muted">{gate.advisory.reason}</span>
                            )}
                          </div>
                        ) : null}
                      </div>

                      <div>
                        <div className="tiny muted">4 · transition</div>
                        {(s["5_transitions"] ?? []).map((t: any, i: number) => (
                          <div key={i} className="tiny">
                            <Chip tone={t.status === "APPLIED" ? "ok" : t.status === "BLOCKED" ? "bad" : "neutral"}>
                              {t.status}
                            </Chip>{" "}
                            {t.prior} → {t.resulting} · {t.reason?.slice(0, 160)}
                          </div>
                        ))}
                        {!s["5_transitions"]?.length && <div className="tiny muted">no transition attempted</div>}
                      </div>

                      <div className="tiny">
                        <span className="muted">5 · resulting state</span> <strong>{s["6_resulting_state"]}</strong>
                      </div>
                      {s.unresolved?.length ? (
                        <div className="tiny muted">open questions: {s.unresolved.slice(0, 3).join("; ")}</div>
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
