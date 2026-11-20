"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { resample, type Point } from "@/utils/shape";

/** Önizleme/düzlük kontrolü için indirgeme. Sorgu ham noktalarla gider. */
const PREVIEW_POINTS = 64;

/**
 * Aynı x sayılacak yatay eşik (kanvas genişliğinin oranı).
 *
 * Bu eşiğin altındaki hareket **noktayı düşürmez**, son noktanın y'sini
 * günceller: eşik altı hareketi atmak, dik çizilen bir tepeyi/dibi
 * (formasyonların tam da tanımlayıcı yerini) düzleştiriyordu.
 */
const MIN_STEP = 0.002;

/** Tek darbede tutulacak azami nokta — sunucu sınırının (4096) altında. */
const MAX_POINTS = 2_000;

/**
 * Serbest çizim durumu.
 *
 * Kanvas koordinatları 0–1 aralığında ve **y yukarı pozitif** tutulur; ekran
 * uzayı burada bir kez terk edilir, aşağıdaki katmanların hiçbiri "yukarı
 * hangi yön" sorusunu tekrar sormaz.
 *
 * Çizim, x ekseni boyunca **tek değerli bir fonksiyondur** (``y = f(x)``).
 * Ham pointer dizisi bunu garanti etmez — el titrer, kullanıcı bir bölümü
 * düzeltmek için sola döner. Sözleşme burada, girişte kurulur; aşağısı
 * (``resample``, sunucudaki ``normalize_drawing``) monoton x varsayabilir.
 * Eskiden bu iş sıralamayla yapılıyordu ve sessizce yanlıştı: sola dönen bir
 * el, y değerlerinin x sırasına dizilmesine yani kullanıcının çizmediği bir
 * şeklin aranmasına yol açıyordu.
 */
export type DrawMode = "freehand" | "polyline" | "spline";

function densifyVertices(
  verts: Point[],
  mode: DrawMode = "polyline",
  samplesPerSeg = 32
): Point[] {
  if (verts.length < 2) return verts.slice();
  const out: Point[] = [];
  for (let i = 0; i < verts.length - 1; i++) {
    const p0 = verts[Math.max(0, i - 1)];
    const p1 = verts[i];
    const p2 = verts[i + 1];
    const p3 = verts[Math.min(verts.length - 1, i + 2)];
    const steps = Math.max(6, Math.round(Math.abs(p2.x - p1.x) * samplesPerSeg * 4));
    for (let s = 0; s < steps; s++) {
      const t = s / steps;
      const x = p1.x + t * (p2.x - p1.x);
      if (mode === "spline" && verts.length >= 3) {
        const t2 = t * t;
        const t3 = t2 * t;
        // Catmull-Rom y(t) — yumuşak çanak, fincan-kulp veya OBO çizimi için
        const yRaw =
          0.5 *
          (2 * p1.y +
            (-p0.y + p2.y) * t +
            (2 * p0.y - 5 * p1.y + 4 * p2.y - p3.y) * t2 +
            (-p0.y + 3 * p1.y - 3 * p2.y + p3.y) * t3);
        out.push({ x, y: Math.min(1, Math.max(0, yRaw)) });
      } else {
        out.push({ x, y: p1.y + t * (p2.y - p1.y) });
      }
    }
  }
  out.push(verts[verts.length - 1]);
  return out;
}

const VERTEX_HIT_RADIUS = 0.04;

