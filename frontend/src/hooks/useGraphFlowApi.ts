"use client";

import {
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query";
import {
  createSearch,
  getSearch,
  getSearchStats,
  getTemplates,
} from "@/services/endpoints";
import { type paths } from "@/types/api";

export type SearchMode = "historical" | "live";
export type Tolerance = "strict" | "medium" | "flexible";
export type Timeframe = "4h" | "1d";

export type SearchPayload =
  paths["/api/search"]["post"]["requestBody"]["content"]["application/json"];

export type SearchResponse =
  paths["/api/search"]["post"]["responses"]["200"]["content"]["application/json"];

export type OutcomeResponse =
  paths["/api/search/{search_id}/stats"]["get"]["responses"]["200"]["content"]["application/json"];

export type TemplateResponse =
  paths["/api/templates"]["get"]["responses"]["200"]["content"]["application/json"];

export function useTemplates() {
  return useQuery({
    queryKey: ["templates"],
    queryFn: getTemplates,
  });
}

export function useCreateSearch() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createSearch,
    onSuccess: (data) => {
      queryClient.setQueryData(["search", data.search_id], data);
    },
  });
}

export function useSearchResults(searchId: string | null, offset = 0, limit = 12) {
  return useQuery({
    queryKey: ["search", searchId, offset, limit],
    queryFn: () => {
      if (!searchId) throw new Error("searchId gerekli");
      return getSearch({ search_id: searchId, offset, limit });
    },
    enabled: !!searchId,
  });
}

export function useSearchStats(searchId: string | null) {
  return useQuery({
    queryKey: ["search", searchId, "stats"],
    queryFn: () => {
      if (!searchId) throw new Error("searchId gerekli");
      return getSearchStats(searchId);
    },
    enabled: !!searchId,
  });
}
