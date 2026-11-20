"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { OutcomePanel } from "@/components/outcome/OutcomePanel";
import { SessionNotice } from "@/components/outcome/SessionNotice";
import { QueryPanel, type SearchHandoff } from "@/components/query/QueryPanel";
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
  type BaselineMode,
  type Direction,
  type LedgerRow,
  type Match,
  type OutcomeCondition,
  type SearchRequest,
  type SessionInfo,
  type Timeframe,
  type Tolerance,
} from "@/services/endpoints";

/** Radar yenileme aralığı — sunucudaki RADAR_TTL ile aynı (5 dk). */
const RADAR_REFRESH_MS = 5 * 60_000;
const HANDOFF_STORAGE_KEY = "graphflow:handoff";

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
  const router = useRouter();
  const { title, description, submit: submitLabel } = t.workspace[copy];
  const [searchId, setSearchId] = useState<string | null>(null);
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [direction, setDirection] = useState<Direction>("long");
  const [baseline, setBaseline] = useState<BaselineMode>("standard");
  const [condition, setCondition] = useState<OutcomeCondition>("all");
  const [configName, setConfigName] = useState<string | null>(null);
  const [refreshedAt, setRefreshedAt] = useState<number | null>(null);
  const [handoff, setHandoff] = useState<SearchHandoff | null>(null);

  const createSearch = useCreateSearch();
  const page = usePaginatedSearch(searchId);
  const stats = useSearchStats(
    withOutcome ? searchId : null,
    direction,
    baseline,
    condition
  );

  // Son sorgu: Radar kendini yenilerken aynı yükü tekrar gönderir.
  const lastPayload = useRef<SearchRequest | null>(null);
  const handoffAutoRan = useRef(false);

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

  useEffect(() => {
    if (mode !== "historical" || handoffAutoRan.current) return;
    try {
      const raw = window.sessionStorage.getItem(HANDOFF_STORAGE_KEY);
      if (!raw) return;
      window.sessionStorage.removeItem(HANDOFF_STORAGE_KEY);
      handoffAutoRan.current = true;
      const parsed = JSON.parse(raw) as SearchHandoff;
      queueMicrotask(() => {
        setHandoff(parsed);
        run({
          mode: "historical",
          timeframe: parsed.timeframe,
          tolerance: parsed.tolerance,
          min_amplitude: parsed.min_amplitude,
          limit: 12,
          window_lengths: parsed.window_lengths,
          points: parsed.sourceKind === "draw" ? parsed.points ?? null : null,
          template_id: parsed.sourceKind === "template" ? parsed.template_id ?? null : null,
          source: parsed.sourceKind === "chart" ? parsed.source ?? null : null,
        });
      });
    } catch {
      // Hatalı sessionStorage yükü aramayı düşürmemeli
    }
  }, [mode, run]);

  const consumeHandoff = useCallback(() => {
    setHandoff(null);
  }, []);

  const handleSearchInHistory = useCallback(() => {
    const p = lastPayload.current;
    if (!p) {
      router.push("/backtest");
      return;
    }
    const sourceKind: SearchHandoff["sourceKind"] = p.template_id
      ? "template"
      : p.source
        ? "chart"
        : "draw";
    const rawPairs =
      Array.isArray(p.points) && p.points.length > 0 && Array.isArray(p.points[0])
        ? (p.points as number[][])
        : null;
    const payload: SearchHandoff = {
      sourceKind,
      points: rawPairs,
      template_id: p.template_id ?? null,
      source: p.source ?? null,
      timeframe: p.timeframe as Timeframe,
      tolerance: (p.tolerance as Tolerance) ?? "medium",
      min_amplitude: typeof p.min_amplitude === "number" ? p.min_amplitude : 10,
      window_lengths: Array.isArray(p.window_lengths) ? p.window_lengths : [24, 40, 64, 100],
    };
    try {
      window.sessionStorage.setItem(HANDOFF_STORAGE_KEY, JSON.stringify(payload));
    } catch {
      // sessionStorage kapalıysa yine de sayfaya geç
    }
    router.push("/backtest");
  }, [router]);

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
          initialHandoff={handoff}
          onConsumeHandoff={consumeHandoff}
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
            baseline={baseline}
            onBaselineChange={setBaseline}
            condition={condition}
            onConditionChange={setCondition}
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
          direction={direction}
          directionLabel={direction === "long" ? t.outcome.long : t.outcome.short}
          onSearchSimilar={handleSearchSimilar}
          onSearchInHistory={mode === "live" ? handleSearchInHistory : undefined}
        />
      </section>
    </main>
  );
}
