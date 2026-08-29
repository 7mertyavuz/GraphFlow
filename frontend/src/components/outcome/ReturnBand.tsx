"use client";

import { type ReturnDistribution } from "@/services/endpoints";
import { formatPercent, formatR } from "@/utils/formatters";

interface ReturnBandProps {
  distribution: ReturnDistribution;
}

/**
 * Medyan R ve artıda kapanma oranı — beklentinin gizlediği şey.
 *
 * Üçlü bariyerde ortalama, dağılımın şeklini tamamen gizler: OBO 2:1'de
 * beklenti +0,015R iken medyan **−1,000R**'dir. Yani "beklenti hafif artıda"
 * cümlesinin arkasında, olayların yarısından fazlasının tam stop yediği bir
 * deneyim vardır. Ortalamaya bakan biri bunu göremez.
 *
 * Yüzdelik bant (p10–p90) bilerek gösterilmiyor: ölçüldü, 12/12 hücrede tam
 * bariyerlere oturuyor — veriden değil, bariyer ayarından geliyor.
 */
export function ReturnBand({ distribution }: ReturnBandProps) {
  const { median, share_positive, shadow_median, shadow_share_positive } = distribution;
  if (!Number.isFinite(median)) return null;

  return (
    <div className="space-y-2">
      <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        Ortalamanın gizlediği
      </h4>

      <div className="grid gap-3 sm:grid-cols-2">
        <Cell
          label="Medyan sonuç"
          hint="Olayların yarısı bunun altında kapandı"
          value={formatR(median)}
          shadow={shadow_median === null || shadow_median === undefined ? null : formatR(shadow_median)}
          negative={median < 0}
        />
        <Cell
          label="Artıda kapanan"
          hint="Kazanma oranından farklı: zaman bariyerinden yeşil çıkanlar da dahil"
          value={formatPercent(share_positive, 1)}
          shadow={
            shadow_share_positive === null || shadow_share_positive === undefined
              ? null
              : formatPercent(shadow_share_positive, 1)
          }
          negative={false}
        />
      </div>
    </div>
  );
}

function Cell({
  label,
  hint,
  value,
  shadow,
  negative,
}: {
  label: string;
  hint: string;
  value: string;
  shadow: string | null;
  negative: boolean;
}) {
  return (
    <div className="rounded-lg border border-border bg-secondary/30 p-3">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs font-medium text-muted-foreground">{label}</span>
        <span
          className={`tabular text-lg font-semibold ${negative ? "text-down" : "text-foreground"}`}
        >
          {value}
        </span>
      </div>
      {shadow && (
        <div className="mt-1 flex items-baseline justify-between gap-2">
          <span className="text-[11px] text-muted-foreground/70">Gölge dağılım</span>
          <span className="tabular text-[11px] text-muted-foreground">{shadow}</span>
        </div>
      )}
      <p className="mt-2 text-[11px] leading-relaxed text-muted-foreground/70">{hint}</p>
    </div>
  );
}
