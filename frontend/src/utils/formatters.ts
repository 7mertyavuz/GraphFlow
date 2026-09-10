/**
 * Sayı biçimleyicileri.
 *
 * Tek kural: **birim asla kaybolmaz.** Beklenti R cinsindendir, başarı oranı
 * yüzdedir; ikisini aynı biçimleyiciden geçirmek "%64 başarı" yerine "+0,64R"
 * yazdırır — ürünün tüm iddiası okunabilirlikse bu bir hatadır.
 */

const DASH = "—";

type Locale = "tr" | "en";
let locale: Locale = "tr";

/** Arayüz dili değişince LanguageProvider çağırır. */
export function setFormatLocale(next: string): void {
  locale = next === "en" ? "en" : "tr";
}

/** Ondalık ayırıcı: Türkçe virgül, İngilizce nokta. */
function dec(text: string): string {
  return locale === "tr" ? text.replace(".", ",") : text;
}

/** Yüzde işareti: Türkçe önde (%64), İngilizce sonda (64%). */
function pct(text: string): string {
  return locale === "tr" ? `%${text}` : `${text}%`;
}

export function formatR(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${dec(Math.abs(value).toFixed(digits))}R`;
}

export function formatPercent(
  value: number | null | undefined,
  digits = 0
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  return pct(dec((value * 100).toFixed(digits)));
}

export function formatDecimal(
  value: number | null | undefined,
  digits = 2
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  return dec(value.toFixed(digits));
}

/** Birimine göre biçimler — `StatEnvelope.unit` sunucudan gelir. */
export function formatStat(
  value: number | null | undefined,
  unit: string | undefined
): string {
  return unit === "ratio" ? formatPercent(value, 1) : formatR(value);
}

export function formatCI(
  ci: number[] | null | undefined,
  unit: string | undefined
): string {
  if (!ci || ci.length < 2 || !ci.every((v) => Number.isFinite(v))) return DASH;
  return `[${formatStat(ci[0], unit)} · ${formatStat(ci[1], unit)}]`;
}

export function formatAmplitude(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  return pct(dec(value.toFixed(1)));
}

export function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  return value.toLocaleString(locale === "tr" ? "tr-TR" : "en-US");
}

const DATE_OPTIONS: Intl.DateTimeFormatOptions = {
  day: "2-digit",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
};
const DATE_FORMATS: Record<Locale, Intl.DateTimeFormat> = {
  tr: new Intl.DateTimeFormat("tr-TR", DATE_OPTIONS),
  en: new Intl.DateTimeFormat("en-GB", DATE_OPTIONS),
};

export function formatDate(ms: number | null | undefined): string {
  if (!ms) return DASH;
  return DATE_FORMATS[locale].format(new Date(ms));
}

export function formatRelative(ms: number | null | undefined): string {
  if (!ms) return DASH;
  const diff = Date.now() - ms;
  const hours = diff / 3_600_000;
  if (locale === "en") {
    if (hours < 1) return "just now";
    if (hours < 48) return `${Math.round(hours)} h ago`;
    return `${Math.round(hours / 24)} days ago`;
  }
  if (hours < 1) return "az önce";
  if (hours < 48) return `${Math.round(hours)} saat önce`;
  return `${Math.round(hours / 24)} gün önce`;
}

/** Yüzdelik dilim → okunur etiket. Küçük dilim = daha benzer. */
export function formatPercentile(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  const top = locale === "tr" ? "ilk" : "top";
  if (value <= 0.0001) return locale === "tr" ? "ilk ‰0,1" : "top 0.1‰";
  if (value < 0.01) {
    const v = dec((value * 1000).toFixed(1));
    return locale === "tr" ? `${top} ‰${v}` : `${top} ${v}‰`;
  }
  return `${top} ${pct(dec((value * 100).toFixed(1)))}`;
}
