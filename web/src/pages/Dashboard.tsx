import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, currentOwner } from "../api/client";
import { Banner, Empty, Panel, Skeleton, StateBadge, fmtTime, shortHash, useAsync } from "../ui";
import { CHAIN_EXITS, CHAIN_STAGES, deadline, roleLabel, scenarioTitle, scenarioWhy } from "../labels";
import { AttentionBeam, Provenance } from "../components";
import { onActivate } from "../design/motion";
import type { CaseRowV4, EscalationSummary } from "../types";
import "../styles/console.css";

type Dash = {
  recent_audit: Array<{ seq: number; at: string; event: string; actor: string; summary: string; case_id: string; hash: string }>;
};

const isRR = (r: CaseRowV4) => r.configuration.startsWith("resultrelay");

export default function Dashboard() {
  const dash = useAsync<Dash>(() => api.dashboard(), []);
  const cases = useAsync<{ cases: CaseRowV4[]; count: number }>(() => api.casesTyped(), []);
  const health = useAsync<any>(() => api.health(), []);
  const navigate = useNavigate();
  const [showAll, setShowAll] = useState(false);
  const [touring, setTouring] = useState(false);

  const everything = cases.data?.cases ?? [];
  const comparison = everything.filter((r) => !isRR(r)).length;
  const all = showAll ? everything : everything.filter(isRR);
  const count = (states: string[]) => all.filter((r) => states.includes(r.current_state)).length;

  const needs = all
    .map((r) => ({ r, owner: currentOwner(r.escalations) }))
    .filter((x): x is { r: CaseRowV4; owner: EscalationSummary } => x.owner !== null)
    .sort((a, b) => String(a.owner.due_at ?? "9").localeCompare(String(b.owner.due_at ?? "9")));

  const openTrace = (runId?: string) => {
    if (runId) navigate(`/trace?run=${encodeURIComponent(runId)}`);
  };

  async function tour() {
    setTouring(true);
    try {
      const runs = (await api.listTraces().catch(() => [])) as any[];
      const hit = [...runs].reverse().find((x) => /S9/.test(x.scenario_id) && x.configuration === "resultrelay_council");
      let id = hit?.run_id as string | undefined;
      if (!id) {
        id = (await api.startRun("S9-reply-from-someone-else", "resultrelay_council")).run.run_id as string;
        await api.playRun(id);
      }
      navigate(`/trace?run=${encodeURIComponent(id)}&step=5`);
    } finally {
      setTouring(false);
    }
  }

  const needItem = (r: CaseRowV4, owner: EscalationSummary, top: boolean) => {
    const dl = deadline(owner.due_at);
    const body = (
      <div
        className={`needs-item${top ? " top" : ""}`}
        tabIndex={0}
        role="link"
        aria-label={`Open case ${scenarioTitle(r.scenario_id)}`}
        onKeyDown={onActivate(() => openTrace(r.run_id))}
        onClick={() => openTrace(r.run_id)}
        style={{ cursor: "pointer" }}
      >
        <div>
          <div className="ttl">
            <span>{scenarioTitle(r.scenario_id, r.title)}</span>
            <Provenance scenarioId={r.scenario_id} size="inline" />
          </div>
          <div className="why">{scenarioWhy(r.scenario_id) ?? owner.reason}</div>
          <div className="meta">
            <StateBadge code={r.current_state} role={owner.role} />
            <span className="small">Owner: <b>{roleLabel(owner.role)}</b>, tier {owner.tier}</span>
            {dl && <span className={`small ${dl.overdue ? "due-over" : "due-ok"}`}>{dl.text}</span>}
            <span className="cid muted">{r.case_id}</span>
          </div>
        </div>
        <Link to={`/trace?run=${encodeURIComponent(r.run_id)}`} className="btn small" onClick={(e) => e.stopPropagation()}>
          Open case →
        </Link>
      </div>
    );
    return top ? (
      <AttentionBeam key={r.case_id} runKey={r.case_id} radius={0}>{body}</AttentionBeam>
    ) : (
      <div key={r.case_id}>{body}</div>
    );
  };

  return (
    <div className="stack">
      <div className="start-strip">
        <span className="lead">Start here</span>
        <button className="linkish" onClick={tour} disabled={touring}>S9 decision trace (3-minute tour)</button>
        <Link to="/compare">Side-by-side on S9</Link>
        <Link to="/standards">Rules &amp; gaps</Link>
      </div>

      <div data-video="needs-person">
        <Panel
          title={`Needs a person now · ${needs.length}`}
          hint="escalating to a person is the correct outcome"
          flush
          action={
            comparison > 0 ? (
              <label className="toggle-row">
                <input type="checkbox" checked={showAll} onChange={(e) => setShowAll(e.target.checked)} />
                {showAll ? "Hide" : "Show"} comparison runs ({comparison})
              </label>
            ) : undefined
          }
        >
          {cases.loading && <div className="panel-body"><Skeleton height={14} /><Skeleton height={14} /></div>}
          {cases.error && <div className="panel-body"><Banner tone="bad">{cases.error}</Banner></div>}
          {!cases.loading && !cases.error && needs.length === 0 && (
            <Empty>
              Nothing is waiting on a person. Run a scenario on the <Link to="/simulator">scenarios page</Link>; each run creates one case.
            </Empty>
          )}
          <div className="needs-list">{needs.map((x, i) => needItem(x.r, x.owner, i === 0))}</div>
        </Panel>
      </div>

      <section aria-label="Where every result is">
        <h2 style={{ fontSize: "var(--t-title-3-size)", marginBottom: 8 }}>Where every result is · {all.length} runs</h2>
        <div className="chain" data-video="chain">
          {CHAIN_STAGES.map((s, i) => {
            const n = cases.loading ? null : count(s.states);
            const last = i === CHAIN_STAGES.length - 1;
            return (
              <div key={s.id} className={`chain-stage${last ? " final" : ""}`} {...(last ? { "data-video": "chain-final" } : {})}>
                <div className="n">{i + 1}</div>
                <div className="name">{s.label}</div>
                <div className={`count${n === 0 ? " zero" : ""}`}>{n ?? "–"}</div>
                <div className="rule-note">{s.note}</div>
              </div>
            );
          })}
        </div>
        <div className="chain-exits">
          {CHAIN_EXITS.map((e) => {
            const n = cases.loading ? null : count(e.states);
            return (
              <div key={e.id} className={`exit ${e.tone}`}>
                <div className="spread">
                  <span className="name">{e.label}</span>
                  <span className={`count${n === 0 ? " zero" : ""}`}>{n ?? "–"}</span>
                </div>
                <div className="why">{e.note}</div>
              </div>
            );
          })}
        </div>
      </section>

      <div className="grid split-8-4">
        <div className="stack">
          <Panel title="Cases" hint={all.length ? `${all.length} shown` : undefined} flush>
            {!cases.loading && !cases.error && all.length === 0 && <Empty>No cases yet.</Empty>}
            {all.length > 0 && (
              <div className="table-wrap" data-video="cases-table">
                <table>
                  <thead>
                    <tr><th>Case</th><th>Scenario</th><th>State</th><th aria-label="open" /></tr>
                  </thead>
                  <tbody>
                    {all.slice(0, 12).map((r) => (
                      <tr
                        key={r.case_id}
                        className="rowlink"
                        tabIndex={0}
                        role="link"
                        aria-label={`Open decision trace for ${r.case_id}`}
                        onClick={() => openTrace(r.run_id)}
                        onKeyDown={onActivate(() => openTrace(r.run_id))}
                      >
                        <td style={{ minWidth: 200 }}><span className="cid">{r.case_id}</span></td>
                        <td>
                          <div>{scenarioTitle(r.scenario_id, r.title)}</div>
                          <Provenance scenarioId={r.scenario_id} size="inline" />
                        </td>
                        <td><StateBadge code={r.current_state} role={currentOwner(r.escalations)?.role} /></td>
                        <td style={{ width: 100, textAlign: "right" }}><span className="go small">Open case →</span></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>
          <details className="panel">
            <summary className="panel-head" style={{ cursor: "pointer" }}><h2>What this console does not do</h2></summary>
            <div className="panel-body layer-grid">
              {[
                ["No clinical judgement", "The critical flag arrives with the result. This system carries it; it never computes it."],
                ["No advice to patients", "Messages ask the patient to collect a result that already exists. No interpretation, treatment or diagnosis."],
                ["No compliance claim", "A passing scenario shows the workflow follows a cited requirement. It is not evidence of clinical safety."],
              ].map(([h, b]) => (
                <div key={h} className="layer-card"><div className="k">{h}</div><div className="v">{b}</div></div>
              ))}
            </div>
          </details>
        </div>

        <div className="stack">
          <Panel title="Evidence base">
            {health.loading && <Skeleton height={90} />}
            {health.data && (
              <dl className="kv" style={{ margin: 0 }}>
                <dt>Excerpts checked against their source</dt>
                <dd className="mono">{health.data.knowledge_base.verification.verified} of {health.data.knowledge_base.chunk_count}</dd>
                <dt>Retrieval for decisions</dt>
                <dd className="mono">{String(health.data.knowledge_base.engine).split(/[\s(]/)[0]}, deterministic</dd>
                <dt>Live network</dt>
                <dd>{health.data.real_network_access ? "connected" : "none"}</dd>
              </dl>
            )}
          </Panel>
          <Panel title="Audit activity" action={<Link to="/audit" className="btn small ghost">Check the chain</Link>} flush>
            {dash.data && dash.data.recent_audit.length === 0 && <Empty>No audit entries yet.</Empty>}
            <div className="timeline panel-body" style={{ paddingBottom: 4 }}>
              {(dash.data?.recent_audit ?? []).slice(0, 6).map((a) => (
                <div className="tl-item" key={`${a.case_id}-${a.seq}`}>
                  <div className="row-wrap" style={{ gap: 8 }}>
                    <span className="mono tiny muted">{fmtTime(a.at)}</span>
                    <span className="mono tiny">{a.event}</span>
                  </div>
                  <div className="small" style={{ marginTop: 2 }}>{a.summary}</div>
                  <div className="mono tiny muted">entry {a.seq}, hash {shortHash(a.hash)}</div>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
