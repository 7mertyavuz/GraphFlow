"use client";

import { type ReturnDistribution } from "@/services/endpoints";
import { formatR } from "@/utils/formatters";

interface ReturnBandProps {
  distribution: ReturnDistribution;
}

/**
 * Gözlenen R dağılımının %80 bandı — beklentinin gizlediği şey.
 *
 * Beklenti bir ortalamadır. +0,1R'lik iki formasyondan biri "çoğu zaman
 * küçük kayıp, ara sıra büyük kazanç", diğeri "çoğu zaman küçük kazanç, ara
 * sıra felaket" olabilir; pozisyon boyutlandıran biri için bu fark
 * ortalamadan daha belirleyicidir.
 *
 * **Bu bir güven aralığı DEĞİLDİR** ve öyle sunulmaz: GA "ortalamayı ne kadar
 * bilmiyoruz"u, bant "olaylar ne kadar saçılıyor"u ölçer. Gölge dağılımın
 * aynı bandı altında durur — bant tek başına bir baseline değildir.
 */
export function ReturnBand({ distribution }: ReturnBandProps) {
  const { median, p10, p90, shadow_median, shadow_p10, shadow_p90 } = distribution;
  if (![median, p10, p90].every(Number.isFinite)) return null;

  const hasShadow =
    shadow_p10 !== null &&
    shadow_p10 !== undefined &&
    shadow_p90 !== null &&
    shadow_p90 !== undefined &&
    Number.isFinite(shadow_p10) &&
    Number.isFinite(shadow_p90);

  // Ortak ölçek: iki bant aynı eksende olmazsa karşılaştırma yanıltır.
  const lows = [p10, ...(hasShadow ? [shadow_p10 as number] : []), 0];
  const highs = [p90, ...(hasShadow ? [shadow_p90 as number] : []), 0];
  const min = Math.min(...lows);
  const max = Math.max(...highs);
  const span = Math.max(1e-9, max - min);
  const pct = (v: number) => ((v - min) / span) * 100;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          Getiri dağılımı · %80 bandı
        </h4>
        <span className="tabular text-[11px] text-muted-foreground">
          medyan {formatR(median)} · {formatR(p10)} … {formatR(p90)}
        </span>
      </div>

      <div className="rounded-lg border border-border bg-secondary/30 p-3">
        <Row label="Eşleşmeler" low={p10} mid={median} high={p90} pct={pct} tone="brand" />
        {hasShadow && (
          <Row
            label="Gölge"
            low={shadow_p10 as number}
            mid={(shadow_median ?? shadow_p10) as number}
            high={shadow_p90 as number}
            pct={pct}
            tone="muted"
          />
        )}

        {/* Sıfır çizgisi: bandın hangi tarafta durduğu tek bakışta okunmalı. */}
        <div className="relative mt-1 h-4">
          <div
            className="absolute top-0 h-2 w-px bg-border"
            style={{ left: `${pct(0)}%` }}
            aria-hidden
          />
          <span
            className="absolute top-2 -translate-x-1/2 text-[10px] text-muted-foreground"
            style={{ left: `${pct(0)}%` }}
          >
            0R
          </span>
        </div>
      </div>
    </div>
  );
}

function Row({
  label,
  low,
  mid,
  high,
  pct,
  tone,
}: {
  label: string;
  low: number;
  mid: number;
  high: number;
  pct: (v: number) => number;
  tone: "brand" | "muted";
}) {
  const left = pct(low);
  const width = Math.max(0.5, pct(high) - left);

  return (
    <div className="flex items-center gap-3 py-1.5">
      <span className="w-20 shrink-0 text-[11px] text-muted-foreground">{label}</span>
      <div className="relative h-3 flex-1">
        <div
          className={
            tone === "brand"
              ? "absolute h-3 rounded-full bg-brand/30"
              : "absolute h-3 rounded-full bg-muted-foreground/15"
          }
          style={{ left: `${left}%`, width: `${width}%` }}
        />
        <div
          className={
            tone === "brand"
              ? "absolute h-3 w-0.5 bg-brand"
              : "absolute h-3 w-0.5 bg-muted-foreground/50"
          }
          style={{ left: `${pct(mid)}%` }}
          title={`medyan ${mid.toFixed(2)}R`}
        />
      </div>
      <span className="tabular w-28 shrink-0 text-right text-[11px] text-muted-foreground">
        {formatR(low)} … {formatR(high)}
      </span>
    </div>
  );
}
