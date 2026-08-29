"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardBody, CardHeader, CardTitle } from "@/components/ui/card";
import { Segmented } from "@/components/ui/segmented";
import { cn } from "@/lib/utils";
import { type Direction, type OutcomeResponse } from "@/services/endpoints";
import { formatCount, formatPercent } from "@/utils/formatters";

import { RegimeTable } from "./RegimeTable";
import { ReturnBand } from "./ReturnBand";
import { StatCard } from "./StatCard";

const OUTCOME_LABELS: Record<string, { label: string; className: string }> = {
  tp: { label: "Hedef", className: "bg-up" },
  sl: { label: "Stop", className: "bg-down" },
  time: { label: "Zaman aşımı", className: "bg-muted-foreground" },
  forced: { label: "Veri sonu", className: "bg-border" },
};

const DIRECTIONS = [
  { value: "long" as Direction, label: "Long", hint: "Yukarı bariyer hedef" },
  { value: "short" as Direction, label: "Short", hint: "Aşağı bariyer hedef" },
];

interface OutcomePanelProps {
  data: OutcomeResponse | undefined;
  isLoading: boolean;
  error: unknown;
  direction: Direction;
  onDirectionChange: (direction: Direction) => void;
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
}: OutcomePanelProps) {
  const configs = data ? Object.entries(data.configs) : [];
  const [configName, setConfigName] = useState<string | null>(null);
  const active = configs.find(([name]) => name === configName) ?? configs[0];

  if (isLoading) {
    return (
      <Card>
        <CardBody className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" />
          İleri pencereler hesaplanıyor, gölge dağılım örnekleniyor…
        </CardBody>
      </Card>
    );
  }

  if (error) {
    return (
      <Alert tone="warn" title="İstatistik hesaplanamadı">
        Bu arama için ileri pencere istatistiği üretilemedi.
      </Alert>
    );
  }

  if (!data || !active) return null;

  const [name, config] = active;
  const total = Object.values(config.outcomes).reduce((sum, v) => sum + v, 0);

  return (
    <Card>
      <CardHeader className="gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <CardTitle className="text-base">Sonra ne oldu?</CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">
              Üçlü bariyer · hedef {config.k_tp}×ATR · stop {config.k_sl}×ATR · zaman
              bariyeri pencere uzunluğunun yarısı
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Segmented
              options={DIRECTIONS}
              value={direction}
              onChange={onDirectionChange}
              size="sm"
              className="w-[150px]"
              ariaLabel="Yön"
            />
            {configs.length > 1 && (
              <Segmented
                options={configs.map(([key]) => ({ value: key, label: key }))}
                value={name}
                onChange={setConfigName}
                size="sm"
                ariaLabel="Bariyer konfigürasyonu"
              />
            )}
          </div>
        </div>

        <EventLedger data={data} />
      </CardHeader>

      <CardBody className="space-y-5">
        {config.expectancy.n_events === 0 ? (
          <Alert tone="warn" title="İstatistiğe giren olay yok">
            Eşleşmeler ileri pencere ayrımı ve işlem maliyeti tabanı filtrelerinden
            geçemedi. Bağımsız olay olmadan dağılım raporlanmaz.
          </Alert>
        ) : (
          <>
            <div className="grid gap-3 lg:grid-cols-3">
              <StatCard
                label="Beklenti"
                hint="Olay başına ortalama R — başrol metrik"
                envelope={config.expectancy}
                emphasis
              />
              <StatCard
                label="Başarı oranı"
                hint="Teorik null ile birlikte okunur"
                envelope={config.win_rate}
              />
              {config.edge ? (
                <StatCard
                  label="Edge"
                  hint="Zaman-eşleştirmeli gölge dağılıma karşı fark"
                  envelope={config.edge}
                />
              ) : (
                <Alert tone="info" title="Edge ölçülemedi">
                  Gölge dağılım örneklenemedi; baseline&apos;sız bir başarı oranı
                  gösterilmez.
                </Alert>
              )}
            </div>

            <ReturnBand distribution={config.distribution} />

            <div className="space-y-2">
              <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Sonuç dağılımı ({formatCount(total)} olay)
              </h4>
              <div className="flex h-2.5 overflow-hidden rounded-full">
                {Object.entries(config.outcomes).map(([key, count]) => (
                  <div
                    key={key}
                    className={cn(OUTCOME_LABELS[key]?.className ?? "bg-secondary")}
                    style={{ width: `${total ? (count / total) * 100 : 0}%` }}
                    title={`${OUTCOME_LABELS[key]?.label ?? key}: ${count}`}
                  />
                ))}
              </div>
              <div className="flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted-foreground">
                {Object.entries(config.outcomes).map(([key, count]) => (
                  <span key={key} className="flex items-center gap-1.5">
                    <span
                      className={cn(
                        "size-2 rounded-full",
                        OUTCOME_LABELS[key]?.className ?? "bg-secondary"
                      )}
                    />
                    {OUTCOME_LABELS[key]?.label ?? key}
                    <span className="tabular text-foreground/80">
                      {formatCount(count)} ({formatPercent(total ? count / total : 0)})
                    </span>
                  </span>
                ))}
                {config.truncated > 0 && (
                  <span title="İleri penceresi fiyat sıçraması veya veri sonu nedeniyle kesilen olaylar">
                    kesilen: <span className="tabular">{formatCount(config.truncated)}</span>
                  </span>
                )}
              </div>
            </div>

            <div className="space-y-2">
              <h4 className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                Rejim kırılımı
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
  const items = [
    { label: "eşleşme", value: data.matches },
    { label: "örtüşme elendi", value: data.dropped_forward_overlap, muted: true },
    { label: "filtre elendi", value: data.dropped_filters, muted: true },
    { label: "bağımsız olay", value: data.n_events, strong: true },
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
      <Badge tone="outline" title="Örtüşen pencereler N'i şişirir, güven aralığını sahte biçimde daraltır">
        yalnızca bağımsız olaylar sayılır
      </Badge>
    </div>
  );
}
