"use client";

import { useEffect, useRef } from "react";
import {
  createChart,
  CandlestickSeries,
  LineSeries,
  type IChartApi,
  type ISeriesApi,
  type CandlestickData,
  type LineData,
  type Time,
} from "lightweight-charts";
import { getChart } from "@/services/endpoints";
import { useQuery } from "@tanstack/react-query";
import { SkeletonChart } from "./SkeletonChart";
import { buildBlueprintOverlay, buildWarpOverlay, type OHLCV } from "@/utils/dtwCoords";
import { formatAmplitude } from "@/utils/formatters";
import { type paths } from "@/types/api";

type Match = paths["/api/search"]["post"]["responses"]["200"]["content"]["application/json"]["results"][number];

interface BlueprintChartProps {
  match: Match;
  queryVector: number[];
}

export function BlueprintChart({ match, queryVector }: BlueprintChartProps) {
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const blueprintSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const warpSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  const { data: chartData, isLoading } = useQuery({
    queryKey: ["chart", match.symbol, match.start_idx, match.end_idx, match.timeframe],
    queryFn: () =>
      getChart(match.symbol, {
        start: match.start_idx,
        end: match.end_idx,
        timeframe: match.timeframe,
      }),
  });

  useEffect(() => {
    if (!chartContainerRef.current) return;
    const chart = createChart(chartContainerRef.current, {
      layout: {
        background: { color: "transparent" },
        textColor: "#94a3b8",
      },
      grid: {
        vertLines: { color: "rgba(148,163,184,0.08)" },
        horzLines: { color: "rgba(148,163,184,0.08)" },
      },
      rightPriceScale: {
        borderVisible: false,
      },
      timeScale: {
        borderVisible: false,
        visible: false,
      },
      crosshair: { mode: 0 },
      autoSize: true,
    });
    chartRef.current = chart;

    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });
    candleSeriesRef.current = candleSeries;

    const blueprintSeries = chart.addSeries(LineSeries, {
      color: "rgba(56,189,248,0.55)",
      lineWidth: 2,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    blueprintSeriesRef.current = blueprintSeries;

    const warpSeries = chart.addSeries(LineSeries, {
      color: "#ef4444",
      lineWidth: 2,
      lineStyle: 2,
      lastValueVisible: false,
      priceLineVisible: false,
    });
    warpSeriesRef.current = warpSeries;

    return () => {
      chart.remove();
      chartRef.current = null;
      candleSeriesRef.current = null;
      blueprintSeriesRef.current = null;
      warpSeriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!chartData || !candleSeriesRef.current || !blueprintSeriesRef.current || !warpSeriesRef.current) return;

    const ohlcv = chartData.ohlcv as OHLCV[];
    const candleData: CandlestickData[] = ohlcv.map((d) => ({
      time: Math.floor(d.time / 1000) as Time,
      open: d.open,
      high: d.high,
      low: d.low,
      close: d.close,
    }));

    candleSeriesRef.current.setData(candleData);

    const start = chartData.highlight_start;
    const end = chartData.highlight_end;
    const blueprint = buildBlueprintOverlay(queryVector, ohlcv, start, end);
    const warp = buildWarpOverlay(queryVector, match.warp_path, ohlcv, start, end);

    blueprintSeriesRef.current.setData(blueprint as LineData[]);
    warpSeriesRef.current.setData(warp as LineData[]);

    chartRef.current?.timeScale().fitContent();
  }, [chartData, match.warp_path, queryVector]);

  if (isLoading || !chartData) return <SkeletonChart />;

  return (
    <div className="group flex flex-col overflow-hidden rounded-xl border border-border bg-card shadow-sm transition-shadow hover:shadow-md">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-sm">{match.symbol}</span>
          <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
            {match.percentile.toFixed(1)}%
          </span>
        </div>
        <span className="text-[10px] text-muted-foreground">
          {match.timeframe} · {match.window_length} bar
        </span>
      </div>
      <div className="relative h-44 w-full">
        <div ref={chartContainerRef} className="absolute inset-0" />
      </div>
      <div className="flex items-center justify-between border-t border-border px-3 py-2 text-[10px] text-muted-foreground">
        <span>Vol: {formatAmplitude(match.amplitude)}</span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-sky-400" />
          şablon
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-red-500" />
          warp
        </span>
      </div>
    </div>
  );
}
