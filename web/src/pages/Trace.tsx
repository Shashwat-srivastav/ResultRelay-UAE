import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, currentOwner } from "../api/client";
import { Badge, CodeLabel, Empty, ErrorNotice, Glyph, Panel, Skeleton, StateBadge, TransitionLabel, fmtTime, humanise, roleLabel, useAsync } from "../ui";
import { scenarioTitle } from "../labels";
import { Confidence, Provenance, TrustBlock, TrustLegend, TrustTag } from "../components";
import { useReveal } from "../design/motion";
import "../styles/trace.css";

/**
 * The decision trace: what the system knew, what each agent said, what code made of it, what the gate decided.
 * Artefacts rather than prose; sections run in a fixed order and each carries its trust register.
 */
function clip(text: string, max: number): string {
  if (text.length <= max) return text;
  const cut = text.slice(0, max);
  return cut.slice(0, cut.lastIndexOf(" ")) + "…";
}

const isEscalation = (s: any) =>
  s["3b_council"]?.decision === "ESCALATE" ||
  String(s["4_gate"]?.enforced_action ?? "").startsWith("ESCALATE") ||
  String(s["6_resulting_state"] ?? "").startsWith("ESCALATION_");
const isRefusal = (s: any) => s["4_gate"]?.permitted === false;

/** Step with the escalation / refusal; otherwise the last. */
function decisiveStep(steps: any[]): number {
  const hit = steps.find((s) => isRefusal(s) || isEscalation(s));
  return (hit ?? steps[steps.length - 1])?.step ?? 1;
}

/** One sentence per step (wireframes 4.7). */
function summarise(s: any): string {
  const g = s["4_gate"] ?? {};
  const ev = humanise("event", s["1_event"]);
  const act = humanise("action", g.enforced_action).toLowerCase();
  const gate = isRefusal(s) ? "the gate refused and held the case" : isEscalation(s) ? "the gate handed it to a person" : `the gate allowed "${act}"`;
  const mid = s["3b_council"]?.decision === "ESCALATE" ? "the agent council objected; " : "";
  return `${ev}: ${mid}${gate}. Now: ${humanise("state", s["6_resulting_state"]).toLowerCase()}.`;
}

function ansText(v: any): string {
  if (v && typeof v === "object") return String(v.choice ?? v.noul ?? v.text ?? JSON.stringify(v));
  return typeof v === "number" ? v.toFixed(2) : String(v);
}

