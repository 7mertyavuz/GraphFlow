"use client";

import { Badge } from "@/components/ui/badge";
import { useI18n } from "@/i18n/LanguageProvider";
import { cn } from "@/lib/utils";
import { type RegimeRow } from "@/services/endpoints";
import { formatCount, formatPercent, formatR } from "@/utils/formatters";

/**
 * Rejim kırılımı — tek bir toplam sayı, 2021 boğasında kazanıp 2022'de
 * kaybeden bir formasyonu "çalışıyor" gösterir.
 */
export function RegimeTable({ regimes }: { regimes: RegimeRow[] }) {
  const { t } = useI18n();
  if (!regimes?.length) {
    return (
      <p className="rounded-lg border border-dashed border-border p-4 text-xs text-muted-foreground">
        {t.regime.none}
      </p>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-secondary/50 text-[11px] uppercase tracking-wide text-muted-foreground">
            <th className="px-4 py-2.5 text-left font-medium">{t.regime.period}</th>
            <th className="px-4 py-2.5 text-right font-medium">{t.regime.n}</th>
            <th className="px-4 py-2.5 text-right font-medium">{t.regime.winRate}</th>
            <th className="px-4 py-2.5 text-right font-medium">{t.regime.expectancy}</th>
          </tr>
        </thead>
        <tbody>
          {regimes.map((row) => (
            <tr key={row.period} className="border-b border-border last:border-0">
              <td className="px-4 py-2.5">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{row.period}</span>
                  {row.insufficient && (
                    <Badge tone="warn" title={t.regime.insufficientTitle}>
                      {t.regime.insufficient}
                    </Badge>
                  )}
                </div>
              </td>
              <td className="px-4 py-2.5 text-right tabular text-muted-foreground">
                {formatCount(row.n)}
              </td>
              <td className="px-4 py-2.5 text-right tabular text-muted-foreground">
                {formatPercent(row.win_rate, 1)}
              </td>
              <td
                className={cn(
                  "px-4 py-2.5 text-right font-medium tabular",
                  (row.expectancy_r ?? 0) > 0 && "text-up",
                  (row.expectancy_r ?? 0) < 0 && "text-down"
                )}
              >
                {formatR(row.expectancy_r)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
