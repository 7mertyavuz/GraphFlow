"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Eraser, MousePointer2, Pencil, PenTool, Spline, Undo2 } from "lucide-react";

import { type DrawMode } from "@/hooks/useDraw";
import { useI18n } from "@/i18n/LanguageProvider";
import { cn } from "@/lib/utils";
import { analyzeDrawing, type Point } from "@/utils/shape";

interface DrawPadProps {
  points: Point[];
  vertices?: Point[];
  hoverPoint?: Point | null;
  hoveredVertexIndex?: number | null;
  drawMode?: DrawMode;
  onDrawModeChange?: (mode: DrawMode) => void;
  onUndoVertex?: () => void;
  onRemoveVertexAt?: (event: React.MouseEvent<HTMLCanvasElement>) => void;
  onLoadPreset?: (vertices: Point[], mode: DrawMode) => void;
  isDrawing: boolean;
  onPointerDown: (event: React.PointerEvent<HTMLCanvasElement>) => void;
  onPointerMove: (event: React.PointerEvent<HTMLCanvasElement>) => void;
  onPointerUp: (event: React.PointerEvent<HTMLCanvasElement>) => void;
  onPointerLeave?: () => void;
  onClear: () => void;
  height?: number;
}

const STARTER_PRESETS: Array<{
  key: "w" | "m" | "hs" | "cup" | "tri" | "flag";
  mode: DrawMode;
  vertices: Point[];
}> = [
  {
    key: "w",
    mode: "polyline",
    vertices: [
      { x: 0.06, y: 0.86 },
      { x: 0.27, y: 0.16 },
      { x: 0.5, y: 0.62 },
      { x: 0.73, y: 0.18 },
      { x: 0.94, y: 0.88 },
    ],
  },
  {
    key: "m",
    mode: "polyline",
    vertices: [
      { x: 0.06, y: 0.16 },
      { x: 0.27, y: 0.88 },
      { x: 0.5, y: 0.4 },
      { x: 0.73, y: 0.82 },
      { x: 0.94, y: 0.14 },
    ],
  },
  {
    key: "hs",
    mode: "polyline",
    vertices: [
      { x: 0.06, y: 0.2 },
      { x: 0.21, y: 0.62 },
      { x: 0.34, y: 0.3 },
      { x: 0.5, y: 0.92 },
      { x: 0.66, y: 0.3 },
      { x: 0.79, y: 0.6 },
      { x: 0.94, y: 0.18 },
    ],
  },
  {
    key: "cup",
    mode: "spline",
    vertices: [
      { x: 0.06, y: 0.84 },
      { x: 0.22, y: 0.32 },
      { x: 0.44, y: 0.16 },
      { x: 0.66, y: 0.5 },
      { x: 0.76, y: 0.84 },
      { x: 0.86, y: 0.66 },
      { x: 0.95, y: 0.9 },
    ],
  },
  {
    key: "tri",
    mode: "polyline",
    vertices: [
      { x: 0.06, y: 0.14 },
      { x: 0.2, y: 0.86 },
      { x: 0.36, y: 0.3 },
      { x: 0.52, y: 0.85 },
      { x: 0.68, y: 0.48 },
      { x: 0.82, y: 0.86 },
      { x: 0.94, y: 0.66 },
    ],
  },
  {
    key: "flag",
    mode: "polyline",
    vertices: [
      { x: 0.06, y: 0.12 },
      { x: 0.26, y: 0.88 },
      { x: 0.42, y: 0.68 },
      { x: 0.58, y: 0.8 },
      { x: 0.72, y: 0.62 },
      { x: 0.85, y: 0.72 },
      { x: 0.95, y: 0.92 },
    ],
  },
];

/**
 * Çizim yüzeyi — düz HTML5 Canvas + pointer events (K-17) + canlı yapısal/zarf önizlemesi.
 *
 * Kütüphane yok: gereken şey bir yol çizmek ve noktaları toplamaktır;
 * Fabric/Konva bu iş için 100 satırlık işi 200 KB'a çevirirdi.
 *
 * **Ölçekleme ile boyama ayrı efektlerdedir.** Aynı efektte olduklarında her
 * pointermove'da ``canvas.width`` yeniden atanıyordu; bu, bitmap'i yeniden
 * tahsis eden pahalı bir işlemdir ve uzun darbelerde kare düşürerek nokta
 * kaybettiriyordu — kullanıcının "çizimi tutmuyor" dediği şey buydu.
 */
