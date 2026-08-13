"use client";

import { useCallback, useMemo, useRef, useState } from "react";

import { resample, type Point } from "@/utils/shape";

const SAMPLE_POINTS = 64; // sunucuya giden ham örnekleme (motor 32'ye indirger)
const MIN_STEP = 0.004; // aynı piksele düşen noktaları toplamayalım

/**
 * Serbest çizim durumu.
 *
 * Kanvas koordinatları 0–1 aralığında ve **y yukarı pozitif** tutulur; ekran
 * uzayı burada bir kez terk edilir, aşağıdaki katmanların hiçbiri "yukarı
 * hangi yön" sorusunu tekrar sormaz.
 */
export function useDraw() {
  const [strokes, setStrokes] = useState<Point[][]>([]);
  const [isDrawing, setIsDrawing] = useState(false);
  const active = useRef<Point[]>([]);

  const points = useMemo(() => strokes.flat(), [strokes]);

  /** Sunucuya gidecek ham seri. Boşsa çizim geçersizdir. */
  const series = useMemo(
    () => (points.length > 1 ? resample(points, SAMPLE_POINTS) : []),
    [points]
  );

  const toLocal = useCallback((event: React.PointerEvent<HTMLElement>): Point => {
    const rect = event.currentTarget.getBoundingClientRect();
    const x = (event.clientX - rect.left) / Math.max(1, rect.width);
    const y = 1 - (event.clientY - rect.top) / Math.max(1, rect.height);
    return { x: Math.min(1, Math.max(0, x)), y: Math.min(1, Math.max(0, y)) };
  }, []);

  const start = useCallback(
    (event: React.PointerEvent<HTMLElement>) => {
      const point = toLocal(event);
      active.current = [point];
      // Yeni bir çizim eskisini siler: iki ayrı formasyon tek sorgu olamaz.
      setStrokes([[point]]);
      setIsDrawing(true);
      event.currentTarget.setPointerCapture?.(event.pointerId);
    },
    [toLocal]
  );

  const move = useCallback(
    (event: React.PointerEvent<HTMLElement>) => {
      if (!isDrawing) return;
      const point = toLocal(event);
      const last = active.current[active.current.length - 1];
      if (last && Math.abs(point.x - last.x) < MIN_STEP) return;
      active.current = [...active.current, point];
      setStrokes([active.current]);
    },
    [isDrawing, toLocal]
  );

  const end = useCallback(
    (event: React.PointerEvent<HTMLElement>) => {
      if (!isDrawing) return;
      setIsDrawing(false);
      try {
        event.currentTarget.releasePointerCapture?.(event.pointerId);
      } catch {
        // pointer zaten bırakılmış
      }
    },
    [isDrawing]
  );

  const reset = useCallback(() => {
    active.current = [];
    setStrokes([]);
  }, []);

  const setSeries = useCallback((values: number[]) => {
    if (values.length < 2) return reset();
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = Math.max(1e-9, max - min);
    const mapped = values.map((v, i) => ({
      x: i / (values.length - 1),
      y: (v - min) / range,
    }));
    active.current = mapped;
    setStrokes([mapped]);
  }, [reset]);

  return { points, series, isDrawing, start, move, end, reset, setSeries };
}
