"use client";

import { Badge } from "@/components/ui/badge";
import { useI18n } from "@/i18n/LanguageProvider";
import { cn } from "@/lib/utils";
import { type StatEnvelope } from "@/services/endpoints";
import { formatCI, formatCount, formatDecimal, formatStat } from "@/utils/formatters";

interface StatCardProps {
  label: string;
  hint?: string;
  envelope: StatEnvelope;
  /** Karşılaştırma çizgisinin adı: "teorik null" veya "gölge dağılım". */
  emphasis?: boolean;
}

/**
 * Bir ``StatEnvelope``'ın tam gösterimi.
 *
 * Değer asla yalnız görünmez: güven aralığı, karşılaştırma tabanı (teorik
 * null / gölge dağılım) ve N aynı karonun içindedir. "%64 başarı" cümlesi
 * bu bileşenden çıkamaz.
 */
export function StatCard({ label, hint, envelope, emphasis }: StatCardProps) {
  const { value, ci95, unit, significant, n_events, n_months, null: nullValue, shadow } = envelope;
  const reference = shadow ?? nullValue;
  const { t } = useI18n();
  const referenceLabel =
    shadow !== null && shadow !== undefined ? t.stat.shadow : t.stat.theoreticalNull;

  const positive = Number.isFinite(value) && value > (reference ?? 0);
  const tone = !significant ? "muted" : positive ? "up" : "down";

  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-xl border p-4",
        emphasis ? "border-brand/25 bg-brand/[0.06]" : "border-border bg-secondary/30"
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-medium text-muted-foreground">{label}</p>
          {hint && <p className="mt-0.5 text-[11px] text-muted-foreground/70">{hint}</p>}
        </div>
        <Badge tone={significant ? (positive ? "up" : "down") : "outline"}>
          {significant ? t.stat.significant : t.stat.notSignificant}
        </Badge>
      </div>

      <div
        className={cn(
          "text-3xl font-semibold tracking-tight tabular",
          tone === "up" && "text-up",
          tone === "down" && "text-down",
          tone === "muted" && "text-foreground"
        )}
      >
        {formatStat(value, unit)}
      </div>

      <CIBar
        value={value}
        ci={ci95}
        reference={reference}
        unit={unit}
        referenceTitle={t.stat.reference(formatStat(reference, unit))}
      />

      <dl className="space-y-1 border-t border-border pt-2.5 text-[11px] text-muted-foreground">
        <Row term={t.stat.ci95} desc={formatCI(ci95, unit)} mono />
        <Row term={t.stat.method} desc={t.stat.ciMethods[envelope.ci_method] ?? envelope.ci_method} />
        {reference !== null && reference !== undefined && (
          <Row term={referenceLabel} desc={formatStat(reference, unit)} mono />
        )}
        <Row
          term={t.stat.independentN}
          desc={`${formatCount(n_events)}${n_months ? ` · ${t.stat.months(n_months)}` : ""}`}
          mono
        />
        {envelope.design_effect !== null && envelope.design_effect !== undefined && (
          <Row
            term={t.stat.designEffect}
            desc={formatDecimal(envelope.design_effect, 2)}
            mono
            title={t.stat.designEffectTitle}
          />
        )}
      </dl>

      {envelope.verdict && (
        <p className="border-t border-border pt-2.5 text-[11px] leading-relaxed text-muted-foreground">
          {envelope.verdict}
        </p>
      )}
    </div>
  );
}

function Row({
  term,
  desc,
  mono,
  title,
}: {
  term: string;
  desc: string;
  mono?: boolean;
  title?: string;
}) {
  return (
    <div className="flex items-center justify-between gap-3" title={title}>
      <dt>{term}</dt>
      <dd className={cn("text-foreground/90", mono && "tabular")}>{desc}</dd>
    </div>
  );
}

/** Güven aralığının görsel karşılığı: nokta tahmin + bant + karşılaştırma çizgisi. */
function CIBar({
  value,
  ci,
  reference,
  referenceTitle,
}: {
  value: number;
  ci: number[];
  reference: number | null | undefined;
  unit: string;
  referenceTitle: string;
}) {
  const points = [value, ...(ci ?? []), reference ?? 0].filter((v) =>
    Number.isFinite(v)
  ) as number[];
  if (points.length < 2) return null;

  const min = Math.min(...points);
  const max = Math.max(...points);
  const pad = Math.max((max - min) * 0.2, 1e-6);
  const lo = min - pad;
  const hi = max + pad;
  const pos = (v: number) => ((v - lo) / (hi - lo)) * 100;

  const hasCI = ci?.length === 2 && ci.every((v) => Number.isFinite(v));
  const refPos = reference !== null && reference !== undefined ? pos(reference) : null;
  const above = reference === null || reference === undefined || value > reference;

  return (
    <div className="space-y-1">
      <div className="relative h-6">
        <div className="absolute inset-x-0 top-1/2 h-px -translate-y-1/2 bg-border" />
        {hasCI && (
          <div
            className={cn(
              "absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full",
              above ? "bg-up/35" : "bg-down/35"
            )}
            style={{ left: `${pos(ci[0])}%`, width: `${Math.max(1, pos(ci[1]) - pos(ci[0]))}%` }}
          />
        )}
        {refPos !== null && (
          <div
            className="absolute top-1/2 h-4 w-px -translate-y-1/2 bg-muted-foreground"
            style={{ left: `${refPos}%` }}
            title={referenceTitle}
          />
        )}
        <div
          className={cn(
            "absolute top-1/2 size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-card",
            above ? "bg-up" : "bg-down"
          )}
          style={{ left: `${pos(value)}%` }}
        />
      </div>
    </div>
  );
}
