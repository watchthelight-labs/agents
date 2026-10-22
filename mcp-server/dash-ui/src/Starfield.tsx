import { useEffect, useRef } from "react";

// Three depth layers. Far stars move least, near stars most.
const LAYERS = [
  { parallax: 0.25, speed: 0.05, size: 0.6 },
  { parallax: 0.5, speed: 0.09, size: 0.85 },
  { parallax: 1.0, speed: 0.14, size: 1.15 },
];
const STAR: [number, number, number] = [214, 222, 212];
const TINT: [number, number, number] = [143, 169, 138];
const FRAME_MS = 1000 / 30; // 30 fps is plenty for a slow drift
const PROXIMITY = 140; // px radius of the cursor glow

interface Star {
  x: number;
  y: number;
  layer: number;
  r: number;
  a: number;
  tw: number;
  phase: number;
  tinted: boolean;
}

export function Starfield() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    let reduced = mq.matches;
    let w = 0;
    let h = 0;
    let stars: Star[] = [];
    let raf = 0;
    let last = 0;
    let px = 0;
    let py = 0;
    let cx = 0;
    let cy = 0;
    let mx = -1e4;
    let my = -1e4;

    function build() {
      // Density scales with area, capped so huge screens stay cheap.
      const n = Math.min(180, Math.round((w * h) / 9000));
      stars = Array.from({ length: n }, (_, i) => {
        const layer = i % 3;
        return {
          x: Math.random() * w,
          y: Math.random() * h,
          layer,
          r: LAYERS[layer].size * (0.6 + Math.random() * 0.8),
          a: 0.2 + Math.random() * 0.5,
          tw: 0.3 + Math.random() * 0.9,
          phase: Math.random() * Math.PI * 2,
          tinted: Math.random() < 0.15,
        };
      });
    }

    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      w = window.innerWidth;
      h = window.innerHeight;
      canvas!.width = Math.floor(w * dpr);
      canvas!.height = Math.floor(h * dpr);
      canvas!.style.width = `${w}px`;
      canvas!.style.height = `${h}px`;
      ctx!.setTransform(dpr, 0, 0, dpr, 0, 0);
      build();
    }

    function draw(t: number) {
      ctx!.clearRect(0, 0, w, h);
      cx += (px - cx) * 0.05;
      cy += (py - cy) * 0.05;
      const time = t * 0.001;
      for (const s of stars) {
        const L = LAYERS[s.layer];
        const x = s.x + cx * L.parallax * 18;
        const y = s.y + cy * L.parallax * 18;
        let a = reduced ? s.a : s.a + Math.sin(time * s.tw + s.phase) * 0.15;
        const dx = x - mx;
        const dy = y - my;
        const d2 = dx * dx + dy * dy;
        if (d2 < PROXIMITY * PROXIMITY) a += (1 - Math.sqrt(d2) / PROXIMITY) * 0.45;
        a = Math.max(0, Math.min(1, a));
        const [r, g, b] = s.tinted ? TINT : STAR;
        ctx!.fillStyle = `rgba(${r},${g},${b},${a})`;
        // Squares, not circles: cheaper, and on brand.
        ctx!.fillRect(x - s.r, y - s.r, s.r * 2, s.r * 2);
      }
    }

    function step(t: number) {
      raf = requestAnimationFrame(step);
      if (t - last < FRAME_MS) return;
      last = t;
      for (const s of stars) {
        const L = LAYERS[s.layer];
        s.x -= L.speed;
        s.y += L.speed * 0.6;
        if (s.x < -4) s.x = w + 4;
        if (s.y > h + 4) s.y = -4;
      }
      draw(t);
    }

    function start() {
      if (!reduced && !raf && !document.hidden) raf = requestAnimationFrame(step);
    }
    function stop() {
      cancelAnimationFrame(raf);
      raf = 0;
    }

    function onPointer(e: PointerEvent) {
      px = (e.clientX / w - 0.5) * 2;
      py = (e.clientY / h - 0.5) * 2;
      mx = e.clientX;
      my = e.clientY;
    }
    function onLeave() {
      mx = my = -1e4;
    }
    function onResize() {
      resize();
      draw(0);
    }
    function onVis() {
      if (document.hidden) stop();
      else start();
    }
    function onMotion() {
      reduced = mq.matches;
      stop();
      draw(0);
      start();
    }

    resize();
    draw(0);
    start();
    window.addEventListener("resize", onResize);
    window.addEventListener("pointermove", onPointer, { passive: true });
    document.addEventListener("pointerleave", onLeave);
    document.addEventListener("visibilitychange", onVis);
    mq.addEventListener("change", onMotion);
    return () => {
      stop();
      window.removeEventListener("resize", onResize);
      window.removeEventListener("pointermove", onPointer);
      document.removeEventListener("pointerleave", onLeave);
      document.removeEventListener("visibilitychange", onVis);
      mq.removeEventListener("change", onMotion);
    };
  }, []);

  return <canvas ref={ref} className="starfield" aria-hidden="true" />;
}
