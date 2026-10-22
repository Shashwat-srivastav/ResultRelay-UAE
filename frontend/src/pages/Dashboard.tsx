import { Link } from "react-router-dom";
import { api } from "../api/client";
import {
  Banner, Chip, Empty, Metric, Panel, Skeleton, fmtTime, pct, shortHash, stateTone, useAsync,
} from "../ui";
import type { Run } from "../types";

type Dash = {
  counters: Record<string, number>;
  filters: Record<string, string[]>;
  recent_audit: Array<{ seq: number; at: string; event: string; actor: string; summary: string; case_id: string; hash: string }>;
};

export default function Dashboard() {
  const dash = useAsync<Dash>(() => api.dashboard(), []);
  const cases = useAsync<{ cases: any[]; count: number }>(() => api.cases(), []);
  const health = useAsync<any>(() => api.health(), []);

  const c = dash.data?.counters;
  const rows = (cases.data?.cases ?? []).slice(0, 8);

  return (
    <div className="stack">
      <Banner tone="info">
        <span>
          <strong>Demonstration prototype.</strong> Every patient, result and channel here is synthetic. The
          system does not diagnose, does not set clinical thresholds and does not give medical advice; it
          enforces <em>communication</em> obligations over results that a laboratory has already finalised.
        </span>
      </Banner>

      <div className="grid cols-4">
        <Metric
          label="Active cases"
          value={c ? c.active_cases : <Skeleton height={26} width="60px" />}
          sub="in flight, all configurations"
        />
        <Metric
          label="Awaiting acknowledgment"
          value={c ? c.awaiting_acknowledgment : <Skeleton height={26} width="60px" />}
          sub="delivered, no acknowledgement bound to current revision"
        />
        <Metric
          label="Delivery state unknown"
          value={c ? c.uncertain_delivery : <Skeleton height={26} width="60px" />}
          sub="must reconcile before any retry"
        />
        <Metric
          label="Open escalations"
          value={c ? c.escalations_open : <Skeleton height={26} width="60px" />}
          sub="routed to a named role, not an action"
        />
      </div>

      <div className="grid split-8-4">
        <Panel
          title="Live cases"
          hint="state is read from the event store"
          action={
            <Link to="/cases" className="btn small">
              Open case timeline
            </Link>
          }
          flush
        >
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
                    <th>Scenario / configuration</th>
                    <th>State</th>
                    <th>Acknowledgment</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.case_id}>
                      <td>
                        <Link to={`/cases?case=${encodeURIComponent(r.case_id)}`} className="mono">
                          {r.case_id}
                        </Link>
                        <div className="tiny muted">{r.jurisdiction} · {r.case_scope}</div>
                      </td>
                      <td>
                        <div className="truncate" style={{ maxWidth: 200 }}>{r.scenario_id}</div>
                        <Chip tone={r.configuration === "resultrelay" ? "ok" : "neutral"}>{r.configuration}</Chip>
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
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

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
                  <span className="small mono">{health.data.knowledge_base.engine}</span>
                </div>
                <div className="spread">
                  <span className="muted small">Real network access</span>
                  <Chip tone="neutral">{String(health.data.real_network_access)}</Chip>
                </div>
                <div className="spread">
                  <span className="muted small">LLM provider</span>
                  <Chip tone="neutral">disabled</Chip>
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
  );
}
