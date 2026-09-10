"use client";

import { createContext, useContext, useEffect, useMemo, useSyncExternalStore } from "react";

import { setApiLanguage } from "@/services/apiClient";
import { setFormatLocale } from "@/utils/formatters";

import { LANGS, messages, type Lang, type Messages } from "./messages";

const STORAGE_KEY = "graphflow.lang";

interface LanguageContextValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: Messages;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

/** Kayıtlı seçim, yoksa tarayıcının dil tercihinden desteklenen ilk dil. */
function detectLanguage(): Lang {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored && (LANGS as string[]).includes(stored)) return stored as Lang;
  } catch {
    // depolama kapalı olabilir (gizli pencere, site verisi engelli)
  }
  const preferred = window.navigator.languages?.length
    ? window.navigator.languages
    : [window.navigator.language];
  for (const tag of preferred) {
    const primary = tag?.toLowerCase().split("-")[0];
    if ((LANGS as string[]).includes(primary)) return primary as Lang;
  }
  return "tr";
}

/*
 * Dil, React dışında küçük bir depo olarak tutulur ve `useSyncExternalStore`
 * ile okunur. Sunucu anlık görüntüsü Türkçe'dir; istemci hidrasyondan sonra
 * tarayıcı tercihine geçer — effect içinde setState yapmadan ve hidrasyon
 * uyuşmazlığı uyarısı üretmeden.
 *
 * Modül düzeyindeki ayarlar (API'nin Accept-Language başlığı, sayıların
 * yazımı) durum değişmeden ÖNCE güncellenir: sonra güncellenseydi dil
 * değişimini izleyen ilk çizim sayıları eski yerel ayarla biçimlerdi.
 */
let current: Lang | null = null;
const listeners = new Set<() => void>();

function applyModuleSettings(lang: Lang): void {
  setApiLanguage(lang);
  setFormatLocale(lang);
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function getSnapshot(): Lang {
  if (current === null) {
    current = detectLanguage();
    applyModuleSettings(current);
  }
  return current;
}

function getServerSnapshot(): Lang {
  return "tr";
}

function setLanguage(next: Lang): void {
  current = next;
  applyModuleSettings(next);
  try {
    window.localStorage.setItem(STORAGE_KEY, next);
  } catch {
    // kayıt olmasa da seçim bu oturumda geçerli
  }
  listeners.forEach((listener) => listener());
}

/**
 * Arayüz dili. Dil değişince sorgu anahtarları dili içerdiği için
 * sunucunun ürettiği metinler (motorun okuması, uyarılar, hükümler) yeni
 * dilde yeniden gelir (engine/i18n.py).
 */
export function LanguageProvider({ children }: { children: React.ReactNode }) {
  const lang = useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);

  useEffect(() => {
    document.documentElement.lang = lang;
    document.title = messages[lang].meta.title;
  }, [lang]);

  const value = useMemo(() => ({ lang, setLang: setLanguage, t: messages[lang] }), [lang]);
  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useI18n(): LanguageContextValue {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useI18n must be used inside LanguageProvider");
  return ctx;
}
