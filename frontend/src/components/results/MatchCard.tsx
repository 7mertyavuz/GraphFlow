"use client";

import { useEffect, useRef } from "react";
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
import { type ChartResponse, type Match } from "@/services/endpoints";
import {
  formatAmplitude,
  formatDate,
  formatDecimal,
  formatPercentile,
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
}

/**
 * Tek eşleşme karosu.
 *
 * Üç katman üst üste: bağlam barları (sönük), eşleşen pencere (canlı),
 * blueprint (aradığın şey) ve bükülmüş blueprint (motorun hizaladığı şey).
 * Geometrinin tamamı sunucudan gelir — arayüz koordinat uydurmaz.
 */
export function MatchCard({ match, searchId }: MatchCardProps) {
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
    <figure className="panel group flex flex-col overflow-hidden transition-colors hover:border-brand/30">
      <figcaption className="flex items-center justify-between gap-2 border-b border-border px-3 py-2">
        <div className="flex min-w-0 items-center gap-2">
          <span className="truncate text-sm font-semibold">{match.symbol}</span>
          <Badge tone="brand" className="tabular" title="Sorgunun null dağılımındaki yüzdelik dilim">
            {formatPercentile(match.percentile)}
          </Badge>
        </div>
        <span className="shrink-0 text-[10px] text-muted-foreground tabular">
          {match.timeframe} · {match.window_length} bar
        </span>
      </figcaption>

      {/* Kap her zaman DOM'da: grafik kütüphanesi mount anında ölçülecek bir
          elemana ihtiyaç duyar. Yükleme durumunu erken return ile göstermek,
          container'ı hiç oluşturmadığı için grafiğin sessizce boş kalmasına
          yol açıyordu. */}
      <div className="relative h-[160px] w-full">
        <div ref={containerRef} className="absolute inset-0" />
        {isLoading && (
          <div className="absolute inset-2">
            <Skeleton className="size-full" />
          </div>
        )}
        {isError && (
          <div className="absolute inset-0 flex items-center justify-center text-[11px] text-muted-foreground">
            Grafik yüklenemedi
          </div>
        )}
      </div>

      <div className="flex items-center justify-between gap-2 border-t border-border px-3 py-2 text-[10px] text-muted-foreground">
        <span className="tabular">
          {formatDate(match.start_time)} → {formatDate(match.end_time)}
        </span>
        <div className="flex shrink-0 items-center gap-2 tabular">
          <span title="Pencere içi toplam hareket">{formatAmplitude(match.amplitude)}</span>
          <span className="text-border">|</span>
          <span title="Pearson korelasyonu (Aşama 1 skoru)">r {formatDecimal(match.score, 2)}</span>
          {typeof data?.warp_amount === "number" && data.warp_amount > 2 && (
            <span
              className="text-warp"
              title="Yüksek bükülme: eşleşme ağır zaman esnetmesiyle kuruldu"
            >
              ↔ {formatDecimal(data.warp_amount, 1)}
            </span>
          )}
        </div>
      </div>
    </figure>
  );
}
