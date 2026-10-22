import { useState } from "react";
import { api } from "../api/client";
import { Banner, Chip, Empty, Panel, Skeleton, fmtTime, shortHash, useAsync } from "../ui";

export default function Audit() {
  const list = useAsync<{ cases: any[]; count: number }>(() => api.cases(), []);
  const [caseId, setCaseId] = useState<string | null>(null);

  const first = list.data?.cases?.[0];
  const active = caseId ?? first?.case_id ?? null;
  const audit = useAsync<any>(
    () => (active ? api.caseAudit(active) : Promise.resolve(null)),
    [active]
  );

  async function download() {
    if (!active) return;
    const bundle = await api.caseBundle(active);
    const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${active}-audit-bundle.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  }

  return (
    <div className="stack">
      <Banner tone="info">
        <span>
          Each entry commits to the hash of its predecessor. Verification is recomputed from the stored rows when
          the page loads, so a chain that was tampered with after the fact will show the broken sequence numbers.
        </span>
      </Banner>

      <Panel
        title="Audit chain"
        hint={audit.data ? `${audit.data.count} entries` : "select a case"}
        action={
          <div className="row">
            <select
              value={active ?? ""}
              onChange={(e) => setCaseId(e.target.value)}
              key={active ?? "none"}
              style={{ width: 260 }}
              aria-label="case"
            >
              {(list.data?.cases ?? []).map((c) => (
                <option key={c.case_id} value={c.case_id}>
                  {c.case_id} · {c.configuration}
                </option>
              ))}
            </select>
            <button className="btn small" onClick={download} disabled={!active}>
              Export bundle
            </button>
          </div>
        }
        flush
      >
        {list.loading && <div className="panel-body"><Skeleton height={100} /></div>}
        {!list.loading && (list.data?.cases.length ?? 0) === 0 && (
          <Empty>No cases stored yet — run a scenario in the simulator first.</Empty>
        )}
        {audit.loading && caseId !== null && <div className="panel-body"><Skeleton height={100} /></div>}
        {audit.data && (
          <div className="panel-body">
            <div className="row-wrap" style={{ marginBottom: 12 }}>
              <Chip tone={audit.data.chain_valid ? "ok" : "bad"}>
                {audit.data.chain_valid ? "chain valid" : `broken at ${audit.data.broken_sequences.join(", ")}`}
              </Chip>
              <span className="mono tiny muted">run {audit.data.run_id}</span>
              <span className="tiny muted">{audit.data.verification}</span>
            </div>
            <div className="table-wrap" style={{ maxHeight: 540 }}>
              <table>
                <thead>
                  <tr>
                    <th className="num">Seq</th>
                    <th>At</th>
                    <th>Event</th>
                    <th>Actor</th>
                    <th>Summary</th>
                    <th>Prev</th>
                    <th>Hash</th>
                  </tr>
                </thead>
                <tbody>
                  {audit.data.entries.map((e: any) => (
                    <tr key={e.seq}>
                      <td className="num">{e.seq}</td>
                      <td className="mono tiny">{fmtTime(e.at)}</td>
                      <td className="mono tiny">{e.event}</td>
                      <td className="mono tiny">{e.actor}</td>
                      <td className="small" style={{ maxWidth: 380 }}>{e.summary}</td>
                      <td className="mono tiny muted">{shortHash(e.prev_hash)}</td>
                      <td className="mono tiny">{shortHash(e.hash)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </Panel>

      <Panel title="What the bundle contains" hint="reproducibility by construction">
        <div className="grid cols-3">
          {[
            ["Case facts", "Revisions, current revision, scope, jurisdiction and the state the case reached."],
            ["Decisions", "Every agent assessment, the proposed action, the gate verdict, the invariant that applied."],
            ["Delivery evidence", "Each transmission attempt with its idempotency key, receipt, and whether it was reconciled."],
            ["Human acts", "Acknowledgements, approvals and escalations, each bound to the revision it refers to."],
            ["Citations", "Source, section, printed page and claim class for every rule relied on."],
            ["Chain", "The audit log itself, plus the verification result computed at export time."],
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
