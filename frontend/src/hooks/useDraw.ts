"use client";

import { useCallback, useRef, useState } from "react";

export type DrawPoint = { x: number; y: number };

function resampleTo32(points: DrawPoint[]): number[] {
  if (points.length < 2) {
    return new Array(32).fill(0);
  }
  const xs = points.map((p) => p.x);
  const ys = points.map((p) => p.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const rangeX = Math.max(1e-9, maxX - minX);

  const normalized = points.map((p) => ({
    u: (p.x - minX) / rangeX,
    y: p.y,
  }));

  const targetUs = Array.from({ length: 32 }, (_, i) => i / 31);
  const out: number[] = [];

  for (let i = 0; i < 32; i++) {
    const u = targetUs[i];
    let left = 0;
    let right = normalized.length - 1;
    while (right - left > 1) {
      const mid = Math.floor((left + right) / 2);
      if (normalized[mid].u < u) left = mid;
      else right = mid;
    }
    const a = normalized[left];
    const b = normalized[right];
    const denom = Math.max(1e-9, b.u - a.u);
    const t = (u - a.u) / denom;
    const interpolated = a.y + t * (b.y - a.y);
    out.push(interpolated);
  }

  const ysOut = out;
  const mean = ysOut.reduce((s, v) => s + v, 0) / ysOut.length;
  const std = Math.sqrt(
    ysOut.reduce((s, v) => s + (v - mean) ** 2, 0) / ysOut.length
  );
  const sigma = Math.max(1e-9, std);
  const z = ysOut.map((v) => (v - mean) / sigma);
  return z;
}

export function useDraw(canvasSize: { width: number; height: number }) {
  const [isDrawing, setIsDrawing] = useState(false);
  const [points, setPoints] = useState<DrawPoint[]>([]);
  const pointsRef = useRef<DrawPoint[]>([]);

  const toCanvasSpace = useCallback(
    (clientX: number, clientY: number, rect: DOMRect) => {
      const x = (clientX - rect.left) / canvasSize.width;
      const y = 1 - (clientY - rect.top) / canvasSize.height;
      return { x: Math.max(0, Math.min(1, x)), y: Math.max(0, Math.min(1, y)) };
    },
    [canvasSize]
  );

  const startDrawing = useCallback(
    (e: React.PointerEvent<HTMLCanvasElement>) => {
      const canvas = e.currentTarget;
      const rect = canvas.getBoundingClientRect();
      const p = toCanvasSpace(e.clientX, e.clientY, rect);
      pointsRef.current = [p];
      setPoints([p]);
      setIsDrawing(true);
      canvas.setPointerCapture(e.pointerId);
    },
    [toCanvasSpace]
  );

  const draw = useCallback(
    (e: React.PointerEvent<HTMLCanvasElement>) => {
      if (!isDrawing) return;
      const rect = e.currentTarget.getBoundingClientRect();
      const p = toCanvasSpace(e.clientX, e.clientY, rect);
      pointsRef.current.push(p);
      setPoints((prev) => [...prev, p]);
    },
    [isDrawing, toCanvasSpace]
  );

  const stopDrawing = useCallback(
    (e: React.PointerEvent<HTMLCanvasElement>) => {
      if (!isDrawing) return;
      setIsDrawing(false);
      try {
        e.currentTarget.releasePointerCapture(e.pointerId);
      } catch {
        // ignore
      }
    },
    [isDrawing]
  );

  const reset = useCallback(() => {
    pointsRef.current = [];
    setPoints([]);
  }, []);

  const vector = resampleTo32(points);

  return {
    points,
    vector,
    isDrawing,
    startDrawing,
    draw,
    stopDrawing,
    reset,
  };
}

export function drawPath(
  canvas: HTMLCanvasElement,
  points: DrawPoint[],
  canvasSize: { width: number; height: number }
): void {
  const ctx = canvas.getContext("2d");
  if (!ctx || points.length < 2) return;

  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.beginPath();
  ctx.strokeStyle = "#38bdf8";
  ctx.lineWidth = 2;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";

  points.forEach((p, i) => {
    const x = p.x * canvas.width;
    const y = (1 - p.y) * canvas.height;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();
}