function AgentCard({ a, assurance, overruled, objected }: { a: any; assurance: any; overruled: boolean; objected: boolean }) {
  const ans = a.answers ?? {};
  const isRev = a.role === "reviewer";
  const outcome = assurance?.outcome;
  const rationale = !isRev && ans.rationale ? clip(ansText(ans.rationale).replace(/\*\*/g, ""), 320) : null;
  const rows: Array<[string, React.ReactNode]> = [];
  if (isRev) {
    if (ans.objection) rows.push(["Objection", <span className="tr-objection"><CodeLabel kind="objection" code={ans.objection} /></span>]);
    if (ans.own_reading) rows.push(["Its own reading", <CodeLabel kind="obligation" code={ans.own_reading} />]);
    if (ans.analyst_issue && ans.analyst_issue !== "NONE") rows.push(["Problem with the analyst", <CodeLabel kind="claimProblem" code={ans.analyst_issue} />]);
    if (ans.alternative) rows.push(["Suggests", <CodeLabel kind="action" code={ans.alternative} />]);
  } else {
    if (ans.obligation) rows.push([overruled ? "Reading (overruled)" : "Reading", <CodeLabel kind="obligation" code={ansText(ans.obligation)} />]);
    if (ans.clause) rows.push(["Clause relied on", <span className="mono tr-clause">{ansText(ans.clause)}</span>]);
    if (ans.gap && ansText(ans.gap) !== "NONE") rows.push(["Gap it sees", <CodeLabel kind="gapNamed" code={ansText(ans.gap)} />]);
  }
  const conf = isRev && typeof ans.analyst_supported === "number" ? ans.analyst_supported : null;
  return (
    <div className={`agent${overruled ? " overruled" : ""}`} data-video={isRev ? "reviewer" : undefined}>
      <div className="agent-head">
        <span className="role"><CodeLabel kind="agent" code={a.role} /></span>
        <Badge tone={a.status === "ANSWERED" ? "neutral" : a.status === "PARTIAL" ? "att" : "crit"} glyph={a.status !== "ANSWERED"}>
          {humanise("agentStatus", a.status)}
        </Badge>
        {overruled && <span className="overruled-note">overruled: the objection stood</span>}
      </div>
      {rows.map(([k, v], i) => (
        <div key={i} className="tr-line"><span className="muted small">{k}</span>{v}</div>
      ))}
      {rationale && <div className="rationale">{rationale}</div>}
      {conf != null && <div className="tr-line"><Confidence value={conf} /></div>}
      <details className="tr-raw">
        <summary>Show raw</summary>
        <pre>{JSON.stringify(ans, null, 2)}</pre>
      </details>
      {outcome && (
        <div className="agent-check">
          <Glyph name={outcome === "DISPUTED" ? "cross" : "check"} size={12} toned={false} />
          <span>
            Code made of it: <strong><CodeLabel kind="check" code={outcome} /></strong>
            {(assurance.checks ?? []).length ? <> — {(assurance.checks as string[]).join("; ")}</> : null}
            {objected && isRev && outcome === "ACCEPTED" ? <> The objection fits the case record.</> : null}
          </span>
        </div>
      )}
    </div>
  );
}

