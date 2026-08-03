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
        textColor: "currentColor",
      },
      grid: {
        vertLines: { color: "rgba(128,128,128,0.1)" },
        horzLines: { color: "rgba(128,128,128,0.1)" },
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
      color: "rgba(56,189,248,0.5)",
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
    <div className="flex flex-col rounded-md border border-border bg-card p-2">
      <div className="flex items-center justify-between px-1 py-1">
        <span className="font-semibold text-sm">{match.symbol}</span>
        <span className="text-xs text-muted-foreground">
          Vol: {formatAmplitude(match.amplitude)}
        </span>
      </div>
      <div ref={chartContainerRef} className="h-40 w-full" />
      <div className="px-1 py-1 text-xs text-muted-foreground">
        {match.timeframe} · {match.window_length} bar · skor{" "}
        {match.percentile.toFixed(1)}%
      </div>
    </div>
  );
}
