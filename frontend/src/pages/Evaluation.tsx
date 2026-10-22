import { useState } from "react";
import { api } from "../api/client";
import { Banner, Chip, Empty, Panel, Spinner, Skeleton, fmtTime, statusTone, useAsync } from "../ui";

const ASSERTION_LABELS: Record<string, string> = {
  no_delivery_without_matched_receipt: "No delivery without a matched receipt",
  no_ack_without_delivery: "No acknowledgement without prior delivery",
  no_false_closure: "No closure with unresolved conditions",
  unknown_preserved_after_timeout: "Unknown delivery state preserved after timeout",
  reconcile_before_retry: "Reconcile before retry",
  no_duplicate_dispatch: "No duplicate dispatch to a channel",
  no_unauthorised_channel: "No transmission on an unauthorised channel",
  no_patient_direct_communication_for_genetic_result: "No patient-direct communication for genetic results",
  stale_ack_not_used_for_current_revision: "Stale acknowledgement not used for the current revision",
  correction_references_previous_revision: "Correction references the superseded revision",
  receipt_bound_to_its_revision: "Receipt bound to its own revision",
  no_out_of_jurisdiction_binding_citation: "No out-of-jurisdiction binding citation",
  fallback_only_with_recorded_authorisation: "Fallback only with recorded authorisation",
  human_approval_enforced: "Human approval enforced",
  audit_chain_valid: "Audit chain valid",
  provenance_present: "Each send carries a policy citation",
};

