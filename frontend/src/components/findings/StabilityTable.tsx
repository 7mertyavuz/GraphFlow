"use client";

import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Segmented } from "@/components/ui/segmented";
import { useI18n } from "@/i18n/LanguageProvider";
import { cn } from "@/lib/utils";
import { type SeedStability, type StabilityRow } from "@/services/endpoints";
import { formatCount, formatR } from "@/utils/formatters";

type Filter = "any" | "all";

/**
 * F4.5'in 56 testi, her biri birkaç null çekilişiyle (docs/12).
 *
 * Yayımlanan tablo tek bir çekilişin sonucudur; "anlamlı" bir hücre başka
 * bir çekilişte düşebilir. Bu tablo her hücrenin kaç çekilişte ayakta
 * kaldığını edge'in yanında gösterir — yerine değil. Sayılar sunucudan
 * gelir; istemci hiçbir anlamlılık hesabı yapmaz.
 */
export function StabilityTable({ stability }: { stability: SeedStability | null | undefined }) {
  const { t } = useI18n();
  const copy = t.findings.stability;
  // Varsayılan TÜMÜ: bütün şablonlar tek tabloda raporlanır (ürün ilkesi);
  // süzgeç okumayı kolaylaştırır, hiçbir hücreyi saklamaz.
  const [filter, setFilter] = useState<Filter>("all");

  if (!stability) {
    return (
      <Alert tone="info" title={copy.missingTitle}>
        {copy.missingBody} <code className="kbd">python -m tools.null_sensitivity</code>
      </Alert>
    );
  }

  const n = stability.seeds;
  const anySignificant = (row: StabilityRow) => row.cells.some((c) => c.seeds_significant > 0);
  const rows = filter === "any" ? stability.rows.filter(anySignificant) : stability.rows;
  const timeframes = stability.rows[0]?.cells.map((c) => c.timeframe) ?? [];

  return (
    <Card>
      <CardHeader className="gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <CardTitle>{copy.title}</CardTitle>
          <Segmented
            options={[
              { value: "any" as Filter, label: copy.onlyAnyShort, hint: copy.onlyAny },
              { value: "all" as Filter, label: copy.all(stability.rows.length) },
            ]}
            value={filter}
            onChange={setFilter}
            size="sm"
            className="w-[200px]"
          />
        </div>
        <p className="text-xs leading-relaxed text-muted-foreground">
          {copy.lead(n, formatCount(stability.null_sample))}
        </p>
        {stability.engine_match !== true && (
          <Alert tone="warn">
            {copy.staleBody} {stability.reason}
          </Alert>
        )}
      </CardHeader>
      <CardBody className="overflow-x-auto p-0">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-border bg-secondary/50 text-left text-muted-foreground">
              <th className="whitespace-nowrap px-3 py-2 font-medium">{copy.pattern}</th>
              <th className="whitespace-nowrap px-2 py-2 font-medium">{copy.direction}</th>
              <th className="whitespace-nowrap px-2 py-2 font-medium">{copy.config}</th>
              {timeframes.map((tf) => (
                <th key={tf} className="whitespace-nowrap px-3 py-2 font-medium" colSpan={2}>
                  {tf} · {copy.edge}
                </th>
              ))}
              <th className="whitespace-nowrap px-3 py-2 font-medium">{copy.replicated}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const robust = row.seeds_replicated === n;
              return (
                <tr
                  key={`${row.template_id}-${row.direction}-${row.config}`}
                  className={cn("border-b border-border last:border-0", robust && "bg-brand/[0.06]")}
                >
                  <td className="whitespace-nowrap px-3 py-2 font-medium">
                    {row.template}
                    {robust && (
                      <Badge tone="brand" className="ml-2">
                        {copy.robust}
                      </Badge>
                    )}
                  </td>
                  <td className="px-2 py-2 text-muted-foreground">{row.direction}</td>
                  <td className="px-2 py-2 tabular text-muted-foreground">{row.config}</td>
                  {row.cells.map((cell) => (
                    <CellColumns key={cell.timeframe} cell={cell} seeds={n} />
                  ))}
                  <td className="px-3 py-2" title={copy.replicatedTitle(row.seeds_replicated, n)}>
                    <Dots k={row.seeds_replicated} n={n} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </CardBody>
    </Card>
  );
}

function CellColumns({ cell, seeds }: { cell: StabilityRow["cells"][number]; seeds: number }) {
  const { t } = useI18n();
  const copy = t.findings.stability;
  const tone =
    cell.edge === null || cell.edge === undefined || !cell.significant
      ? "text-muted-foreground"
      : cell.edge > 0
        ? "text-up"
        : "text-down";
  return (
    <>
      <td className="whitespace-nowrap px-3 py-2 tabular">
        <span className={cn("font-medium", tone)}>{formatR(cell.edge)}</span>
        {cell.ci95 && (
          <span className="ml-1.5 text-[10px] text-muted-foreground/80">
            [{formatR(cell.ci95[0])} · {formatR(cell.ci95[1])}]
          </span>
        )}
        <span className="ml-1.5 text-[10px] text-muted-foreground/60">N={cell.n_events}</span>
      </td>
      <td className="whitespace-nowrap px-3 py-2" title={copy.seedsTitle(cell.seeds_significant, seeds)}>
        <Dots k={cell.seeds_significant} n={seeds} />
        {cell.seeds_bonferroni > 0 && (
          <span className="ml-2 text-[10px] text-warp">{copy.bonferroni(cell.seeds_bonferroni)}</span>
        )}
      </td>
    </>
  );
}

/** k/n dolu nokta — oranı sayıyla da yazar (renk tek taşıyıcı değil). */
function Dots({ k, n }: { k: number; n: number }) {
  return (
    <span className="inline-flex items-center gap-1 align-middle">
      {Array.from({ length: n }).map((_, i) => (
        <span
          key={i}
          className={cn(
            "size-1.5 rounded-full",
            i < k ? (k === n ? "bg-brand" : "bg-brand/60") : "bg-border"
          )}
        />
      ))}
      <span className="ml-1 tabular text-[10px] text-muted-foreground">
        {k}/{n}
      </span>
    </span>
  );
}
