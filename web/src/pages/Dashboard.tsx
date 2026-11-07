import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { Banner, Chip, Empty, Panel, Skeleton, fmtTime, shortHash, stateTone, useAsync } from "../ui";
import { onActivate } from "../design/motion";

type Dash = {
  counters: Record<string, number>;
  filters: Record<string, string[]>;
  recent_audit: Array<{ seq: number; at: string; event: string; actor: string; summary: string; case_id: string; hash: string }>;
};

/** The six stages a result must pass, in order. Each case sits in exactly one stage or one exit. */
const STAGES: Array<{ name: string; states: string[]; note: string }> = [
  { name: "Finalised", states: ["RESULT_DRAFT", "RESULT_FINALIZED"], note: "the laboratory has released the result" },
  { name: "Sending", states: ["TRANSMISSION_QUEUED", "TRANSMISSION_ATTEMPTED", "RETRY_PENDING"], note: "a message is queued or in flight" },
  { name: "Accepted by gateway", states: ["TRANSPORT_ACCEPTED"], note: "accepted is not delivered" },
  { name: "Delivered", states: ["DELIVERY_CONFIRMED", "AWAITING_ACKNOWLEDGMENT"], note: "delivered is not acknowledged" },
  { name: "Acknowledged", states: ["CLINICAL_ACKNOWLEDGMENT_CONFIRMED"], note: "a named person, the current revision" },
  { name: "Documented", states: ["COMMUNICATION_DOCUMENTED", "CORRECTED_RESULT_ACKNOWLEDGED"], note: "the only state that closes a case" },
];

const EXITS: Array<{ name: string; states: string[]; why: string; tone: "bad" | "warn" }> = [
  { name: "With a named person", states: ["ESCALATION_REQUIRED", "ESCALATION_IN_REVIEW"], why: "escalated, with an owner and a deadline", tone: "bad" },
  { name: "Delivery unknown or failed", states: ["DELIVERY_STATE_UNKNOWN", "DELIVERY_FAILED"], why: "must be reconciled before any retry", tone: "bad" },
  { name: "Correction in progress", states: ["CORRECTION_PENDING", "CORRECTED_RESULT_FINALIZED", "CORRECTED_RESULT_DELIVERY_PENDING"], why: "an earlier acknowledgment no longer counts", tone: "warn" },
];

