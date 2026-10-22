import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import {
  Banner, Chip, Empty, Panel, PillGroup, Skeleton, Tabs, fmtTime, stateTone, statusTone, useAsync,
} from "../ui";

const LAYERS = [
  { id: "WORKFLOW", label: "Workflow", blurb: "Where the case is in the institution's own process." },
  { id: "CLINICAL", label: "Clinical", blurb: "Result facts produced by the laboratory." },
  { id: "TRANSPORT", label: "Transport", blurb: "What the network did with the message." },
  { id: "HUMAN", label: "Human", blurb: "People: acknowledgements, approvals, escalation responses." },
  { id: "POLICY", label: "Policy", blurb: "Evidence consulted and the rule it supports." },
  { id: "AUDIT", label: "Audit", blurb: "Governance checks over the record itself." },
] as const;

const TONE_BY_LAYER: Record<string, string> = {
  WORKFLOW: "#1f4e79",
  CLINICAL: "#0b6b5f",
  TRANSPORT: "#8a5a00",
  HUMAN: "#6b3f8c",
  POLICY: "#1c5d99",
  AUDIT: "#3d4854",
};

export default function CaseTimeline() {
  const [params, setParams] = useSearchParams();
  const selected = params.get("case");
  const [tab, setTab] = useState<"layers" | "events" | "transitions" | "evidence">("layers");
  const [layerFilter, setLayerFilter] = useState<"all" | string>("all");

  const list = useAsync<{ cases: any[]; count: number }>(() => api.cases(), []);
  const detail = useAsync<any>(
    () => (selected ? api.caseDetail(selected) : Promise.resolve(null)),
    [selected]
  );

  const d = detail.data;
  const events: any[] = d?.events ?? [];

  const grouped = useMemo(() => {
    const g: Record<string, any[]> = {};
    for (const e of events) (g[e.source_layer] ??= []).push(e);
    return g;
  }, [events]);

  const statusCounts = useMemo(() => {
    const t = d?.transitions ?? [];
    return {
      applied: t.filter((x: any) => x.status === "APPLIED").length,
      blocked: t.filter((x: any) => x.status === "BLOCKED").length,
      forbidden: t.filter((x: any) => x.status === "FORBIDDEN").length,
    };
  }, [d]);

  return (
    <div className="stack">
      <Panel title="Cases" hint={list.data ? `${list.data.count} stored` : "loading"} flush>
        {list.loading && <div className="panel-body"><Skeleton height={14} /><Skeleton height={14} /></div>}
        {!list.loading && (list.data?.cases.length ?? 0) === 0 && (
          <Empty>No cases in the store yet. Release a scenario in the simulator to create one.</Empty>
        )}
        {(list.data?.cases.length ?? 0) > 0 && (
          <div className="table-wrap" style={{ maxHeight: 260 }}>
            <table>
              <thead>
                <tr>
                  <th>Case</th>
                  <th>Scenario</th>
                  <th>Configuration</th>
                  <th>State</th>
                  <th>Revision</th>
                  <th className="num">Acks</th>
                  <th>Delivery</th>
                  <th>Escalations</th>
                </tr>
              </thead>
              <tbody>
                {list.data!.cases.map((r) => (
                  <tr
                    key={r.case_id}
                    onClick={() => setParams({ case: r.case_id })}
                    style={{ cursor: "pointer", background: r.case_id === selected ? "#f3f8f7" : undefined }}
                  >
                    <td className="mono">{r.case_id}</td>
                    <td className="truncate" style={{ maxWidth: 170 }}>{r.scenario_id}</td>
                    <td><Chip tone={r.configuration === "resultrelay" ? "ok" : "neutral"}>{r.configuration}</Chip></td>
                    <td><Chip tone={stateTone(r.current_state)}>{r.current_state}</Chip></td>
                    <td className="mono tiny">{r.current_revision_id ?? "—"}</td>
                    <td className="num">
                      {r.acknowledgment_count}
                      {r.acknowledgment_count > 0 && (
                        <span title={r.acknowledges_current ? "acknowledgement bound to current revision" : "acknowledgement bound to a superseded revision"}>
                          {" "}
                          <Chip tone={r.acknowledges_current ? "ok" : "bad"}>
                            {r.acknowledges_current ? "current" : "stale"}
                          </Chip>
                        </span>
                      )}
                    </td>
                    <td className="small">
                      {r.delivered_attempts > 0 ? (
                        <Chip tone="ok">{r.delivered_attempts} delivered</Chip>
                      ) : (
                        <span className="muted">none</span>
                      )}
                    </td>
                    <td className="num">{r.escalation_count || <span className="muted">0</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {!selected && <Banner tone="info">Select a case above to inspect its timeline.</Banner>}

      {selected && detail.loading && <Panel title="Loading case"><Skeleton height={90} /></Panel>}
      {detail.error && <Banner tone="bad">{detail.error}</Banner>}

      {d && (
        <>
          <div className="grid cols-4">
            <div className="panel metric">
              <div className="label">Current state</div>
              <div style={{ marginTop: 8 }}><Chip tone={stateTone(d.case.current_state)}>{d.case.current_state}</Chip></div>
              <div className="sub">{d.case.jurisdiction} · {d.case.facility_type} · {d.case.case_scope}</div>
            </div>
            <div className="panel metric">
              <div className="label">Transitions</div>
              <div className="value">{d.transitions.length}</div>
              <div className="sub">
                {statusCounts.applied} applied · {statusCounts.blocked} blocked · {statusCounts.forbidden} forbidden
              </div>
            </div>
            <div className="panel metric">
              <div className="label">Revisions</div>
              <div className="value">{d.revisions.length}</div>
              <div className="sub">
                current <span className="mono">{d.case.current_revision_id ?? "—"}</span>
              </div>
            </div>
            <div className="panel metric">
              <div className="label">Open conditions</div>
              <div className="value">{d.case.open_questions?.length ?? 0}</div>
              <div className="sub">
                {(d.case.blocking_conditions ?? []).length > 0
                  ? d.case.blocking_conditions.join(", ")
                  : "no blocking conditions recorded"}
              </div>
            </div>
          </div>

          <Panel flush>
            <Tabs
              value={tab}
              onChange={setTab}
              tabs={[
                { id: "layers", label: "Layer view", count: events.length },
                { id: "events", label: "Event stream" },
                { id: "transitions", label: "Transitions", count: d.transitions.length },
                { id: "evidence", label: "Evidence & delivery" },
              ]}
            />
            <div className="panel-body">
              {tab === "layers" && (
                <div className="stack">
                  <div className="row-wrap">
                    <PillGroup
                      value={layerFilter}
                      onChange={setLayerFilter}
                      options={[{ id: "all" as const, label: "All layers" }, ...LAYERS.map((l) => ({ id: l.id, label: l.label }))]}
                    />
                    <span className="tiny muted">
                      The same underlying events, separated so that one layer's success cannot stand in for another's.
                    </span>
                  </div>
                  <div className="grid cols-2">
                    {LAYERS.filter((l) => layerFilter === "all" || l.id === layerFilter).map((l) => {
                      const items = grouped[l.id] ?? [];
                      return (
                        <div key={l.id} className="panel" style={{ boxShadow: "none" }}>
                          <div className="panel-head">
                            <div className="row">
                              <span
                                style={{
                                  width: 8, height: 8, borderRadius: 2, background: TONE_BY_LAYER[l.id],
                                }}
                              />
                              <h2 style={{ fontSize: 13 }}>{l.label}</h2>
                              <span className="hint">{items.length} event{items.length === 1 ? "" : "s"}</span>
                            </div>
                            <span className="tiny muted truncate" style={{ maxWidth: 230 }}>{l.blurb}</span>
                          </div>
                          <div className="panel-body" style={{ paddingTop: 12 }}>
                            {items.length === 0 && <Empty>No {l.label.toLowerCase()} events recorded.</Empty>}
                            <div className="timeline">
                              {items.map((e) => (
                                <div className="tl-item" key={e.seq}>
                                  <div className="row-wrap" style={{ gap: 6 }}>
                                    <span className="mono tiny muted">{fmtTime(e.at)}</span>
                                    <Chip tone="neutral">{e.kind}</Chip>
                                  </div>
                                  <div className="small">{e.summary}</div>
                                  <div className="tiny muted">by {e.actor}</div>
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {tab === "events" && (
                <div className="table-wrap" style={{ maxHeight: 520 }}>
                  <table>
                    <thead>
                      <tr>
                        <th className="num">#</th>
                        <th>At</th>
                        <th>Layer</th>
                        <th>Kind</th>
                        <th>Summary</th>
                        <th>Actor</th>
                      </tr>
                    </thead>
                    <tbody>
                      {events.map((e) => (
                        <tr key={e.seq}>
                          <td className="num">{e.seq}</td>
                          <td className="mono tiny">{fmtTime(e.at)}</td>
                          <td><Chip tone="info">{e.source_layer}</Chip></td>
                          <td className="mono tiny">{e.kind}</td>
                          <td>{e.summary}</td>
                          <td className="mono tiny">{e.actor}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {tab === "transitions" && (
                <div className="table-wrap" style={{ maxHeight: 520 }}>
                  <table>
                    <thead>
                      <tr>
                        <th className="num">Step</th>
                        <th>Event</th>
                        <th>From → To</th>
                        <th>Status</th>
                        <th>Reason</th>
                        <th>Invariant</th>
                      </tr>
                    </thead>
                    <tbody>
                      {d.transitions.map((t: any, i: number) => (
                        <tr key={`${t.step}-${i}`}>
                          <td className="num">{t.step}</td>
                          <td className="mono tiny">{t.trigger_event}</td>
                          <td className="mono tiny">
                            {t.prior_state} → <strong>{t.resulting_state}</strong>
                          </td>
                          <td><Chip tone={statusTone(t.status)}>{t.status}</Chip></td>
                          <td className="small">{t.reason}</td>
                          <td className="mono tiny">{t.invariant ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {tab === "evidence" && (
                <div className="stack">
                  <div className="grid cols-2">
                    <div className="panel" style={{ boxShadow: "none" }}>
                      <div className="panel-head"><h2 style={{ fontSize: 13 }}>Revisions</h2></div>
                      <div className="panel-body" style={{ paddingTop: 8 }}>
                        {d.revisions.length === 0 && <Empty>No revisions.</Empty>}
                        {d.revisions.map((r: any) => (
                          <div key={r.revision_id} className="spread" style={{ padding: "6px 0", borderBottom: "1px solid var(--line-2)" }}>
                            <div>
                              <div className="mono small">{r.revision_id}</div>
                              <div className="tiny muted">{r.test_name} · v{r.version}</div>
                            </div>
                            <div className="row">
                              <Chip tone={r.revision_id === d.case.current_revision_id ? "ok" : "neutral"}>{r.status}</Chip>
                              {r.supersedes_revision_id && <Chip tone="warn">supersedes {r.supersedes_revision_id}</Chip>}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="panel" style={{ boxShadow: "none" }}>
                      <div className="panel-head"><h2 style={{ fontSize: 13 }}>Delivery attempts & acknowledgements</h2></div>
                      <div className="panel-body" style={{ paddingTop: 8 }}>
                        {d.attempts.length === 0 && <Empty>No transmission attempted.</Empty>}
                        {d.attempts.map((a: any) => (
                          <div key={a.attempt_id} className="spread" style={{ padding: "6px 0", borderBottom: "1px solid var(--line-2)" }}>
                            <div>
                              <div className="mono small">{a.attempt_id}</div>
                              <div className="tiny muted">{a.channel} · rev {a.result_revision_id}</div>
                            </div>
                            <div className="row" style={{ gap: 4 }}>
                              <Chip tone={a.delivered ? "ok" : a.failed ? "bad" : "warn"}>{a.outcome}</Chip>
                              {a.reconciled && <Chip tone="info">reconciled</Chip>}
                              {a.duplicate_suppressed && <Chip tone="warn">dup suppressed</Chip>}
                            </div>
                          </div>
                        ))}
                        <hr className="sep" />
                        {d.acknowledgments.length === 0 && <Empty>No acknowledgement recorded.</Empty>}
                        {d.acknowledgments.map((a: any) => (
                          <div key={a.ack_id} className="spread" style={{ padding: "6px 0" }}>
                            <div>
                              <div className="mono small">{a.ack_id}</div>
                              <div className="tiny muted">{a.role} · {a.channel} · {fmtTime(a.at)}</div>
                            </div>
                            <Chip tone={a.result_revision_id === d.case.current_revision_id ? "ok" : "bad"}>
                              rev {a.result_revision_id}
                            </Chip>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>

                  <div className="panel" style={{ boxShadow: "none" }}>
                    <div className="panel-head">
                      <h2 style={{ fontSize: 13 }}>Citations relied on</h2>
                      <span className="hint">{d.citations.length} recorded</span>
                    </div>
                    <div className="table-wrap">
                      <table>
                        <thead>
                          <tr>
                            <th>Source</th>
                            <th>Section</th>
                            <th className="num">Page</th>
                            <th>Claim class</th>
                            <th>Agent</th>
                            <th className="num">Step</th>
                          </tr>
                        </thead>
                        <tbody>
                          {d.citations.map((c: any, i: number) => (
                            <tr key={i}>
                              <td className="mono tiny">{c.source_id}</td>
                              <td className="mono tiny">{c.section}</td>
                              <td className="num">{c.page}</td>
                              <td><Chip tone={c.claim_type === "BINDING_REQUIREMENT" ? "ok" : c.claim_type === "GLOBAL_COMPARATOR" ? "outline" : "info"}>{c.claim_type}</Chip></td>
                              <td className="mono tiny">{c.agent_id}</td>
                              <td className="num">{c.step}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </Panel>
        </>
      )}
    </div>
  );
}
