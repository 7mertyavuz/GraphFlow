/**
 * Şekil yardımcıları — yalnızca **görselleştirme** için.
 *
 * Normalizasyonun tek otoritesi motordur (K-02/K-04): istemci ham çizim
 * noktalarını gönderir, z-score'u sunucu yapar. Buradaki fonksiyonlar sorgu
 * üretmez; ekranda eğri çizmeye yarar.
 */

export type Point = { x: number; y: number };

/**
 * x ekseninde tek değerli hâle getirir — ``y = f(x)``.
 *
 * Sıralamak **değil**: sola dönen bir el, sıralamada y değerlerinin yeniden
 * dizilmesine yani çizilmemiş bir şekle yol açar. Geri dönülen aralık
 * yeniden çiziliyor demektir; sonra yazan kazanır. Sunucudaki
 * ``engine/normalize/pipeline.py:monotone_xy`` ile aynı kuraldır — iki taraf
 * ayrışırsa önizleme ile aranan şekil ayrışır.
 */
export function monotoneByX(points: Point[]): Point[] {
  const out: Point[] = [];
  for (const p of points) {
    while (out.length > 0 && out[out.length - 1].x >= p.x) out.pop();
    out.push(p);
  }
  return out;
}

/** Eşit aralıklı n noktaya indirger. */
export function resample(points: Point[], n = 32): number[] {
  if (points.length === 0) return [];
  if (points.length === 1) return new Array(n).fill(points[0].y);

  const sorted = monotoneByX(points);
  if (sorted.length === 1) return new Array(n).fill(sorted[0].y);
  const minX = sorted[0].x;
  const maxX = sorted[sorted.length - 1].x;
  const span = Math.max(1e-9, maxX - minX);

  const out: number[] = [];
  let cursor = 0;
  for (let i = 0; i < n; i++) {
    const target = minX + (i / (n - 1)) * span;
    while (cursor < sorted.length - 2 && sorted[cursor + 1].x < target) cursor++;
    const a = sorted[cursor];
    const b = sorted[Math.min(cursor + 1, sorted.length - 1)];
    const denom = Math.max(1e-9, b.x - a.x);
    const t = Math.min(1, Math.max(0, (target - a.x) / denom));
    out.push(a.y + t * (b.y - a.y));
  }
  return out;
}

/** Bir diziyi 0–1 aralığına taşır (çizim ölçeği). */
export function normalizeRange(values: number[]): number[] {
  if (values.length === 0) return [];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(1e-9, max - min);
  return values.map((v) => (v - min) / range);
}

/** Çizimin "düz" olup olmadığı — σ ≈ 0 sorguyu motor reddeder. */
export function isFlat(values: number[], eps = 1e-6): boolean {
  if (values.length < 2) return true;
  const mean = values.reduce((s, v) => s + v, 0) / values.length;
  const variance =
    values.reduce((s, v) => s + (v - mean) ** 2, 0) / values.length;
  return Math.sqrt(variance) < eps;
}

/**
 * Düzgün bir SVG yolu (Catmull-Rom → kübik Bézier).
 * Kırık çizgi, elle çizilmiş bir formasyonu olduğundan daha gürültülü gösterir.
 */
export function smoothPath(values: number[], width: number, height: number, pad = 0): string {
  if (values.length < 2) return "";
  const normalized = normalizeRange(values);
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  const pts = normalized.map((v, i) => ({
    x: pad + (i / (normalized.length - 1)) * innerW,
    y: pad + (1 - v) * innerH,
  }));

  let d = `M ${pts[0].x.toFixed(2)} ${pts[0].y.toFixed(2)}`;
  for (let i = 0; i < pts.length - 1; i++) {
    const p0 = pts[Math.max(0, i - 1)];
    const p1 = pts[i];
    const p2 = pts[i + 1];
    const p3 = pts[Math.min(pts.length - 1, i + 2)];
    const c1x = p1.x + (p2.x - p0.x) / 6;
    const c1y = p1.y + (p2.y - p0.y) / 6;
    const c2x = p2.x - (p3.x - p1.x) / 6;
    const c2y = p2.y - (p3.y - p1.y) / 6;
    d += ` C ${c1x.toFixed(2)} ${c1y.toFixed(2)}, ${c2x.toFixed(2)} ${c2y.toFixed(
      2
    )}, ${p2.x.toFixed(2)} ${p2.y.toFixed(2)}`;
  }
  return d;
}

