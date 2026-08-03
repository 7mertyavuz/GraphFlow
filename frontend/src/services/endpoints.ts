import { apiClient } from "./apiClient";
import { type paths } from "@/types/api";

type SearchRequest =
  paths["/api/search"]["post"]["requestBody"]["content"]["application/json"];
type SearchResponse =
  paths["/api/search"]["post"]["responses"]["200"]["content"]["application/json"];

type GetSearchParams = {
  search_id: string;
  offset?: number;
  limit?: number;
};

type PaginatedSearchResponse =
  paths["/api/search/{search_id}"]["get"]["responses"]["200"]["content"]["application/json"];

type OutcomeResponse =
  paths["/api/search/{search_id}/stats"]["get"]["responses"]["200"]["content"]["application/json"];

type TemplateResponse =
  paths["/api/templates"]["get"]["responses"]["200"]["content"]["application/json"];

type ChartResponse =
  paths["/api/chart/{symbol}"]["get"]["responses"]["200"]["content"]["application/json"];

export async function createSearch(payload: SearchRequest): Promise<SearchResponse> {
  const res = await apiClient.post<SearchResponse>("/search", payload);
  return res.data;
}

export async function getSearch({
  search_id,
  offset = 0,
  limit = 12,
}: GetSearchParams): Promise<PaginatedSearchResponse> {
  const res = await apiClient.get<PaginatedSearchResponse>(
    `/search/${search_id}`,
    { params: { offset, limit } }
  );
  return res.data;
}

export async function getSearchStats(search_id: string): Promise<OutcomeResponse> {
  const res = await apiClient.get<OutcomeResponse>(`/search/${search_id}/stats`);
  return res.data;
}

export async function getTemplates(): Promise<TemplateResponse> {
  const res = await apiClient.get<TemplateResponse>("/templates");
  return res.data;
}

export async function getChart(
  symbol: string,
  params: {
    start: number;
    end: number;
    timeframe?: string;
  }
): Promise<ChartResponse> {
  const res = await apiClient.get<ChartResponse>(`/chart/${symbol}`, {
    params,
  });
  return res.data;
}
