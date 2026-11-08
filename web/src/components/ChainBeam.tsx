import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { CHAIN_STAGES, chainExit, chainIndex, lookup, type Tone } from "../labels";
import { Glyph } from "../ui";
import { usePrefersReducedMotion } from "./AttentionBeam";

/**
 * Compact single-case chain (visual-system §5.3, 64px) with the chain beam (§6.2; port of Magic UI
 * `animated-beam`: orthogonal path, 8px elbow, a 6px head dot on CSS offset-path instead of a gradient
 * sweep, runs ONCE per change and never on mount).
 *
 *   <ChainBeam states={run.steps.map(s => s.resulting_state)} role={owner?.role} />
 *
 * `states` is the case's state history, oldest first; the last entry is the current state. When the
 * case leaves the chain (escalated, delivery unknown, correction) a branch drops from the furthest
 * stage reached to a pill on the right ("◆ With the supervisor on duty"). When the current state
 * changes, a dot travels from the previous position to the new one (or down the branch to the person).
 * Reduced motion: no dot; the destination gets a brief outline (colour only).
 */
export interface ChainBeamProps {
  states: string[];
  /** Role of the current owner (SUPERVISOR / CLINICAL_LEAD) for the exit pill. */
  role?: string | null;
  className?: string;
}

const SOLID: Record<string, string> = {
  ok: "var(--ok-solid)", att: "var(--att-solid)", crit: "var(--crit-solid)", progress: "var(--ink-2)", neutral: "var(--ink-2)",
};

export function ChainBeam({ states, role, className = "" }: ChainBeamProps) {
  const host = useRef<HTMLDivElement | null>(null);
  const pill = useRef<HTMLSpanElement | null>(null);
  const [w, setW] = useState(0);
  const [pillX, setPillX] = useState(0);
  const reduce = usePrefersReducedMotion();

  const current = states[states.length - 1] ?? "RESULT_DRAFT";
  const reached = Math.max(0, ...states.map(chainIndex));
  const exit = chainExit(current);
  const curIdx = exit ? reached : Math.max(0, chainIndex(current) >= 0 ? chainIndex(current) : reached);
  const cur = lookup("state", current, { role: role ?? undefined });
  const curTone: Tone = exit ? exit.tone : (cur.tone ?? "progress");
  const pos = exit ? `exit:${exit.id}` : `n:${curIdx}`;

  useLayoutEffect(() => {
    const el = host.current;
    if (!el) return;
    const measure = () => {
      setW(el.clientWidth);
      setPillX(pill.current ? pill.current.offsetLeft : el.clientWidth);
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    if (pill.current) ro.observe(pill.current);
    return () => ro.disconnect();
  }, [exit?.id, cur.label]);

  const chainW = exit ? Math.max(0, w - Math.min(280, w * 0.4)) : w;
  const col = chainW / CHAIN_STAGES.length;
  const x = (i: number) => col * (i + 0.5);
  const Y = 12;
  const branchD = (from: number) => `M ${x(from)} ${Y + 5} V ${44} a 8 8 0 0 0 8 8 H ${Math.max(x(from) + 8, pillX)}`;

  // Beam: on change of position only (never on mount).
  const prev = useRef<{ pos: string; idx: number } | null>(null);
  const [beam, setBeam] = useState<{ d: string; t: number; c: string; k: number } | null>(null);
  const [arrive, setArrive] = useState(0);
  useEffect(() => {
    const p = prev.current;
    prev.current = { pos, idx: curIdx };
    if (!p || p.pos === pos || !w) return;
    const color = SOLID[curTone] ?? SOLID.progress;
    if (reduce) { setArrive((k) => k + 1); return; }
    let d: string; let hops: number;
    if (exit) {
      const start = Math.min(p.idx, curIdx);
      d = (start < curIdx ? `M ${x(start)} ${Y} H ${x(curIdx)} ` : `M ${x(curIdx)} ${Y} `)
        + `V ${44} a 8 8 0 0 0 8 8 H ${Math.max(x(curIdx) + 8, pillX)}`;
      hops = Math.abs(curIdx - start) + 1;
    } else {
      d = `M ${x(p.idx)} ${Y} H ${x(curIdx)}`;
      hops = Math.max(1, Math.abs(curIdx - p.idx));
    }
    const t = Math.min(1080, Math.max(360, 360 * hops));
    setBeam((b) => ({ d, t, c: color, k: (b?.k ?? 0) + 1 }));
    setArrive((k) => k + 1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pos]);

  const summary = `Furthest stage reached: ${CHAIN_STAGES[reached].label}. Now: ${cur.label}.`;

  return (
    <div ref={host} className={`cchain ${className}`.trim()} role="img" aria-label={summary}>
      {w > 0 && (
        <svg className="cchain-lines" aria-hidden>
          {CHAIN_STAGES.slice(0, -1).map((_, i) => (
            <line key={i} className={`seg${i < curIdx ? " passed" : ""}`} x1={x(i)} y1={Y} x2={x(i + 1)} y2={Y} />
          ))}
          {exit && <path className={`branch ${exit.tone}`} d={branchD(curIdx)} />}
          {beam && <path key={beam.k} className="beam-trail" d={beam.d} pathLength={1000}
            style={{ ["--beam-c" as any]: beam.c, ["--beam-t" as any]: `${beam.t}ms` }} />}
        </svg>
      )}
      {w > 0 && CHAIN_STAGES.map((s, i) => {
        const state = i < curIdx ? "passed" : i === curIdx ? "current" : "";
        const tone = i === curIdx ? (exit ? exit.tone : curTone) : "";
        const isLast = i === CHAIN_STAGES.length - 1;
        return (
          <React.Fragment key={s.id}>
            <span key={i === curIdx ? `n${arrive}` : undefined}
              className={`cnode ${state} ${tone}${i === curIdx && arrive && !exit ? " arrive" : ""}`}
              style={{ left: x(i), ["--beam-c" as any]: SOLID[tone] }} />
            <span className={`cname ${state}`} style={{ left: x(i), maxWidth: Math.max(40, col - 6) }}
              title={s.label}>{isLast && chainW < 420 ? "Documented" : s.label}</span>
          </React.Fragment>
        );
      })}
      {exit && (
        <span ref={pill} key={`p${arrive}`} className={`exit-pill ${exit.tone}${arrive ? " arrive" : ""}`}
          style={{ ["--beam-c" as any]: SOLID[exit.tone] }}>
          <Glyph name={exit.tone} size={8} />
          <span className="truncate">{cur.label}</span>
        </span>
      )}
      {beam && (
        <span key={beam.k} className="beam-head" aria-hidden
          style={{ offsetPath: `path("${beam.d}")`, ["--beam-c" as any]: beam.c, ["--beam-t" as any]: `${beam.t}ms` } as React.CSSProperties}
          onAnimationEnd={() => setBeam(null)} />
      )}
    </div>
  );
}

export default ChainBeam;
