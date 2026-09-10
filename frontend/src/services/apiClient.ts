"use client";

import axios, { AxiosHeaders } from "axios";

import { getOrCreateSessionId } from "@/hooks/useSessionId";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: { "Content-Type": "application/json" },
  timeout: 60_000,
});

/** Arayüz dili — sunucu kullanıcı metinlerini (okuma, uyarı, hüküm) bu dilde üretir. */
let apiLanguage = "tr";

export function setApiLanguage(lang: string): void {
  apiLanguage = lang;
}

/**
 * Oturum kimliği her istekte gider: sunucu denenen şekil sayısını sayar ve
 * Bonferroni düzeltilmiş α'yı yanıtla birlikte döner (çoklu karşılaştırma).
 */
apiClient.interceptors.request.use((config) => {
  // Dil başlığı oturumdan bağımsızdır: kimlik yokken de gitmeli.
  if (config.headers instanceof AxiosHeaders) {
    config.headers.set("Accept-Language", apiLanguage);
  } else {
    config.headers = AxiosHeaders.from({
      ...(config.headers as Record<string, string> | undefined),
      "Accept-Language": apiLanguage,
    });
  }

  const sessionId = getOrCreateSessionId();
  if (!sessionId) return config;

  // Başlığı sessizce düşürmek, oturum sayacını hiç artmayan bir sayaca —
  // yani hiç görünmeyen bir Bonferroni uyarısına — çevirirdi.
  if (config.headers instanceof AxiosHeaders) {
    config.headers.set("X-Session-Id", sessionId);
  } else {
    config.headers = AxiosHeaders.from({
      ...(config.headers as Record<string, string> | undefined),
      "X-Session-Id": sessionId,
    });
  }
  return config;
});

/** Sunucunun `detail` mesajını yüzeye çıkarır; ağ hatası için çağıranın metni. */
export function errorMessage(error: unknown, fallback: string, networkMessage?: string): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (error.code === "ERR_NETWORK" && networkMessage) return networkMessage;
  }
  return fallback;
}