export default function Dashboard() {
  const dash = useAsync<Dash>(() => api.dashboard(), []);
  const cases = useAsync<{ cases: any[]; count: number }>(() => api.cases(), []);
  const health = useAsync<any>(() => api.health(), []);
  const navigate = useNavigate();

  const all = cases.data?.cases ?? [];
  const rows = all.slice(0, 10);
  const count = (states: string[]) => all.filter((r) => states.includes(r.current_state)).length;

  const openTrace = (runId?: string) => {
    if (runId) navigate(`/trace?run=${encodeURIComponent(runId)}`);
  };

  return (
    <div className="stack">
      <section aria-label="Where each case is">
        <div className="chain">
          {STAGES.map((s, i) => {
            const n = cases.loading ? null : count(s.states);
            return (
              <div key={s.name} className={`chain-stage${i === STAGES.length - 1 ? " final" : ""}`}>
                <div className="n">{i + 1}</div>
                <div className="name">{s.name}</div>
                <div className={`count${n === 0 ? " zero" : ""}`}>{n ?? "–"}</div>
                <div className="rule-note">{s.note}</div>
              </div>
            );
          })}
        </div>
        <div className="chain-exits">
          {EXITS.map((e) => {
            const n = cases.loading ? null : count(e.states);
            return (
              <div key={e.name} className={`exit${e.tone === "bad" ? " bad" : ""}`}>
                <div className="spread">
                  <span className="name">{e.name}</span>
                  <span className={`count${n === 0 ? " zero" : ""}`}>{n ?? "–"}</span>
                </div>
                <div className="why">{e.why}</div>
              </div>
            );
          })}
        </div>
      </section>

      <div className="grid split-8-4">
        <div className="stack">
          <Panel
            title="Cases"
            hint={all.length ? `${all.length} in this store; open one to see why it is where it is` : undefined}
            action={<Link to="/simulator" className="btn small primary">Run a scenario</Link>}
            flush
          >
            {cases.loading && (
              <div className="panel-body">
                <Skeleton height={14} />
                <Skeleton height={14} />
              </div>
            )}
            {cases.error && <div className="panel-body"><Banner tone="bad">{cases.error}</Banner></div>}
            {!cases.loading && !cases.error && rows.length === 0 && (
              <Empty>
                No cases yet. Run a scenario in the <Link to="/simulator">simulator</Link>; each run creates one case.
              </Empty>
            )}
            {rows.length > 0 && (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Case</th>
                      <th>Scenario and configuration</th>
                      <th>State</th>
                      <th>Acknowledgment</th>
                      <th aria-label="open" />
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((r) => (
                      <tr
                        key={r.case_id}
                        className="rowlink"
                        tabIndex={0}
                        role="link"
                        aria-label={`Open decision trace for ${r.case_id}`}
                        onClick={() => openTrace(r.run_id)}
                        onKeyDown={onActivate(() => openTrace(r.run_id))}
                      >
                        <td style={{ minWidth: 180 }}>
                          <span className="mono">{r.case_id.split("-").slice(0, 3).join("-")}</span>
                          <div className="tiny muted">{r.jurisdiction}, {String(r.case_scope).toLowerCase().replace("_", "-")}</div>
                        </td>
                        <td>
                          <div className="truncate" style={{ maxWidth: 260 }}>{r.scenario_id}</div>
                          <div className="tiny muted mono">{r.configuration}</div>
                        </td>
                        <td>
                          <Chip tone={stateTone(r.current_state)}>{r.current_state}</Chip>
                        </td>
                        <td>
                          {r.acknowledgment_count === 0 ? (
                            <span className="muted small">none</span>
                          ) : (
                            <Chip tone={r.acknowledges_current ? "ok" : "bad"}>
                              {r.acknowledges_current ? "current revision" : "earlier revision"}
                            </Chip>
                          )}
                        </td>
                        <td style={{ width: 70, textAlign: "right" }}>
                          <span className="go small">Trace</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          <Panel title="What this console does not do">
            <div className="layer-grid">
              {[
                ["No clinical judgement", "The critical flag arrives with the result. This system carries it; it never computes it."],
                ["No advice to patients", "Messages ask the patient to collect a result that already exists. No interpretation, treatment or diagnosis."],
                ["No compliance claim", "A passing scenario shows the workflow follows a cited requirement. It is not evidence of clinical safety."],
              ].map(([h, b]) => (
                <div key={h} className="layer-card">
                  <div className="k">{h}</div>
                  <div className="v">{b}</div>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        <div className="stack">
          <Panel title="Evidence base">
            {health.loading && <Skeleton height={90} />}
            {health.data && (
              <dl className="kv" style={{ margin: 0 }}>
                <dt>Excerpts checked against their source</dt>
                <dd className="mono">
                  {health.data.knowledge_base.verification.verified} of {health.data.knowledge_base.chunk_count}
                </dd>
                <dt>Retrieval for decisions</dt>
                <dd className="mono">{String(health.data.knowledge_base.engine).split(/[\s(]/)[0]}, deterministic</dd>
                <dt>Live network</dt>
                <dd>{health.data.real_network_access ? "connected" : "none"}</dd>
              </dl>
            )}
            {health.data && (
              <p className="tiny muted" style={{ marginTop: 12 }}>
                A quotation that cannot be found on its source page is left out of retrieval, not shown with a warning.
              </p>
            )}
          </Panel>

          <Panel
            title="Audit activity"
            action={<Link to="/audit" className="btn small ghost">Verify the chain</Link>}
            flush
          >
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
