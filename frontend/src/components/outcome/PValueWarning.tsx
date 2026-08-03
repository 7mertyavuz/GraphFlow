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
    <div className="flex flex-col gap-2 rounded-xl border border-border bg-card p-4 text-sm">
      <div className="flex items-center gap-2 text-muted-foreground">
        <Info className="size-4 shrink-0" />
        <span>Bu oturumda {sessionQueries} şekil denendi.</span>
      </div>
      {multipleComparisonWarning && (
        <div className="flex items-start gap-2 rounded-md border border-amber-500/20 bg-amber-500/10 p-2 text-amber-200">
          <AlertTriangle className="size-4 shrink-0" />
          <span>
            Çoklu karşılaştırma uyarısı: Bonferroni düzeltilmiş α ={" "}
            {adjustedAlpha.toFixed(4)}. Sonuçlar şansa bağlı olabilir.
          </span>
        </div>
      )}
    </div>
  );
}
