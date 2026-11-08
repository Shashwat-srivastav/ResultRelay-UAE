import React from "react";
import { Glyph } from "../ui";

/**
 * Trust marks (visual-system §0/§4.3, wireframes §6). The mark shows how much a statement counts;
 * the tag says who said it. Weight rises with authority:
 *   AI suggested (dashed, advisory) < rules suggested (dotted) < checked by code (solid hairline)
 *   < gate decided (3px ink bar, binding) < person decided (filled, named role and time).
 * Green/amber/red are never trust colours: a refused gate is ▣ with a red outcome badge inside it.
 * Each actor has its own verbs: AI suggests/objects/flags, code checks/upholds/rejects,
 * the gate allows/refuses/hands to, a person acknowledges/takes/records.
 */

export type TrustKind = "ai" | "rules" | "code" | "gate" | "person";

const GLYPH: Record<TrustKind, "ai" | "rules" | "check" | "gate" | "person"> = {
  ai: "ai", rules: "rules", code: "check", gate: "gate", person: "person",
};

const DEFAULT_LABEL: Record<TrustKind, string> = {
  ai: "AI suggested · advisory",
  rules: "Rules suggested · heuristic",
  code: "Checked by code",
  gate: "Gate decided",
  person: "Person decided",
};

const ARIA: Record<TrustKind, string> = {
  ai: "AI suggestion", rules: "Rule assessor suggestion", code: "Code check", gate: "Gate decision", person: "Decision by a person",
};

export interface TrustTagProps {
  kind: TrustKind;
  /** Who: "Adversarial reviewer", "Supervisor on duty". For ai it renders "{who} · model, advisory". */
  who?: React.ReactNode;
  /** Replace the default caption entirely. */
  label?: React.ReactNode;
  /** Code check failed: red cross, "Check failed". */
  failed?: boolean;
  /** Model family for AI marks, e.g. "Mistral" → "· Mistral". */
  model?: string;
}

/** Inline provenance tag (§5.16): 12px glyph + caption. Used in trace lanes, audit actor cells, events, toasts. */
export function TrustTag({ kind, who, label, failed, model }: TrustTagProps) {
  const text = label ?? (
    kind === "ai" && who ? <><span className="who">{who}</span> · model, advisory{model ? ` · ${model}` : ""}</>
    : kind === "rules" && who ? <><span className="who">{who}</span> · rules, advisory</>
    : kind === "code" ? (failed ? "Check failed" : "Checked by code")
    : kind === "person" && who ? who
    : kind === "gate" ? "Gate"
    : DEFAULT_LABEL[kind]
  );
  const aria = `${ARIA[kind]}${typeof who === "string" ? ` from the ${who.toLowerCase()}` : ""}${failed ? ", failed" : ""}`;
  return (
    <span className={`trust-tag ${kind}${failed ? " failed" : ""}`} aria-label={aria}>
      <Glyph name={kind === "code" && failed ? "cross" : GLYPH[kind]} size={12} toned={false}
        className={kind === "ai" || kind === "rules" ? "ai-ink" : undefined} />
      <span>{text}</span>
    </span>
  );
}

export interface TrustBlockProps extends TrustTagProps {
  /** Right side of the head row (status, time, outcome badge). */
  meta?: React.ReactNode;
  /** Person register only: no one has acted yet → "Nobody yet" slot (shown, not hidden). */
  emptySlot?: boolean;
  children?: React.ReactNode;
  className?: string;
}

/**
 * A statement in its register's container. ai: dashed violet, 15/24 body, no fill, no quote marks;
 * code: 1px rule at inline-start, 13/18; gate: 3px ink bar, 14/20 500; person: filled, named.
 */
export function TrustBlock({ kind, meta, emptySlot, children, className = "", ...tag }: TrustBlockProps) {
  return (
    <div className={`trust-block ${kind}${tag.failed ? " failed" : ""}${emptySlot ? " empty-slot" : ""} ${className}`.trim()}>
      <div className="tb-head">
        <TrustTag kind={kind} {...tag} label={emptySlot && !tag.label ? "Nobody yet" : tag.label} />
        {meta && <span className="tb-meta">{meta}</span>}
      </div>
      {children && <div className="tb-body">{children}</div>}
    </div>
  );
}

/**
 * Numbers an advisor may show (wireframes §4.3). model: "model confidence 0.93 (its own score)";
 * rules: "support 0.60 (rule heuristic, not a probability)". A 40×4 meter follows for model scores.
 */
export function Confidence({ value, kind = "model", meter = true }: { value: number | null | undefined; kind?: "model" | "rules"; meter?: boolean }) {
  if (value == null || Number.isNaN(value)) return null;
  const v = Math.max(0, Math.min(1, value));
  return (
    <span className="meter">
      {kind === "model" ? "model confidence" : "support"} <span className="p">{v.toFixed(2)}</span>
      {meter && kind === "model" && <span className="bar" aria-hidden><i style={{ width: `${v * 100}%` }} /></span>}
      <span>{kind === "model" ? "(its own score)" : "(rule heuristic, not a probability)"}</span>
    </span>
  );
}

/** Breadcrumb read left to right: ◇ AI reviewer objected → ✓ code kept it → ▣ gate handed to Supervisor → ● Supervisor took it 14:30 */
export function TrustChain({ items }: { items: Array<{ kind: TrustKind; text: React.ReactNode; failed?: boolean }> }) {
  return (
    <span className="trust-chain">
      {items.map((it, i) => (
        <React.Fragment key={i}>
          {i > 0 && <Glyph name="arrow" size={12} className="sep-arrow" />}
          <TrustTag kind={it.kind} label={it.text} failed={it.failed} />
        </React.Fragment>
      ))}
    </span>
  );
}

/** Legend, shown once (trace step rail). Never a modal. */
export function TrustLegend() {
  return (
    <span className="legend" aria-label="How much each statement counts">
      <TrustTag kind="ai" label="AI suggested (advisory)" />
      <TrustTag kind="code" label="Checked by code" />
      <TrustTag kind="gate" label="Gate decided (binding)" />
      <TrustTag kind="person" label="Person decided" />
    </span>
  );
}

export default TrustTag;
