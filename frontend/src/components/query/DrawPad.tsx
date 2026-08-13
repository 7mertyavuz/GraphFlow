"use client";

import { useEffect, useRef } from "react";
import { Eraser, MousePointer2 } from "lucide-react";

import { type Point } from "@/utils/shape";

interface DrawPadProps {
  points: Point[];
  isDrawing: boolean;
  onPointerDown: (event: React.PointerEvent<HTMLCanvasElement>) => void;
  onPointerMove: (event: React.PointerEvent<HTMLCanvasElement>) => void;
  onPointerUp: (event: React.PointerEvent<HTMLCanvasElement>) => void;
  onClear: () => void;
  height?: number;
}

/**
 * Çizim yüzeyi — düz HTML5 Canvas + pointer events (K-17).
 *
 * Kütüphane yok: gereken şey bir yol çizmek ve noktaları toplamaktır;
 * Fabric/Konva bu iş için 100 satırlık işi 200 KB'a çevirirdi.
 */
export function DrawPad({
  points,
  isDrawing,
  onPointerDown,
  onPointerMove,
  onPointerUp,
  onClear,
  height = 260,
}: DrawPadProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const parent = canvas.parentElement;
    const width = parent?.clientWidth ?? 320;
    const ratio = window.devicePixelRatio || 1;

    canvas.width = Math.floor(width * ratio);
    canvas.height = Math.floor(height * ratio);
    canvas.style.width = "100%";
    canvas.style.height = `${height}px`;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.scale(ratio, ratio);
    ctx.clearRect(0, 0, width, height);

    // Izgara — göz, eğimi referanssız okuyamaz.
    ctx.strokeStyle = "rgba(255,255,255,0.045)";
    ctx.lineWidth = 1;
    const step = Math.max(24, Math.round(width / 12));
    for (let x = step; x < width; x += step) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, height);
      ctx.stroke();
    }
    for (let y = step; y < height; y += step) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(width, y);
      ctx.stroke();
    }

    // Orta çizgi
    ctx.strokeStyle = "rgba(255,255,255,0.08)";
    ctx.setLineDash([4, 6]);
    ctx.beginPath();
    ctx.moveTo(0, height / 2);
    ctx.lineTo(width, height / 2);
    ctx.stroke();
    ctx.setLineDash([]);

    if (points.length < 2) return;

    const toX = (p: Point) => p.x * width;
    const toY = (p: Point) => (1 - p.y) * height;

    // Alan dolgusu
    ctx.beginPath();
    ctx.moveTo(toX(points[0]), toY(points[0]));
    points.forEach((p) => ctx.lineTo(toX(p), toY(p)));
    ctx.lineTo(toX(points[points.length - 1]), height);
    ctx.lineTo(toX(points[0]), height);
    ctx.closePath();
    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, "rgba(56,189,248,0.22)");
    gradient.addColorStop(1, "rgba(56,189,248,0)");
    ctx.fillStyle = gradient;
    ctx.fill();

    // Çizgi
    ctx.beginPath();
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 2.5;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    points.forEach((p, i) => {
      const x = toX(p);
      const y = toY(p);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // Uç noktalar
    const last = points[points.length - 1];
    ctx.fillStyle = "#38bdf8";
    ctx.beginPath();
    ctx.arc(toX(last), toY(last), 3.5, 0, Math.PI * 2);
    ctx.fill();
  }, [points, height]);

  const empty = points.length < 2;

  return (
    <div className="space-y-2">
      <div className="relative overflow-hidden rounded-lg border border-border bg-[oklch(0.13_0.015_255)]">
        <canvas
          ref={canvasRef}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerLeave={onPointerUp}
          className="block w-full cursor-crosshair touch-none select-none"
          style={{ height }}
        />
        {empty && !isDrawing && (
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-2 text-center">
            <MousePointer2 className="size-5 text-muted-foreground" />
            <p className="text-sm font-medium text-muted-foreground">
              Formasyonu buraya çizin
            </p>
            <p className="max-w-[220px] text-xs text-muted-foreground/70">
              Soldan sağa tek hamlede çizin. Fiyat seviyesi değil,{" "}
              <span className="text-brand">şeklin kendisi</span> aranır.
            </p>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span className="tabular">
          {empty ? "Çizim bekleniyor" : `${points.length} nokta`}
        </span>
        <button
          type="button"
          onClick={onClear}
          disabled={empty}
          className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 transition-colors hover:bg-accent hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
        >
          <Eraser className="size-3.5" />
          Temizle
        </button>
      </div>
    </div>
  );
}