export interface OverlayLine {
  x1: number;
  y1: number;
  x2: number;
  y2: number;
}

export interface DrawingAnalysis {
  peaks: Point[];
  troughs: Point[];
  upperLine: OverlayLine | null;
  lowerLine: OverlayLine | null;
  poleLine: OverlayLine | null;
  parabolicCurve: Point[] | null;
  stable: boolean;
  badgeTr: string;
  badgeEn: string;
  summaryTr: string | null;
  summaryEn: string | null;
}

function fitLine(pts: Point[]): { m: number; b: number } | null {
  if (pts.length < 2) return null;
  const n = pts.length;
  let sx = 0,
    sy = 0,
    sxy = 0,
    sxx = 0;
  for (const p of pts) {
    sx += p.x;
    sy += p.y;
    sxy += p.x * p.y;
    sxx += p.x * p.x;
  }
  const denom = sxx - (sx * sx) / n;
  if (Math.abs(denom) < 1e-12) return null;
  const m = (sxy - (sx * sy) / n) / denom;
  const b = (sy - m * sx) / n;
  return { m, b };
}

/**
 * Ortonormal Legendre bazı (P0, P1, P2) ile 2. derece parabolik uyum (K-24).
 * `engine/search/constraints.py:_quad_r2` fonksiyonunun istemci karşılığıdır.
 */
function fitParabola(vals: number[]): { r2: number; a2: number; fitted: number[] } | null {
  const m = vals.length;
  if (m < 6) return null;
  const t = Array.from({ length: m }, (_, i) => -1 + (2 * i) / (m - 1));
  const norm0 = Math.sqrt(m);
  const p0 = t.map(() => 1 / norm0);

  const norm1 = Math.sqrt(t.reduce((s, x) => s + x * x, 0)) || 1;
  const p1 = t.map((x) => x / norm1);

  const raw2 = t.map((x) => 1.5 * x * x - 0.5);
  const dot20 = raw2.reduce((s, v, i) => s + v * p0[i], 0);
  const ortho2 = raw2.map((v, i) => v - dot20 * p0[i]);
  const norm2 = Math.sqrt(ortho2.reduce((s, v) => s + v * v, 0)) || 1;
  const p2 = ortho2.map((v) => v / norm2);

  const c0 = vals.reduce((s, v, i) => s + v * p0[i], 0);
  const c1 = vals.reduce((s, v, i) => s + v * p1[i], 0);
  const c2 = vals.reduce((s, v, i) => s + v * p2[i], 0);

  const mean = vals.reduce((s, v) => s + v, 0) / m;
  const ssTot = vals.reduce((s, v) => s + (v - mean) * (v - mean), 0);
  if (ssTot < 1e-12) return null;

  const ssReg = c1 * c1 + c2 * c2;
  const r2 = Math.min(1, Math.max(0, ssReg / ssTot));
  const fitted = Array.from({ length: m }, (_, i) => c0 * p0[i] + c1 * p1[i] + c2 * p2[i]);
  return { r2, a2: c2, fitted };
}

/**
 * Çizim üzerinde canlı yapısal/zarf/eğrisellik önizlemesi (K-20 / K-21 / K-22 / K-24).
 *
 * Motorun `engine/search/constraints.py` içindeki belirgin uç (prominence >= 0.5σ),
 * zarf dokunuşu (width=2), direk+gövde (K-22) ve parabolik çanak/kulp (K-24)
 * kurallarının birebir istemci önizleme karşılığıdır.
 */
