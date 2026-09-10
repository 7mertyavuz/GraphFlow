import { apiClient } from "./apiClient";
import { type components } from "@/types/api";

export type SearchRequest = components["schemas"]["SearchRequest"];
export type SearchResponse = components["schemas"]["SearchResponse"];
export type Match = components["schemas"]["MatchResponse"];
export type OutcomeResponse = components["schemas"]["OutcomeResponse"];
export type OutcomeConfig = components["schemas"]["OutcomeConfigResponse"];
export type StatEnvelope = components["schemas"]["StatEnvelope"];
export type RegimeRow = components["schemas"]["RegimeRow"];
export type ReturnDistribution = components["schemas"]["ReturnDistribution"];
export type FanReport = components["schemas"]["FanReport"];
export type FanBands = components["schemas"]["FanBands"];
export type LedgerRow = components["schemas"]["LedgerRow"];

/** Eşleşme ↔ defter satırı eşlemesinin anahtarı (sunucunun olay kimliği). */
export function ledgerKey(row: { symbol_id: number; end_idx: number; window_length: number }): string {
  return `${row.symbol_id}:${row.end_idx}:${row.window_length}`;
}
export type Template = components["schemas"]["TemplateResponse"];
export type ChartResponse = components["schemas"]["ChartResponse"];
export type FindingsResponse = components["schemas"]["FindingsResponse"];
export type HealthResponse = components["schemas"]["HealthResponse"];
export type SessionInfo = components["schemas"]["SessionInfo"];
export type ChartSource = components["schemas"]["ChartSource"];
export type SourceInfo = components["schemas"]["SourceInfo"];

export type Mode = SearchRequest["mode"];
export type Timeframe = SearchRequest["timeframe"];
export type Tolerance = SearchRequest["tolerance"];
export type Direction = "long" | "short";

export async function createSearch(payload: SearchRequest): Promise<SearchResponse> {
  const { data } = await apiClient.post<SearchResponse>("/search", payload);
  return data;
}

export async function getSearch(
  searchId: string,
  offset = 0,
  limit = 12
): Promise<SearchResponse> {
  const { data } = await apiClient.get<SearchResponse>(`/search/${searchId}`, {
    params: { offset, limit },
  });
  return data;
}

export async function getSearchStats(
  searchId: string,
  direction: Direction = "long"
): Promise<OutcomeResponse> {
  const { data } = await apiClient.get<OutcomeResponse>(`/search/${searchId}/stats`, {
    params: { direction },
  });
  return data;
}

export async function getTemplates(): Promise<Template[]> {
  const { data } = await apiClient.get<Template[]>("/templates");
  return data;
}

export async function getSymbols(timeframe: Timeframe): Promise<string[]> {
  const { data } = await apiClient.get<string[]>("/symbols", { params: { timeframe } });
  return data;
}

export async function getChart(params: {
  symbol: string;
  start: number;
  end: number;
  timeframe: string;
  searchId?: string;
}): Promise<ChartResponse> {
  const { data } = await apiClient.get<ChartResponse>(`/chart/${params.symbol}`, {
    params: {
      start: params.start,
      end: params.end,
      timeframe: params.timeframe,
      search_id: params.searchId,
    },
  });
  return data;
}

export async function getFindings(): Promise<FindingsResponse> {
  const { data } = await apiClient.get<FindingsResponse>("/findings");
  return data;
}

export async function getHealth(): Promise<HealthResponse> {
  const { data } = await apiClient.get<HealthResponse>("/health");
  return data;
}