export function DrawPad({
  points,
  vertices = [],
  hoverPoint = null,
  hoveredVertexIndex = null,
  drawMode = "freehand",
  onDrawModeChange,
  onUndoVertex,
  onRemoveVertexAt,
  onLoadPreset,
  isDrawing,
  onPointerDown,
  onPointerMove,
  onPointerUp,
  onPointerLeave,
  onClear,
  height = 260,
}: DrawPadProps) {
  const { t, lang } = useI18n();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [width, setWidth] = useState(0);

  const analysis = useMemo(() => analyzeDrawing(points), [points]);

  // --- Ölçekleme: yalnız kap genişliği ya da DPR değişince --------------
  useEffect(() => {
    const canvas = canvasRef.current;
    const parent = canvas?.parentElement;
    if (!canvas || !parent) return;

    const apply = () => {
      // clientWidth kenarlığı dışlar; işaretçi koordinatları da kanvasın
      // kendi rect'inden okunur — iki ölçü aynı kutuyu göstermeli.
      const next = canvas.getBoundingClientRect().width || parent.clientWidth;
      if (next > 0) setWidth(next);
    };

    apply();
    const observer = new ResizeObserver(apply);
    observer.observe(parent);
    return () => observer.disconnect();
  }, []);

  // --- Boyama: noktalar ya da ölçü değişince ----------------------------
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || width <= 0) return;

    const ratio = window.devicePixelRatio || 1;
    const pixelWidth = Math.round(width * ratio);
    const pixelHeight = Math.round(height * ratio);
    // Yeniden tahsis yalnız ölçü gerçekten değiştiyse.
    if (canvas.width !== pixelWidth) canvas.width = pixelWidth;
    if (canvas.height !== pixelHeight) canvas.height = pixelHeight;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
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

    const toX = (p: Point) => p.x * width;
    const toY = (p: Point) => (1 - p.y) * height;

    const isVertexMode = drawMode === "polyline" || drawMode === "spline";
    const drawGhostSegment = () => {
      if (!isVertexMode || vertices.length === 0 || !hoverPoint) return;
      const lastV = vertices[vertices.length - 1];
      if (hoverPoint.x <= lastV.x) return;
      ctx.save();
      ctx.strokeStyle = "rgba(56,189,248,0.45)";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(toX(lastV), toY(lastV));
      ctx.lineTo(toX(hoverPoint), toY(hoverPoint));
      ctx.stroke();
      ctx.fillStyle = "rgba(56,189,248,0.65)";
      ctx.beginPath();
      ctx.arc(toX(hoverPoint), toY(hoverPoint), 3.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();
    };

    // Tek köşe varsa (polyline/spline modunda ilk tıklama) nokta + hayalet çizgi göster
    if (points.length === 0 && vertices.length === 1) {
      drawGhostSegment();
      ctx.fillStyle = "#38bdf8";
      ctx.beginPath();
      ctx.arc(toX(vertices[0]), toY(vertices[0]), 4.5, 0, Math.PI * 2);
      ctx.fill();
      return;
    }

    if (points.length < 2) return;

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

    // Canlı zarf (trend çizgisi), direk (K-22) ve parabolik çanak (K-24) önizlemesi
    if (analysis) {
      if (analysis.parabolicCurve && analysis.parabolicCurve.length >= 2) {
        ctx.save();
        ctx.strokeStyle = "rgba(192,132,252,0.85)";
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 3]);
        ctx.beginPath();
        analysis.parabolicCurve.forEach((p, idx) => {
          if (idx === 0) ctx.moveTo(toX(p), toY(p));
          else ctx.lineTo(toX(p), toY(p));
        });
        ctx.stroke();
        ctx.restore();
      }
      if (analysis.poleLine) {
        ctx.save();
        ctx.strokeStyle = "rgba(251,191,36,0.75)";
        ctx.lineWidth = 2;
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.moveTo(analysis.poleLine.x1 * width, (1 - analysis.poleLine.y1) * height);
        ctx.lineTo(analysis.poleLine.x2 * width, (1 - analysis.poleLine.y2) * height);
        ctx.stroke();
        ctx.restore();
      }
      for (const line of [analysis.upperLine, analysis.lowerLine]) {
        if (!line) continue;
        ctx.save();
        ctx.strokeStyle = "rgba(251,191,36,0.65)";
        ctx.lineWidth = 1.5;
        ctx.setLineDash([5, 4]);
        ctx.beginPath();
        ctx.moveTo(line.x1 * width, (1 - line.y1) * height);
        ctx.lineTo(line.x2 * width, (1 - line.y2) * height);
        ctx.stroke();
        ctx.restore();
      }
    }

    drawGhostSegment();

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

    // Belirgin tepe (yeşil), dip (kırmızı) ve PIP dirsek (amber eşkenar dörtgen) işaretçileri
    if (analysis) {
      for (const el of analysis.elbows) {
        const ex = toX(el);
        const ey = toY(el);
        ctx.fillStyle = "rgba(251,191,36,0.85)";
        ctx.beginPath();
        ctx.moveTo(ex, ey - 3.5);
        ctx.lineTo(ex + 3.5, ey);
        ctx.lineTo(ex, ey + 3.5);
        ctx.lineTo(ex - 3.5, ey);
        ctx.closePath();
        ctx.fill();
      }
      for (const pk of analysis.peaks) {
        ctx.fillStyle = "#34d399";
        ctx.beginPath();
        ctx.arc(toX(pk), toY(pk), 4, 0, Math.PI * 2);
        ctx.fill();
      }
      for (const tr of analysis.troughs) {
        ctx.fillStyle = "#f87171";
        ctx.beginPath();
        ctx.arc(toX(tr), toY(tr), 4, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // Kırık çizgi / yumuşak eğri sürüklenebilir köşe tutamaçları
    if (isVertexMode && vertices.length > 0) {
      vertices.forEach((v, idx) => {
        const cx = toX(v);
        const cy = toY(v);
        const isHovered = hoveredVertexIndex === idx;
        if (isHovered) {
          ctx.fillStyle = "rgba(56,189,248,0.22)";
          ctx.beginPath();
          ctx.arc(cx, cy, 8, 0, Math.PI * 2);
          ctx.fill();
        }
        ctx.fillStyle = isHovered ? "#38bdf8" : "#0f172a";
        ctx.strokeStyle = "#38bdf8";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(cx, cy, isHovered ? 5 : 4, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
      });
    } else {
      // Uç nokta
      const last = points[points.length - 1];
      ctx.fillStyle = "#38bdf8";
      ctx.beginPath();
      ctx.arc(toX(last), toY(last), 3.5, 0, Math.PI * 2);
      ctx.fill();
    }
  }, [points, vertices, hoverPoint, hoveredVertexIndex, drawMode, analysis, width, height]);

  const empty = points.length < 2 && vertices.length === 0;
  const liveSummary = lang === "en" ? analysis?.summaryEn : analysis?.summaryTr;
  const liveBadge = lang === "en" ? analysis?.badgeEn : analysis?.badgeTr;

  return (
    <div className="space-y-2">
      {onDrawModeChange && (
        <div className="flex flex-wrap items-center justify-between gap-2 text-xs">
          <div className="inline-flex rounded-md border border-border bg-secondary/40 p-0.5">
            <button
              type="button"
              onClick={() => onDrawModeChange("freehand")}
              className={cn(
                "inline-flex items-center gap-1 rounded px-2 py-1 text-[11px] font-medium transition-colors",
                drawMode === "freehand"
                  ? "bg-brand/15 text-brand"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Pencil className="size-3" />
              {t.drawpad.modeFreehand}
            </button>
            <button
              type="button"
              onClick={() => onDrawModeChange("polyline")}
              className={cn(
                "inline-flex items-center gap-1 rounded px-2 py-1 text-[11px] font-medium transition-colors",
                drawMode === "polyline"
                  ? "bg-brand/15 text-brand"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <PenTool className="size-3" />
              {t.drawpad.modePolyline}
            </button>
            <button
              type="button"
              onClick={() => onDrawModeChange("spline")}
              className={cn(
                "inline-flex items-center gap-1 rounded px-2 py-1 text-[11px] font-medium transition-colors",
                drawMode === "spline"
                  ? "bg-brand/15 text-brand"
                  : "text-muted-foreground hover:text-foreground"
              )}
            >
              <Spline className="size-3" />
              {t.drawpad.modeSpline}
            </button>
          </div>

          {(drawMode === "polyline" || drawMode === "spline") && onUndoVertex && (
            <button
              type="button"
              onClick={onUndoVertex}
              disabled={vertices.length === 0}
              className="inline-flex items-center gap-1 rounded px-2 py-1 text-[11px] text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
            >
              <Undo2 className="size-3" />
              {t.drawpad.undoVertex}
            </button>
          )}
        </div>
      )}

      {onLoadPreset && (
        <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
          <span className="text-muted-foreground">{t.drawpad.presetsLabel}</span>
          {STARTER_PRESETS.map((preset) => (
            <button
              key={preset.key}
              type="button"
              onClick={() => onLoadPreset(preset.vertices, preset.mode)}
              className="rounded border border-border bg-secondary/40 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground transition-colors hover:border-brand/40 hover:text-foreground"
            >
              {t.drawpad.presets[preset.key]}
            </button>
          ))}
        </div>
      )}

      <div className="relative overflow-hidden rounded-lg border border-border bg-[oklch(0.13_0.015_255)]">
        <canvas
          ref={canvasRef}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
          onPointerLeave={onPointerLeave}
          onContextMenu={onRemoveVertexAt}
          onDoubleClick={onRemoveVertexAt}
          className={cn(
            "block w-full touch-none select-none",
            hoveredVertexIndex !== null ? "cursor-grab active:cursor-grabbing" : "cursor-crosshair"
          )}
          style={{ height }}
        />
        {empty && !isDrawing && (
          <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center gap-2 text-center">
            <MousePointer2 className="size-5 text-muted-foreground" />
            <p className="text-sm font-medium text-muted-foreground">
              {t.drawpad.placeholderTitle}
            </p>
            <p className="max-w-[230px] text-xs text-muted-foreground/70">
              {drawMode === "polyline" ? (
                t.drawpad.polylineHint
              ) : drawMode === "spline" ? (
                t.drawpad.splineHint
              ) : (
                <>
                  {t.drawpad.placeholderStart}{" "}
                  <span className="text-brand">{t.drawpad.placeholderHighlight}</span>{" "}
                  {t.drawpad.placeholderEnd}
                </>
              )}
            </p>
          </div>
        )}
      </div>

      {liveSummary && (
        <div className="flex items-center justify-between gap-2 rounded-md border border-brand/20 bg-brand/[0.06] px-2.5 py-1.5 text-[11px]">
          <div className="flex min-w-0 items-center gap-1.5">
            <span className="size-1.5 shrink-0 rounded-full bg-brand" />
            <span className="shrink-0 text-muted-foreground">{t.drawpad.livePreview}</span>
            <span className="truncate font-medium text-foreground">{liveSummary}</span>
          </div>
          {liveBadge && (
            <span
              className={cn(
                "shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium",
                analysis?.stable
                  ? "bg-emerald-500/15 text-emerald-400"
                  : "bg-amber-500/15 text-amber-300"
              )}
            >
              {liveBadge}
            </span>
          )}
        </div>
      )}

      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span className="tabular">
          {empty
            ? t.drawpad.waiting
            : (drawMode === "polyline" || drawMode === "spline") && vertices.length >= 2
              ? `${t.drawpad.points(vertices.length)} · ${t.drawpad.presetEditHint}`
              : t.drawpad.points(points.length)}
        </span>
        <button
          type="button"
          onClick={onClear}
          disabled={empty}
          className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 transition-colors hover:bg-accent hover:text-foreground disabled:pointer-events-none disabled:opacity-40"
        >
          <Eraser className="size-3.5" />
          {t.drawpad.clear}
        </button>
      </div>
    </div>
  );
}
