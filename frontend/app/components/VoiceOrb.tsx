"use client";

import React, { useRef, useEffect } from "react";

interface VoiceOrbProps {
  getFrequencies: () => Uint8Array | null;
  onClick?: () => void;
}

export function VoiceOrb({ getFrequencies, onClick }: VoiceOrbProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rafRef = useRef<number>(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let t = 0;

    const resize = () => {
      canvas.width = canvas.offsetWidth * window.devicePixelRatio;
      canvas.height = canvas.offsetHeight * window.devicePixelRatio;
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    };
    resize();
    window.addEventListener("resize", resize);

    const draw = () => {
      const w = canvas.offsetWidth;
      const h = canvas.offsetHeight;
      ctx.clearRect(0, 0, w, h);

      // Audio amplitude (0-1)
      const freqs = getFrequencies();
      let amp = 0;
      if (freqs) {
        let sum = 0;
        for (let i = 0; i < 32; i++) sum += freqs[i];
        amp = sum / (32 * 255);
      }

      const cx = w / 2;
      const cy = h / 2;
      const baseR = Math.min(w, h) * 0.32;
      const pulse = 1 + amp * 0.35;

      // ── Outer glow ───────────────────────────────────────────────────────
      const glowR = baseR * pulse * 1.55;
      const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, glowR);
      glow.addColorStop(0, `rgba(255,255,255,${0.06 + amp * 0.08})`);
      glow.addColorStop(0.5, `rgba(200,220,255,${0.04 + amp * 0.04})`);
      glow.addColorStop(1, "rgba(0,0,0,0)");
      ctx.beginPath();
      ctx.arc(cx, cy, glowR, 0, Math.PI * 2);
      ctx.fillStyle = glow;
      ctx.fill();

      // ── Animated blob path ───────────────────────────────────────────────
      const numPoints = 8;
      const points: [number, number][] = [];
      for (let i = 0; i < numPoints; i++) {
        const angle = (i / numPoints) * Math.PI * 2;
        const noise =
          Math.sin(t * 1.2 + i * 1.7) * 0.12 +
          Math.sin(t * 0.7 + i * 2.3) * 0.08 +
          amp * 0.28;
        const r = baseR * pulse * (1 + noise);
        points.push([cx + Math.cos(angle) * r, cy + Math.sin(angle) * r]);
      }

      ctx.beginPath();
      for (let i = 0; i < numPoints; i++) {
        const [x1, y1] = points[i];
        const [x2, y2] = points[(i + 1) % numPoints];
        const mx = (x1 + x2) / 2;
        const my = (y1 + y2) / 2;
        if (i === 0) ctx.moveTo(mx, my);
        else ctx.quadraticCurveTo(x1, y1, mx, my);
      }
      ctx.closePath();

      // Fill gradient — silver/white orb
      const fill = ctx.createRadialGradient(
        cx - baseR * 0.3, cy - baseR * 0.3, baseR * 0.05,
        cx, cy, baseR * pulse * 1.1
      );
      fill.addColorStop(0, "rgba(255,255,255,0.95)");
      fill.addColorStop(0.35, "rgba(220,230,245,0.88)");
      fill.addColorStop(0.7, "rgba(170,185,210,0.75)");
      fill.addColorStop(1, "rgba(100,120,160,0.55)");
      ctx.fillStyle = fill;
      ctx.fill();

      // Inner specular highlight
      const spec = ctx.createRadialGradient(
        cx - baseR * 0.28, cy - baseR * 0.28, 0,
        cx - baseR * 0.18, cy - baseR * 0.18, baseR * 0.55
      );
      spec.addColorStop(0, "rgba(255,255,255,0.7)");
      spec.addColorStop(0.5, "rgba(255,255,255,0.15)");
      spec.addColorStop(1, "rgba(255,255,255,0)");
      ctx.fillStyle = spec;
      ctx.fill();

      // Rim light (bottom-right)
      const rim = ctx.createRadialGradient(
        cx + baseR * 0.5, cy + baseR * 0.4, 0,
        cx + baseR * 0.3, cy + baseR * 0.3, baseR * 0.7
      );
      rim.addColorStop(0, `rgba(150,180,255,${0.18 + amp * 0.15})`);
      rim.addColorStop(1, "rgba(150,180,255,0)");
      ctx.fillStyle = rim;
      ctx.fill();

      t += 0.018;
      rafRef.current = requestAnimationFrame(draw);
    };

    rafRef.current = requestAnimationFrame(draw);

    return () => {
      cancelAnimationFrame(rafRef.current);
      window.removeEventListener("resize", resize);
    };
  }, [getFrequencies]);

  return (
    <div
      className="relative w-full h-full flex flex-col items-center justify-center cursor-pointer transition-transform hover:scale-105 active:scale-95"
      onClick={onClick}
    >
      <div className="w-full h-40 md:h-64 pointer-events-none">
        <canvas
          ref={canvasRef}
          style={{ width: "100%", height: "100%" }}
        />
      </div>
    </div>
  );
}
