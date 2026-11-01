import { useEffect, useRef } from "react";
import * as THREE from "three";
import { prefersReducedMotion } from "./motion";

/**
 * The pipeline, drawn once in 3-D because position encodes sequence and depth encodes precedence.
 *
 * Steps sit on a receding rail. The gate is a membrane: a step that was refused is drawn short of it
 * and tinted. Clicking a node reports its index so the page can move to that step's artefacts — the
 * scene is navigation, not ornament. Everything is disposed on unmount, and the whole render loop is
 * skipped under prefers-reduced-motion (one still frame is drawn instead).
 */
export type PipelineStep = { label: string; permitted: boolean; active: boolean };

export function Pipeline3D({
  steps,
  onSelect,
  caption = "event → evidence → proposal → gate → transition → state",
}: {
  steps: PipelineStep[];
  onSelect?: (index: number) => void;
  caption?: string;
}) {
  const host = useRef<HTMLDivElement | null>(null);
  const selectRef = useRef(onSelect);
  selectRef.current = onSelect;

  useEffect(() => {
    const mount = host.current;
    if (!mount) return;

    const width = mount.clientWidth || 720;
    const height = 190;
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, width / height, 0.1, 100);
    camera.position.set(0, 1.95, 8.2);
    camera.lookAt(0, 0, -0.6);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
    renderer.setSize(width, height);
    renderer.setClearColor(0x000000, 0);
    mount.appendChild(renderer.domElement);

    scene.add(new THREE.AmbientLight(0xffffff, 0.55));
    const key = new THREE.PointLight(0x8ef0dc, 1.5, 24);
    key.position.set(2.4, 4.2, 5);
    scene.add(key);

    const count = Math.max(1, steps.length);
    const span = 6.4;
    const gateIndex = steps.findIndex((s) => s.label.toLowerCase().includes("gate"));

    const group = new THREE.Group();
    scene.add(group);

    const nodes: THREE.Mesh[] = [];
    const positions: THREE.Vector3[] = [];

    for (let i = 0; i < count; i += 1) {
      const t = count === 1 ? 0.5 : i / (count - 1);
      const x = -span / 2 + span * t;
      const z = -2.0 * t;
      const pos = new THREE.Vector3(x, 0, z);
      positions.push(pos);

      const denied = steps[i]?.permitted === false;
      const geo = new THREE.SphereGeometry(steps[i]?.active ? 0.24 : 0.17, 26, 20);
      const mat = new THREE.MeshStandardMaterial({
        color: denied ? 0xa3242b : steps[i]?.active ? 0x12a08d : 0xc8d3dc,
        emissive: denied ? 0x4a0f12 : steps[i]?.active ? 0x0b6b5f : 0x1b232a,
        emissiveIntensity: steps[i]?.active ? 0.9 : 0.35,
        roughness: 0.45,
        metalness: 0.1,
      });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.position.copy(pos);
      mesh.userData.index = i;
      group.add(mesh);
      nodes.push(mesh);
    }

    // The rail through the nodes.
    const railGeo = new THREE.BufferGeometry().setFromPoints(positions);
    const railMat = new THREE.LineBasicMaterial({ color: 0x2c3a45, transparent: true, opacity: 0.9 });
    group.add(new THREE.Line(railGeo, railMat));

    // The gate membrane sits between the last proposal and the transition.
    if (gateIndex > 0) {
      const gp = positions[Math.min(gateIndex, count - 1)];
      const plane = new THREE.Mesh(
        new THREE.PlaneGeometry(3.1, 2.0),
        new THREE.MeshBasicMaterial({ color: 0x12a08d, transparent: true, opacity: 0.13, side: THREE.DoubleSide })
      );
      plane.position.set(gp.x - 0.42, 0, gp.z);
      plane.rotation.y = Math.PI / 2.6;
      group.add(plane);
      const edge = new THREE.LineSegments(
        new THREE.EdgesGeometry(new THREE.PlaneGeometry(3.1, 2.0)),
        new THREE.LineBasicMaterial({ color: 0x12a08d, transparent: true, opacity: 0.55 })
      );
      edge.position.copy(plane.position);
      edge.rotation.copy(plane.rotation);
      group.add(edge);
    }

    // A faint floor grid gives the eye a horizon without adding a "scene".
    const grid = new THREE.GridHelper(18, 22, 0x1b2730, 0x141d24);
    grid.position.y = -1.55;
    scene.add(grid);

    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    const reduce = prefersReducedMotion();
    let frame = 0;
    let visible = true;
    let hovered: number | null = null;

    function setPointer(e: PointerEvent) {
      const rect = renderer.domElement.getBoundingClientRect();
      pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
    }

    function onMove(e: PointerEvent) {
      setPointer(e);
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects(nodes, false)[0];
      const next = hit ? (hit.object.userData.index as number) : null;
      if (next !== hovered) {
        hovered = next;
        renderer.domElement.style.cursor = next === null ? "default" : "pointer";
      }
    }

    function onClick(e: PointerEvent) {
      setPointer(e);
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObjects(nodes, false)[0];
      if (hit) selectRef.current?.(hit.object.userData.index as number);
    }

    function onVisibility() {
      visible = !document.hidden;
      if (visible && !reduce) frame = requestAnimationFrame(tick);
    }

    let t = 0;
    function tick() {
      if (!visible) return;
      t += 0.008;
      group.rotation.y = Math.sin(t) * 0.055;
      camera.position.y = 1.95 + Math.sin(t * 1.6) * 0.1;
      camera.lookAt(0, 0, -0.6);
      nodes.forEach((n, i) => {
        const base = steps[i]?.active ? 0.9 : 0.35;
        const mat = n.material as THREE.MeshStandardMaterial;
        mat.emissiveIntensity = base + Math.sin(t * 3 + i) * (steps[i]?.active ? 0.35 : 0.12);
        n.scale.setScalar(hovered === i ? 1.45 : 1);
      });
      renderer.render(scene, camera);
      frame = requestAnimationFrame(tick);
    }

    function resize() {
      const w = mount?.clientWidth || width;
      camera.aspect = w / height;
      camera.updateProjectionMatrix();
      renderer.setSize(w, height, false);
      renderer.render(scene, camera);
    }

    renderer.domElement.addEventListener("pointermove", onMove);
    renderer.domElement.addEventListener("click", onClick);
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("resize", resize);

    renderer.render(scene, camera);
    if (!reduce) frame = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(frame);
      renderer.domElement.removeEventListener("pointermove", onMove);
      renderer.domElement.removeEventListener("click", onClick);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener("resize", resize);
      scene.traverse((o) => {
        const anyObj = o as THREE.Mesh;
        anyObj.geometry?.dispose?.();
        const m = anyObj.material as THREE.Material | THREE.Material[] | undefined;
        if (Array.isArray(m)) m.forEach((x) => x.dispose());
        else m?.dispose?.();
      });
      renderer.dispose();
      const host = mount;
      if (host && renderer.domElement.parentNode === host) host.removeChild(renderer.domElement);
    };
  }, [steps]);

  return (
    <div className="pipeline3d" ref={host}>
      <span className="cap">{caption}</span>
      {onSelect && <span className="hint">click a step to open its artefacts</span>}
    </div>
  );
}
