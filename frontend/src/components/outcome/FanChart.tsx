"use client";

import { useCallback, useState } from "react";

import { useI18n } from "@/i18n/LanguageProvider";
import { cn } from "@/lib/utils";
import { type Direction, type FanReport } from "@/services/endpoints";
import { formatATR, formatDecimal, formatPercent } from "@/utils/formatters";

interface FanChartProps {
  paths: FanReport;
  direction: Direction;
  kTp: number;
  kSl: number;
  dimmed?: boolean;
}

type Series = (number | null)[];

const HEIGHT = 200;
const PAD = { left: 44, right: 34, top: 10, bottom: 22 };

/**
 * İleri yol fanı — eşleşmelerin fanı gölgenin fanıyla aynı eksende.
 *
 * Geometriyi sunucu ölçer (engine/outcome/paths.py); burada yalnız çizilir.
 * Yüzdelikler, ATR birimi ve zaman bariyerine göre normalize eksen oradan
 * gelir. Ölçülemeyen noktalar (``null``) çizgide boşluk olarak kalır —
 * ara değerlemeyle kapatılmaz.
 *
 * TP/SL çizgileri seçili konfigürasyonun bariyerleridir; fan onlarda
 * durmaz. İstatistik paneli "işlem ne oldu" sorusunu, fan "fiyat ne yaptı"
 * sorusunu yanıtlar.
 */
export function FanChart({ paths, direction, kTp, kSl, dimmed }: FanChartProps) {
  const { t } = useI18n();
  const [width, setWidth] = useState(0);
  const [hover, setHover] = useState<number | null>(null);

  // Genişlik bağlanırken hemen ölçülür: ResizeObserver'ın ilk bildirimi bir
  // boyama karesini bekler, görünmeyen sekmede grafik hiç çizilmezdi.
  const ref = useCallback((el: HTMLDivElement | null) => {
    if (!el) return;
    setWidth(el.getBoundingClientRect().width);
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const { matches, shadow } = paths;
  const grid = matches.u.length;
  if (grid < 2) return null;

  const sign = direction === "long" ? 1 : -1;
  const tp = sign * kTp;
  const sl = -sign * kSl;

  const values = [
    ...finite(matches.p10),
    ...finite(matches.p90),
    ...finite(shadow.p25),
    ...finite(shadow.p75),
    tp,
    sl,
    0,
  ];
  const rawMin = Math.min(...values);
  const rawMax = Math.max(...values);
  const pad = (rawMax - rawMin) * 0.08 || 1;
  const yMin = rawMin - pad;
  const yMax = rawMax + pad;

  const plotW = Math.max(width - PAD.left - PAD.right, 1);
  const plotH = HEIGHT - PAD.top - PAD.bottom;
  const x = (u: number) => PAD.left + u * plotW;
  const y = (v: number) => PAD.top + ((yMax - v) / (yMax - yMin)) * plotH;

  const ticks = niceTicks(yMin, yMax);
  const index = hover ?? grid - 1;
  const u = matches.u;

  const onPointerMove = (event: React.PointerEvent<SVGSVGElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    const rel = (event.clientX - rect.left - PAD.left) / plotW;
    setHover(Math.min(grid - 1, Math.max(0, Math.round(rel * (grid - 1)))));
  };

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          {t.fan.title}
        </h4>
        <span className="tabular text-[11px] text-muted-foreground">
          {t.fan.counts(matches.n[0], matches.n[grid - 1])}
        </span>
      </div>
      <p className="text-[11px] leading-relaxed text-muted-foreground/80">{t.fan.subtitle}</p>

      <div ref={ref} className={cn("w-full", dimmed && "opacity-60")}>
        {width > 0 && (
          <svg
            width={width}
            height={HEIGHT}
            role="img"
            aria-label={t.fan.aria}
            className="block touch-none select-none"
            onPointerMove={onPointerMove}
            onPointerLeave={() => setHover(null)}
          >
            {ticks.map((tick) => (
              <g key={tick}>
                <line
                  x1={PAD.left}
                  x2={PAD.left + plotW}
                  y1={y(tick)}
                  y2={y(tick)}
                  className={tick === 0 ? "stroke-muted-foreground/50" : "stroke-border"}
                  strokeWidth={1}
                />
                <text
                  x={PAD.left - 6}
                  y={y(tick)}
                  dy="0.32em"
                  textAnchor="end"
                  className="fill-muted-foreground tabular text-[10px]"
                >
                  {formatDecimal(tick, Number.isInteger(tick) ? 0 : 1)}
                </text>
              </g>
            ))}

            <path d={area(u, matches.p10, matches.p90, x, y)} className="fill-brand/10" />
            <path d={area(u, matches.p25, matches.p75, x, y)} className="fill-brand/25" />
            <path d={line(u, matches.p50, x, y)} className="fill-none stroke-brand" strokeWidth={2} />

            {/* Gölge eşleşme bantlarının ÜSTÜNDE, dolgusuz: altta kalırsa
                kıyas görünmez olur — fanın varlık sebebi o kıyas. */}
            <path
              d={`${line(u, shadow.p25, x, y)}${line(u, shadow.p75, x, y)}`}
              className="fill-none stroke-muted-foreground/70"
              strokeWidth={1}
              strokeDasharray="1 3"
            />
            <path
              d={line(u, shadow.p50, x, y)}
              className="fill-none stroke-foreground/80"
              strokeWidth={1.5}
              strokeDasharray="5 3"
            />

            <Barrier y={y(tp)} x1={PAD.left} x2={PAD.left + plotW} label={t.fan.tp} tone="up" />
            <Barrier y={y(sl)} x1={PAD.left} x2={PAD.left + plotW} label={t.fan.sl} tone="down" />

            <line
              x1={x(u[index])}
              x2={x(u[index])}
              y1={PAD.top}
              y2={PAD.top + plotH}
              className="stroke-foreground/30"
              strokeWidth={1}
            />
            {matches.p50[index] !== null && (
              <circle cx={x(u[index])} cy={y(matches.p50[index]!)} r={3} className="fill-brand" />
            )}

            <text x={PAD.left} y={HEIGHT - 6} className="fill-muted-foreground text-[10px]">
              {t.fan.xStart}
            </text>
            <text
              x={PAD.left + plotW / 2}
              y={HEIGHT - 6}
              textAnchor="middle"
              className="fill-muted-foreground text-[10px]"
            >
              {t.fan.xMid}
            </text>
            <text
              x={PAD.left + plotW}
              y={HEIGHT - 6}
              textAnchor="end"
              className="fill-muted-foreground text-[10px]"
            >
              {t.fan.xEnd}
            </text>
          </svg>
        )}
      </div>

      <p className="tabular text-[11px] text-muted-foreground">
        <span className="text-foreground/80">{t.fan.at(formatPercent(u[index]))}:</span>{" "}
        {t.fan.matchesAt(
          formatATR(matches.p50[index]),
          formatATR(matches.p25[index]),
          formatATR(matches.p75[index])
        )}
        {" · "}
        {t.fan.shadowAt(formatATR(shadow.p50[index]))}
      </p>

      <Legend />
      <p className="text-[11px] leading-relaxed text-muted-foreground/70">{t.fan.note}</p>
    </div>
  );
}

function Legend() {
  const { t } = useI18n();
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
      <span className="flex items-center gap-1.5">
        <span className="h-0.5 w-4 rounded bg-brand" />
        {t.fan.matches} · {t.fan.median}
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-2.5 w-4 rounded-sm bg-brand/25" />
        {t.fan.band50}
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-2.5 w-4 rounded-sm bg-brand/10" />
        {t.fan.band80}
      </span>
      <span className="flex items-center gap-1.5">
        <span className="w-4 border-t-[1.5px] border-dashed border-foreground/80" />
        {t.fan.shadow} · {t.fan.median}
      </span>
      <span className="flex items-center gap-1.5">
        <span className="h-2.5 w-4 border-y border-dotted border-muted-foreground" />
        {t.fan.shadow} · {t.fan.band50}
      </span>
    </div>
  );
}

