"use client";

import { formatPercent, formatR } from "@/utils/formatters";

export type RegimeRow = {
  period: string;
  n: number;
  win_rate: number;
  expectancy_r: number;
};

interface RegimeTableProps {
  regimes: RegimeRow[];
}

export function RegimeTable({ regimes }: RegimeTableProps) {
  if (!regimes || regimes.length === 0) {
    return (
      <div className="text-sm text-muted-foreground">Rejim kırılımı yok.</div>
    );
  }

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card">
      <table className="w-full text-sm">
        <thead className="border-b border-border bg-muted/50">
          <tr>
            <th className="px-4 py-3 text-left font-medium">Dönem</th>
            <th className="px-4 py-3 text-right font-medium">N</th>
            <th className="px-4 py-3 text-right font-medium">Başarı</th>
            <th className="px-4 py-3 text-right font-medium">Beklenti</th>
          </tr>
        </thead>
        <tbody>
          {regimes.map((r) => (
            <tr key={r.period} className="border-b border-border last:border-0">
              <td className="px-4 py-3 font-medium">{r.period}</td>
              <td className="px-4 py-3 text-right tabular-nums">{r.n}</td>
              <td className="px-4 py-3 text-right tabular-nums">{formatPercent(r.win_rate)}</td>
              <td className={`px-4 py-3 text-right tabular-nums font-medium ${r.expectancy_r > 0 ? "text-green-400" : r.expectancy_r < 0 ? "text-red-400" : ""}`}>
                {formatR(r.expectancy_r)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
