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
  getTemplates,
  type Direction,
  type Match,
  type SearchRequest,
  type SearchResponse,
} from "@/services/endpoints";

export const PAGE_SIZE = 12;

export function useTemplates() {
  return useQuery({
    queryKey: ["templates"],
    queryFn: getTemplates,
    staleTime: Infinity, // şablon kütüphanesi sürüm başına sabittir
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
  return useQuery({ queryKey: ["findings"], queryFn: getFindings, staleTime: Infinity });
}

export function useCreateSearch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: SearchRequest) => createSearch(payload),
    onSuccess: (data) => {
      // İlk sayfa zaten yanıtta: aynı veriyi ikinci kez çekmeyelim.
      queryClient.setQueryData(["search", data.search_id, PAGE_SIZE], {
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
  const query = useInfiniteQuery({
    queryKey: ["search", searchId, limit],
    enabled: Boolean(searchId),
    initialPageParam: 0,
    queryFn: ({ pageParam }) => getSearch(searchId as string, pageParam as number, limit),
    getNextPageParam: (lastPage: SearchResponse, pages: SearchResponse[]) => {
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
  return useQuery({
    queryKey: ["search", searchId, "stats", direction],
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