function Barrier({
  y,
  x1,
  x2,
  label,
  tone,
}: {
  y: number;
  x1: number;
  x2: number;
  label: string;
  tone: "up" | "down";
}) {
  const stroke = tone === "up" ? "stroke-up/60" : "stroke-down/60";
  const fill = tone === "up" ? "fill-up" : "fill-down";
  return (
    <g>
      <line x1={x1} x2={x2} y1={y} y2={y} className={stroke} strokeWidth={1} strokeDasharray="2 3" />
      <text x={x2 + 6} y={y} dy="0.32em" className={cn(fill, "text-[10px] font-medium")}>
        {label}
      </text>
    </g>
  );
}

function finite(series: Series): number[] {
  return series.filter((v): v is number => v !== null && Number.isFinite(v));
}

/** Ölçülemeyen noktada çizgi kopar; iki yanı birleştirilmez. */
function line(u: number[], series: Series, x: (u: number) => number, y: (v: number) => number) {
  let d = "";
  let pen = false;
  series.forEach((v, i) => {
    if (v === null) {
      pen = false;
      return;
    }
    d += `${pen ? "L" : "M"}${x(u[i]).toFixed(1)},${y(v).toFixed(1)}`;
    pen = true;
  });
  return d;
}

/** Bant: iki sınırın da ölçüldüğü her kesintisiz parça ayrı çokgen. */
function area(
  u: number[],
  lo: Series,
  hi: Series,
  x: (u: number) => number,
  y: (v: number) => number
) {
  const runs: number[][] = [];
  let run: number[] = [];
  lo.forEach((v, i) => {
    if (v !== null && hi[i] !== null) run.push(i);
    else if (run.length) {
      runs.push(run);
      run = [];
    }
  });
  if (run.length) runs.push(run);

  return runs
    .filter((r) => r.length > 1)
    .map((r) => {
      const top = r.map((i) => `${x(u[i]).toFixed(1)},${y(hi[i]!).toFixed(1)}`);
      const bottom = [...r].reverse().map((i) => `${x(u[i]).toFixed(1)},${y(lo[i]!).toFixed(1)}`);
      return `M${top.join("L")}L${bottom.join("L")}Z`;
    })
    .join("");
}

/** En fazla ~6 çizgi: 0,5 / 1 / 2 / 5 adımlarından ilk uyan. */
function niceTicks(min: number, max: number): number[] {
  const span = max - min;
  const step = [0.5, 1, 2, 5, 10, 20].find((s) => span / s <= 6) ?? 50;
  const ticks: number[] = [];
  for (let v = Math.ceil(min / step) * step; v <= max; v += step) {
    ticks.push(Math.round(v * 100) / 100);
  }
  return ticks;
}
