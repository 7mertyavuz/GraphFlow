"use client";

import { formatR, formatPercent, formatDecimal } from "@/utils/formatters";
import { type paths } from "@/types/api";

type StatEnvelopeType =
  paths["/api/search/{search_id}/stats"]["get"]["responses"]["200"]["content"]["application/json"]["configs"][string]["expectancy"];

interface StatEnvelopeProps {
  label: string;
  envelope: StatEnvelopeType;
  showEdge?: boolean;
}

export function StatEnvelope({ label, envelope, showEdge }: StatEnvelopeProps) {
  const { value, ci95, null: nullVal, shadow, significant, verdict, n_events } = envelope;
  const [lo, hi] = ci95;

  let tone = "text-muted-foreground";
  let badge = "bg-muted text-muted-foreground";
  if (significant) {
    tone = value > 0 ? "text-green-600" : "text-red-600";
    badge = value > 0 ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700";
  }

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-muted-foreground">{label}</span>
        <span className={`rounded px-2 py-0.5 text-xs font-semibold ${badge}`}>
          {significant ? "Anlamlı" : "Anlamsız"}
        </span>
      </div>
      <div className={`mt-2 text-3xl font-bold ${tone}`}>
        {showEdge ? formatR(value) : formatR(value)}
      </div>
      <div className="mt-1 text-xs text-muted-foreground">
        %95 GA: [{formatDecimal(lo, 3)}, {formatDecimal(hi, 3)}] · N = {n_events}
      </div>
      {(nullVal !== null && nullVal !== undefined) && (
        <div className="mt-2 text-xs text-muted-foreground">
          Teorik null: {formatR(nullVal)}
        </div>
      )}
      {(shadow !== null && shadow !== undefined) && (
        <div className="text-xs text-muted-foreground">
          Gölge: {formatR(shadow)}
        </div>
      )}
      {verdict && (
        <div className="mt-2 border-t border-border pt-2 text-xs italic text-muted-foreground">
          {verdict}
        </div>
      )}
    </div>
  );
}
