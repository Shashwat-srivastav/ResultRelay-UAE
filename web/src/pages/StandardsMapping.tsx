import { useReveal } from "../design/motion";
import "../styles/evidence.css";
import { useState } from "react";
import { api } from "../api/client";
import {
  Banner, Chip, CLASS_TONE, CLAIM_TONE, CodeLabel, Empty, Panel, PillGroup, Skeleton, Tabs, statusTone, useAsync,
} from "../ui";

type Tab = "sources" | "search" | "gaps" | "y3172" | "readiness" | "profile";

export default function StandardsMapping() {
  const [tab, setTab] = useState<Tab>("sources");

  const reveal = useReveal<HTMLDivElement>([], 0.03);

  return (
    <div className="stack" ref={reveal}>
      <Banner tone="info">
        <span>
          Requirements are classified before they are used. A clause from another jurisdiction is a{" "}
          <em>comparator</em>, and the UI keeps that visible wherever it is cited — a comparator is never rendered
          as a binding obligation. The same data is exported as a static{" "}
          <a href="/data/manifest.json" download>manifest.json</a> so the claims can be checked without
          running the system.
        </span>
      </Banner>

      <Panel flush>
        <Tabs
          value={tab}
          onChange={setTab}
          tabs={[
            { id: "sources", label: "Sources" },
            { id: "search", label: "Retrieval" },
            { id: "gaps", label: "Gap register" },
            { id: "y3172", label: "ITU-T Y.3172 mapping" },
            { id: "readiness", label: "AI readiness" },
            { id: "profile", label: "Institutional profile" },
          ]}
        />
        <div className="panel-body">
          {tab === "sources" && <Sources />}
          {tab === "search" && <Search />}
          {tab === "gaps" && <Gaps />}
          {tab === "y3172" && <Mapping name="y3172" />}
          {tab === "readiness" && <Mapping name="readiness" />}
          {tab === "profile" && <Profile />}
        </div>
      </Panel>
    </div>
  );
}

