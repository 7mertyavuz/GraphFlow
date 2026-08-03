"use client";

import { useEffect, useRef } from "react";
import { useDraw, drawPath, type DrawPoint } from "@/hooks/useDraw";

interface DrawPadProps {
  onChange: (vector: number[]) => void;
  size?: { width: number; height: number };
  className?: string;
}

export function DrawPad({
  onChange,
  size = { width: 320, height: 240 },
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
    drawPath(canvas, points as DrawPoint[], size);
  }, [points, size]);

  return (
    <div className={`flex flex-col gap-2 ${className ?? ""}`}>
      <canvas
        ref={canvasRef}
        onPointerDown={startDrawing}
        onPointerMove={draw}
        onPointerUp={stopDrawing}
        onPointerLeave={stopDrawing}
        className="cursor-crosshair rounded-md border border-border bg-black touch-none"
        style={{ width: size.width, height: size.height }}
      />
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{points.length > 0 ? `${points.length} nokta` : "Çizmeye başlayın"}</span>
        <button
          type="button"
          onClick={reset}
          className="underline hover:text-foreground"
        >
          Temizle
        </button>
      </div>
    </div>
  );
}
