import { Suspense, lazy } from "react";
import type { ComponentProps } from "react";

/**
 * three.js is ~600 kB and is needed on two screens. Loading it eagerly made it the largest thing in
 * the initial bundle; the scene now arrives after first paint, in its own chunk, and the fallback is
 * a static rail rather than a spinner so the layout never jumps.
 */
const Pipeline3D = lazy(() => import("./Pipeline3D").then((m) => ({ default: m.Pipeline3D })));

function RailFallback() {
  return (
    <div className="pipeline3d" aria-hidden>
      <span className="cap">loading the step field…</span>
      <div style={{ display: "flex", gap: 10, alignItems: "center", padding: "76px 18px 0" }}>
        {[0, 1, 2, 3, 4, 5].map((i) => (
          <span
            key={i}
            style={{
              width: i === 3 ? 12 : 9,
              height: i === 3 ? 12 : 9,
              borderRadius: 999,
              background: i === 3 ? "#12a08d" : "#33414c",
              opacity: 0.75,
            }}
          />
        ))}
      </div>
    </div>
  );
}

export function Pipeline3DLazy(props: ComponentProps<typeof Pipeline3D>) {
  return (
    <Suspense fallback={<RailFallback />}>
      <Pipeline3D {...props} />
    </Suspense>
  );
}
