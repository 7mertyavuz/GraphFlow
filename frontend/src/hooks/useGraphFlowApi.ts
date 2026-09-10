"use client";

import { useCallback, useMemo } from "react";
import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  createSearch,
  getChart,
  getFindings,
  getHealth,
  getSearch,
  getSearchStats,
  getSymbols,
  getTemplates,
  type Direction,
  type Match,
  type SearchRequest,
  type SearchResponse,
  type Timeframe,
} from "@/services/endpoints";
import { useI18n } from "@/i18n/LanguageProvider";

export const PAGE_SIZE = 12;

/*
 * Sunucunun ürettiği metinleri taşıyan sorguların anahtarı DİLİ içerir: dil
 * değişince aynı veri yeni dilde yeniden istenir (engine/i18n.py — sunucu
 * önbelleğinde metin değil veri durduğu için bu ucuzdur).
 */

export function useTemplates() {
  const { lang } = useI18n();
  return useQuery({
    queryKey: ["templates", lang],
    queryFn: getTemplates,
    staleTime: Infinity, // şablon kütüphanesi sürüm başına sabittir
  });
}

/** Zaman diliminin sembol evreni — grafikten sorgu için (id uzayı tf başına). */
export function useSymbols(timeframe: Timeframe, enabled = true) {
  return useQuery({
    queryKey: ["symbols", timeframe],
    queryFn: () => getSymbols(timeframe),
    enabled,
    staleTime: 10 * 60_000,
  });
}

export function useHealth() {
  return useQuery({
    queryKey: ["health"],
    queryFn: getHealth,
    refetchInterval: 120_000,
    retry: false,
  });
}

export function useFindings() {
  const { lang } = useI18n();
  return useQuery({ queryKey: ["findings", lang], queryFn: getFindings, staleTime: Infinity });
}

export function useCreateSearch() {
  const queryClient = useQueryClient();
  const { lang } = useI18n();
  return useMutation({
    mutationFn: (payload: SearchRequest) => createSearch(payload),
    onSuccess: (data) => {
      // İlk sayfa zaten yanıtta: aynı veriyi ikinci kez çekmeyelim.
      queryClient.setQueryData(["search", data.search_id, PAGE_SIZE, lang], {
        pages: [data],
        pageParams: [0],
      });
    },
  });
}

/**
 * Sayfalama önbellekten beslenir: "Daha fazla" tüm matrisi yeniden
 * skorlamaz, sunucudaki arama havuzundan sonraki dilimi ister (K-08).
 */
export function usePaginatedSearch(searchId: string | null, limit = PAGE_SIZE) {
  const { lang } = useI18n();
  const query = useInfiniteQuery({
    queryKey: ["search", searchId, limit, lang],
    enabled: Boolean(searchId),
    initialPageParam: 0,
    queryFn: ({ pageParam }) => getSearch(searchId as string, pageParam as number, limit),
    getNextPageParam: (lastPage: SearchResponse, pages: SearchResponse[]) => {
      // Eksik sayfa = havuz bitti. `total` motorun bulduğu eşleşme sayısıdır
      // ama sunucu bunun yalnızca ilk SEARCH_CACHE_MATCHES tanesini
      // önbelleğe alır (K-08). Yalnız `total`'a bakmak, havuz tükendikten
      // sonra da "Daha fazla" tuşunu açık bırakıp boş sayfa döndürüyordu.
      if (lastPage.results.length < limit) return undefined;
      const loaded = pages.reduce((sum, page) => sum + page.results.length, 0);
      return loaded < lastPage.total ? loaded : undefined;
    },
  });

  const results: Match[] = useMemo(
    () => query.data?.pages.flatMap((page) => page.results) ?? [],
    [query.data]
  );
  const head = query.data?.pages[0];

  return {
    results,
    total: head?.total ?? 0,
    warning: head?.warning ?? null,
    structureRead: head?.structure_read ?? null,
    structureFiltered: head?.structure_filtered ?? false,
    structureStable: head?.structure_stable ?? true,
    envelopeRead: head?.envelope_read ?? null,
    envelopeFiltered: head?.envelope_filtered ?? false,
    source: head?.source ?? null,
    discriminative: head?.discriminative ?? true,
    staleWarning: head?.stale_warning ?? false,
    dataAsOf: head?.data_as_of ?? 0,
    elapsedMs: head?.elapsed_ms ?? 0,
    isLoading: query.isLoading,
    isFetchingNextPage: query.isFetchingNextPage,
    hasMore: Boolean(query.hasNextPage),
    loadMore: useCallback(() => {
      if (query.hasNextPage && !query.isFetchingNextPage) query.fetchNextPage();
    }, [query]),
    error: query.error,
  };
}

export function useSearchStats(searchId: string | null, direction: Direction = "long") {
  const { lang } = useI18n();
  return useQuery({
    queryKey: ["search", searchId, "stats", direction, lang],
    queryFn: () => getSearchStats(searchId as string, direction),
    enabled: Boolean(searchId),
    retry: false,
  });
}

export function useChart(match: Match | null, searchId: string | null, enabled = true) {
  return useQuery({
    queryKey: [
      "chart",
      match?.symbol,
      match?.start_idx,
      match?.end_idx,
      match?.timeframe,
      searchId,
    ],
    enabled: Boolean(match) && enabled,
    staleTime: 5 * 60_000,
    queryFn: () =>
      getChart({
        symbol: (match as Match).symbol,
        start: (match as Match).start_idx,
        end: (match as Match).end_idx,
        timeframe: (match as Match).timeframe,
        searchId: searchId ?? undefined,
      }),
  });
}
