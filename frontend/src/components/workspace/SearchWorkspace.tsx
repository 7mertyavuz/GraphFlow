"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { OutcomePanel } from "@/components/outcome/OutcomePanel";
import { SessionNotice } from "@/components/outcome/SessionNotice";
import { QueryPanel } from "@/components/query/QueryPanel";
import { MatchGrid } from "@/components/results/MatchGrid";
import { ResultsHeader } from "@/components/results/ResultsHeader";
import { Alert } from "@/components/ui/alert";
import {
  useCreateSearch,
  usePaginatedSearch,
  useSearchStats,
} from "@/hooks/useGraphFlowApi";
import { useI18n } from "@/i18n/LanguageProvider";
import { errorMessage } from "@/services/apiClient";
import {
  ledgerKey,
  type Direction,
  type LedgerRow,
  type Match,
  type SearchRequest,
  type SessionInfo,
  type Timeframe,
  type Tolerance,
} from "@/services/endpoints";

/** Radar yenileme aralığı — sunucudaki RADAR_TTL ile aynı (5 dk). */
const RADAR_REFRESH_MS = 5 * 60_000;

interface SearchWorkspaceProps {
  mode: SearchRequest["mode"];
  /** Sayfa metinlerinin anahtarı (i18n/messages.ts → workspace). */
  copy: "radar" | "backtest";
  /** Tarihsel modda "sonra ne oldu" paneli gösterilir. */
  withOutcome?: boolean;
}

/**
 * Radar ve Backtest aynı çalışma alanıdır.
 *
 * Tek motor, tek arayüz: mod yalnızca ``mode`` parametresini değiştirir
 * (K-15). İki ayrı ekran yazmak, Radar'da görülen bir eşleşmenin Backtest'te
 * bulunamadığı tutarsızlıkların kapısını açardı.
 */
export function SearchWorkspace({ mode, copy, withOutcome = false }: SearchWorkspaceProps) {
  const { t } = useI18n();
  const { title, description, submit: submitLabel } = t.workspace[copy];
  const [searchId, setSearchId] = useState<string | null>(null);
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [direction, setDirection] = useState<Direction>("long");
  const [configName, setConfigName] = useState<string | null>(null);
  const [refreshedAt, setRefreshedAt] = useState<number | null>(null);

  const createSearch = useCreateSearch();
  const page = usePaginatedSearch(searchId);
  const stats = useSearchStats(withOutcome ? searchId : null, direction);

  // Son sorgu: Radar kendini yenilerken aynı yükü tekrar gönderir.
  const lastPayload = useRef<SearchRequest | null>(null);

  const run = useCallback(
    (payload: SearchRequest) => {
      lastPayload.current = payload;
      createSearch.mutate(payload, {
        onSuccess: (data) => {
          setSearchId(data.search_id);
          setSession(data.session);
          setRefreshedAt(Date.now());
        },
      });
    },
    [createSearch]
  );

  const handleSearchSimilar = useCallback(
    (match: Match) => {
      run({
        mode,
        timeframe: match.timeframe as Timeframe,
        tolerance: (lastPayload.current?.tolerance as Tolerance) ?? "medium",
        limit: lastPayload.current?.limit ?? 12,
        window_lengths: lastPayload.current?.window_lengths ?? [24, 40, 64, 100],
        source: {
          symbol: match.symbol,
          length: match.window_length,
          end_time: match.end_time,
        },
      });
    },
    [mode, run]
  );

  /**
   * Radar otomatik yenilenir; Backtest yenilenmez.
   *
   * Kendini güncellemeyen bir radar radar değildir: 4h barı kapandığında
   * ekrandaki liste sessizce eskir. Aralık sunucudaki Radar önbelleğiyle
   * aynıdır (RADAR_TTL = 5 dk), yani yenileme çoğu zaman matrisi yeniden
   * taramaz — ölçüldü: 552 ms → 1,2 ms.
   *
   * Muhasebe açısından güvenli olmasının sebebi ayrı: oturum sayacı artık
   * ayrı HİPOTEZ sayıyor, istek değil. Aksi hâlde açık bırakılmış bir sekme
   * kullanıcı hiçbir şey denemeden Bonferroni α'sını küçültürdü.
   */
  useEffect(() => {
    if (mode !== "live" || !searchId) return;
    const timer = setInterval(() => {
      if (lastPayload.current && !createSearch.isPending) {
        run(lastPayload.current);
      }
    }, RADAR_REFRESH_MS);
    return () => clearInterval(timer);
  }, [mode, searchId, createSearch.isPending, run]);

  const hasSearched = Boolean(searchId);

  // Panel ile kartlar aynı konfigürasyonu gösterir: panelde 1:1 seçiliyken
  // kartta 2:1 sonucu okumak iki farklı soruyu karıştırmak olurdu.
  const configs = stats.data ? Object.keys(stats.data.configs) : [];
  const activeConfig = configName && configs.includes(configName) ? configName : (configs[0] ?? null);
  const ledger = useMemo(
    () =>
      stats.data?.ledger?.length
        ? new Map<string, LedgerRow>(stats.data.ledger.map((row) => [ledgerKey(row), row]))
        : null,
    [stats.data]
  );

  return (
    <main className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-6 px-4 py-6 lg:flex-row lg:px-6">
      <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[340px] xl:w-[380px]">
        <QueryPanel
          mode={mode}
          submitLabel={submitLabel}
          isPending={createSearch.isPending}
          errorMessage={
            createSearch.error
              ? errorMessage(createSearch.error, t.workspace.searchFailed, t.errors.network)
              : null
          }
          lastSource={page.source}
          onSubmit={run}
        />
        <SessionNotice session={session} />
      </aside>

      <section className="flex min-w-0 flex-1 flex-col gap-5">
        <ResultsHeader
          title={title}
          description={description}
          total={page.total}
          shown={page.results.length}
          elapsedMs={page.elapsedMs}
          dataAsOf={page.dataAsOf}
          hasSearched={hasSearched && !page.isLoading}
          refreshedAt={mode === "live" ? refreshedAt : null}
          structureRead={page.structureRead}
          structureFiltered={page.structureFiltered}
          structureStable={page.structureStable}
          envelopeRead={page.envelopeRead}
          envelopeFiltered={page.envelopeFiltered}
        />

        {hasSearched && page.staleWarning && (
          <Alert tone="warn" title={t.workspace.staleTitle}>
            {t.workspace.staleBody}{" "}
            <code className="kbd">python -m engine.ingest.download</code>.
          </Alert>
        )}

        {hasSearched && page.warning && (
          <Alert tone="warn" title={t.workspace.noStructureTitle}>
            {page.warning}
          </Alert>
        )}

        {withOutcome && hasSearched && (
          <OutcomePanel
            data={stats.data}
            isLoading={stats.isLoading}
            error={stats.error}
            direction={direction}
            onDirectionChange={setDirection}
            configName={activeConfig}
            onConfigChange={setConfigName}
          />
        )}

        <MatchGrid
          results={page.results}
          searchId={searchId}
          isLoading={createSearch.isPending || (hasSearched && page.isLoading)}
          isFetchingMore={page.isFetchingNextPage}
          hasMore={page.hasMore}
          onLoadMore={page.loadMore}
          hasSearched={hasSearched}
          ledger={withOutcome ? ledger : null}
          config={activeConfig}
          directionLabel={direction === "long" ? t.outcome.long : t.outcome.short}
          onSearchSimilar={handleSearchSimilar}
        />
      </section>
    </main>
  );
}
