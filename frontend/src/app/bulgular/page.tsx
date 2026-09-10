"use client";

import { Loader2 } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { useFindings } from "@/hooks/useGraphFlowApi";
import { useI18n } from "@/i18n/LanguageProvider";
import { formatDate, formatPercent } from "@/utils/formatters";

/**
 * Eleme zinciri sayfası.
 *
 * "2 anlamlı bulgu" cümlesi, 52 testin 50'sinin nasıl elendiği bilgisi
 * olmadan yanıltıcıdır. Bu sayfa o muhasebeyi görünür kılar.
 */
export default function FindingsPage() {
  const { data, isLoading, isError } = useFindings();
  const { t } = useI18n();

  return (
    <main className="mx-auto w-full max-w-[900px] flex-1 px-4 py-8 lg:px-6">
      <header className="mb-6">
        <h1 className="text-xl font-semibold tracking-tight">{t.findings.title}</h1>
        <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-muted-foreground">
          {t.findings.lead}
        </p>
      </header>

      {isLoading && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          {t.findings.loading}
        </div>
      )}

      {isError && (
        <Alert tone="danger" title={t.findings.failed}>
          {t.findings.apiRunning} <code className="kbd">uvicorn engine.api.main:app</code>
        </Alert>
      )}

      {data && (
        <div className="space-y-4">
          {data.stale && (
            <Alert tone="warn" title={t.findings.staleTitle}>
              {t.findings.staleBody}{" "}
              <code className="kbd">python -m tools.run_outcomes</code>.
            </Alert>
          )}

          <Card>
            <CardHeader>
              <CardTitle>{t.findings.stages}</CardTitle>
            </CardHeader>
            <CardBody className="space-y-4">
              {data.stages.map((stage) => {
                const ratio = stage.total ? stage.significant / stage.total : 0;
                return (
                  <div key={stage.stage} className="space-y-2">
                    <div className="flex flex-wrap items-baseline justify-between gap-2">
                      <span className="text-sm font-medium">{stage.stage}</span>
                      <Badge tone={ratio > 0.2 ? "warn" : "outline"} className="tabular">
                        {t.findings.significantOf(stage.significant, stage.total)}{" "}
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

          {data.provenance && data.provenance.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>{t.findings.provenance}</CardTitle>
              </CardHeader>
              <CardBody className="space-y-2">
                {data.provenance.map((p) => (
                  <div
                    key={p.file}
                    className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 text-xs"
                  >
                    <span className="font-medium">{p.file}</span>
                    <span className="flex flex-wrap items-center gap-2 text-muted-foreground tabular">
                      {p.data_as_of ? <>{t.findings.data(formatDate(p.data_as_of))}</> : null}
                      {p.generated_at ? <>{t.findings.measured(p.generated_at.slice(0, 10))}</> : null}
                      <Badge
                        tone={p.engine_match === true ? "outline" : "warn"}
                        className="tabular"
                      >
                        {p.engine_match === true
                          ? t.findings.currentEngine
                          : p.engine_match === false
                            ? t.findings.differentEngine
                            : t.findings.unknownOrigin}
                      </Badge>
                    </span>
                    {p.reason && (
                      <p className="w-full text-[11px] text-muted-foreground">{p.reason}</p>
                    )}
                  </div>
                ))}
              </CardBody>
            </Card>
          )}

          <Card>
            <CardHeader>
              <CardTitle>{t.findings.methodology}</CardTitle>
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
                <CardTitle>{t.findings.fullTable(data.full_table.length)}</CardTitle>
              </CardHeader>
              <CardBody className="overflow-x-auto p-0">
                <FullTable rows={data.full_table} yes={t.findings.yes} no={t.findings.no} />
              </CardBody>
            </Card>
          )}
        </div>
      )}
    </main>
  );
}

function FullTable({
  rows,
  yes,
  no,
}: {
  rows: Record<string, unknown>[];
  yes: string;
  no: string;
}) {
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
                {formatCell(row[column], yes, no)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function formatCell(value: unknown, yes: string, no: string): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(3);
  if (typeof value === "boolean") return value ? yes : no;
  return String(value);
}