export function analyzeDrawing(points: Point[]): DrawingAnalysis | null {
  const sorted = monotoneByX(points);
  if (sorted.length < 2) return null;
  const minX = sorted[0].x;
  const maxX = sorted[sorted.length - 1].x;
  const spanX = maxX - minX;
  if (spanX < 0.05) return null;

  const N = 32;
  const yRaw = resample(sorted, N);
  if (yRaw.length !== N || isFlat(yRaw)) return null;

  const mean = yRaw.reduce((a, b) => a + b, 0) / N;
  const std = Math.sqrt(yRaw.reduce((a, b) => a + (b - mean) ** 2, 0) / N);
  if (std < 1e-6) return null;
  const z = yRaw.map((v) => (v - mean) / std);

  const gridX = (i: number) => minX + (i / (N - 1)) * spanX;
  const gridPt = (i: number): Point => ({ x: gridX(i), y: yRaw[i] });

  // 1) Belirgin tepe ve dipler (prominence >= 0.5σ)
  const findProminent = (arr: number[]): number[] => {
    const cands: number[] = [];
    for (let i = 1; i < N - 1; i++) {
      if (
        arr[i] >= arr[i - 1] &&
        arr[i] >= arr[i + 1] &&
        (arr[i] > arr[i - 1] || arr[i] > arr[i + 1])
      ) {
        cands.push(i);
      }
    }
    const kept: number[] = [];
    for (const i of cands) {
      let lBase = arr[i];
      for (let j = i - 1; j >= 0; j--) {
        if (arr[j] > arr[i]) break;
        if (arr[j] < lBase) lBase = arr[j];
      }
      let rBase = arr[i];
      for (let j = i + 1; j < N; j++) {
        if (arr[j] > arr[i]) break;
        if (arr[j] < rBase) rBase = arr[j];
      }
      if (arr[i] - Math.max(lBase, rBase) >= 0.5) kept.push(i);
    }
    return kept;
  };

  const peakIdx = findProminent(z);
  const troughIdx = findProminent(z.map((v) => -v));
  const peaks = peakIdx.map(gridPt);
  const troughs = troughIdx.map(gridPt);

  // 2) K-22 Direk + gövde kontrolü
  const POLE_K = 11;
  const BODY_START = 8;
  const leftDisp = z[POLE_K - 1] - z[0];
  const bodySlice = z.slice(POLE_K - 1);
  const bodySpan = Math.max(...bodySlice) - Math.min(...bodySlice);
  const hasPole = Math.abs(leftDisp) >= 1.8 && bodySpan <= Math.abs(leftDisp) * 0.72;

  // 3) K-24 Parabolik çanak / fincan-kulp kontrolü
  let parabolicCurve: Point[] | null = null;
  let curvatureSummaryTr: string | null = null;
  let curvatureSummaryEn: string | null = null;

  if (!hasPole && peakIdx.length + troughIdx.length <= 3) {
    const fullQuad = fitParabola(z);
    const cupQuad = fitParabola(z.slice(0, 23));
    const lRimFull = Math.max(...z.slice(0, 4));
    const rRimFull = Math.max(...z.slice(N - 4));
    const midMinFull = Math.min(...z.slice(8, 24));

    const lRimCup = Math.max(...z.slice(0, 4));
    const rRimCup = Math.max(...z.slice(19, 25));
    const midMinCup = Math.min(...z.slice(6, 18));
    const handleMin = Math.min(...z.slice(23));
    const cupDepth = Math.max(0.5, 0.5 * (lRimCup + rRimCup) - midMinCup);
    const handleRetrace = (rRimCup - handleMin) / cupDepth;

    if (
      cupQuad &&
      cupQuad.a2 > 0.35 &&
      cupQuad.r2 >= 0.58 &&
      Math.abs(lRimCup - rRimCup) <= 1.1 &&
      rRimCup - midMinCup >= 1.1 &&
      handleRetrace >= 0.12 &&
      handleRetrace <= 0.75 &&
      troughIdx.length >= 1
    ) {
      const cupRaw = fitParabola(yRaw.slice(0, 23));
      if (cupRaw) {
        parabolicCurve = cupRaw.fitted.map((val, i) => ({
          x: gridX(i),
          y: Math.min(1, Math.max(0, val)),
        }));
      }
      const r2Str = cupQuad.r2.toFixed(2);
      curvatureSummaryTr = `fincan + kulp (parabolik R²=${r2Str})`;
      curvatureSummaryEn = `cup & handle (parabolic R²=${r2Str})`;
    } else if (
      fullQuad &&
      fullQuad.a2 > 0.4 &&
      fullQuad.r2 >= 0.62 &&
      Math.abs(lRimFull - rRimFull) <= 1.0 &&
      Math.min(lRimFull, rRimFull) - midMinFull >= 1.1
    ) {
      const fullRaw = fitParabola(yRaw);
      if (fullRaw) {
        parabolicCurve = fullRaw.fitted.map((val, i) => ({
          x: gridX(i),
          y: Math.min(1, Math.max(0, val)),
        }));
      }
      const r2Str = fullQuad.r2.toFixed(2);
      curvatureSummaryTr = `çanak eğrisi (parabolik R²=${r2Str})`;
      curvatureSummaryEn = `rounding bottom (parabolic R²=${r2Str})`;
    }
  }

  const segStart = hasPole ? BODY_START : 0;
  const segLen = N - segStart;
  const highs: number[] = [];
  const lows: number[] = [];
  for (let i = segStart + 1; i < N - 1; i++) {
    const a = Math.max(segStart, i - 2);
    const b = Math.min(N - 1, i + 2);
    let maxW = -Infinity;
    let minW = Infinity;
    for (let k = a; k <= b; k++) {
      if (z[k] > maxW) maxW = z[k];
      if (z[k] < minW) minW = z[k];
    }
    if (z[i] >= maxW - 1e-9 && (z[i] > z[i - 1] || z[i] > z[i + 1])) highs.push(i);
    if (z[i] <= minW + 1e-9 && (z[i] < z[i - 1] || z[i] < z[i + 1])) lows.push(i);
  }

  let upperLine: OverlayLine | null = null;
  let lowerLine: OverlayLine | null = null;
  let poleLine: OverlayLine | null = null;

  if (hasPole) {
    poleLine = {
      x1: gridX(0),
      y1: yRaw[0],
      x2: gridX(POLE_K - 1),
      y2: yRaw[POLE_K - 1],
    };
  }

  const xStart = gridX(segStart);
  const xEnd = gridX(N - 1);
  const uFit = !parabolicCurve ? fitLine(highs.map(gridPt)) : null;
  const lFit = !parabolicCurve ? fitLine(lows.map(gridPt)) : null;
  if (uFit) {
    upperLine = {
      x1: xStart,
      y1: Math.min(1, Math.max(0, uFit.m * xStart + uFit.b)),
      x2: xEnd,
      y2: Math.min(1, Math.max(0, uFit.m * xEnd + uFit.b)),
    };
  }
  if (lFit) {
    lowerLine = {
      x1: xStart,
      y1: Math.min(1, Math.max(0, lFit.m * xStart + lFit.b)),
      x2: xEnd,
      y2: Math.min(1, Math.max(0, lFit.m * xEnd + lFit.b)),
    };
  }

  // Z-score eğimleri
  const uFitZ = fitLine(
    highs.map((idx) => ({ x: (idx - segStart) / Math.max(1, segLen - 1), y: z[idx] }))
  );
  const lFitZ = fitLine(
    lows.map((idx) => ({ x: (idx - segStart) / Math.max(1, segLen - 1), y: z[idx] }))
  );

  let summaryTr: string | null = null;
  let summaryEn: string | null = null;
  let stable = false;

  if (curvatureSummaryTr && curvatureSummaryEn) {
    summaryTr = curvatureSummaryTr;
    summaryEn = curvatureSummaryEn;
    stable = true;
  } else if (hasPole && uFitZ && lFitZ) {
    const dirTr = leftDisp > 0 ? "yükselen direk" : "düşen direk";
    const dirEn = leftDisp > 0 ? "upward pole" : "downward pole";
    const diff = lFitZ.m - uFitZ.m;
    const convTr = diff > 0.7 ? "daralan gövde" : "paralel kanal";
    const convEn = diff > 0.7 ? "narrowing body" : "parallel channel";
    summaryTr = `${dirTr} · ${convTr}`;
    summaryEn = `${dirEn} · ${convEn}`;
    stable = true;
  } else if (peaks.length > 0 || troughs.length > 0) {
    const partsTr: string[] = [];
    const partsEn: string[] = [];

    // Klasik dönüş ilişkileri (OBO, TOBO, Çift Tepe, Çift Dip)
    if (peakIdx.length === 3) {
      const [p0, p1, p2] = peakIdx.map((idx) => z[idx]);
      if (p1 > p0 + 0.25 && p1 > p2 + 0.25 && Math.abs(p0 - p2) <= 0.65) {
        partsTr.push("3 belirgin tepe · ortadaki en yüksek");
        partsEn.push("3 prominent peaks · middle highest");
        stable = true;
      } else {
        partsTr.push("3 tepe");
        partsEn.push("3 peaks");
      }
    } else if (peakIdx.length === 2) {
      const [p0, p1] = peakIdx.map((idx) => z[idx]);
      if (Math.abs(p0 - p1) <= 0.55) {
        partsTr.push("2 eş tepe");
        partsEn.push("2 equal peaks");
        stable = true;
      } else {
        partsTr.push("2 tepe");
        partsEn.push("2 peaks");
      }
    } else if (peaks.length > 0) {
      partsTr.push(`${peaks.length} tepe`);
      partsEn.push(`${peaks.length} peak${peaks.length > 1 ? "s" : ""}`);
    }

    if (troughIdx.length === 3) {
      const [t0, t1, t2] = troughIdx.map((idx) => z[idx]);
      if (t1 < t0 - 0.25 && t1 < t2 - 0.25 && Math.abs(t0 - t2) <= 0.65) {
        partsTr.push("3 belirgin dip · ortadaki en derin");
        partsEn.push("3 prominent troughs · middle deepest");
        stable = true;
      } else {
        partsTr.push("3 dip");
        partsEn.push("3 troughs");
      }
    } else if (troughIdx.length === 2) {
      const [t0, t1] = troughIdx.map((idx) => z[idx]);
      if (Math.abs(t0 - t1) <= 0.55) {
        partsTr.push("2 eş dip");
        partsEn.push("2 equal troughs");
        stable = true;
      } else {
        partsTr.push("2 dip");
        partsEn.push("2 troughs");
      }
    } else if (troughs.length > 0) {
      partsTr.push(`${troughs.length} dip`);
      partsEn.push(`${troughs.length} trough${troughs.length > 1 ? "s" : ""}`);
    }

    if (uFitZ && lFitZ) {
      const thr = 0.8;
      const uTr =
        Math.abs(uFitZ.m) <= thr
          ? "yatay direnç"
          : uFitZ.m > 0
            ? "yükselen tepeler"
            : "alçalan tepeler";
      const lTr =
        Math.abs(lFitZ.m) <= thr
          ? "yatay destek"
          : lFitZ.m > 0
            ? "yükselen dipler"
            : "alçalan dipler";
      const uEn =
        Math.abs(uFitZ.m) <= thr
          ? "flat resistance"
          : uFitZ.m > 0
            ? "rising highs"
            : "falling highs";
      const lEn =
        Math.abs(lFitZ.m) <= thr
          ? "flat support"
          : lFitZ.m > 0
            ? "rising lows"
            : "falling lows";
      const diff = lFitZ.m - uFitZ.m;
      const convTr = diff > 0.7 ? " · daralan" : "";
      const convEn = diff > 0.7 ? " · narrowing" : "";
      partsTr.push(`${uTr}, ${lTr}${convTr}`);
      partsEn.push(`${uEn}, ${lEn}${convEn}`);
      if (diff > 0.7 && highs.length >= 2 && lows.length >= 2) {
        stable = true;
      }
    }
    summaryTr = partsTr.join(" · ");
    summaryEn = partsEn.join(" · ");
  }

  return {
    peaks,
    troughs,
    upperLine,
    lowerLine,
    poleLine,
    parabolicCurve,
    stable,
    badgeTr: stable ? "Kararlı ✓" : "Esnek okuma",
    badgeEn: stable ? "Stable ✓" : "Flexible read",
    summaryTr,
    summaryEn,
  };
}