export function useDraw() {
  const [points, setPoints] = useState<Point[]>([]);
  const [vertices, setVertices] = useState<Point[]>([]);
  const [drawMode, setDrawModeState] = useState<DrawMode>("freehand");
  const [hoverPoint, setHoverPoint] = useState<Point | null>(null);
  const [hoveredVertexIndex, setHoveredVertexIndex] = useState<number | null>(null);
  const [isDrawing, setIsDrawing] = useState(false);

  const buffer = useRef<Point[]>([]);
  const pointerId = useRef<number | null>(null);
  const frame = useRef<number | null>(null);
  const draggingVertexIndex = useRef<number | null>(null);

  const setDrawMode = useCallback((nextMode: DrawMode) => {
    setDrawModeState(nextMode);
    setHoverPoint(null);
    setHoveredVertexIndex(null);
    draggingVertexIndex.current = null;
    if (nextMode === "polyline" || nextMode === "spline") {
      setVertices((prev) => {
        if (prev.length >= 2) {
          const dense = densifyVertices(prev, nextMode);
          buffer.current = dense;
          setPoints(dense);
        }
        return prev;
      });
    }
  }, []);

  /** Boyama en fazla kare başına bir kez: pointermove'da state güncellemek
   *  uzun darbelerde kareyi düşürüyor, düşen kare de nokta kaybettiriyordu. */
  const flush = useCallback(() => {
    if (frame.current !== null) return;
    frame.current = requestAnimationFrame(() => {
      frame.current = null;
      setPoints(buffer.current.slice());
    });
  }, []);

  const cancelFrame = useCallback(() => {
    if (frame.current !== null) {
      cancelAnimationFrame(frame.current);
      frame.current = null;
    }
  }, []);

  useEffect(() => cancelFrame, [cancelFrame]);

  /** ``y = f(x)`` sözleşmesini koruyarak nokta ekler. */
  const push = useCallback((p: Point) => {
    const pts = buffer.current;
    const last = pts[pts.length - 1];

    if (!last) {
      pts.push(p);
      return;
    }

    if (p.x > last.x + MIN_STEP) {
      if (pts.length < MAX_POINTS) pts.push(p);
      else pts[pts.length - 1] = p;
      return;
    }

    if (p.x < last.x - MIN_STEP) {
      // Geri çizim: kullanıcı o bölgeyi yeniden çiziyor → sonra yazan kazanır.
      while (pts.length > 1 && pts[pts.length - 1].x >= p.x) pts.pop();
      if (pts.length === 1 && pts[0].x >= p.x) pts[0] = p;
      else pts.push(p);
      return;
    }

    // Aynı x: dikey hareket. Nokta düşmez, y güncellenir — sivri tepe korunur.
    pts[pts.length - 1] = { x: last.x, y: p.y };
  }, []);

  /** Kap ölçülebilir mi? Sıfır genişlikte her nokta aynı x'e düşer. */
  const measurable = (rect: DOMRect) => rect.width > 1 && rect.height > 1;

  const toLocal = useCallback((clientX: number, clientY: number, rect: DOMRect): Point => {
    const x = (clientX - rect.left) / Math.max(1, rect.width);
    const y = 1 - (clientY - rect.top) / Math.max(1, rect.height);
    return {
      x: Math.min(1, Math.max(0, x)),
      y: Math.min(1, Math.max(0, y)),
    };
  }, []);

  const findHitVertex = useCallback(
    (pt: Point, list: Point[]): number | null => {
      let bestIdx: number | null = null;
      let bestDist = VERTEX_HIT_RADIUS;
      for (let i = 0; i < list.length; i++) {
        const d = Math.hypot(list[i].x - pt.x, list[i].y - pt.y);
        if (d <= bestDist) {
          bestDist = d;
          bestIdx = i;
        }
      }
      return bestIdx;
    },
    []
  );

  const start = useCallback(
    (event: React.PointerEvent<HTMLElement>) => {
      // Yalnız birincil işaretçi: ikinci parmak ya da sağ tık, sürmekte olan
      // darbeyi silmemeli.
      if (!event.isPrimary || (event.pointerType === "mouse" && event.button !== 0)) return;

      const rect = event.currentTarget.getBoundingClientRect();
      if (!measurable(rect)) return;
      const pt = toLocal(event.clientX, event.clientY, rect);

      if (drawMode === "polyline" || drawMode === "spline") {
        const hit = findHitVertex(pt, vertices);
        if (hit !== null) {
          draggingVertexIndex.current = hit;
          pointerId.current = event.pointerId;
          setHoveredVertexIndex(hit);
          setIsDrawing(true);
          event.currentTarget.setPointerCapture?.(event.pointerId);
          return;
        }
        setVertices((prev) => {
          const filtered = prev.filter((v) => v.x < pt.x - MIN_STEP);
          const next = [...filtered, pt];
          const dense = densifyVertices(next, drawMode);
          buffer.current = dense;
          setPoints(dense);
          return next;
        });
        setHoverPoint(null);
        return;
      }

      pointerId.current = event.pointerId;
      // Yeni bir çizim eskisini siler: iki ayrı formasyon tek sorgu olamaz.
      setVertices([]);
      setHoverPoint(null);
      setHoveredVertexIndex(null);
      buffer.current = [pt];
      setPoints(buffer.current.slice());
      setIsDrawing(true);
      event.currentTarget.setPointerCapture?.(event.pointerId);
    },
    [drawMode, findHitVertex, toLocal, vertices]
  );

  const move = useCallback(
    (event: React.PointerEvent<HTMLElement>) => {
      const rect = event.currentTarget.getBoundingClientRect();
      if ((drawMode === "polyline" || drawMode === "spline") && draggingVertexIndex.current !== null) {
        if (pointerId.current !== event.pointerId || !measurable(rect)) return;
        const pt = toLocal(event.clientX, event.clientY, rect);
        const dragIdx = draggingVertexIndex.current;
        setVertices((prev) => {
          if (dragIdx < 0 || dragIdx >= prev.length) return prev;
          const minX = dragIdx > 0 ? prev[dragIdx - 1].x + MIN_STEP * 2 : 0;
          const maxX = dragIdx < prev.length - 1 ? prev[dragIdx + 1].x - MIN_STEP * 2 : 1;
          const clampedX = Math.min(maxX, Math.max(minX, pt.x));
          const clampedY = Math.min(1, Math.max(0, pt.y));
          const next = prev.map((v, i) => (i === dragIdx ? { x: clampedX, y: clampedY } : v));
          const dense = densifyVertices(next, drawMode);
          buffer.current = dense;
          setPoints(dense);
          return next;
        });
        return;
      }

      if ((drawMode === "polyline" || drawMode === "spline") && pointerId.current === null) {
        if (measurable(rect)) {
          const pt = toLocal(event.clientX, event.clientY, rect);
          const hit = findHitVertex(pt, vertices);
          setHoveredVertexIndex(hit);
          setHoverPoint(hit !== null ? null : pt);
        }
        return;
      }

      if (pointerId.current !== event.pointerId) return;

      // Tarayıcı hızlı darbelerde pointermove'ları birleştirir; birleşenleri
      // açmadan çizilen keskin köşeler kesilir.
      const native = event.nativeEvent;
      const coalesced =
        typeof native.getCoalescedEvents === "function" ? native.getCoalescedEvents() : [];
      const samples = coalesced.length > 0 ? coalesced : [native];

      for (const sample of samples) {
        push(toLocal(sample.clientX, sample.clientY, rect));
      }
      flush();
    },
    [drawMode, findHitVertex, flush, push, toLocal, vertices]
  );

  const leave = useCallback(() => {
    setHoverPoint(null);
    setHoveredVertexIndex(null);
  }, []);

  const end = useCallback(
    (event: React.PointerEvent<HTMLElement>) => {
      if (pointerId.current !== event.pointerId) return;
      pointerId.current = null;
      draggingVertexIndex.current = null;
      setIsDrawing(false);
      cancelFrame();
      setPoints(buffer.current.slice());
      try {
        event.currentTarget.releasePointerCapture?.(event.pointerId);
      } catch {
        // pointer zaten bırakılmış
      }
    },
    [cancelFrame]
  );

  const removeVertexAt = useCallback(
    (event: React.MouseEvent<HTMLElement>) => {
      if (drawMode !== "polyline" && drawMode !== "spline") return;
      const rect = event.currentTarget.getBoundingClientRect();
      if (!measurable(rect)) return;
      const pt = toLocal(event.clientX, event.clientY, rect);
      const hit = findHitVertex(pt, vertices);
      if (hit === null || vertices.length <= 2) return;
      event.preventDefault();
      setVertices((prev) => {
        if (prev.length <= 2 || hit >= prev.length) return prev;
        const next = prev.filter((_, idx) => idx !== hit);
        const dense = densifyVertices(next, drawMode);
        buffer.current = dense;
        setPoints(dense);
        return next;
      });
      setHoveredVertexIndex(null);
    },
    [drawMode, findHitVertex, toLocal, vertices]
  );

  const reset = useCallback(() => {
    cancelFrame();
    pointerId.current = null;
    draggingVertexIndex.current = null;
    buffer.current = [];
    setVertices([]);
    setHoverPoint(null);
    setHoveredVertexIndex(null);
    setPoints([]);
    setIsDrawing(false);
  }, [cancelFrame]);

  const undoVertex = useCallback(() => {
    setVertices((prev) => {
      if (prev.length === 0) return prev;
      const next = prev.slice(0, -1);
      const dense = next.length >= 2 ? densifyVertices(next, drawMode) : next.slice();
      buffer.current = dense;
      setPoints(dense);
      return next;
    });
  }, [drawMode]);

  const loadPreset = useCallback(
    (verts: Point[], mode: DrawMode = "polyline") => {
      cancelFrame();
      pointerId.current = null;
      draggingVertexIndex.current = null;
      const clean = verts
        .map((v) => ({ x: Math.min(1, Math.max(0, v.x)), y: Math.min(1, Math.max(0, v.y)) }))
        .sort((a, b) => a.x - b.x);
      setDrawModeState(mode);
      setHoverPoint(null);
      setHoveredVertexIndex(null);
      setVertices(clean);
      const dense = densifyVertices(clean, mode);
      buffer.current = dense;
      setPoints(dense);
      setIsDrawing(false);
    },
    [cancelFrame]
  );

  const setRawPoints = useCallback(
    (rawPairs: number[][]) => {
      if (rawPairs.length < 2) return reset();
      const mapped = rawPairs.map((pair) => ({
        x: Math.min(1, Math.max(0, Number(pair[0]) || 0)),
        y: Math.min(1, Math.max(0, Number(pair[1]) || 0)),
      }));
      cancelFrame();
      pointerId.current = null;
      draggingVertexIndex.current = null;
      setDrawModeState("freehand");
      setVertices([]);
      setHoverPoint(null);
      setHoveredVertexIndex(null);
      buffer.current = mapped;
      setPoints(mapped);
      setIsDrawing(false);
    },
    [cancelFrame, reset]
  );

  const setSeries = useCallback(
    (values: number[]) => {
      if (values.length < 2) return reset();
      const min = Math.min(...values);
      const max = Math.max(...values);
      const range = Math.max(1e-9, max - min);
      const mapped = values.map((v, i) => ({
        x: i / (values.length - 1),
        y: (v - min) / range,
      }));
      cancelFrame();
      setVertices([]);
      setHoverPoint(null);
      buffer.current = mapped;
      setPoints(mapped);
    },
    [cancelFrame, reset]
  );

  /** Önizleme ve düzlük kontrolü için eşit aralıklı seri. */
  const series = useMemo(
    () => (points.length > 1 ? resample(points, PREVIEW_POINTS) : []),
    [points]
  );

  /**
   * Sunucuya gidecek yük: **ham (x, y) çiftleri**.
   *
   * x'i istemcide düzgün ızgaraya oturtup yalnız y göndermek, sunucuya
   * "bu noktalar eşit aralıklı" demektir — oysa kullanıcı çizerken hızlanıp
   * yavaşlar. 32'ye indirgemenin ve z-score'un tek otoritesi motordur (K-02).
   */
  const queryPoints = useMemo(
    () => points.map((p) => [p.x, p.y] as [number, number]),
    [points]
  );

  return {
    points,
    vertices,
    hoverPoint,
    hoveredVertexIndex,
    drawMode,
    setDrawMode,
    undoVertex,
    removeVertexAt,
    loadPreset,
    setRawPoints,
    series,
    queryPoints,
    isDrawing,
    start,
    move,
    leave,
    end,
    reset,
    setSeries,
  };
}