export default function Evaluation() {
  const latest = useAsync<any>(() => api.latestEvaluation().catch(() => null), []);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);

  async function runAll() {
    setRunning(true);
    setErr(null);
    try {
      const res = await api.evaluate();
      setResult(res);
      latest.reload();
    } catch (e: any) {
      setErr(String(e.message ?? e));
    } finally {
      setRunning(false);
    }
  }

  const report = result ?? latest.data;
  const summary: Record<string, any> = report?.summary?.by_configuration ?? {};

  return (
    <div className="stack">
      <Banner tone="warn">
        <span>
          <strong>These numbers are not a safety or compliance claim.</strong> The scenarios are synthetic and
          were authored by the same team that built the system. What they show is that named invariants hold —
          or fail — deterministically, under a configuration that is supposed to exercise them.
          {(report?.caveats ?? []).slice(0, 1).map((c: string) => (
            <span key={c}> {c}</span>
          ))}
        </span>
      </Banner>

      <Panel
        title="Evaluation run"
        hint={report ? `${report.run_count ?? "—"} runs · finished ${fmtTime(report.run_finished)}` : "no results loaded"}
        action={
          <button className="btn primary small" onClick={runAll} disabled={running}>
            {running ? <Spinner /> : "Run 7 × 4 matrix"}
          </button>
        }
      >
        {err && <Banner tone="bad">{err}</Banner>}
        {latest.loading && !report && <Skeleton height={120} />}
        {!report && !latest.loading && !latest.error && (
          <Empty>
            No evaluation has been run in this deployment. Press “Run 7 × 4 matrix”; it takes a few seconds and
            rewrites <span className="mono">evaluation/report.md</span>.
          </Empty>
        )}
        {report && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Configuration</th>
                  <th className="num">Safe scenarios</th>
                  <th className="num">Assertions</th>
                  <th className="num">False closure</th>
                  <th className="num">Stale ack</th>
                  <th className="num">Unauth. channel</th>
                  <th className="num">Scope violations</th>
                  <th className="num">Comparator as binding</th>
                  <th className="num">Send provenance</th>
                  <th>Replay</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(summary).map(([name, s]: any) => (
                  <tr key={name}>
                    <td>
                      <div className="mono small">{name}</div>
                      <div className="tiny muted">{s.label}</div>
                    </td>
                    <td className="num">
                      <Chip tone={s.scenarios_fully_safe === s.runs ? "ok" : s.scenarios_fully_safe === 0 ? "bad" : "warn"}>
                        {s.scenarios_fully_safe}/{s.runs}
                      </Chip>
                    </td>
                    <td className="num">
                      {s.assertions_passed}/{s.assertions_total}
                      <div className="tiny muted">{Math.round((s.assertion_pass_rate ?? 0) * 100)}%</div>
                    </td>
                    <td className="num">{s.false_closures}</td>
                    <td className="num">{s.stale_ack_uses}</td>
                    <td className="num">{s.unauthorised_channels}</td>
                    <td className="num">{s.scope_violations}</td>
                    <td className="num">{s.comparator_cited_as_binding}</td>
                    <td className="num">{s.mean_provenance_completeness.toFixed(2)}</td>
                    <td>{s.replay_reproducible ? <Chip tone="ok">stable</Chip> : <Chip tone="bad">drift</Chip>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {report && <PerScenario runs={report.runs ?? []} />}

      <Panel title="Invariants under test" hint="each one can fail" flush>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Assertion key</th>
                <th>What it refuses to allow</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(ASSERTION_LABELS).map(([k, v]) => (
                <tr key={k}>
                  <td className="mono tiny">{k}</td>
                  <td className="small">{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel title="How to read the columns">
        <div className="grid cols-2">
          <div className="stack" style={{ gap: 10 }}>
            <div>
              <h3 style={{ fontSize: 12.5, marginBottom: 3 }}>Safe scenarios</h3>
              <p className="small muted">
                Scenarios whose final state is in the independently authored set of acceptable outcomes{" "}
                <em>and</em> whose invariants held. A baseline configuration is expected to score lower; a
                configuration scoring the same as the full one would mean the extra controls are not load-bearing.
              </p>
            </div>
            <div>
              <h3 style={{ fontSize: 12.5, marginBottom: 3 }}>Send provenance</h3>
              <p className="small muted">
                Fraction of transmission steps where a policy citation was actually attached. A configuration
                with no knowledge base cannot score 1.00 here — that is the point of the metric.
              </p>
            </div>
          </div>
          <div className="stack" style={{ gap: 10 }}>
            <div>
              <h3 style={{ fontSize: 12.5, marginBottom: 3 }}>Replay</h3>
              <p className="small muted">
                Each run is executed twice and the resulting state signatures compared. Drift would mean the
                workflow is not deterministic, which would make the other columns meaningless.
              </p>
            </div>
            <div>
              <h3 style={{ fontSize: 12.5, marginBottom: 3 }}>Known caveat</h3>
              <p className="small muted">
                One scenario (S6) separates only the retrieval-only configuration: it demonstrates that ranking
                relevance is not applicability. It is a partial discriminator and is described as such.
              </p>
            </div>
          </div>
        </div>
      </Panel>
    </div>
  );
}

function PerScenario({ runs }: { runs: any[] }) {
  const scenarios = Array.from(new Set(runs.map((r) => r.scenario_id)));
  const configs = Array.from(new Set(runs.map((r) => r.configuration)));
  const get = (s: string, c: string) => runs.find((r) => r.scenario_id === s && r.configuration === c);

  if (!runs.length) return null;

  return (
    <Panel title="Assertion matrix" hint="passed / total, per scenario and configuration" flush>
      <div className="table-wrap">
        <table className="matrix-table matrix-fixed">
          <colgroup>
            <col style={{ width: 210 }} />
            {configs.map((c) => (
              <col key={c} />
            ))}
          </colgroup>
          <thead>
            <tr>
              <th>Scenario</th>
              {configs.map((c) => (
                <th key={c}>{c}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {scenarios.map((s) => (
              <tr key={s}>
                <td className="mono tiny" style={{ overflowWrap: "anywhere" }}>{s}</td>
                {configs.map((c) => {
                  const r = get(s, c);
                  if (!r) return <td key={c} className="muted">—</td>;
                  const entries = Object.entries(r.assertions ?? {}) as Array<[string, boolean]>;
                  const failed = entries.filter(([, ok]) => !ok);
                  return (
                    <td key={c}>
                      <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>
                        <Chip tone={failed.length === 0 ? "ok" : failed.length >= 3 ? "bad" : "warn"}>
                          {r.assertions_passed}/{r.assertions_total}
                        </Chip>
                        {r.final_state && (
                          <span
                            className="mono tiny muted"
                            title={r.final_state}
                            style={{ overflowWrap: "anywhere", whiteSpace: "normal" }}
                          >
                            {r.final_state}
                          </span>
                        )}
                      </div>
                      {failed.length > 0 && (
                        <div className="tiny" style={{ color: "var(--bad)", marginTop: 3, overflowWrap: "anywhere" }}>
                          {failed.map(([k]) => k).join(", ")}
                        </div>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  );
}
