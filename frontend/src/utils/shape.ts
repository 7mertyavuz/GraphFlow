/**
 * Şekil yardımcıları — yalnızca **görselleştirme** için.
 *
 * Normalizasyonun tek otoritesi motordur (K-02/K-04): istemci ham çizim
 * noktalarını gönderir, z-score'u sunucu yapar. Buradaki fonksiyonlar sorgu
 * üretmez; ekranda eğri çizmeye yarar.
 */

export type Point = { x: number; y: number };

/** Eşit aralıklı n noktaya indirger (x artan varsayılır). */
export function resample(points: Point[], n = 32): number[] {
  if (points.length === 0) return [];
  if (points.length === 1) return new Array(n).fill(points[0].y);

  const sorted = [...points].sort((a, b) => a.x - b.x);
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
