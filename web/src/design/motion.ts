import { useRef } from "react";

/**
 * Pages render at once. The console used to fade and blur every panel in on mount; on a screen people
 * read to decide whether a result reached a person, that only delayed the answer. The hook is kept so
 * callers do not change.
 */
export function useReveal<T extends HTMLElement>(_deps: unknown[] = [], _stagger = 0) {
  return useRef<T | null>(null);
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
