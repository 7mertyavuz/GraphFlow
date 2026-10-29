"use client";

import { Loader2 } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Segmented } from "@/components/ui/segmented";
import { useI18n } from "@/i18n/LanguageProvider";
import { cn } from "@/lib/utils";
import {
  type BaselineMode,
  type Direction,
  type OutcomeCondition,
  type OutcomeResponse,
} from "@/services/endpoints";
import { formatCount, formatPercent } from "@/utils/formatters";

import { FanChart } from "./FanChart";
import { RegimeTable } from "./RegimeTable";
import { ReturnBand } from "./ReturnBand";
import { StatCard } from "./StatCard";

const OUTCOME_CLASSES: Record<string, string> = {
  tp: "bg-up",
  sl: "bg-down",
  time: "bg-muted-foreground",
  forced: "bg-border",
};

interface OutcomePanelProps {
  data: OutcomeResponse | undefined;
  isLoading: boolean;
  error: unknown;
  direction: Direction;
  onDirectionChange: (direction: Direction) => void;
  /** Seçili bariyer konfigürasyonu — eşleşme kartları da bunu gösterir. */
  configName: string | null;
  onConfigChange: (name: string) => void;
  baseline?: BaselineMode;
  onBaselineChange?: (baseline: BaselineMode) => void;
  condition?: OutcomeCondition;
  onConditionChange?: (condition: OutcomeCondition) => void;
}

/**
 * "Sonra ne oldu?" paneli.
 *
 * Başrol metriği beklenti (R). Kazanma oranı yanında durur ama tek başına
 * gösterilmez: stop'u genişleterek yükseltilebilir, bu yüzden bir başarı
 * ölçütü değildir.
 */
