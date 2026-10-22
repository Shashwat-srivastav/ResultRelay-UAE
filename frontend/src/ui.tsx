import React, { useCallback, useEffect, useRef, useState } from "react";

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
  tone?: "neutral" | "ok" | "warn" | "bad" | "info" | "outline";
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
  tone?: "info" | "warn" | "bad" | "ok";
  children: React.ReactNode;
}) {
  return <div className={`banner ${tone}`}>{children}</div>;
}

export function Spinner() {
  return <span className="spinner" aria-label="loading" />;
}

export function Empty({ children }: { children: React.ReactNode }) {
  return (
    <div className="muted small" style={{ padding: "18px 4px", textAlign: "center" }}>
      {children}
    </div>
  );
}

export function Skeleton({ height = 16, width = "100%" }: { height?: number; width?: string }) {
  return <div className="skeleton" style={{ height, width, margin: "6px 0" }} />;
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
          {t.count !== undefined && <span className="muted"> · {t.count}</span>}
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

export const CLAIM_TONE: Record<string, "ok" | "info" | "warn" | "bad" | "neutral" | "outline"> = {
  BINDING_REQUIREMENT: "ok",
  OFFICIAL_GUIDANCE: "info",
  INSTITUTIONAL_PROCEDURE: "info",
  GLOBAL_COMPARATOR: "outline",
  PRODUCT_DESIGN_CONTROL: "warn",
  RESEARCH_HYPOTHESIS: "neutral",
  UNRESOLVED: "bad",
};

export const CLASS_TONE: Record<string, "ok" | "info" | "warn" | "bad" | "neutral" | "outline"> = {
  SOURCE_AMBIGUITY: "warn",
  INSUFFICIENT_EVIDENCE: "bad",
  CANDIDATE_POLICY_GAP: "warn",
  SOURCE_CONFLICT: "bad",
  IMPLEMENTATION_GAP: "info",
  INTEROPERABILITY_GAP: "info",
};

export function stateTone(state: string): "ok" | "info" | "warn" | "bad" | "neutral" {
  if (state === "COMMUNICATION_DOCUMENTED" || state === "CORRECTED_RESULT_ACKNOWLEDGED") return "ok";
  if (state === "DELIVERY_STATE_UNKNOWN" || state === "ESCALATION_REQUIRED" || state === "ESCALATION_IN_REVIEW")
    return "bad";
  if (
    ["AWAITING_ACKNOWLEDGMENT", "TRANSMISSION_QUEUED", "TRANSMISSION_ATTEMPTED", "DELIVERY_CONFIRMED",
      "CORRECTION_PENDING", "CORRECTED_RESULT_FINALIZED", "CORRECTED_RESULT_DELIVERY_PENDING", "RETRY_PENDING"].includes(state)
  )
    return "warn";
  return "info";
}

export function statusTone(status: string): "ok" | "warn" | "bad" | "neutral" {
  const s = (status || "").toUpperCase();
  if (["COMPLETE", "PASS", "IMPLEMENTED", "VERIFIED", "ACKNOWLEDGED", "APPLIED", "YES", "TRUE"].includes(s)) return "ok";
  if (["PARTIAL", "PENDING", "DEGRADED", "UNRESOLVED", "REVIEW"].includes(s)) return "warn";
  if (["FAIL", "BLOCKED", "NOT_IMPLEMENTED", "FORBIDDEN", "REJECTED", "ERROR", "NO"].includes(s)) return "bad";
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
