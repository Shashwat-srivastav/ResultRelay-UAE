import React, { useEffect, useState } from "react";
import { loadScenarios } from "../api/client";
import type { ScenarioInfo, ScenarioProvenance } from "../types";
import { scenarioKey } from "../labels";
import { Glyph, Tooltip } from "../ui";

/**
 * Where a scenario comes from (wireframes §5, ux-research §6). Two claims, both always visible:
 * the failure mode is published; the people, numbers and timings are invented.
 *
 * The verb is calibrated to the stored match and never rounded up:
 *   very strong / almost exact → "Reconstructed from"
 *   strong / close             → "Adapted from"
 *   related / related, not exact → "Informed by"
 *   no provenance (S6)         → "Designed test, not from an incident"
 */

export type ProvenanceTier = "reconstructed" | "adapted" | "informed" | "designed";

export function provenanceTier(p?: ScenarioProvenance | null): ProvenanceTier {
  const m = (p?.match ?? "").trim().toLowerCase();
  if (!p || !m) return "designed";
  if (m === "very strong" || m === "almost exact" || m === "exact") return "reconstructed";
  if (m === "strong" || m === "close") return "adapted";
  return "informed";
}

export const TIER_VERB: Record<ProvenanceTier, string> = {
  reconstructed: "Reconstructed from",
  adapted: "Adapted from",
  informed: "Informed by",
  designed: "Designed test, not from an incident",
};

/** What a designed test checks, per scenario without a source. */
const DESIGNED_PURPOSE: Record<string, string> = {
  S6: "it checks that a higher-ranked Abu Dhabi clause can't govern a Dubai case.",
};

export const IDENTITIES = "Names, times and values are invented.";

/** "AHRQ PSNet WebM&M (2017): Delayed …" → "AHRQ PSNet, 2017" (inline density). */
export function shortSource(s: { title: string; url: string }): string {
  const u = s.url || "";
  const year = /\((?:[^)]*?)(\d{4})/.exec(s.title)?.[1] ?? /\b(19|20)\d{2}\b/.exec(s.title)?.[0];
  const y = year ? `, ${year}` : "";
  if (u.includes("psnet.ahrq.gov")) return `AHRQ PSNet${y}`;
  if (u.includes("PMC8442100")) return "BMJ Open Quality, 2021";
  if (u.includes("PMC7065418")) return "AJCP, 2011";
  if (u.includes("rmf.harvard.edu")) return "CRICO, 2023";
  if (u.includes("medicalprotection.org")) return `Medical Protection${/2017/.test(s.title) ? ", 2017" : ""}`;
  if (u.includes("31335384")) return "Genetic-testing case series, 2019";
  if (u.includes("PMC4607287")) return "Return-of-results case studies, 2015";
  const head = s.title.split(":")[0].replace(/\s*\([^)]*\)\s*/g, " ").trim();
  return `${head}${y}`;
}

function Ext({ href, children, className }: { href: string; children: React.ReactNode; className?: string }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={className}>
      {children}
      <span className="ext" aria-hidden>↗</span>
      <span className="sr-only"> (opens in a new tab)</span>
    </a>
  );
}

/** Scenario index from GET /scenarios, cached per page load. Returns {} until loaded. */
export function useScenarioIndex(): Record<string, ScenarioInfo> {
  const [idx, setIdx] = useState<Record<string, ScenarioInfo>>({});
  useEffect(() => {
    let alive = true;
    loadScenarios()
      .then((r) => { if (alive) setIdx(Object.fromEntries(r.scenarios.map((s) => [s.scenario_id, s]))); })
      .catch(() => undefined);
    return () => { alive = false; };
  }, []);
  return idx;
}

export interface ProvenanceProps {
  /** Scenario id (e.g. "S9-reply-from-someone-else"). Used to look up provenance when it isn't passed. */
  scenarioId: string;
  /**
   * The scenario's provenance. Pass it when you already have GET /scenarios; pass `null` for "no source".
   * Leave undefined and the component fetches (cached) and resolves it by scenarioId.
   */
  provenance?: ScenarioProvenance | null;
  /** inline: rows and pickers · strip: case / run / compare header · panel: "About this scenario". */
  size?: "inline" | "strip" | "panel";
  className?: string;
}

