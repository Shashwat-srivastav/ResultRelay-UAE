import { useEffect, useRef, useState } from "react";
import gsap from "gsap";

/** One curve, three durations — see docs/design/03-moodboard.html §04. */
export const EASE = "power2.out";
export const DUR = { fast: 0.12, base: 0.2, slow: 0.32 } as const;

export function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * Reveal a subtree on mount or when `deps` change.
 *
 * Uses gsap.matchMedia so the reduced-motion branch is not a second code path that can drift: both
 * branches animate opacity only at different durations, and `mm.revert()` restores inline styles when
 * the preference changes mid-session.
 */
export function useReveal<T extends HTMLElement>(deps: unknown[] = [], stagger = 0.04) {
  const ref = useRef<T | null>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const mm = gsap.matchMedia();
    const targets = () => {
      const found = el.querySelectorAll<HTMLElement>("[data-reveal]");
      return found.length ? Array.from(found) : [el];
    };
    mm.add("(prefers-reduced-motion: no-preference)", () => {
      gsap.fromTo(
        targets(),
        { opacity: 0, y: 10, filter: "blur(4px)" },
        { opacity: 1, y: 0, filter: "none", duration: DUR.slow, stagger, ease: EASE, clearProps: "filter,transform" }
      );
    });
    mm.add("(prefers-reduced-motion: reduce)", () => {
      gsap.fromTo(targets(), { opacity: 0 }, { opacity: 1, duration: 0.09, stagger: 0 });
    });
    return () => mm.revert();
  }, deps);
  return ref;
}

/** Count up once, on first paint in view. Never used for values that imply live data. */
export function useCountUp(target: number | null | undefined, duration = 0.6) {
  const [value, setValue] = useState(target ?? 0);
  const ref = useRef<HTMLSpanElement | null>(null);
  useEffect(() => {
    if (target === null || target === undefined) return;
    if (prefersReducedMotion()) {
      setValue(target);
      return;
    }
    const node = ref.current;
    const obj = { n: 0 };
    const tween = gsap.to(obj, {
      n: target,
      duration,
      ease: "power1.out",
      onUpdate: () => setValue(Math.round(obj.n)),
      scrollTrigger: undefined,
      paused: false,
      onComplete: () => {
        setValue(target);
        if (node) node.dataset.done = "1";
      },
    });
    return () => {
      tween.kill();
    };
  }, [target, duration]);
  return { value, ref };
}

/** Keyboard activation for elements that behave like links but are not anchors. */
export function onActivate(handler: () => void) {
  return (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      handler();
    }
  };
}