function StepBody({ s }: { s: any }) {
  const gate = s["4_gate"] ?? {};
  const council = s["3b_council"];
  const ev = s["2_evidence"] ?? [];
  const props = s["3_proposals"] ?? [];
  const reviewer = council?.agents?.find((a: any) => a.role === "reviewer");
  const objected = !!reviewer && reviewer.answers?.objection && reviewer.answers.objection !== "NONE";
  let agents: any[] = council?.agents ?? [];
  if (objected) agents = [...agents].sort((a, b) => (a.role === "reviewer" ? -1 : b.role === "reviewer" ? 1 : 0));
  const escalate = council?.decision === "ESCALATE";
  const failedCheck = (council?.assurance ?? []).some((r: any) => r.outcome === "DISPUTED");
  return (
    <div className="step-body">
      <section className="tr-sec">
        <h3>What happened</h3>
        <div className="tr-line"><CodeLabel kind="event" code={s["1_event"]} showCode /> <span className="muted small">at {fmtTime(s.at)}</span></div>
      </section>

      <section className="tr-sec">
        <h3>Rules checked</h3>
        <TrustBlock kind="rules" who="Rule assessors" meta={`${props.length} assessors · ${ev.length} clauses`}>
          {ev.length === 0 ? <span className="muted">No clause matched above the relevance floor.</span> :
            ev.slice(0, 4).map((e: any, i: number) => (
              <div key={i} className={`evidence${e.claim_type === "GLOBAL_COMPARATOR" ? " comparator" : ""}`}>
                <div className="ev-head">
                  <span className="ref">{e.source_id} §{e.section}</span><span className="place">p.{e.page}</span>
                  <CodeLabel kind="claim" code={e.claim_type} />
                </div>
                <div className="ev-quote">{clip(String(e.quote ?? ""), 200)}</div>
              </div>
            ))}
          <div className="stack-6" style={{ marginTop: 8 }}>
            {props.map((p: any, i: number) => (
              <div key={i} className="tr-line">
                <CodeLabel kind="assessor" code={p.agent} /> <span className="muted">proposed</span>
                <strong><CodeLabel kind="action" code={p.action} /></strong>
                <Confidence value={p.confidence} kind="rules" meter={false} />
              </div>
            ))}
          </div>
        </TrustBlock>
      </section>

      {council && (
        <section className="tr-sec" data-video="council">
          <h3>What the agents said</h3>
          <div className="stack-6">
            {agents.map((a: any, i: number) => (
              <TrustBlock key={i} kind="ai" who={humanise("agent", a.role)} model={council.provider?.[a.role]?.replace(/^replay:recorded-/, "")}>
                <AgentCard
                  a={a}
                  assurance={(council.assurance ?? []).find((r: any) => r.role === a.role)}
                  overruled={escalate && objected && a.role !== "reviewer"}
                  objected={objected}
                />
              </TrustBlock>
            ))}
          </div>
        </section>
      )}

      <section className="tr-sec">
        <h3>What code checked</h3>
        <TrustBlock kind="code" failed={failedCheck}>
          {(gate.conditions_checked ?? []).length === 0 && !(council?.assurance ?? []).length && <span className="muted">No conditions applied at this step.</span>}
          {(gate.conditions_checked ?? []).map((c: string, i: number) => (
            <div key={i} className="check-line"><Glyph name="check" size={12} toned={false} /><span>{c}</span></div>
          ))}
          {(council?.assurance ?? []).map((r: any, i: number) => (
            <div key={`a${i}`} className="check-line">
              <Glyph name={r.outcome === "DISPUTED" ? "cross" : "check"} size={12} toned={false} />
              <span>The {humanise("agent", r.role).toLowerCase()}: <CodeLabel kind="check" code={r.outcome} />{(r.checks ?? []).length ? ` — ${r.checks.join("; ")}` : ""}</span>
            </div>
          ))}
        </TrustBlock>
      </section>

      <section className="tr-sec" data-video="decision">
        <h3>What the gate decided</h3>
        <TrustBlock kind="gate" meta={<Badge tone={gate.permitted ? "progress" : "crit"}>{humanise("gate", !!gate.permitted)}</Badge>}>
          <div><strong><CodeLabel kind="action" code={gate.enforced_action} /></strong>. {gate.reason}
            {gate.invariant ? <> Rule that applied: <CodeLabel kind="invariant" code={gate.invariant} showCode />.</> : null}</div>
          {council && (
            <div className="tr-line" style={{ marginTop: 6 }}>
              <span className="muted small">Orchestrator</span>
              <Badge tone={escalate ? "att" : "neutral"}>{humanise("orchestrator", council.decision)}</Badge>
              {council.conflicts?.length ? <span className="tiny muted">Recorded differences: {council.conflicts.join("; ")}</span> : null}
            </div>
          )}
          {gate.advisory?.candidate_action && (
            <div className="small" style={{ marginTop: 4 }}>
              Adviser proposed <strong><CodeLabel kind="action" code={gate.advisory.candidate_action} /></strong>
              {gate.advisory_overruled ? ", overruled by the gate." : ", agreed; agreement is not evidence."}
            </div>
          )}
        </TrustBlock>
      </section>

      <section className="tr-sec">
        <h3>Result</h3>
        {(s["5_transitions"] ?? []).map((t: any, i: number) => (
          <div key={i} className="tr-line">
            <TransitionLabel from={t.prior} to={t.resulting} />
            <span className="muted small"><CodeLabel kind="transition" code={t.status} /></span>
          </div>
        ))}
        {!s["5_transitions"]?.length && <div className="tr-line"><StateBadge code={s["6_resulting_state"]} /><span className="muted small">no transition attempted</span></div>}
        {s.unresolved?.length ? (
          <details className="tr-raw"><summary>{s.unresolved.length} open question(s)</summary>
            <ul>{s.unresolved.slice(0, 4).map((u: string, i: number) => <li key={i}>{clip(u, 220)}</li>)}</ul></details>
        ) : null}
        <details className="tr-raw"><summary>Show raw</summary><pre>{JSON.stringify({ gate, council: council ?? undefined }, null, 2)}</pre></details>
      </section>
    </div>
  );
}