export function Provenance({ scenarioId, provenance, size = "inline", className = "" }: ProvenanceProps) {
  const idx = useScenarioIndex();
  const info = idx[scenarioId];
  // "Designed test" only when the API says so (provenance: null). A missing field (older API, unknown
  // scenario, still loading) renders nothing: never claim a scenario has no source when we don't know.
  const known = provenance !== undefined || (info !== undefined && "provenance" in info);
  if (!known) return <span className={`prov ${size} ${className}`} aria-busy={!info} />;
  const p = (provenance !== undefined ? provenance : info!.provenance) ?? null;
  const tier = provenanceTier(p);
  const verb = TIER_VERB[tier];
  const key = scenarioKey(scenarioId);

  if (tier === "designed") {
    const purpose = DESIGNED_PURPOSE[key];
    if (size === "inline") {
      return (
        <span className={`prov inline designed ${className}`}>
          <Glyph name="branch" size={12} className="faint" />
          <span className="verb">{verb}</span>
        </span>
      );
    }
    return (
      <div className={`prov ${size} designed ${className}`}>
        {size === "panel" && <div className="prov-title">{verb}</div>}
        <span>
          {size === "strip" && <><Glyph name="branch" size={12} className="faint" /> <span className="verb">{verb}</span>: </>}
          {purpose ? `Designed by the team with no incident source; ${purpose}` : "Designed by the team with no incident source."}{" "}
          {IDENTITIES}
        </span>
      </div>
    );
  }

  const sources = p!.sources ?? [];
  const first = sources[0];

  if (size === "inline") {
    const tip = (
      <>
        <span className="tip-label">{verb} {first?.title}</span>
        {sources.length > 1 && <span className="tip-sub"> and {sources.length - 1} more</span>}
        <span className="tip-code">match: {p!.match} · Identities invented.</span>
      </>
    );
    return (
      <span className={`prov inline ${className}`}>
        <Glyph name="branch" size={12} className="faint" />
        <span className="src">
          <span className="verb">{verb}</span>{" "}
          {first ? (
            <Tooltip content={tip}>
              <Ext href={first.url}>{shortSource(first)}</Ext>
            </Tooltip>
          ) : null}
        </span>
        {sources.length > 1 && <span className="more">+{sources.length - 1}</span>}
      </span>
    );
  }

  if (size === "strip") {
    const lead = tier === "reconstructed" ? "a published incident: " : tier === "adapted" ? "the failure described in " : "";
    const tail = tier === "informed"
      ? "The specific sequence was designed by the team. Names, times and values are invented."
      : tier === "adapted" ? "Moved to a Dubai walk-in laboratory; names, times and values are invented." : IDENTITIES;
    return (
      <div className={`prov strip ${className}`}>
        <Glyph name="branch" size={12} className="faint" />{" "}
        <span className="verb">{verb}</span> {lead}
        {first && <Ext href={first.url}>{first.title}</Ext>}
        {sources.length > 1 && <> and {sources.length - 1} more source{sources.length > 2 ? "s" : ""}</>}
        {" · "}<span className="prov-match">Match: {p!.match}</span>{" · "}{tail}
      </div>
    );
  }

  // panel
  return (
    <div className={`prov panel ${className}`}>
      <div className="prov-title">{verb} {tier === "reconstructed" ? "a published incident" : tier === "adapted" ? "a published failure" : "published work"}</div>
      <ul>
        {sources.map((s) => (
          <li key={s.url}><Ext href={s.url}>{s.title}</Ext></li>
        ))}
      </ul>
      <div><span className="k">What happened there: </span>{p!.failure_mode}.</div>
      <div><span className="k">Match: </span>{p!.match}</div>
      <div className="muted">
        The source is cited as provenance, not reproduced. {tier === "informed" ? "The specific sequence here was designed by the team. " : ""}
        Setting moved to a Dubai walk-in laboratory. Identities invented: {IDENTITIES.toLowerCase()}
      </div>
    </div>
  );
}

export default Provenance;
