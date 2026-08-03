"use client";

import { formatR, formatPercent, formatDecimal } from "@/utils/formatters";
import { type paths } from "@/types/api";

type StatEnvelopeType =
  paths["/api/search/{search_id}/stats"]["get"]["responses"]["200"]["content"]["application/json"]["configs"][string]["expectancy"];

interface StatEnvelopeProps {
  label: string;
  envelope: StatEnvelopeType;
}

export function StatEnvelope({ label, envelope }: StatEnvelopeProps) {
  const { value, ci95, null: nullVal, shadow, significant, verdict, n_events } = envelope;
  const [lo, hi] = ci95;

  let tone = "text-muted-foreground";
  let badgeClass = "bg-muted text-muted-foreground";
  if (significant) {
    if (value > 0) {
      tone = "text-green-400";
      badgeClass = "bg-green-500/15 text-green-400 border border-green-500/20";
    } else {
      tone = "text-red-400";
      badgeClass = "bg-red-500/15 text-red-400 border border-red-500/20";
    }
  }

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-muted-foreground">{label}</span>
        <span className={`rounded-md px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${badgeClass}`}>
          {significant ? "Anlamlı" : "Anlamsız"}
        </span>
      </div>
      <div className={`mt-2 text-4xl font-bold tracking-tight ${tone}`}>
        {formatR(value)}
      </div>
      <div className="mt-1 text-xs tabular-nums text-muted-foreground">
        %95 GA: [{formatDecimal(lo, 3)}, {formatDecimal(hi, 3)}] · N = {n_events}
      </div>
      <div className="mt-3 space-y-1 border-t border-border pt-3 text-xs text-muted-foreground">
        {(nullVal !== null && nullVal !== undefined) && (
          <div className="flex justify-between">
            <span>Teorik null</span>
            <span className="font-medium text-foreground">{formatR(nullVal)}</span>
          </div>
        )}
        {(shadow !== null && shadow !== undefined) && (
          <div className="flex justify-between">
            <span>Gölge dağılım</span>
            <span className="font-medium text-foreground">{formatR(shadow)}</span>
          </div>
        )}
      </div>
      {verdict && (
        <div className="mt-3 border-t border-border pt-3 text-xs italic leading-relaxed text-muted-foreground">
          {verdict}
        </div>
      )}
    </div>
  );
}
