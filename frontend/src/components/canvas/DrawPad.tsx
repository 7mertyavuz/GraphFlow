"use client";

import { useEffect, useRef } from "react";
import { useDraw, drawPath, type DrawPoint } from "@/hooks/useDraw";

interface DrawPadProps {
  onChange: (vector: number[]) => void;
  initialVector?: number[];
  size?: { width: number; height: number };
  className?: string;
}

function vectorToPoints(
  vector: number[],
  width: number,
  height: number
): DrawPoint[] {
  if (!vector || vector.length < 2) return [];
  const min = Math.min(...vector);
  const max = Math.max(...vector);
  const range = Math.max(1e-9, max - min);
  return vector.map((v, i) => ({
    x: (i / (vector.length - 1)) * width,
    y: 1 - (v - min) / range,
  }));
}

export function DrawPad({
  onChange,
  initialVector,
  size = { width: 360, height: 280 },
  className,
}: DrawPadProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const { points, vector, isDrawing, startDrawing, draw, stopDrawing, reset } =
    useDraw(size);

  useEffect(() => {
    if (!isDrawing && points.length > 1) {
      onChange(vector);
    }
  }, [isDrawing, points, vector, onChange]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ratio = typeof window !== "undefined" ? window.devicePixelRatio || 1 : 1;
    canvas.width = Math.floor(size.width * ratio);
    canvas.height = Math.floor(size.height * ratio);
    canvas.style.width = `${size.width}px`;
    canvas.style.height = `${size.height}px`;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.scale(ratio, ratio);

    // grid
    ctx.strokeStyle = "rgba(255,255,255,0.06)";
    ctx.lineWidth = 1;
    const step = 30;
    for (let x = 0; x <= size.width; x += step) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, size.height);
      ctx.stroke();
    }
    for (let y = 0; y <= size.height; y += step) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(size.width, y);
      ctx.stroke();
    }

    const drawPoints = points.length > 1 ? (points as DrawPoint[]) : [];
    if (initialVector && drawPoints.length === 0) {
      const preview = vectorToPoints(initialVector, size.width, size.height);
      drawPath(canvas, preview, size, "rgba(56,189,248,0.6)");
    } else {
      drawPath(canvas, drawPoints, size);
    }
  }, [points, size, initialVector]);

  const hasInput = points.length > 1 || (initialVector && initialVector.length > 1);

  return (
    <div className={`flex flex-col gap-3 ${className ?? ""}`}>
      <div className="relative overflow-hidden rounded-xl border border-border bg-black shadow-inner">
        <canvas
          ref={canvasRef}
          onPointerDown={startDrawing}
          onPointerMove={draw}
          onPointerUp={stopDrawing}
          onPointerLeave={stopDrawing}
          className="cursor-crosshair touch-none block"
          style={{ width: size.width, height: size.height }}
        />
        {!hasInput && (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-sm text-muted-foreground">
            Buraya çizin
          </div>
        )}
      </div>
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{points.length > 0 ? `${points.length} nokta toplandı` : "Çizmeye başlayın"}</span>
        <button
          type="button"
          onClick={reset}
          className="rounded px-2 py-1 text-xs hover:bg-muted hover:text-foreground"
        >
          Temizle
        </button>
      </div>
    </div>
  );
}
