"use client";

import { Clock, Database } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { formatCount, formatDate, formatDecimal } from "@/utils/formatters";

interface ResultsHeaderProps {
  title: string;
  description: string;
  total: number;
  shown: number;
  elapsedMs: number;
  dataAsOf: number;
  hasSearched: boolean;
}

export function ResultsHeader({
  title,
  description,
  total,
  shown,
  elapsedMs,
  dataAsOf,
  hasSearched,
}: ResultsHeaderProps) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
        <p className="mt-0.5 text-xs text-muted-foreground">{description}</p>
      </div>

      {hasSearched && (
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="brand" className="tabular">
            {formatCount(total)} eşleşme
          </Badge>
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
