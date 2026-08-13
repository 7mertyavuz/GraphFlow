/**
 * Sayı biçimleyicileri.
 *
 * Tek kural: **birim asla kaybolmaz.** Beklenti R cinsindendir, başarı oranı
 * yüzdedir; ikisini aynı biçimleyiciden geçirmek "%64 başarı" yerine "+0,64R"
 * yazdırır — ürünün tüm iddiası okunabilirlikse bu bir hatadır.
 */

const DASH = "—";

export function formatR(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  const sign = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${sign}${Math.abs(value).toFixed(digits).replace(".", ",")}R`;
}

export function formatPercent(
  value: number | null | undefined,
  digits = 0
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  return `%${(value * 100).toFixed(digits).replace(".", ",")}`;
}

export function formatDecimal(
  value: number | null | undefined,
  digits = 2
): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  return value.toFixed(digits).replace(".", ",");
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
  return `%${value.toFixed(1).replace(".", ",")}`;
}

export function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  return value.toLocaleString("tr-TR");
}

const DATE_FORMAT = new Intl.DateTimeFormat("tr-TR", {
  day: "2-digit",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

export function formatDate(ms: number | null | undefined): string {
  if (!ms) return DASH;
  return DATE_FORMAT.format(new Date(ms));
}

export function formatRelative(ms: number | null | undefined): string {
  if (!ms) return DASH;
  const diff = Date.now() - ms;
  const hours = diff / 3_600_000;
  if (hours < 1) return "az önce";
  if (hours < 48) return `${Math.round(hours)} saat önce`;
  return `${Math.round(hours / 24)} gün önce`;
}

/** Yüzdelik dilim → okunur etiket. Küçük dilim = daha benzer. */
export function formatPercentile(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  if (value <= 0.0001) return "ilk ‰0,1";
  if (value < 0.01) return `ilk ‰${(value * 1000).toFixed(1).replace(".", ",")}`;
  return `ilk %${(value * 100).toFixed(1).replace(".", ",")}`;
}
