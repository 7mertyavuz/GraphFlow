export type OHLCV = {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
};

export type LinePoint = {
  time: number;
  value: number;
};

function timeToSeconds(t: number): number {
  return Math.floor(t / 1000);
}

export function buildBlueprintOverlay(
  queryVector: number[],
  ohlcv: OHLCV[],
  startIdx: number,
  endIdx: number
): LinePoint[] {
  if (!ohlcv.length || startIdx < 0 || endIdx >= ohlcv.length) return [];
  const window = ohlcv.slice(startIdx, endIdx + 1);
  const minP = Math.min(...window.map((d) => d.low));
  const maxP = Math.max(...window.map((d) => d.high));
  const range = Math.max(1e-9, maxP - minP);

  const qMin = Math.min(...queryVector);
  const qMax = Math.max(...queryVector);
  const qRange = Math.max(1e-9, qMax - qMin);

  const len = endIdx - startIdx;
  if (len <= 0) return [];

  return queryVector.map((v, i) => {
    const idx = Math.round(startIdx + (i / 31) * len);
    const bar = ohlcv[idx];
    const normalized = (v - qMin) / qRange;
    const value = minP + normalized * range;
    return { time: timeToSeconds(bar.time), value };
  });
}

export function buildWarpOverlay(
  queryVector: number[],
  warpPath: number[][] | null | undefined,
  ohlcv: OHLCV[],
  startIdx: number,
  endIdx: number
): LinePoint[] {
  if (!warpPath || !warpPath.length || !ohlcv.length) return [];
  const window = ohlcv.slice(startIdx, endIdx + 1);
  const minP = Math.min(...window.map((d) => d.low));
  const maxP = Math.max(...window.map((d) => d.high));
  const range = Math.max(1e-9, maxP - minP);

  const qMin = Math.min(...queryVector);
  const qMax = Math.max(...queryVector);
  const qRange = Math.max(1e-9, qMax - qMin);

  return warpPath
    .filter(([qIdx]) => qIdx >= 0 && qIdx < queryVector.length)
    .map(([qIdx, cIdx]) => {
      const bar = ohlcv[cIdx];
      if (!bar) return null;
      const normalized = (queryVector[qIdx] - qMin) / qRange;
      const value = minP + normalized * range;
      return { time: timeToSeconds(bar.time), value };
    })
    .filter((p): p is LinePoint => p !== null);
}
