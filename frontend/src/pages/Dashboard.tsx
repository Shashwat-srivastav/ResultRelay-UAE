import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import {
  Banner, Chip, Empty, Panel, Skeleton, fmtTime, shortHash, stateTone, useAsync,
} from "../ui";
import { Pipeline3DLazy as Pipeline3D } from "../design/Pipeline3DLazy";
import { useCountUp, useReveal, onActivate } from "../design/motion";

type Dash = {
  counters: Record<string, number>;
  filters: Record<string, string[]>;
  recent_audit: Array<{ seq: number; at: string; event: string; actor: string; summary: string; case_id: string; hash: string }>;
};

/** One lead figure, counted up once because it is computed once per page load — not live data. */
function LeadMetric({ value, of, label }: { value: number | null; of: number | null; label: string }) {
  const v = useCountUp(value);
  return (
    <div>
      <div className="label">{label}</div>
      <div className="display tnum" style={{ marginTop: 6 }}>
        <span ref={v.ref}>{value === null ? "—" : v.value}</span>
        <span style={{ fontSize: 20, color: "var(--ink-3)", fontWeight: 600 }}>
          {" / "}
          {of === null ? "—" : of}
        </span>
      </div>
    </div>
  );
}

export default function Dashboard() {
  const dash = useAsync<Dash>(() => api.dashboard(), []);
  const cases = useAsync<{ cases: any[]; count: number }>(() => api.cases(), []);
  const health = useAsync<any>(() => api.health(), []);
  const navigate = useNavigate();
  const reveal = useReveal<HTMLDivElement>([dash.data, cases.data], 0.035);

  const c = dash.data?.counters;
  const rows = (cases.data?.cases ?? []).slice(0, 8);
  const documented = rows.filter((r) => r.current_state === "COMMUNICATION_DOCUMENTED").length;
  const active = cases.data?.count ?? rows.length;

  const pipeline = [
    { label: "event", permitted: true, active: false },
    { label: "evidence", permitted: true, active: false },
    { label: "proposal", permitted: true, active: false },
    { label: "gate", permitted: true, active: true },
    { label: "transition", permitted: true, active: false },
    { label: "state", permitted: true, active: false },
  ];

  const openTrace = (runId?: string) => {
    if (!runId) return;
    navigate(`/trace?run=${encodeURIComponent(runId)}`);
  };

  return (
    <div className="stack" ref={reveal}>
      <div data-reveal>
        <Banner tone="info">
          <span>
            <strong>Demonstration prototype.</strong> Every patient, result and channel here is synthetic. The
            system does not diagnose, does not set clinical thresholds and does not give medical advice; it
            enforces <em>communication</em> obligations over results that a laboratory has already finalised.
          </span>
        </Banner>
      </div>

      {/* The screen's one question: how many cases are documented, out of how many. */}
      <div className="lead-card" data-reveal>
        <div className="lead-split">
          <div>
            <LeadMetric
              value={cases.loading ? null : documented}
              of={cases.loading ? null : active}
              label="Cases with a documented communication"
            />
            <p className="lead-note" style={{ marginTop: 10 }}>
              A case reaches <span className="mono">COMMUNICATION_DOCUMENTED</span> only when the gate has
              permitted the transition <em>and</em> a record of the communication exists. Delivery is not
              acknowledgment, and neither is assumed.
            </p>
            <div className="legend" style={{ marginTop: 14 }}>
              <Chip tone="ok">documented</Chip>
              <Chip tone="warn" title="an obligation needs a named person">needs a human</Chip>
              <Chip tone="bad" title="the gate refused the transition">refused</Chip>
              <Chip tone="info" title="material that cannot bind this case's jurisdiction">comparator</Chip>
              <Chip tone="neutral" title="labels, never status">metadata</Chip>
            </div>
          </div>
          <Pipeline3D steps={pipeline} caption="the chain every case must pass" />
        </div>
      </div>

      <div className="metric-row" data-reveal>
        <div className="metric-sm">
          <div className="k">Awaiting acknowledgment</div>
          <div className="v">{c ? c.awaiting_acknowledgment : "—"}</div>
          <div className="s">delivered, no acknowledgment bound to the current revision</div>
        </div>
        <div className="metric-sm">
          <div className="k">Delivery unknown</div>
          <div className="v">{c ? c.uncertain_delivery : "—"}</div>
          <div className="s">must be reconciled before any retry</div>
        </div>
        <div className="metric-sm">
          <div className="k">Open escalations</div>
          <div className="v">{c ? c.escalations_open : "—"}</div>
          <div className="s">routed to a named role — not an action</div>
        </div>
      </div>

      <div className="grid split-8-4" data-reveal>
        <div className="stack">
          <Panel title="Live cases" hint="state is read from the event store · open a row for its decision trace" flush>
            {cases.loading && (
              <div className="panel-body">
                <Skeleton height={14} />
                <Skeleton height={14} />
                <Skeleton height={14} />
              </div>
            )}
            {cases.error && <div className="panel-body"><Banner tone="bad">{cases.error}</Banner></div>}
            {!cases.loading && !cases.error && rows.length === 0 && (
              <Empty>
                No cases yet. Open the <Link to="/simulator">simulator</Link> and release a scenario to create one.
              </Empty>
            )}
            {rows.length > 0 && (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Case</th>
                      <th>Scenario</th>
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
                        <td style={{ minWidth: 190 }}>
                          <span className="mono" style={{ fontSize: 11.5 }}>{r.case_id}</span>
                          <div className="tiny muted">{r.jurisdiction} · {r.case_scope}</div>
                        </td>
                        <td>
                          <div className="truncate" style={{ maxWidth: 180 }}>{r.scenario_id}</div>
                          <Chip tone="neutral">{r.configuration}</Chip>
                        </td>
                        <td>
                          <Chip tone={stateTone(r.current_state)}>{r.current_state}</Chip>
                        </td>
                        <td>
                          {r.acknowledgment_count === 0 ? (
                            <span className="muted small">none</span>
                          ) : (
                            <Chip tone={r.acknowledges_current ? "ok" : "bad"}>
                              {r.acknowledges_current ? "current rev" : "stale rev"}
                            </Chip>
                          )}
                        </td>
                        <td style={{ width: 64, textAlign: "right" }}>
                          <span className="go small" style={{ color: "var(--accent)", whiteSpace: "nowrap" }}>
                            why →
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          <Panel title="What this console deliberately does not show" hint="scope limits, stated up front">
            <div className="grid cols-3">
              {[
                ["No clinical judgement", "No result is flagged critical by this system. The critical flag arrives with the result and is carried, not computed."],
                ["No patient-facing advice", "Messages are about collection of a result that already exists. No interpretation, no treatment, no diagnosis."],
                ["No compliance claim", "Passing a scenario shows the workflow is internally consistent with a cited requirement. It is not evidence of clinical safety or regulatory conformity."],
              ].map(([h, b]) => (
                <div key={h} className="layer-card">
                  <div className="k">{h}</div>
                  <div className="v muted">{b}</div>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        <div className="stack">
          <Panel title="Evidence base" hint="retrieval manifest">
            {health.loading && <Skeleton height={90} />}
            {health.data && (
              <div className="stack" style={{ gap: 10 }}>
                <div className="spread">
                  <span className="muted small">Verified excerpts</span>
                  <Chip tone="ok">
                    {health.data.knowledge_base.verification.verified}/{health.data.knowledge_base.chunk_count}
                  </Chip>
                </div>
                <div className="spread">
                  <span className="muted small">Retrieval</span>
                  <span className="small mono truncate" style={{ maxWidth: 190, textAlign: "right" }} title={health.data.knowledge_base.engine}>
                    {health.data.knowledge_base.engine}
                  </span>
                </div>
                <div className="spread">
                  <span className="muted small">Real network access</span>
                  <Chip tone="neutral">{String(health.data.real_network_access)}</Chip>
                </div>
                <div className="spread">
                  <span className="muted small">Adviser</span>
                  <Chip tone={health.data.advisory_boundary?.status === "closed" ? "neutral" : "warn"}>
                    {health.data.advisory_boundary?.status ?? "closed"}
                  </Chip>
                </div>
                <hr className="sep" />
                <div className="tiny muted">
                  Every quoted clause is verified against the local source text at index time. A quote that
                  cannot be located is excluded from retrieval rather than shown with a warning.
                </div>
              </div>
            )}
          </Panel>

          <Panel
            title="Audit activity"
            hint="hash-chained"
            action={
              <Link to="/audit" className="btn small ghost">
                Verify chain →
              </Link>
            }
            flush
          >
            {dash.data && dash.data.recent_audit.length === 0 && <Empty>No audit entries yet.</Empty>}
            <div className="timeline panel-body" style={{ paddingBottom: 4 }}>
              {(dash.data?.recent_audit ?? []).map((a) => (
                <div className="tl-item" key={`${a.case_id}-${a.seq}`}>
                  <div className="row-wrap" style={{ gap: 6 }}>
                    <span className="mono tiny muted">{fmtTime(a.at)}</span>
                    <Chip tone="neutral">{a.event}</Chip>
                    <span className="mono tiny muted">#{a.seq}</span>
                  </div>
                  <div className="small" style={{ marginTop: 2 }}>{a.summary}</div>
                  <div className="mono tiny muted">{a.case_id} · {shortHash(a.hash)}</div>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </div>
  );
}