export default function Trace() {
  const [params, setParams] = useSearchParams();
  const runParam = params.get("run");
  const stepParam = params.get("step") ? Number(params.get("step")) || null : null;

  const traces = useAsync<any[]>(() => api.listTraces(), []);
  const runs = traces.data ?? [];
  const active = runParam ?? runs[0]?.run_id ?? null;
  const trace = useAsync<any>(() => (active ? api.traceTyped(active) : Promise.resolve(null)), [active]);

  const steps: any[] = trace.data?.steps ?? [];
  const decisive = steps.length ? decisiveStep(steps) : null;
  const [picked, setPicked] = useState<number | null>(null);
  useEffect(() => setPicked(null), [active, stepParam]);
  const open = picked ?? stepParam ?? decisive;

  const reveal = useReveal<HTMLDivElement>([trace.data, active], 0.03);
  const stepRefs = useRef<Record<number, HTMLDivElement | null>>({});

  function goTo(step: number) {
    setPicked(step);
    const next = new URLSearchParams(params);
    if (active) next.set("run", String(active));
    next.set("step", String(step));
    setParams(next, { replace: true });
    stepRefs.current[step]?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  const d = trace.data;
  const owner = d ? currentOwner(d.escalations) : null;

  return (
    <div className="stack" ref={reveal}>
      <Panel
        title="Decision trace"
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
          <Empty title="No runs in memory" body="Open the Simulator, start a scenario, then come back. Traces are served from the live run." />
        ) : trace.loading ? (
          <Skeleton height={200} />
        ) : trace.error ? (
          <ErrorNotice title="The trace could not be loaded" error={String(trace.error)} onRetry={trace.reload} />
        ) : d ? (
          <div className="stack" style={{ gap: 14 }}>
            <div className="case-head" data-video="case-header">
              <h2 className="ch-title">{scenarioTitle(d.scenario_id)}</h2>
              <div className="ch-row">
                <StateBadge code={d.state} role={owner?.role} size="lg" showCode />
                <span className="small">
                  {owner ? <>Owner: <strong>{roleLabel(owner.role)}</strong></> : <span className="muted">No open owner</span>}
                </span>
                <span className="ch-meta">{humanise("config", d.configuration)}</span>
                <span className="ch-meta mono" title={d.kb_index_sha256}>corpus {d.kb_index_sha256?.slice(0, 10)}</span>
              </div>
              <Provenance scenarioId={d.scenario_id} size="strip" />
            </div>

            <div className="row-wrap" style={{ justifyContent: "space-between" }}>
              <div className="step-rail" role="tablist" aria-label="steps" style={{ flex: 1 }}>
                {steps.map((s: any) => {
                  const cls = isRefusal(s) ? " refused" : isEscalation(s) ? " escalated" : "";
                  return (
                    <button key={s.step} role="tab" className={`step-pip${cls}${s.step === open ? " current" : ""}`}
                      aria-current={s.step === open ? "true" : undefined} aria-selected={s.step === open}
                      onClick={() => goTo(s.step)}
                      title={isRefusal(s) ? "Gate refused" : isEscalation(s) ? "Handed to a person" : undefined}>
                      <span className="n">{s.step}</span>
                    </button>
                  );
                })}
              </div>
              <TrustLegend />
            </div>

            {steps.map((s: any) => {
              const isOpen = open === s.step;
              return (
                <div key={s.step} className={`step-card${s.step === decisive ? " decisive" : ""}`}
                  ref={(el) => { stepRefs.current[s.step] = el; }} data-reveal>
                  <button className="step-toggle" onClick={() => goTo(s.step)} aria-expanded={isOpen}>
                    <span className="st-n">Step {s.step}</span>
                    <span className="st-sum">
                      {summarise(s)}
                      {s.step === decisive && isEscalation(s) && <> <TrustTag kind="gate" label="Decisive step" /></>}
                    </span>
                    <span className="st-time">{fmtTime(s.at)}</span>
                    <Glyph name={isOpen ? "chevron-down" : "chevron"} size={12} />
                  </button>
                  {isOpen && <StepBody s={s} />}
                </div>
              );
            })}
          </div>
        ) : null}
      </Panel>
    </div>
  );
}
