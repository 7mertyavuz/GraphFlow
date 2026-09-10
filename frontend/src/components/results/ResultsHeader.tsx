"use client";

import { Clock, Database, RefreshCw, ScanEye, TrendingUp, TriangleAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { useI18n } from "@/i18n/LanguageProvider";
import { formatCount, formatDate, formatDecimal, formatRelative } from "@/utils/formatters";

interface ResultsHeaderProps {
  title: string;
  description: string;
  total: number;
  shown: number;
  elapsedMs: number;
  dataAsOf: number;
  hasSearched: boolean;
  /** Radar kendini yenilediğinde son tazeleme anı; Backtest'te null. */
  refreshedAt?: number | null;
  /** Motorun çizimden okuduğu yapı — yanlış okunduysa kullanıcı görsün. */
  structureRead?: string | null;
  structureFiltered?: boolean;
  /**
   * Okuma sağlam mı. Eğimle tanımlı formasyonlarda (üçgen, takoz, flama) uç
   * düzeni kararsızdır. Motor bu durumda yapısal filtreyi UYGULAMAZ (K-20):
   * kararsız imzayla elemek gerçek formasyonları da siliyordu — ground
   * truth'ta yakalama oranı %45'ten %57'ye çıktı. Arayüz hem okumayı hem
   * kararsız olduğunu hem de elemenin yapılmadığını söyler.
   */
  structureStable?: boolean;
  /**
   * Motorun okuduğu trend çizgisi düzeni ve sonuçların buna göre daraltılıp
   * daraltılmadığı. Eğimle tanımlı formasyonlarda daralmayı YAPAN okuma
   * budur (K-21); yalnız uç düzeni okumasını göstermek motorun gerçek
   * gerekçesini gizlerdi.
   */
  envelopeRead?: string | null;
  envelopeFiltered?: boolean;
}

export function ResultsHeader({
  title,
  description,
  total,
  shown,
  elapsedMs,
  dataAsOf,
  hasSearched,
  refreshedAt = null,
  structureRead = null,
  structureFiltered = false,
  structureStable = true,
  envelopeRead = null,
  envelopeFiltered = false,
}: ResultsHeaderProps) {
  const { t } = useI18n();
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
        <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
        {hasSearched && structureRead && (
          <p className="mt-1.5 inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <ScanEye className="size-3.5 shrink-0 text-brand" />
            <span>
              {t.results.engineRead}{" "}
              <span className="text-foreground">{structureRead}</span>
              {structureFiltered && t.results.limitedByStructure}
            </span>
          </p>
        )}
        {hasSearched && envelopeRead && envelopeFiltered && (
          <p className="mt-1 inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <TrendingUp className="size-3.5 shrink-0 text-brand" />
            <span>
              {t.results.trendLines}{" "}
              <span className="text-foreground">{envelopeRead}</span>
              {t.results.limitedByTrend}
            </span>
          </p>
        )}
        {hasSearched && structureRead && !structureStable && (
          <p className="mt-1 inline-flex items-start gap-1.5 text-[11px] text-amber-600 dark:text-amber-500">
            <TriangleAlert className="mt-px size-3.5 shrink-0" />
            <span>
              {t.results.unstableStart}{" "}
              <span className="text-foreground">
                {envelopeFiltered ? t.results.unstableByTrend : t.results.unstableNoNarrow}
              </span>{" "}
              {t.results.unstableEnd}
            </span>
          </p>
        )}
      </div>

      {hasSearched && (
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="brand" className="tabular">
            {t.results.matches(formatCount(total))}
          </Badge>
          {refreshedAt !== null && (
            <Badge tone="outline" className="tabular gap-1">
              <RefreshCw className="size-3" />
              {t.results.scanned(formatRelative(refreshedAt))}
            </Badge>
          )}
          {shown > 0 && shown < total && (
            <Badge tone="outline" className="tabular">
              {t.results.showing(formatCount(shown))}
            </Badge>
          )}
          <span className="flex items-center gap-1 text-[11px] text-muted-foreground tabular">
            <Clock className="size-3" />
            {formatDecimal(elapsedMs, 0)} ms
          </span>
          {dataAsOf > 0 && (
            <span
              className="flex items-center gap-1 text-[11px] text-muted-foreground tabular"
              title={t.results.dataAsOfTitle}
            >
              <Database className="size-3" />
              {formatDate(dataAsOf)}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
