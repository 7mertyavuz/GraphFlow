"use client";

import { useState } from "react";
import { ArrowRight, Eye, EyeOff, Loader2, SearchX, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Segmented } from "@/components/ui/segmented";
import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/i18n/LanguageProvider";
import { cn } from "@/lib/utils";
import { ledgerKey, type Direction, type LedgerRow, type Match } from "@/services/endpoints";

import { MatchCard } from "./MatchCard";

interface MatchGridProps {
  results: Match[];
  searchId: string | null;
  isLoading: boolean;
  isFetchingMore: boolean;
  hasMore: boolean;
  onLoadMore: () => void;
  hasSearched: boolean;
  /** Backtest: eşleşme başına defter (anahtar: ledgerKey). */
  ledger?: Map<string, LedgerRow> | null;
  config?: string | null;
  direction?: Direction;
  directionLabel?: string;
  onSearchSimilar?: (match: Match) => void;
  onSearchInHistory?: () => void;
}

export function MatchGrid({
  results,
  searchId,
  isLoading,
  isFetchingMore,
  hasMore,
  onLoadMore,
  hasSearched,
  ledger = null,
  config = null,
  direction = "long",
  directionLabel,
  onSearchSimilar,
  onSearchInHistory,
}: MatchGridProps) {
  const { t } = useI18n();
  const [framing, setFraming] = useState<"fit" | "context">("fit");
  const [showBlueprint, setShowBlueprint] = useState(true);
  const [showWarp, setShowWarp] = useState(false);

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 2xl:grid-cols-3">
        {Array.from({ length: 6 }).map((_, i) => (
          <Skeleton key={i} className="h-[248px]" />
        ))}
      </div>
    );
  }

  if (!hasSearched) {
    return (
      <Placeholder
        icon={Sparkles}
        title={t.grid.notYetTitle}
        body={t.grid.notYetBody}
      />
    );
  }

  if (results.length === 0) {
    return (
      <div className="space-y-4">
        <Placeholder
          icon={SearchX}
          title={t.grid.noneTitle}
          body={t.grid.noneBody}
        />
        {onSearchInHistory && (
          <div className="flex flex-col items-center gap-3 rounded-xl border border-brand/25 bg-brand/[0.06] p-4 text-center">
            <p className="max-w-lg text-xs text-muted-foreground">{t.grid.radarScarceHint}</p>
            <Button onClick={onSearchInHistory} size="sm" className="gap-1.5">
              {t.grid.searchHistoryCta}
              <ArrowRight className="size-3.5" />
            </Button>
          </div>
        )}
      </div>
    );
  }

  const framingOptions = [
    { value: "fit" as const, label: t.grid.fitPattern },
    { value: "context" as const, label: t.grid.fullContext },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Segmented options={framingOptions} value={framing} onChange={setFraming} size="sm" />
        <div className="flex items-center gap-1.5 text-[11px]">
          <button
            type="button"
            onClick={() => setShowBlueprint((v) => !v)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 transition-colors",
              showBlueprint
                ? "border-brand/40 bg-brand/10 text-brand"
                : "border-border bg-secondary/40 text-muted-foreground hover:text-foreground"
            )}
          >
            {showBlueprint ? <Eye className="size-3" /> : <EyeOff className="size-3" />}
            {t.grid.toggleOverlay}
          </button>
          <button
            type="button"
            onClick={() => setShowWarp((v) => !v)}
            className={cn(
              "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 transition-colors",
              showWarp
                ? "border-warp/40 bg-warp/10 text-warp"
                : "border-border bg-secondary/40 text-muted-foreground hover:text-foreground"
            )}
          >
            {t.grid.toggleWarp}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 2xl:grid-cols-3">
        {results.map((match) => (
          <MatchCard
            key={`${match.symbol}-${match.timeframe}-${match.start_idx}-${match.window_length}`}
            match={match}
            searchId={searchId}
            ledger={ledger?.get(ledgerKey(match)) ?? null}
            config={config}
            direction={direction}
            directionLabel={directionLabel}
            fitPattern={framing === "fit"}
            showBlueprint={showBlueprint}
            showWarp={showWarp}
            onSearchSimilar={onSearchSimilar}
          />
        ))}
      </div>

      {onSearchInHistory && results.length < 3 && (
        <div className="flex flex-col items-center justify-between gap-3 rounded-xl border border-brand/25 bg-brand/[0.06] px-4 py-3 sm:flex-row">
          <p className="text-xs text-muted-foreground">{t.grid.radarScarceHint}</p>
          <Button onClick={onSearchInHistory} size="sm" className="shrink-0 gap-1.5">
            {t.grid.searchHistoryCta}
            <ArrowRight className="size-3.5" />
          </Button>
        </div>
      )}

      {hasMore && (
        <div className="flex justify-center pt-2">
          <Button variant="outline" onClick={onLoadMore} disabled={isFetchingMore} className="gap-2">
            {isFetchingMore && <Loader2 className="size-4 animate-spin" />}
            {t.grid.more}
          </Button>
        </div>
      )}
    </div>
  );
}

function Placeholder({
  icon: Icon,
  title,
  body,
}: {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  body: string;
}) {
  return (
    <div className="flex min-h-[280px] flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border p-10 text-center">
      <div className="rounded-full border border-border bg-secondary/50 p-3">
        <Icon className="size-5 text-muted-foreground" />
      </div>
      <p className="text-sm font-medium">{title}</p>
      <p className="max-w-md text-xs leading-relaxed text-muted-foreground">{body}</p>
    </div>
  );
}
