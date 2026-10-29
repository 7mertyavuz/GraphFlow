"use client";

import { useEffect, useRef, useState } from "react";
import { Maximize2, ScanSearch, X } from "lucide-react";
import {
  CandlestickSeries,
  createChart,
  LineSeries,
  type CandlestickData,
  type IChartApi,
  type ISeriesApi,
  type LineData,
  type Time,
  type WhitespaceData,
} from "lightweight-charts";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { useChart } from "@/hooks/useGraphFlowApi";
import { useI18n } from "@/i18n/LanguageProvider";
import { cn } from "@/lib/utils";
import {
  type ChartResponse,
  type Direction,
  type LedgerRow,
  type Match,
} from "@/services/endpoints";
import {
  formatAmplitude,
  formatDate,
  formatDecimal,
  formatPercentile,
  formatR,
} from "@/utils/formatters";

const COLORS = {
  up: "#34d399",
  down: "#f87171",
  dim: "#4b5563",
  blueprint: "#38bdf8",
  warp: "#fbbf24",
  axis: "#94a3b8",
};

interface MatchCardProps {
  match: Match;
  searchId: string | null;
  /** Backtest'te: bu eşleşmenin istatistikteki yeri (sayıldı mı, sonucu). */
  ledger?: LedgerRow | null;
  config?: string | null;
  direction?: Direction;
  directionLabel?: string;
  onSearchSimilar?: (match: Match) => void;
}

/**
 * Tek eşleşme karosu.
 *
 * Üç katman üst üste: bağlam barları (sönük), eşleşen pencere (canlı),
 * blueprint (aradığın şey) ve bükülmüş blueprint (motorun hizaladığı şey).
 * Geometrinin tamamı sunucudan gelir — arayüz koordinat uydurmaz.
 */
