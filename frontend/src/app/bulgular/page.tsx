"use client";

import { Loader2 } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { useFindings } from "@/hooks/useGraphFlowApi";
import { formatPercent } from "@/utils/formatters";

/**
 * Eleme zinciri sayfası.
 *
 * "2 anlamlı bulgu" cümlesi, 52 testin 50'sinin nasıl elendiği bilgisi
 * olmadan yanıltıcıdır. Bu sayfa o muhasebeyi görünür kılar.
 */
export default function FindingsPage() {
  const { data, isLoading, isError } = useFindings();

  return (
    <main className="mx-auto w-full max-w-[900px] flex-1 px-4 py-8 lg:px-6">
      <header className="mb-6">
        <h1 className="text-xl font-semibold tracking-tight">Bulgular ve eleme zinciri</h1>
        <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-muted-foreground">
          Her doğrulama aşaması bir öncekinin bulgularını sınadı. Elenen
          bulgular da raporlanır: bir sonucun hangi aşamada düştüğü, kalan
          sonucun ne kadar güvenilir olduğunu belirler.
        </p>
      </header>

      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          Bulgular yükleniyor…
        </div>
      )}

      {isError && (
        <Alert tone="danger" title="Bulgular alınamadı">
          API çalışıyor mu? <code className="kbd">uvicorn engine.api.main:app</code>
        </Alert>
      )}

      {data && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Aşamalar</CardTitle>
            </CardHeader>
            <CardBody className="space-y-4">
              {data.stages.map((stage) => {
                const ratio = stage.total ? stage.significant / stage.total : 0;
                return (
                  <div key={stage.stage} className="space-y-2">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <span className="text-sm font-medium">{stage.stage}</span>
                      <Badge tone={ratio > 0.2 ? "warn" : "outline"} className="tabular">
                        {stage.significant} / {stage.total} anlamlı ·{" "}
                        {formatPercent(ratio)}
                      </Badge>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-secondary">
                      <div
                        className="h-full rounded-full bg-brand transition-all"
                        style={{ width: `${Math.max(2, ratio * 100)}%` }}
                      />
                    </div>
                    <p className="text-xs leading-relaxed text-muted-foreground">{stage.desc}</p>
                  </div>
                );
              })}
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Yöntem</CardTitle>
            </CardHeader>
            <CardBody>
              <p className="text-xs leading-relaxed text-muted-foreground">
                {data.methodology}
              </p>
            </CardBody>
          </Card>

          {data.full_table.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Tam tablo ({data.full_table.length} satır)</CardTitle>
              </CardHeader>
              <CardBody className="overflow-x-auto p-0">
                <FullTable rows={data.full_table} />
              </CardBody>
            </Card>
          )}
        </div>
      )}
    </main>
  );
}

function FullTable({ rows }: { rows: Record<string, unknown>[] }) {
  const columns = Array.from(new Set(rows.flatMap((row) => Object.keys(row))));

  return (
    <table className="w-full text-xs">
      <thead>
        <tr className="border-b border-border bg-secondary/50 text-left text-muted-foreground">
          {columns.map((column) => (
            <th key={column} className="whitespace-nowrap px-3 py-2 font-medium">
              {column}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i} className="border-b border-border last:border-0">
            {columns.map((column) => (
              <td key={column} className="whitespace-nowrap px-3 py-2 tabular text-muted-foreground">
                {formatCell(row[column])}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(3);
  if (typeof value === "boolean") return value ? "evet" : "hayır";
  return String(value);
}
