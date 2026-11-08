import React, { useEffect, useLayoutEffect, useRef, useState } from "react";

/**
 * Attention beam (visual-system §6.4; port of Magic UI `border-beam` to SVG + CSS, no gradients).
 * Marks THE one item that needs a person now: an amber dash runs round the border twice (2 × 2400ms,
 * under WCAG 2.2.2's 5s), then settles to a static amber outline + 3px inline-start bar.
 * Re-runs only when `runKey` changes (a new item became the top item). Reduced motion: settled only.
 * Pauses while the tab is hidden. At most one per screen — the page decides which item gets it.
 *
 *   <AttentionBeam active={isTop} runKey={topCaseId} radius={6}>
 *     <section className="panel">…</section>
 *   </AttentionBeam>
 *
 * `as="tr"` is not supported (SVG can't sit in a <tr>); for table rows put the beam on the first
 * cell's content, or use the static `className="attn-host settled"` on the <tr>.
 */
export function AttentionBeam({
  active = true, runKey, radius = 6, children, className = "", as: Tag = "div", style,
}: {
  active?: boolean;
  runKey?: string | number;
  radius?: number;
  children: React.ReactNode;
  className?: string;
  as?: "div" | "section" | "span";
  style?: React.CSSProperties;
}) {
  const host = useRef<HTMLElement | null>(null);
  const [box, setBox] = useState<{ w: number; h: number } | null>(null);
  const [phase, setPhase] = useState<"run" | "settled">("settled");
  const [hidden, setHidden] = useState(false);
  const reduce = usePrefersReducedMotion();

  useLayoutEffect(() => {
    const el = host.current;
    if (!el) return;
    const measure = () => setBox({ w: el.offsetWidth, h: el.offsetHeight });
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  // A new top item: run (unless reduced motion), else settle.
  useEffect(() => {
    if (!active) return;
    setPhase(reduce ? "settled" : "run");
  }, [active, runKey, reduce]);

  useEffect(() => {
    const onVis = () => setHidden(document.visibilityState === "hidden");
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  const cls = [
    "attn-host", className,
    active && phase === "settled" ? "settled" : "",
    hidden ? "paused" : "",
  ].filter(Boolean).join(" ");

  return (
    <Tag ref={host as any} className={cls} style={style}>
      {children}
      {active && phase === "run" && box && (
        <svg className="attn-beam" aria-hidden width={box.w + 2} height={box.h + 2}>
          <rect key={String(runKey)} x="0.75" y="0.75" width={Math.max(0, box.w + 0.5)} height={Math.max(0, box.h + 0.5)}
            rx={radius + 0.75} ry={radius + 0.75} pathLength={100}
            onAnimationEnd={() => setPhase("settled")} />
        </svg>
      )}
    </Tag>
  );
}

export function usePrefersReducedMotion(): boolean {
  const q = "(prefers-reduced-motion: reduce)";
  const [reduce, setReduce] = useState(() => typeof window !== "undefined" && window.matchMedia?.(q).matches);
  useEffect(() => {
    const m = window.matchMedia?.(q);
    if (!m) return;
    const on = () => setReduce(m.matches);
    m.addEventListener?.("change", on);
    return () => m.removeEventListener?.("change", on);
  }, []);
  return !!reduce;
}

export default AttentionBeam;