export function MatchCard({
  match,
  searchId,
  ledger,
  config,
  direction = "long",
  directionLabel,
  onSearchSimilar,
}: MatchCardProps) {
  const { t } = useI18n();
  const [expanded, setExpanded] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const contextRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const windowRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const blueprintRef = useRef<ISeriesApi<"Line"> | null>(null);
  const warpRef = useRef<ISeriesApi<"Line"> | null>(null);

  const { data, isLoading, isError } = useChart(match, searchId);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const chart = createChart(container, {
      layout: {
        background: { color: "transparent" },
        textColor: COLORS.axis,
        fontSize: 10,
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: "rgba(148,163,184,0.05)" },
        horzLines: { color: "rgba(148,163,184,0.05)" },
      },
      rightPriceScale: { borderVisible: false, scaleMargins: { top: 0.15, bottom: 0.12 } },
      timeScale: { borderVisible: false, visible: false },
      crosshair: { mode: 0 },
      handleScale: false,
      handleScroll: false,
      autoSize: true,
    });
    chartRef.current = chart;

    // Bağlam barları sönük: formasyon nereden geldi, sonra ne oldu.
    contextRef.current = chart.addSeries(CandlestickSeries, {
      upColor: "transparent",
      downColor: "transparent",
      borderColor: COLORS.dim,
      wickColor: COLORS.dim,
      borderVisible: true,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    windowRef.current = chart.addSeries(CandlestickSeries, {
      upColor: COLORS.up,
      downColor: COLORS.down,
      borderVisible: false,
      wickUpColor: COLORS.up,
      wickDownColor: COLORS.down,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    blueprintRef.current = chart.addSeries(LineSeries, {
      color: COLORS.blueprint,
      lineWidth: 2,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    warpRef.current = chart.addSeries(LineSeries, {
      color: COLORS.warp,
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: false,
    });

    return () => {
      chart.remove();
      chartRef.current = null;
      contextRef.current = null;
      windowRef.current = null;
      blueprintRef.current = null;
      warpRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!data || !contextRef.current || !windowRef.current) return;

    const bars = data.ohlcv as ChartResponse["ohlcv"];
    const toCandle = (bar: ChartResponse["ohlcv"][number]): CandlestickData => ({
      time: bar.time as Time,
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
    });
    const blank = (bar: ChartResponse["ohlcv"][number]): WhitespaceData => ({
      time: bar.time as Time,
    });

    const inWindow = (i: number) => i >= data.highlight_start && i <= data.highlight_end;

    contextRef.current.setData(bars.map((b, i) => (inWindow(i) ? blank(b) : toCandle(b))));
    windowRef.current.setData(bars.map((b, i) => (inWindow(i) ? toCandle(b) : blank(b))));

    blueprintRef.current?.setData(
      data.blueprint_overlay.map((p) => ({ time: p.time as Time, value: p.value })) as LineData[]
    );
    warpRef.current?.setData(
      data.warped_overlay.map((p) => ({ time: p.time as Time, value: p.value })) as LineData[]
    );

    chartRef.current?.timeScale().fitContent();
  }, [data]);

  return (
    <>
      <figure className="panel group flex flex-col overflow-hidden transition-colors hover:border-brand/30">
        <figcaption className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
          <div className="flex min-w-0 items-center gap-2">
            <span className="truncate text-sm font-semibold">{match.symbol}</span>
            <Badge tone="brand" className="tabular" title={t.card.percentileTitle}>
              {formatPercentile(match.percentile)}
            </Badge>
          </div>
          <div className="flex shrink-0 items-center gap-1.5">
            <span className="text-[10px] text-muted-foreground tabular">
              {match.timeframe} · {t.card.bars(match.window_length)}
            </span>
            {onSearchSimilar && (
              <button
                type="button"
                onClick={() => onSearchSimilar(match)}
                title={t.card.searchSimilarTitle}
                className="inline-flex items-center gap-1 rounded border border-border/70 bg-secondary/40 px-1.5 py-0.5 text-[10px] text-muted-foreground transition-colors hover:border-brand/40 hover:text-foreground"
              >
                <ScanSearch className="size-3" />
                <span className="hidden sm:inline">{t.card.searchSimilar}</span>
              </button>
            )}
            <button
              type="button"
              onClick={() => setExpanded(true)}
              title={t.card.expandChart}
              aria-label={t.card.expandChart}
              className="inline-flex items-center justify-center rounded border border-border/70 bg-secondary/40 p-1 text-muted-foreground transition-colors hover:border-brand/40 hover:text-foreground"
            >
              <Maximize2 className="size-3" />
            </button>
          </div>
        </figcaption>

        {/* Kap her zaman DOM'da: grafik kütüphanesi mount anında ölçülecek bir
            elemana ihtiyaç duyar. Yükleme durumunu erken return ile göstermek,
            container'ı hiç oluşturmadığı için grafiğin sessizce boş kalmasına
            yol açıyordu. */}
        <div
          className="relative h-[160px] w-full cursor-pointer"
          onClick={() => setExpanded(true)}
          title={t.card.expandChart}
        >
          <div ref={containerRef} className="absolute inset-0" />
          {isLoading && (
            <div className="absolute inset-2">
              <Skeleton className="size-full" />
            </div>
          )}
          {isError && (
            <div className="absolute inset-0 flex items-center justify-center text-[11px] text-muted-foreground">
              {t.card.chartFailed}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between gap-2 border-t border-border px-3 py-2 text-[10px] text-muted-foreground">
          <span className="tabular">
            {formatDate(match.start_time)} → {formatDate(match.end_time)}
          </span>
          <div className="flex shrink-0 items-center gap-2 tabular">
            <span title={t.card.amplitudeTitle}>{formatAmplitude(match.amplitude)}</span>
            <span className="text-border">|</span>
            <span title={t.card.correlationTitle}>r {formatDecimal(match.score, 2)}</span>
            {typeof data?.warp_amount === "number" && data.warp_amount > 2 && (
              <span
                className="text-warp"
                title={t.card.warpTitle}
              >
                ↔ {formatDecimal(data.warp_amount, 1)}
              </span>
            )}
          </div>
        </div>

        {ledger && config && (
          <LedgerLine row={ledger} config={config} directionLabel={directionLabel ?? ""} />
        )}
      </figure>

      {expanded && data && (
        <ExpandedMatchModal
          match={match}
          data={data}
          ledger={ledger}
          config={config}
          direction={direction}
          directionLabel={directionLabel}
          onClose={() => setExpanded(false)}
          onSearchSimilar={
            onSearchSimilar
              ? () => {
                  setExpanded(false);
                  onSearchSimilar(match);
                }
              : undefined
          }
        />
      )}
    </>
  );
}

function ExpandedMatchModal({
  match,
  data,
  ledger,
  config,
  direction = "long",
  directionLabel,
  onClose,
  onSearchSimilar,
}: {
  match: Match;
  data: ChartResponse;
  ledger?: LedgerRow | null;
  config?: string | null;
  direction?: Direction;
  directionLabel?: string;
  onClose: () => void;
  onSearchSimilar?: () => void;
}) {
  const { t } = useI18n();
  const modalChartRef = useRef<HTMLDivElement>(null);
  const hasBarriers = Boolean(ledger && config && match.atr > 0);
  const countedResult =
    ledger?.status === "counted" && config ? ledger.outcomes?.[config] : undefined;

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  useEffect(() => {
    const container = modalChartRef.current;
    if (!container) return;

    const chart = createChart(container, {
      layout: {
        background: { color: "transparent" },
        textColor: COLORS.axis,
        fontSize: 11,
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: "rgba(148,163,184,0.08)" },
        horzLines: { color: "rgba(148,163,184,0.08)" },
      },
      rightPriceScale: { borderVisible: true, scaleMargins: { top: 0.14, bottom: 0.14 } },
      timeScale: { borderVisible: true, visible: true, timeVisible: true },
      crosshair: { mode: 0 },
      handleScale: true,
      handleScroll: true,
      autoSize: true,
    });

    const contextSeries = chart.addSeries(CandlestickSeries, {
      upColor: "transparent",
      downColor: "transparent",
      borderColor: COLORS.dim,
      wickColor: COLORS.dim,
      borderVisible: true,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    const windowSeries = chart.addSeries(CandlestickSeries, {
      upColor: COLORS.up,
      downColor: COLORS.down,
      borderVisible: false,
      wickUpColor: COLORS.up,
      wickDownColor: COLORS.down,
      priceLineVisible: true,
      lastValueVisible: true,
    });

    const blueprintSeries = chart.addSeries(LineSeries, {
      color: COLORS.blueprint,
      lineWidth: 2,
      lineStyle: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: true,
    });

    const warpSeries = chart.addSeries(LineSeries, {
      color: COLORS.warp,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
      crosshairMarkerVisible: true,
    });

    const bars = data.ohlcv as ChartResponse["ohlcv"];
    const toCandle = (bar: ChartResponse["ohlcv"][number]): CandlestickData => ({
      time: bar.time as Time,
      open: bar.open,
      high: bar.high,
      low: bar.low,
      close: bar.close,
    });
    const blank = (bar: ChartResponse["ohlcv"][number]): WhitespaceData => ({
      time: bar.time as Time,
    });
    const inWindow = (i: number) => i >= data.highlight_start && i <= data.highlight_end;

    contextSeries.setData(bars.map((b, i) => (inWindow(i) ? blank(b) : toCandle(b))));
    windowSeries.setData(bars.map((b, i) => (inWindow(i) ? toCandle(b) : blank(b))));

    blueprintSeries.setData(
      data.blueprint_overlay.map((p) => ({ time: p.time as Time, value: p.value })) as LineData[]
    );
    warpSeries.setData(
      data.warped_overlay.map((p) => ({ time: p.time as Time, value: p.value })) as LineData[]
    );

    // Backtest modunda Triple-Barrier seviyeleri (C0, TP, SL ve çıkış izi)
    const i0 = data.highlight_end;
    const c0 = bars[i0]?.close;
    if (
      ledger &&
      config &&
      Number.isFinite(c0) &&
      c0 > 0 &&
      Number.isFinite(match.atr) &&
      match.atr > 0 &&
      i0 < bars.length - 1
    ) {
      const dirSign = direction === "short" ? -1 : 1;
      const kTp = config.startsWith("2:") ? 2.0 : 1.0;
      const kSl = 1.0;
      const tpPrice = c0 + dirSign * kTp * match.atr;
      const slPrice = Math.max(1e-9, c0 - dirSign * kSl * match.atr);

      const horizonBars = Math.max(1, Math.round(0.5 * match.window_length));
      const exitOffset = countedResult
        ? Math.min(horizonBars, Math.max(1, countedResult.exit_bar))
        : horizonBars;
      const iEnd = Math.min(bars.length - 1, i0 + exitOffset);

      if (iEnd > i0) {
        const tStart = bars[i0].time as Time;
        const tEnd = bars[iEnd].time as Time;

        const entryLine = chart.addSeries(LineSeries, {
          color: COLORS.axis,
          lineWidth: 1,
          lineStyle: 2,
          priceLineVisible: false,
          lastValueVisible: false,
          crosshairMarkerVisible: false,
        });
        entryLine.setData([
          { time: tStart, value: c0 },
          { time: tEnd, value: c0 },
        ]);

        const tpLine = chart.addSeries(LineSeries, {
          color: COLORS.up,
          lineWidth: 2,
          lineStyle: 2,
          priceLineVisible: false,
          lastValueVisible: true,
          crosshairMarkerVisible: false,
        });
        tpLine.setData([
          { time: tStart, value: tpPrice },
          { time: tEnd, value: tpPrice },
        ]);

        const slLine = chart.addSeries(LineSeries, {
          color: COLORS.down,
          lineWidth: 2,
          lineStyle: 2,
          priceLineVisible: false,
          lastValueVisible: true,
          crosshairMarkerVisible: false,
        });
        slLine.setData([
          { time: tStart, value: slPrice },
          { time: tEnd, value: slPrice },
        ]);

        if (countedResult) {
          const exitPrice = Math.max(1e-9, c0 + dirSign * countedResult.r * match.atr);
          const exitPath = chart.addSeries(LineSeries, {
            color: countedResult.r >= 0 ? COLORS.up : COLORS.down,
            lineWidth: 2,
            lineStyle: 0,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: true,
          });
          exitPath.setData([
            { time: tStart, value: c0 },
            { time: tEnd, value: exitPrice },
          ]);
        }
      }
    }

    chart.timeScale().fitContent();

    return () => {
      chart.remove();
    };
  }, [data, ledger, config, direction, match.atr, match.window_length, countedResult]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-xs"
      onClick={onClose}
    >
      <div
        className="panel flex w-full max-w-4xl flex-col overflow-hidden border border-border bg-background shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="text-base font-semibold">{match.symbol}</span>
            <Badge tone="brand" className="tabular">
              {formatPercentile(match.percentile)}
            </Badge>
            <span className="text-xs text-muted-foreground tabular">
              {match.timeframe} · {t.card.bars(match.window_length)} · {formatDate(match.start_time)} →{" "}
              {formatDate(match.end_time)}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {onSearchSimilar && (
              <button
                type="button"
                onClick={onSearchSimilar}
                className="inline-flex items-center gap-1.5 rounded-md border border-brand/40 bg-brand/10 px-2.5 py-1 text-xs font-medium text-brand transition-colors hover:bg-brand/20"
              >
                <ScanSearch className="size-3.5" />
                {t.card.searchSimilar}
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              aria-label={t.card.closeModal}
              className="inline-flex items-center justify-center rounded-md border border-border p-1.5 text-muted-foreground transition-colors hover:text-foreground"
            >
              <X className="size-4" />
            </button>
          </div>
        </div>

        <div className="relative h-[420px] w-full p-2">
          <div ref={modalChartRef} className="size-full" />
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-4 py-2.5 text-xs text-muted-foreground">
          <div className="flex items-center gap-4 tabular">
            <span>
              {t.card.amplitudeTitle}: <strong className="text-foreground">{formatAmplitude(match.amplitude)}</strong>
            </span>
            <span>
              r: <strong className="text-foreground">{formatDecimal(match.score, 3)}</strong>
            </span>
            {typeof data.warp_amount === "number" && (
              <span>
                DTW: <strong className="text-warp">↔ {formatDecimal(data.warp_amount, 1)}</strong>
              </span>
            )}
          </div>
          <div className="flex flex-wrap items-center gap-3 text-[11px]">
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-0.5 w-3 bg-[#38bdf8]" /> Blueprint
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block h-0.5 w-3 bg-[#fbbf24]" /> DTW
            </span>
            {hasBarriers && (
              <>
                <span className="flex items-center gap-1.5">
                  <span className="inline-block h-0.5 w-3 border-t border-dashed border-[#94a3b8]" />{" "}
                  {t.card.barrierEntry}
                </span>
                <span className="flex items-center gap-1.5 text-up">
                  <span className="inline-block h-0.5 w-3 bg-[#34d399]" /> {t.card.barrierTp}
                </span>
                <span className="flex items-center gap-1.5 text-down">
                  <span className="inline-block h-0.5 w-3 bg-[#f87171]" /> {t.card.barrierSl}
                </span>
              </>
            )}
          </div>
        </div>

        {ledger && config && (
          <LedgerLine row={ledger} config={config} directionLabel={directionLabel ?? ""} />
        )}
      </div>
    </div>
  );
}

/**
 * Eşleşmenin istatistikteki yeri. Toplam, ekrandaki olaylardan kurulur
 * (K-09); hangisinin nasıl sonuçlandığı ve hangisinin NEDEN sayılmadığı
 * kartta görünür — sayılmayanı gizlemek, örneklemin nasıl daraldığını
 * gizlemek olurdu.
 */
function LedgerLine({
  row,
  config,
  directionLabel,
}: {
  row: LedgerRow;
  config: string;
  directionLabel: string;
}) {
  const { t } = useI18n();
  const result = row.outcomes?.[config];

  if (row.status !== "counted" || !result) {
    const reason = (t.card.reasons as Record<string, string>)[row.status] ?? row.status;
    return (
      <div className="border-t border-border px-3 py-1.5 text-[10px] text-muted-foreground/80">
        {t.card.notCounted} {reason}
      </div>
    );
  }

  const label = (t.outcome.outcomes as Record<string, string>)[result.outcome] ?? result.outcome;
  const tone = result.r > 0 ? "text-up" : result.r < 0 ? "text-down" : "text-muted-foreground";
  return (
    <div
      className="flex items-center justify-between gap-2 border-t border-border px-3 py-1.5 text-[10px]"
      title={t.card.outcomeTitle(config, directionLabel)}
    >
      <span className="text-muted-foreground">
        {label} · {t.card.exitBar(result.exit_bar)}
      </span>
      <span className={cn("tabular font-semibold", tone)}>{formatR(result.r)}</span>
    </div>
  );
}
