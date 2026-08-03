"use client";

import { AlertTriangle, Info } from "lucide-react";

interface PValueWarningProps {
  sessionQueries: number;
  multipleComparisonWarning: boolean;
  adjustedAlpha: number;
}

export function PValueWarning({
  sessionQueries,
  multipleComparisonWarning,
  adjustedAlpha,
}: PValueWarningProps) {
  return (
    <div className="flex flex-col gap-2 rounded-md border border-border bg-card p-3 text-sm">
      <div className="flex items-center gap-2 text-muted-foreground">
        <Info className="size-4" />
        <span>Bu oturumda {sessionQueries} şekil denendi.</span>
      </div>
      {multipleComparisonWarning && (
        <div className="flex items-center gap-2 text-amber-600">
          <AlertTriangle className="size-4" />
          <span>
            Çoklu karşılaştırma uyarısı: Bonferroni düzeltilmiş α ={" "}
            {adjustedAlpha.toFixed(4)}.
          </span>
        </div>
      )}
    </div>
  );
}
