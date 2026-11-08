import { useState } from "react";
import { api } from "../api/client";
import { Banner, Empty, Glyph, Panel, Skeleton, fmtTime, humanise, shortHash, useAsync } from "../ui";
import { TrustTag } from "../components";
import "../styles/evidence.css";

/** Who acted: AI agents get the dashed mark, code and the gate their own, people the filled one. */
function By({ actor }: { actor: string }) {
  const a = String(actor ?? "");
  if (a.startsWith("AGENT:")) return <TrustTag kind="ai" who={humanise("agent", a.slice(6))} />;
  if (a.includes("ASSURANCE")) return <TrustTag kind="code" />;
  if (a.startsWith("ORCHESTRATOR") || a === "GATE" || a.includes("GATE")) return <TrustTag kind="gate" label="Gate / orchestrator" />;
  if (a === "SYSTEM" || a === "NETWORK" || a === "LAB") return <TrustTag kind="code" label={a === "LAB" ? "Laboratory system" : a === "NETWORK" ? "Delivery network" : "System"} />;
  return <TrustTag kind="person" who={humanise("role", a)} />;
}

function short(v: any, n = 90): string {
  const t0 = typeof v === "string" ? v : v && typeof v === "object" ? String(v.choice ?? v.text ?? v.noul ?? "") : String(v ?? "");
  const t = t0.replace(/\*\*/g, "");
  return t.length > n ? t.slice(0, n).replace(/\s+\S*$/, "") + "…" : t;
}

/** Humanised one-line summary; never raw JSON. */
function Summary({ e }: { e: any }) {
  let text: string = String(e.summary ?? "");
  const p = e.payload ?? {};
  if (e.event === "agent.message") {
    const who = humanise("agent", p.role);
    const a = p.answers ?? {};
    const lead = a.rationale ? short(a.rationale, 110) : a.objection ? humanise("objection", a.objection) : a.obligation ? humanise("obligation", short(a.obligation)) : humanise("agentStatus", p.status);
    text = `${who} answered: ${lead}`;
  } else if (/[{][\"]/.test(text)) {
    text = text.replace(/:\s*[{].*$/s, "").trim() || humanise("event", e.event);
  }
  const raw = e.payload && Object.keys(e.payload).length ? JSON.stringify(e.payload, null, 2) : null;
  return (
    <div className="audit-sum">
      <div>{text}</div>
      {raw && <details><summary>Full payload</summary><pre>{raw}</pre></details>}
    </div>
  );
}

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
            <div className={`audit-verdict${audit.data.chain_valid ? "" : " broken"}`} data-video="audit-verdict">
              <Glyph name={audit.data.chain_valid ? "check" : "crit"} size={audit.data.chain_valid ? 16 : 12} toned={!audit.data.chain_valid} />
              <span className="av-text">
                {audit.data.chain_valid
                  ? `Chain intact: ${audit.data.count} entries re-verified from stored rows`
                  : `Chain broken at entry ${audit.data.broken_sequences[0]}`}
              </span>
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
                    <th>By</th>
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
                      <td className="small" title={e.event}>{humanise("event", e.event)}</td>
                      <td><By actor={e.actor} /></td>
                      <td className="small" style={{ maxWidth: 420 }}><Summary e={e} /></td>
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
