"use client";

import { useState } from "react";

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
import { errorMessage } from "@/services/apiClient";
import {
  type Direction,
  type SearchRequest,
  type SessionInfo,
} from "@/services/endpoints";

interface SearchWorkspaceProps {
  mode: SearchRequest["mode"];
  title: string;
  description: string;
  submitLabel: string;
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
export function SearchWorkspace({
  mode,
  title,
  description,
  submitLabel,
  withOutcome = false,
}: SearchWorkspaceProps) {
  const [searchId, setSearchId] = useState<string | null>(null);
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [direction, setDirection] = useState<Direction>("long");

  const createSearch = useCreateSearch();
  const page = usePaginatedSearch(searchId);
  const stats = useSearchStats(withOutcome ? searchId : null, direction);

  const handleSubmit = (payload: SearchRequest) => {
    createSearch.mutate(payload, {
      onSuccess: (data) => {
        setSearchId(data.search_id);
        setSession(data.session);
      },
    });
  };

  const hasSearched = Boolean(searchId);

  return (
    <main className="mx-auto flex w-full max-w-[1600px] flex-1 flex-col gap-6 px-4 py-6 lg:flex-row lg:px-6">
      <aside className="flex w-full shrink-0 flex-col gap-4 lg:w-[340px] xl:w-[380px]">
        <QueryPanel
          mode={mode}
          submitLabel={submitLabel}
          isPending={createSearch.isPending}
          errorMessage={
            createSearch.error
              ? errorMessage(createSearch.error, "Arama başarısız oldu.")
              : null
          }
          onSubmit={handleSubmit}
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
        />

        {hasSearched && page.staleWarning && (
          <Alert tone="warn" title="Veri bayat">
            Depodaki en yeni bar tazelik sınırının gerisinde. Sonuçlar güncel
            piyasayı yansıtmayabilir; yeni veri indirmek için{" "}
            <code className="kbd">python -m engine.ingest.download</code>.
          </Alert>
        )}

        {hasSearched && page.warning && (
          <Alert tone="warn" title="Yapısal benzerlik bulunamadı">
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
        />
      </section>
    </main>
  );
}
