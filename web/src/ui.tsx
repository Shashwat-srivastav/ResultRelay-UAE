import React, { useCallback, useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { KINDS, lookup, humanise, explain, roleLabel, type LabelKind, type LabelVars, type Tone } from "./labels";

export { humanise, explain, roleLabel };
export type { Tone, LabelKind };

/** Every tone a Chip/Badge/Banner accepts: v4 tones plus the v3 names pages still pass (warn = att, bad = crit). */
export type AnyTone = Tone | "warn" | "bad" | "outline";

/* ------------------------------------------------------------------ */
/* primitives                                                          */
/* ------------------------------------------------------------------ */

/**
 * Does this chip's text read as an identifier rather than a phrase?
 *
 * Identifiers (states, events, clause numbers, digests) belong in the mono face so their characters
 * line up and 0/O is unambiguous; phrases ("needs a human") belong in the sans face, because mono at
 * 11px slows word recognition. This is a heuristic with a narrow job, not a parser.
 */
export function looksLikeIdentifier(node: React.ReactNode): boolean {
  if (typeof node !== "string") return false;
  const s = node.trim();
  if (!s || s.length > 64) return false;
  if (/^[A-Z0-9_.[\]|/§:+-]+(?: [A-Z0-9_.[\]|/§:+-]+)*$/.test(s)) return true; // ALL_CAPS / codes
  if (/^[a-z0-9-]+(?:\.[a-z0-9-]+)+$/.test(s)) return true; // dotted.paths, never prose
  if (/^[A-Z]{2,}-[A-Za-z0-9-]+$/.test(s)) return true; // RUN-abc123, SYN-CASE-007
  if (/^#[\w-]+/.test(s)) return true; // #19
  return false;
}

export function Chip({
  children,
  tone = "neutral",
  mono,
  title,
}: {
  children: React.ReactNode;
  tone?: AnyTone;
  mono?: boolean;
  title?: string;
}) {
  const useMono = mono ?? looksLikeIdentifier(children);
  return (
    <span className={`chip ${tone}${useMono ? " mono" : ""}`} title={title}>
      {children}
    </span>
  );
}

export function Panel({
  title,
  hint,
  action,
  children,
  flush,
}: {
  title?: React.ReactNode;
  hint?: React.ReactNode;
  action?: React.ReactNode;
  children: React.ReactNode;
  flush?: boolean;
}) {
  return (
    <section className="panel">
      {(title || action) && (
        <div className="panel-head">
          <div className="row" style={{ minWidth: 0 }}>
            <h2>{title}</h2>
            {hint && <span className="hint">{hint}</span>}
          </div>
          {action}
        </div>
      )}
      <div className={`panel-body${flush ? " flush" : ""}`}>{children}</div>
    </section>
  );
}

export function Metric({
  label,
  value,
  sub,
  onClick,
  selected,
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  onClick?: () => void;
  selected?: boolean;
}) {
  return (
    <div
      className={`panel metric${onClick ? " clickable" : ""}${selected ? " selected" : ""}`}
      onClick={onClick}
      role={onClick ? "button" : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={(e) => {
        if (onClick && (e.key === "Enter" || e.key === " ")) onClick();
      }}
    >
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  );
}

export function Banner({
  tone = "info",
  children,
}: {
  tone?: AnyTone | "scope";
  children: React.ReactNode;
}) {
  const t = tone === "warn" ? "att" : tone === "bad" ? "crit" : tone;
  return (
    <div className={`banner ${t}`} role={t === "crit" ? "alert" : undefined}>
      {children}
    </div>
  );
}

/** §5.17 error state: crit banner, a plain title, the server message in mono, and a retry. */
export function ErrorNotice({ title, error, onRetry, unchanged }: {
  title: string; error: string; onRetry?: () => void; unchanged?: boolean;
}) {
  return (
    <Banner tone="crit">
      <Glyph name="crit" size={12} />
      <div className="stack-4">
        <div className="title">{title}</div>
        <div>The server said: <span className="mono">{error.slice(0, 240)}</span></div>
        {unchanged && <div>Nothing was changed or recorded.</div>}
        {onRetry && <div><button className="btn small" onClick={onRetry}>Try again</button></div>}
      </div>
    </Banner>
  );
}

export function Spinner() {
  return <span className="spinner" aria-label="loading" />;
}

/**
 * Empty state. Legacy: <Empty>text</Empty> renders a compact centred line. v4 (§5.17):
 * <Empty title="No cases yet" body="Each simulator run creates one case." action={<button className="btn small">…</button>} />
 */
export function Empty({ children, title, body, action, icon }: {
  children?: React.ReactNode; title?: React.ReactNode; body?: React.ReactNode; action?: React.ReactNode; icon?: React.ReactNode;
}) {
  if (!title) return <div className="empty compact small">{children}</div>;
  return (
    <div className="empty">
      {icon ?? <Glyph name="dot" size={20} />}
      <div className="empty-title">{title}</div>
      {(body || children) && <div className="empty-body">{body ?? children}</div>}
      {action}
    </div>
  );
}

export function Skeleton({ height = 16, width = "100%" }: { height?: number; width?: string }) {
  return <div className="skeleton skel-delay" aria-hidden style={{ height, width, margin: "6px 0" }} />;
}

export function Tabs<T extends string>({
  tabs,
  value,
  onChange,
}: {
  tabs: Array<{ id: T; label: string; count?: number }>;
  value: T;
  onChange: (id: T) => void;
}) {
  return (
    <div className="tabs" role="tablist">
      {tabs.map((t) => (
        <button
          key={t.id}
          role="tab"
          aria-selected={value === t.id}
          className={`tab${value === t.id ? " active" : ""}`}
          onClick={() => onChange(t.id)}
        >
          {t.label}
          {t.count !== undefined && <span className="tab-count">{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function PillGroup<T extends string>({
  options,
  value,
  onChange,
}: {
  options: Array<{ id: T; label: string }>;
  value: T;
  onChange: (id: T) => void;
}) {
  return (
    <div className="pill-group">
      {options.map((o) => (
        <button
          key={o.id}
          className={`pill${value === o.id ? " active" : ""}`}
          onClick={() => onChange(o.id)}
          aria-pressed={value === o.id}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* hooks                                                               */
/* ------------------------------------------------------------------ */

export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const alive = useRef(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    fnRef
      .current()
      .then((d) => {
        if (alive.current) setData(d);
      })
      .catch((e) => {
        if (alive.current) setError(String(e.message ?? e));
      })
      .finally(() => {
        if (alive.current) setLoading(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    alive.current = true;
    reload();
    return () => {
      alive.current = false;
    };
  }, [reload]);

  return { data, error, loading, reload, setData };
}

/* ------------------------------------------------------------------ */
/* domain helpers                                                      */
/* ------------------------------------------------------------------ */

/** Claim class → tone (v4: binding is a neutral classification; only comparators get a tone). */
export const CLAIM_TONE: Record<string, AnyTone> = {
  BINDING_REQUIREMENT: "neutral",
  OFFICIAL_GUIDANCE: "neutral",
  INSTITUTIONAL_PROCEDURE: "neutral",
  GLOBAL_COMPARATOR: "info",
  PRODUCT_DESIGN_CONTROL: "neutral",
  RESEARCH_HYPOTHESIS: "neutral",
  UNRESOLVED: "att",
};

export const CLASS_TONE: Record<string, AnyTone> = {
  SOURCE_AMBIGUITY: "att",
  INSUFFICIENT_EVIDENCE: "att",
  CANDIDATE_POLICY_GAP: "att",
  SOURCE_CONFLICT: "crit",
  IMPLEMENTATION_GAP: "neutral",
  INTEROPERABILITY_GAP: "neutral",
};

/**
 * Case state → tone. v4 semantics: Documented = ok; escalated / correction = att ("needs a person",
 * the designed safe exit, never red); delivery unknown or failed = crit; everything on the chain = progress.
 */
export function stateTone(state: string): Tone {
  return (lookup("state", state).tone as Tone) ?? "progress";
}

/** Transition / check / run status → tone. "Applied", "pass", "verified" are code facts: neutral, not green. */
export function statusTone(status: string): Tone {
  const s = (status || "").toUpperCase();
  if (["IMPLEMENTED", "ACKNOWLEDGED", "DOCUMENTED"].includes(s)) return "ok";
  if (["COMPLETE", "PASS", "VERIFIED", "APPLIED", "YES", "TRUE", "OK", "ANSWERED", "UPHELD", "RECORDED"].includes(s)) return "neutral";
  if (["PARTIAL", "PENDING", "DEGRADED", "UNRESOLVED", "REVIEW", "REQUIRES_HUMAN", "OPEN", "IN_REVIEW"].includes(s)) return "att";
  if (["FAIL", "BLOCKED", "NOT_IMPLEMENTED", "FORBIDDEN", "REJECTED", "ERROR", "NO", "DISPUTED", "DOWN"].includes(s)) return "crit";
  return "neutral";
}

export function fmtTime(iso?: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleTimeString("en-GB", { hour12: false });
}

export function shortHash(h?: string): string {
  if (!h) return "—";
  return h.slice(0, 10);
}

export function pct(n: number, d: number): string {
  if (!d) return "—";
  return `${Math.round((n / d) * 100)}%`;
}

/* ------------------------------------------------------------------ */
/* v4: glyphs (inline SVG, currentColor; visual-system §5.8)           */
/* ------------------------------------------------------------------ */

export type GlyphName =
  | Tone | "check" | "cross" | "gate" | "person" | "rules" | "arrow" | "arrow-ext" | "branch"
  | "dot" | "chevron" | "chevron-down" | "minus";

const TONE_GLYPH = new Set(["ok", "progress", "att", "crit", "info", "ai"]);

/**
 * <Glyph name="att" /> — the shape carries the meaning so state never rests on colour alone.
 * Tone glyphs (ok ● progress ◐ att ◆ crit ▲ info ○ ai ◇ dashed) get their tone colour; the rest use
 * currentColor. Decorative by default (aria-hidden); pass `label` to expose it.
 */
export function Glyph({ name, size, label, className = "", toned = true }: {
  name: GlyphName; size?: number; label?: string; className?: string; toned?: boolean;
}) {
  const sz = size ?? (TONE_GLYPH.has(name) ? 8 : 12);
  const stroke = { fill: "none", stroke: "currentColor", strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  let body: React.ReactNode = null;
  switch (name) {
    case "ok": body = <circle cx="6" cy="6" r="5.5" fill="currentColor" />; break;
    case "progress": body = (<>
      <circle cx="6" cy="6" r="4.75" {...stroke} strokeWidth="1.5" />
      <path d="M6 1.25a4.75 4.75 0 0 0 0 9.5z" fill="currentColor" /></>); break;
    case "att": body = <path d="M6 .4 11.6 6 6 11.6 .4 6z" fill="currentColor" />; break;
    case "crit": body = <path d="M6 .8 11.6 11H.4z" fill="currentColor" />; break;
    case "info": body = <circle cx="6" cy="6" r="4.75" {...stroke} strokeWidth="1.5" />; break;
    case "ai": body = <path d="M6 1.1 10.9 6 6 10.9 1.1 6z" {...stroke} strokeWidth="1.4" strokeDasharray="2.2 1.5" />; break;
    case "rules": body = <path d="M6 1.1 10.9 6 6 10.9 1.1 6z" {...stroke} strokeWidth="1.4" strokeDasharray="0.1 2.2" />; break;
    case "neutral": body = <circle cx="6" cy="6" r="2.5" fill="currentColor" />; break;
    case "check": body = (<>
      <circle cx="6" cy="6" r="5" {...stroke} strokeWidth="1.25" opacity=".7" />
      <path d="M3.6 6.2 5.3 7.8 8.5 4.4" {...stroke} strokeWidth="1.5" /></>); break;
    case "cross": body = (<>
      <circle cx="6" cy="6" r="5" {...stroke} strokeWidth="1.25" />
      <path d="M4.2 4.2 7.8 7.8M7.8 4.2 4.2 7.8" {...stroke} strokeWidth="1.5" /></>); break;
    case "gate": body = (<>
      <rect x="1" y="1" width="10" height="10" rx="2" fill="currentColor" />
      <rect x="3" y="5" width="6" height="2" fill="#fff" /></>); break;
    case "person": body = (<>
      <circle cx="6" cy="6" r="5" fill="currentColor" />
      <circle cx="6" cy="4.6" r="1.6" fill="#fff" /><path d="M3.4 9.2a2.8 2.6 0 0 1 5.2 0" fill="#fff" /></>); break;
    case "arrow": body = <path d="M1.5 6h8.5M7 3l3 3-3 3" {...stroke} strokeWidth="1.5" />; break;
    case "arrow-ext": body = <path d="M3.5 8.5 8.5 3.5M4.5 3.5h4v4" {...stroke} strokeWidth="1.4" />; break;
    case "branch": body = <path d="M3 1.5v4.5a2 2 0 0 0 2 2h5M7.5 5.5 10 8l-2.5 2.5" {...stroke} strokeWidth="1.4" />; break;
    case "dot": body = <circle cx="6" cy="6" r="2.5" fill="currentColor" />; break;
    case "chevron": body = <path d="M4.5 2.5 8 6l-3.5 3.5" {...stroke} strokeWidth="1.5" />; break;
    case "chevron-down": body = <path d="M2.5 4.5 6 8l3.5-3.5" {...stroke} strokeWidth="1.5" />; break;
    case "minus": body = <path d="M3 6h6" {...stroke} strokeWidth="1.5" />; break;
  }
  const toneClass = toned && TONE_GLYPH.has(name) ? ` ${name}` : "";
  return (
    <svg className={`glyph${toneClass} ${className}`.trim()} width={sz} height={sz} viewBox="0 0 12 12"
      aria-hidden={label ? undefined : true} role={label ? "img" : undefined} aria-label={label} focusable="false">
      {body}
    </svg>
  );
}

/* ------------------------------------------------------------------ */
/* v4: tooltip (§5.19) — ink surface, 400ms hover, instant on focus     */
/* ------------------------------------------------------------------ */

export function Tooltip({ content, children, focusable, className = "" }: {
  content: React.ReactNode; children: React.ReactNode; focusable?: boolean; className?: string;
}) {
  const id = useId();
  const host = useRef<HTMLSpanElement | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const [pos, setPos] = useState<{ x: number; y: number; above: boolean } | null>(null);
  const show = useCallback((delay: number) => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      const r = host.current?.getBoundingClientRect();
      if (!r) return;
      const above = r.bottom + 6 + 64 > window.innerHeight;
      setPos({ x: Math.min(Math.max(8, r.left), window.innerWidth - 288), y: above ? r.top - 6 : r.bottom + 6, above });
    }, delay);
  }, []);
  const hide = useCallback(() => { window.clearTimeout(timer.current); setPos(null); }, []);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  if (content == null || content === "") return <>{children}</>;
  return (
    <span ref={host} className={`tip-host ${className}`.trim()} aria-describedby={pos ? id : undefined}
      tabIndex={focusable ? 0 : undefined}
      onMouseEnter={() => show(400)} onMouseLeave={hide} onFocus={() => show(0)} onBlur={hide}
      onKeyDown={(e) => { if (e.key === "Escape") hide(); }}>
      {children}
      {pos && createPortal(
        <div id={id} role="tooltip" className="tooltip"
          style={{ left: pos.x, top: pos.y, transform: pos.above ? "translateY(-100%)" : undefined }}>
          {content}
        </div>, document.body)}
    </span>
  );
}

/** Standard tooltip body: label — explanation, then the raw code in mono (§5.5). */
export function CodeTip({ label, explain: why, code }: { label?: React.ReactNode; explain?: React.ReactNode; code?: React.ReactNode }) {
  return (
    <>
      {label && <span className="tip-label">{label}</span>}
      {label && why ? <span className="tip-sub"> — </span> : null}
      {why && <span>{why}</span>}
      {code != null && code !== "" && <span className="tip-code">{code}</span>}
    </>
  );
}

/* ------------------------------------------------------------------ */
/* v4: badges and humanised codes                                      */
/* ------------------------------------------------------------------ */

/** Status badge (§5.5): 20px (lg 24px), tone glyph + sentence-case label. Never interactive. */
export function Badge({ tone = "neutral", size = "md", glyph, children, weight }: {
  tone?: AnyTone; size?: "md" | "lg"; glyph?: boolean; children: React.ReactNode; weight?: boolean;
}) {
  const t: string = tone === "warn" ? "att" : tone === "bad" ? "crit" : tone;
  const showGlyph = (glyph ?? true) && TONE_GLYPH.has(t);
  return (
    <span className={`badge ${t}${size === "lg" ? " lg" : ""}${weight ? " weight" : ""}`}>
      {showGlyph && <Glyph name={t as Tone} size={size === "lg" ? 10 : 8} />}
      <span className="label-text">{children}</span>
    </span>
  );
}

/**
 * Humanised case-state badge. <StateBadge code="ESCALATION_REQUIRED" role="SUPERVISOR" />
 * → ◆ "With the supervisor on duty" (att). Raw code + explanation in the tooltip; `showCode` also prints
 * the code after the badge (detail views: Trace, Audit, Case timeline).
 */
export function StateBadge({ code, role, size = "md", showCode, tip = true, focusable }: {
  code: string; role?: string | null; size?: "md" | "lg"; showCode?: boolean; tip?: boolean; focusable?: boolean;
}) {
  const l = lookup("state", code, { role: role ?? undefined });
  const badge = <Badge tone={l.tone ?? "progress"} size={size}>{l.label}</Badge>;
  return (
    <span className="state-badge">
      {tip ? <Tooltip focusable={focusable} content={<CodeTip label={l.label} explain={l.explain} code={code} />}>{badge}</Tooltip> : badge}
      {showCode && <span className="code-after">{code}</span>}
    </span>
  );
}

/**
 * Any code, humanised as plain text (or a badge with `badge`). <CodeLabel kind="event" code="transport.accepted" />
 * Kinds: see labels.ts KINDS.
 */
export function CodeLabel({ kind, code, vars, showCode, badge, tone, tip = true }: {
  kind: LabelKind; code: string | boolean | null | undefined; vars?: LabelVars;
  showCode?: boolean; badge?: boolean; tone?: AnyTone; tip?: boolean;
}) {
  const l = lookup(kind, code, vars);
  const raw = String(code ?? "");
  const tipBody = <CodeTip label={l.label} explain={l.explain} code={raw} />;
  const inner = badge
    ? <Badge tone={tone ?? l.tone ?? "neutral"}>{l.label}</Badge>
    : <span className={`code-label${tip && l.explain ? "" : " plain"}`}>{l.label}</span>;
  return (
    <>
      {tip ? <Tooltip content={tipBody}>{inner}</Tooltip> : inner}
      {showCode && raw && <span className="code-after">{raw}</span>}
    </>
  );
}

/** "[Acknowledged] → [With the supervisor on duty]" (trace lane 6, case timeline). */
export function TransitionLabel({ from, to, role, showCode }: { from: string; to: string; role?: string | null; showCode?: boolean }) {
  return (
    <span className="transition">
      <StateBadge code={from} showCode={showCode} />
      <Glyph name="arrow" size={12} className="arrow" />
      <StateBadge code={to} role={role} showCode={showCode} />
    </span>
  );
}

/** Is this code known to the label layer? */
export function isKnownCode(kind: LabelKind, code: string): boolean {
  return Object.prototype.hasOwnProperty.call(KINDS[kind], code);
}

/* ------------------------------------------------------------------ */
/* v4: toast (§5.18) — presentational; pages own the queue              */
/* ------------------------------------------------------------------ */

export function ToastStack({ children }: { children: React.ReactNode }) {
  return <div className="toast-stack">{children}</div>;
}

export function Toast({ tone = "progress", title, sub, action, onClose, glyph }: {
  tone?: Tone; title: React.ReactNode; sub?: React.ReactNode; action?: React.ReactNode; onClose?: () => void; glyph?: React.ReactNode;
}) {
  // att and crit need a person: no auto-dismiss (the page removes them).
  useEffect(() => {
    if (!onClose || tone === "att" || tone === "crit") return;
    const t = window.setTimeout(onClose, 6000);
    return () => window.clearTimeout(t);
  }, [onClose, tone]);
  return (
    <div className={`toast ${tone}`} role={tone === "crit" ? "alert" : "status"}>
      {glyph}
      <div className="grow">
        <div>{title}</div>
        {sub && <div className="toast-sub">{sub}</div>}
        {action && <div className="mt-4">{action}</div>}
      </div>
      {onClose && <button className="toast-close" aria-label="Dismiss" onClick={onClose}>×</button>}
    </div>
  );
}