export function OutcomePanel({
  data,
  isLoading,
  error,
  direction,
  onDirectionChange,
  configName,
  onConfigChange,
  baseline = "standard",
  onBaselineChange,
  condition = "all",
  onConditionChange,
}: OutcomePanelProps) {
  const { t } = useI18n();
  const outcomeLabel = (key: string) =>
    (t.outcome.outcomes as Record<string, string>)[key] ?? key;
  const directions = [
    { value: "long" as Direction, label: t.outcome.long, hint: t.outcome.longHint },
    { value: "short" as Direction, label: t.outcome.short, hint: t.outcome.shortHint },
  ];
  const baselines = [
    {
      value: "standard" as BaselineMode,
      label: t.outcome.baselineStandard,
      hint: t.outcome.baselineStandardHint,
    },
    {
      value: "return_matched" as BaselineMode,
      label: t.outcome.baselineMomentum,
      hint: t.outcome.baselineMomentumHint,
    },
  ];
  const conditions = [
    { value: "all" as OutcomeCondition, label: t.outcome.condAll },
    { value: "high_vol" as OutcomeCondition, label: t.outcome.condHighVol },
    { value: "low_vol" as OutcomeCondition, label: t.outcome.condLowVol },
    { value: "strong_breakout" as OutcomeCondition, label: t.outcome.condBreakout },
  ];
  const configs = data ? Object.entries(data.configs) : [];
  const active = configs.find(([name]) => name === configName) ?? configs[0];

  if (isLoading) {
    return (
      <Card>
        <CardBody className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          {t.outcome.computing}
        </CardBody>
      </Card>
    );
  }

  if (error) {
    return (
      <Alert tone="warn" title={t.outcome.errorTitle}>
        {t.outcome.errorBody}
      </Alert>
    );
  }

  if (!data) return null;

  // Hiç konfigürasyon yoksa istatistiğe giren olay da yoktur. Sessizce boş
  // dönmek, kullanıcıya panelin bozuk olduğunu düşündürür — sebebi yazılır.
  if (!active) {
    return (
      <Alert tone="info" title={t.outcome.noEventsTitle}>
        {t.outcome.noEventsBody}
      </Alert>
    );
  }

  const [name, config] = active;
  const total = Object.values(config.outcomes).reduce((sum, v) => sum + v, 0);

  return (
    <Card>
      <CardHeader className="gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle className="text-base">{t.outcome.title}</CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">
              {t.outcome.subtitle(config.k_tp, config.k_sl)}
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Segmented
              options={directions}
              value={direction}
              onChange={onDirectionChange}
              size="sm"
              className="w-[150px]"
              ariaLabel={t.outcome.directionAria}
            />
            {configs.length > 1 && (
              <Segmented
                options={configs.map(([key]) => ({ value: key, label: key }))}
                value={name}
                onChange={onConfigChange}
                size="sm"
                ariaLabel={t.outcome.configAria}
              />
            )}
          </div>
        </div>

        {(onBaselineChange || onConditionChange) && (
          <div className="flex flex-wrap items-center justify-between gap-2.5 rounded-lg border border-border/60 bg-secondary/20 px-3 py-2 text-xs">
            {onBaselineChange && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-muted-foreground">
                  {t.outcome.baselineLabel}
                </span>
                <Segmented
                  options={baselines}
                  value={baseline}
                  onChange={onBaselineChange}
                  size="sm"
                  ariaLabel={t.outcome.baselineAria}
                />
              </div>
            )}
            {onConditionChange && (
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-medium text-muted-foreground">
                  {t.outcome.conditionLabel}
                </span>
                <Segmented
                  options={conditions}
                  value={condition}
                  onChange={onConditionChange}
                  size="sm"
                  ariaLabel={t.outcome.conditionAria}
                />
              </div>
            )}
          </div>
        )}

        <EventLedger data={data} />
      </CardHeader>

      <CardBody className="space-y-5">
        {config.expectancy.n_events === 0 ? (
          <Alert tone="warn" title={t.outcome.zeroTitle}>
            {t.outcome.zeroBody}
          </Alert>
        ) : (
          <>
            {config.insufficient && (
              <Alert tone="warn" title={t.outcome.insufficientTitle(config.expectancy.n_events)}>
                {t.outcome.insufficientStart} <strong>{t.outcome.insufficientStrong}</strong>
                {t.outcome.insufficientEnd}
              </Alert>
            )}

            <div
              className={cn(
                "grid gap-3",
                config.return_matched_edge ? "lg:grid-cols-4" : "lg:grid-cols-3",
                config.insufficient && "opacity-60"
              )}
            >
              <StatCard
                label={t.outcome.expectancy}
                hint={t.outcome.expectancyHint}
                envelope={config.expectancy}
                emphasis
              />
              <StatCard
                label={t.outcome.winRate}
                hint={t.outcome.winRateHint}
                envelope={config.win_rate}
              />
              {config.edge ? (
                <StatCard
                  label={t.outcome.edge}
                  hint={t.outcome.edgeHint}
                  envelope={config.edge}
                />
              ) : (
                <Alert tone="info" title={t.outcome.edgeNaTitle}>
                  {t.outcome.edgeNaBody}
                </Alert>
              )}
              {config.return_matched_edge && (
                <StatCard
                  label={t.outcome.returnMatchedEdge}
                  hint={t.outcome.returnMatchedEdgeHint}
                  envelope={config.return_matched_edge}
                />
              )}
            </div>

            <ReturnBand distribution={config.distribution} />

            {data.paths && (
              <FanChart
                paths={data.paths}
                direction={direction}
                kTp={config.k_tp}
                kSl={config.k_sl}
                dimmed={config.insufficient}
              />
            )}

            <div className="space-y-2">
              <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                {t.outcome.distribution(formatCount(total))}
              </h4>
              <div className="flex h-2.5 overflow-hidden rounded-full">
                {Object.entries(config.outcomes).map(([key, count]) => (
                  <div
                    key={key}
                    className={cn(OUTCOME_CLASSES[key] ?? "bg-secondary")}
                    style={{ width: `${total ? (count / total) * 100 : 0}%` }}
                    title={`${outcomeLabel(key)}: ${count}`}
                  />
                ))}
              </div>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
                {Object.entries(config.outcomes).map(([key, count]) => (
                  <span key={key} className="flex items-center gap-1.5">
                    <span
                      className={cn(
                        "size-2 rounded-full",
                        OUTCOME_CLASSES[key] ?? "bg-secondary"
                      )}
                    />
                    {outcomeLabel(key)}
                    <span className="tabular text-foreground/80">
                      {formatCount(count)} ({formatPercent(total ? count / total : 0)})
                    </span>
                  </span>
                ))}
                {config.truncated > 0 && (
                  <span title={t.outcome.truncatedTitle}>
                    {t.outcome.truncated} <span className="tabular">{formatCount(config.truncated)}</span>
                  </span>
                )}
              </div>
            </div>

            <div className="space-y-2">
              <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                {t.outcome.regime}
              </h4>
              <RegimeTable regimes={config.by_regime} />
            </div>
          </>
        )}

        <p className="border-t border-border pt-4 text-[11px] leading-relaxed text-muted-foreground">
          {data.disclaimer}
        </p>
      </CardBody>
    </Card>
  );
}

/** Eşleşmeden bağımsız olaya giden yol — kaç tanesi neden düştü. */
function EventLedger({ data }: { data: OutcomeResponse }) {
  const { t } = useI18n();
  const items = [
    { label: t.outcome.ledger.matches, value: data.matches },
    { label: t.outcome.ledger.overlap, value: data.dropped_forward_overlap, muted: true },
    { label: t.outcome.ledger.filtered, value: data.dropped_filters, muted: true },
    { label: t.outcome.ledger.independent, value: data.n_events, strong: true },
  ];

  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted-foreground">
      {items.map((item, i) => (
        <span key={item.label} className="flex items-center gap-2">
          {i > 0 && <span className="text-border">→</span>}
          <span className={cn("tabular", item.strong && "font-medium text-foreground")}>
            {formatCount(item.value)}
          </span>
          <span className={cn(item.muted && "text-muted-foreground/70")}>{item.label}</span>
        </span>
      ))}
      <Badge tone="outline" title={t.outcome.onlyIndependentTitle}>
        {t.outcome.onlyIndependent}
      </Badge>
    </div>
  );
}
