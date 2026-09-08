"use client";

import { Clock, Database, RefreshCw, ScanEye } from "lucide-react";

import { Badge } from "@/components/ui/badge";
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
}: ResultsHeaderProps) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
        <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
        {hasSearched && structureRead && (
          <p className="mt-1.5 inline-flex items-center gap-1.5 text-[11px] text-muted-foreground">
            <ScanEye className="size-3.5 shrink-0 text-brand" />
            <span>
              Motor şeklinizi şöyle okudu:{" "}
              <span className="text-foreground">{structureRead}</span>
              {structureFiltered && " — sonuçlar bu yapıyla sınırlı"}
            </span>
          </p>
        )}
      </div>

      {hasSearched && (
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="brand" className="tabular">
            {formatCount(total)} eşleşme
          </Badge>
          {refreshedAt !== null && (
            <Badge tone="outline" className="tabular gap-1">
              <RefreshCw className="size-3" />
              {formatRelative(refreshedAt)} tarandı
            </Badge>
          )}
          {shown > 0 && shown < total && (
            <Badge tone="outline" className="tabular">
              {formatCount(shown)} gösteriliyor
            </Badge>
          )}
          <span className="flex items-center gap-1 text-[11px] text-muted-foreground tabular">
            <Clock className="size-3" />
            {formatDecimal(elapsedMs, 0)} ms
          </span>
          {dataAsOf > 0 && (
            <span
              className="flex items-center gap-1 text-[11px] text-muted-foreground tabular"
              title="Deponun gördüğü en yeni bar"
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
