"use client";

import { useEffect, useRef } from "react";

interface QueryPreviewProps {
  vector: number[];
  height?: number;
  className?: string;
}

export function QueryPreview({ vector, height = 80, className }: QueryPreviewProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || vector.length < 2) return;
    const rect = canvas.getBoundingClientRect();
    const width = Math.max(1, rect.width);
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.floor(width * ratio);
    canvas.height = Math.floor(height * ratio);
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.scale(ratio, ratio);

    ctx.clearRect(0, 0, width, height);
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 2;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";

    const min = Math.min(...vector);
    const max = Math.max(...vector);
    const range = Math.max(1e-9, max - min);

    ctx.beginPath();
    vector.forEach((v, i) => {
      const x = (i / (vector.length - 1)) * width;
      const y = height - ((v - min) / range) * height;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    // area fill
    ctx.lineTo(width, height);
    ctx.lineTo(0, height);
    ctx.closePath();
    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, "rgba(56,189,248,0.15)");
    gradient.addColorStop(1, "rgba(56,189,248,0)");
    ctx.fillStyle = gradient;
    ctx.fill();
  }, [vector, height]);

  if (vector.length < 2) return null;

  return (
    <div className={`rounded-md border border-border bg-black/50 ${className ?? ""}`}>
      <canvas
        ref={canvasRef}
        className="block w-full"
        style={{ height }}
      />
    </div>
  );
}