function Sources() {
  const q = useAsync<any>(() => api.sources(), []);
  if (q.loading) return <Skeleton height={180} />;
  if (q.error) return <Banner tone="bad">{q.error}</Banner>;
  const rows: any[] = q.data.sources;

  return (
    <div className="stack">
      <div className="row-wrap">
        <Chip tone="ok">{q.data.manifest.verification.verified} verified excerpts</Chip>
        <Chip tone="neutral">{q.data.count} sources</Chip>
        <span className="tiny muted">{q.data.manifest.engine}</span>
      </div>
      <div className="table-wrap" style={{ maxHeight: 560 }}>
        {/* Fixed column widths: with auto layout the long classification chip took the space it
            wanted and squeezed the document title into a 10-line column beside 400px of empty table. */}
        <table className="table-fixed">
          <colgroup>
            <col style={{ width: 74 }} />
            <col />
            <col style={{ width: 112 }} />
            <col style={{ width: 300 }} />
            <col style={{ width: 78 }} />
          </colgroup>
          <thead>
            <tr>
              <th>Source</th>
              <th>Document</th>
              <th>Jurisdiction</th>
              <th>Class</th>
              <th className="num">Excerpts</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.source_id}>
                <td className="mono">{r.source_id}</td>
                <td>
                  <div className="small">{r.title}</div>
                  <div className="tiny muted">
                    {r.issuing_authority}
                    {r.version_or_issue ? ` · ${r.version_or_issue}` : ""}
                  </div>
                </td>
                <td className="mono tiny">{r.jurisdiction}</td>
                <td>
                  {/* The register stores the class plus its scope in one string ("BINDING_REQUIREMENT
                      (within Abu Dhabi); OUT-OF-JURISDICTION COMPARATOR for a Dubai case"). A chip is
                      for the token; the scope is a sentence and belongs in text, not in a badge. */}
                  <Chip tone={CLAIM_TONE[r.legal_or_guidance_status] ?? "neutral"}>
                    {String(r.legal_or_guidance_status).split(/[\s;(]/)[0]}
                  </Chip>
                  {String(r.legal_or_guidance_status).slice(String(r.legal_or_guidance_status).split(/[\s;(]/)[0].length).replace(/^[\s;(]+/, "").length > 0 && (
                    <div className="tiny muted" style={{ marginTop: 4, lineHeight: 1.45 }}>
                      {String(r.legal_or_guidance_status).slice(String(r.legal_or_guidance_status).split(/[\s;(]/)[0].length).replace(/^[\s;(]+/, "").replace(/\)$/, "")}
                    </div>
                  )}
                  <div className="tiny muted" style={{ marginTop: 3 }}>
                    <CodeLabel kind="verification" code={r.verification_status} />
                  </div>
                </td>
                <td className="num">{r.chunk_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Search() {
  const [q, setQ] = useState("walk-in critical result reported clearly to the patient");
  const [jurisdiction, setJurisdiction] = useState("AE-DU");
  const [scope, setScope] = useState<"all" | "applied" | "comparator">("applied");
  const [submitted, setSubmitted] = useState(0);
  const res = useAsync<any>(
    () =>
      submitted === 0
        ? Promise.resolve(null)
        : api.search(q, {
            jurisdiction: jurisdiction === "ALL" ? undefined : jurisdiction,
            scope: scope === "all" ? "all" : scope === "applied" ? "applicable" : "comparator",
          }),
    [submitted]
  );

  return (
    <div className="stack">
      <div className="grid cols-4" style={{ alignItems: "end" }}>
        <div className="field" style={{ gridColumn: "span 2" }}>
          <label htmlFor="kbq">Query</label>
          <input
            id="kbq"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && setSubmitted((n) => n + 1)}
          />
        </div>
        <div className="field">
          <label htmlFor="juris">Jurisdiction</label>
          <select id="juris" value={jurisdiction} onChange={(e) => setJurisdiction(e.target.value)}>
            <option value="ALL">All</option>
            <option value="AE-DU">AE-DU (Dubai — includes the federal layer)</option>
            <option value="AE-FED">AE-FED (Federal)</option>
            <option value="AE-AZ">AE-AZ (Abu Dhabi)</option>
            <option value="GLOBAL">GLOBAL</option>
          </select>
        </div>
        <div className="row">
          <button className="btn primary" onClick={() => setSubmitted((n) => n + 1)}>
            Search
          </button>
        </div>
      </div>

      <div className="row-wrap">
        <PillGroup
          value={scope}
          onChange={setScope}
          options={[
            { id: "applied" as const, label: "Applicable only" },
            { id: "comparator" as const, label: "Comparators only" },
            { id: "all" as const, label: "Everything" },
          ]}
        />
        <span className="tiny muted">
          “Applicable only” is the filter the policy agents use. Removing it is what the retrieval-only
          configuration does.
        </span>
      </div>

      {res.loading && <Skeleton height={120} />}
      {res.error && <Banner tone="bad">{res.error}</Banner>}
      {res.data && (
        <>
          <div className="row-wrap">
            <Chip tone="neutral">{res.data.chunks.length} results</Chip>
            <Chip tone="info">{res.data.considered} considered</Chip>
            {res.data.excluded_by_filter > 0 && (
              <Chip tone="warn">{res.data.excluded_by_filter} excluded by filter</Chip>
            )}
          </div>
          {(res.data.notes ?? []).map((n: string, i: number) =>
            /hybrid|chroma|ollama/i.test(n) ? (
              <div key={i} className="ev-note">Search is using keyword ranking (BM25); vector ranking needs the local embedding service.</div>
            ) : (
              <div key={i} className="ev-note">{n}</div>
            )
          )}
          {/[؀-ۿ]/.test(q) && <div className="ev-note">Arabic terms are mapped to their English clauses.</div>}
          {res.data.chunks.length === 0 && <Empty>No excerpt in scope matches that query.</Empty>}
          <div className="stack" style={{ gap: 8 }}>
            {res.data.chunks.map((r: any, ri: number) => (
              <div key={r.chunk_id} className="panel" style={{ boxShadow: "none" }} data-video={ri === 0 ? "first-result" : undefined}>
                <div className="panel-head" style={{ padding: "8px 12px" }}>
                  <div className="row" style={{ minWidth: 0 }}>
                    <Chip tone={CLAIM_TONE[r.claim_classification] ?? "neutral"}><CodeLabel kind="claim" code={r.claim_classification} /></Chip>
                    <span className="mono tiny">
                      {r.source_id} · {r.section_id} · printed p.{r.page_start}–{r.page_end} · {r.jurisdiction}
                    </span>
                  </div>
                  <span className="mono tiny muted">score {Number(r.score).toFixed(3)}</span>
                </div>
                <div className="panel-body" style={{ padding: "10px 12px" }}>
                  <div className="quote">{r.text}</div>
                  <div className="row-wrap" style={{ marginTop: 6 }}>
                    <Chip tone={r.excerpt_status === "VERIFIED_AGAINST_SOURCE" ? "ok" : "warn"}>
                      {r.excerpt_status ? <CodeLabel kind="verification" code={r.excerpt_status} /> : "unverified this run"}
                    </Chip>
                    <span className="tiny muted">
                      {r.title} · {r.document_version}
                      {r.pdf_page_start && r.pdf_page_start !== r.page_start
                        ? ` · pdf p.${r.pdf_page_start}`
                        : ""}
                    </span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function Gaps() {
  const q = useAsync<any>(() => api.gaps(), []);
  const [cls, setCls] = useState<string>("ALL");
  if (q.loading) return <Skeleton height={200} />;
  if (q.error) return <Banner tone="bad">{q.error}</Banner>;

  const all: any[] = q.data.gaps;
  const rows = cls === "ALL" ? all : all.filter((g) => g.classification === cls);

  return (
    <div className="stack">
      <div className="row-wrap">
        <PillGroup
          value={cls}
          onChange={setCls}
          options={[{ id: "ALL", label: `All (${all.length})` }, ...q.data.facets.classification.map((c: string) => ({
            id: c, label: c.replace(/_/g, " ").toLowerCase(),
          }))]}
        />
      </div>
      <Banner tone="warn">
        <span>
          A gap register is the honest half of a standards mapping: it records where the sources do not settle
          the question. Nothing in this list is implemented by guessing.
        </span>
      </Banner>
      <div className="table-wrap" style={{ maxHeight: 560 }}>
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Gap</th>
              <th>Class</th>
              <th>Workflow stage</th>
              <th>Jurisdictions</th>
              <th>Verification</th>
              <th>Confidence (author rating)</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((g) => (
              <tr key={g.gap_id}>
                <td className="mono gap-id">{g.gap_id}</td>
                <td style={{ maxWidth: 420 }}>
                  <div className="small">{g.question ?? g.description ?? g.gap_description}</div>
                  {g.consequence && <div className="tiny muted" style={{ marginTop: 3 }}>{g.consequence}</div>}
                  {g.candidate_action && (
                    <div className="tiny" style={{ marginTop: 3, color: "var(--info)" }}>
                      candidate: {g.candidate_action}
                    </div>
                  )}
                </td>
                <td><Chip tone={CLASS_TONE[g.classification] ?? "neutral"}><CodeLabel kind="gapKind" code={g.classification} /></Chip></td>
                <td className="mono tiny">{g.workflow_stage}</td>
                <td className="mono tiny">{g.jurisdictions_compared}</td>
                <td><Chip tone={g.verification_status === "VERIFIED" ? "ok" : "warn"}><CodeLabel kind="verification" code={g.verification_status} /></Chip></td>
                <td className="tiny">{g.confidence}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Mapping({ name }: { name: string }) {
  const q = useAsync<any>(() => api.mappings(name), [name]);
  if (q.loading) return <Skeleton height={200} />;
  if (q.error) return <Banner tone="bad">{q.error}</Banner>;
  const rows: any[] = q.data.rows;
  const keys = Object.keys(rows[0] ?? {});
  return (
    <div className="stack">
      <div className="row-wrap">
        <Chip tone="neutral">{rows.length} requirements</Chip>
        {["IMPLEMENTED", "PARTIAL", "NOT_IMPLEMENTED"].map((s) => {
          const n = rows.filter((r) => (r.status ?? "").toUpperCase() === s).length;
          return n > 0 ? <Chip key={s} tone={statusTone(s)}>{s.toLowerCase()} · {n}</Chip> : null;
        })}
      </div>
      <div className="table-wrap" style={{ maxHeight: 560 }}>
        <table>
          <thead>
            <tr>
              {keys.map((k) => (
                <th key={k}>{k.replace(/_/g, " ")}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                {keys.map((k) => (
                  <td key={k} className={k === "status" ? "" : "small"} style={{ maxWidth: k === "status" ? 120 : 300 }}>
                    {k === "status" ? (
                      <Chip tone={statusTone(r[k])}>{r[k]}</Chip>
                    ) : (
                      <span className={k.includes("id") || k.includes("ref") || k === "requirement_id" ? "mono tiny" : ""}>
                        {r[k]}
                      </span>
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="tiny muted">
        Statuses describe this prototype's implementation against the reference, not conformance certification.
        Rows marked NOT_IMPLEMENTED are non-claims and are kept deliberately.
      </div>
    </div>
  );
}

function Profile() {
  const q = useAsync<any>(() => api.stateMachine(), []);
  if (q.loading) return <Skeleton height={220} />;
  if (q.error) return <Banner tone="bad">{q.error}</Banner>;
  const p = q.data.institutional_profile;

  return (
    <div className="stack">
      <Banner tone="warn">
        <span>
          These values are <strong>product design controls</strong>, not statutory requirements. No retrieved
          source sets a response clock; the numbers below are the institution's own, and the gap register says so.
        </span>
      </Banner>
      <div className="grid cols-2">
        <div className="panel" style={{ boxShadow: "none" }}>
          <div className="panel-head"><h2 style={{ fontSize: 13 }}>Timing and retry</h2></div>
          <div className="panel-body">
            <dl className="kv">
              {Object.entries(p)
                .filter(([k, v]) => typeof v !== "object")
                .map(([k, v]) => (
                  <div key={k} style={{ display: "contents" }}>
                    <dt className="mono tiny">{k}</dt>
                    <dd className="mono tiny">{String(v)}</dd>
                  </div>
                ))}
            </dl>
          </div>
        </div>
        <div className="panel" style={{ boxShadow: "none" }}>
          <div className="panel-head"><h2 style={{ fontSize: 13 }}>Channels</h2></div>
          <div className="panel-body">
            <table>
              <thead>
                <tr>
                  <th>Channel</th>
                  <th>Kind</th>
                  <th>Role</th>
                </tr>
              </thead>
              <tbody>
                {(p.channels ?? []).map((c: any) => (
                  <tr key={c.channel_id}>
                    <td className="mono tiny">{c.channel_id}</td>
                    <td className="small">{c.kind}</td>
                    <td>{c.primary ? <Chip tone="ok">primary</Chip> : <Chip tone="neutral">secondary</Chip>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
      <div className="panel" style={{ boxShadow: "none" }}>
        <div className="panel-head">
          <h2 style={{ fontSize: 13 }}>State machine</h2>
          <span className="hint">{Object.keys(q.data.states).length} states · {q.data.transitions.length} transition rows</span>
        </div>
        <div className="panel-body">
          <div className="grid cols-3">
            {Object.entries(q.data.states).map(([k, v]: any) => (
              <div key={k} className="layer-card">
                <div className="k mono">{k}</div>
                <div className="v muted tiny">{v}</div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
