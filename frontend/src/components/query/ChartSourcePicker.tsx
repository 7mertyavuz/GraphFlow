"use client";

import { useId } from "react";
import { X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Slider } from "@/components/ui/slider";
import { useI18n } from "@/i18n/LanguageProvider";
import { type Mode, type SourceInfo } from "@/services/endpoints";
import { formatCount, formatDate } from "@/utils/formatters";

import { ShapeThumb } from "./ShapeThumb";

/** Sunucu şemasındaki sınırlar (ChartSource, engine/config.py SOURCE_*). */
export const SOURCE_MIN_BARS = 24;
export const SOURCE_MAX_BARS = 200;
export const SOURCE_DEFAULT_BARS = 64;

export interface ChartSourceValue {
  symbol: string;
  length: number;
  /** YYYY-MM-DD (UTC) ya da boş = son kapanmış bar. */
  endDate: string;
}

interface ChartSourcePickerProps {
  mode: Mode;
  value: ChartSourceValue;
  onChange: (value: ChartSourceValue) => void;
  symbols: string[] | undefined;
  unknown: boolean;
  /** Son aramanın parçası — motorun gerçekte ne okuduğu. */
  lastSource: SourceInfo | null;
}

/**
 * Gerçek bir grafiğin parçasından sorgu.
 *
 * İstemci parçayı kendisi kesmez ve normalize etmez: sembol, uzunluk ve
 * bitiş sunucuya gider, parça orada matris pencereleriyle aynı yoldan geçer
 * (engine/search/source.py). Motorun okuduğu şekil yanıtla döner ve burada
 * gösterilir — sunucunun normalizasyonu, istemcinin tahmini değil.
 */
export function ChartSourcePicker({
  mode,
  value,
  onChange,
  symbols,
  unknown,
  lastSource,
}: ChartSourcePickerProps) {
  const { t } = useI18n();
  const listId = useId();
  const today = new Date().toISOString().slice(0, 10);

  return (
    <div className="space-y-4">
      <label className="block space-y-1.5">
        <span className="text-xs font-medium">{t.chartSource.symbol}</span>
        <input
          list={listId}
          value={value.symbol}
          onChange={(e) => onChange({ ...value, symbol: e.target.value.toUpperCase() })}
          placeholder="BTCUSDT"
          spellCheck={false}
          autoComplete="off"
          className="h-9 w-full rounded-md border border-border bg-secondary/40 px-3 font-mono text-sm uppercase outline-none transition-colors placeholder:normal-case placeholder:text-muted-foreground/60 focus:border-brand/50"
        />
        <datalist id={listId}>
          {symbols?.map((symbol) => <option key={symbol} value={symbol} />)}
        </datalist>
        <span className={unknown ? "block text-[11px] text-down" : "block text-[11px] text-muted-foreground"}>
          {unknown
            ? t.chartSource.unknownSymbol
            : symbols
              ? t.chartSource.symbolHint(formatCount(symbols.length))
              : " "}
        </span>
      </label>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-medium">{t.chartSource.length}</span>
          <Badge tone="brand" className="tabular">
            {t.chartSource.lengthValue(value.length)}
          </Badge>
        </div>
        <Slider
          value={[value.length]}
          onValueChange={(v) => onChange({ ...value, length: Array.isArray(v) ? v[0] : v })}
          min={SOURCE_MIN_BARS}
          max={SOURCE_MAX_BARS}
          step={4}
          className="pt-1"
        />
        <p className="text-[11px] leading-relaxed text-muted-foreground">{t.chartSource.lengthHint}</p>
      </div>

      {mode === "historical" ? (
        <label className="block space-y-1.5">
          <span className="text-xs font-medium">{t.chartSource.end}</span>
          <div className="flex gap-2">
            <input
              type="date"
              value={value.endDate}
              max={today}
              min="2017-08-17"
              onChange={(e) => onChange({ ...value, endDate: e.target.value })}
              className="h-9 min-w-0 flex-1 rounded-md border border-border bg-secondary/40 px-3 text-sm tabular outline-none [color-scheme:dark] focus:border-brand/50"
            />
            {value.endDate && (
              <button
                type="button"
                onClick={() => onChange({ ...value, endDate: "" })}
                className="inline-flex h-9 items-center gap-1 rounded-md border border-border px-2.5 text-[11px] text-muted-foreground transition-colors hover:text-foreground"
              >
                <X className="size-3" />
                {t.chartSource.clearEnd}
              </button>
            )}
          </div>
          <span className="block text-[11px] leading-relaxed text-muted-foreground">
            {t.chartSource.endHint}
          </span>
        </label>
      ) : (
        <p className="text-[11px] leading-relaxed text-muted-foreground">{t.chartSource.endLive}</p>
      )}

      {lastSource && (
        <div className="space-y-2 rounded-lg border border-border bg-secondary/40 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            {t.chartSource.read}
          </p>
          <div className="flex items-center gap-3">
            <div className="h-10 w-24 shrink-0">
              <ShapeThumb values={lastSource.query_vector} />
            </div>
            <p className="min-w-0 text-xs font-medium tabular">
              {t.chartSource.range(
                lastSource.symbol,
                formatDate(lastSource.start_time),
                formatDate(lastSource.end_time),
                lastSource.length
              )}
            </p>
          </div>
          {lastSource.excluded_overlap > 0 && (
            <p className="text-[11px] leading-relaxed text-muted-foreground">
              {mode === "historical"
                ? t.chartSource.excludedHistorical(formatCount(lastSource.excluded_overlap))
                : t.chartSource.excludedLive(formatCount(lastSource.excluded_overlap))}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

/** YYYY-MM-DD → o günün son anı (UTC, ms): o gün açılmış son bar alınır. */
export function endOfDayMs(date: string): number | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  if (!match) return null;
  const [, y, m, d] = match;
  return Date.UTC(Number(y), Number(m) - 1, Number(d), 23, 59, 59, 999);
}
