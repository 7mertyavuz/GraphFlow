# F7 — Backtest Arayüzü (MVP 2)

**Durum:** ✅ Bitti (temel MVP)
**Modül:** `frontend/`
**İlgili kararlar:** [K-06](../00-tasarim-kararlari.md#k-06--öldürücü-özellik-sonra-ne-oldu) · [K-12](../00-tasarim-kararlari.md#k-12--zaman-eşleştirmeli-baseline-gölge-dağılım) · [K-16](../00-tasarim-kararlari.md#k-16--triple-barrier-atr-tabanlı-göreli-bariyerler)

**Tarih:** 4 Ağustos 2026
**Teknoloji:** Next.js 16 · TypeScript · Tailwind v4 · shadcn/ui (Base UI) · lightweight-charts v5 · React Query v5

---

## Amaç

**"Geçmişte bu şekil oluştuğunda ne olmuş?"**

F6 ile aynı arayüz iskeleti, aynı motor (`mode='historical'`), üzerine **outcome kartı** eklenir. Sistem ölçülmüş geçmiş dağılımı dürüstçe raporlar.

---

## Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  GraphFlow    [Radar] [Backtest]                                  │
├──────────────────────┬─────────────────────────────────────────────┤
│  SORGU               │  SONRA NE OLDU?                             │
│  [Çizim] [Şablon]    │  Beklenti: +0.18R  [Anlamlı / Anlamsız]     │
│  Canvas              │  Başarı: %41  (null: %33 · gölge: %34)     │
│  Aranan şekil (mini) │  Edge: +0.06R                               │
│  Tolerans / Genlik   │  N = 112 bağımsız olay                      │
│  Zaman: 4H / 1G      │  ── Rejim Kırılımı ──                       │
│  [Geçmişte Tara]     │  2021: +0.31R (n=38)                        │
│                      │  2022: -0.08R (n=24)                        │
├──────────────────────┴─────────────────────────────────────────────┤
│  EŞLEŞMELER                                                       │
│  3×4 grid + Daha Fazla (+12)                                      │
└──────────────────────────────────────────────────────────────────┘
```

---

## Outcome kartı

| Bileşen | Dosya |
|---|---|
| Beklenti (R) | `src/components/outcome/StatEnvelope.tsx` |
| Başarı oranı | `src/components/outcome/StatEnvelope.tsx` |
| Edge (R) | `src/components/outcome/StatEnvelope.tsx` |
| Rejim kırılımı | `src/components/outcome/RegimeTable.tsx` |
| Sorumluluk reddi | `src/app/backtest/page.tsx` |
| P-hacking uyarısı | `src/components/outcome/PValueWarning.tsx` |

### Sunum kuralları

| Kural | Uygulama |
|---|---|
| **Baseline'sız başarı oranı gösterilmez** | Her oran yanında teorik null ve gölge dağılım gösterilir |
| **Beklenti (R) başrolde** | En büyük metrik beklentidir; kazanma oranı manipüle edilebilir |
| **N = bağımsız olay** | API post-NMS + ileri pencere ayrımı uygular (K-09) |
| **Rejim kırılımı zorunlu** | Yıllara göre dağılım tablosu her zaman gösterilir |
| **Sorumluluk reddi görünür** | "Bu veriler geçmiş dağılımlardır, işlem sinyali değildir" |
| **Çıplak sayı yasak** | Backend `StatEnvelope` zarfıyla döner; frontend sayı çıplak bırakmaz |

---

## Bileşenler

| Dosya | Görev |
|---|---|
| `src/app/backtest/page.tsx` | Sayfa düzeni, sorgu + outcome kartı + eşleşmeler |
| `src/components/outcome/StatEnvelope.tsx` | Tek bir metrik için zarf kartı (value, %95 GA, null, shadow, n) |
| `src/components/outcome/RegimeTable.tsx` | Yıllara göre beklenti/başarı tablosu |
| `src/components/outcome/PValueWarning.tsx` | Oturum sorgu sayacı ve Bonferroni uyarısı |
| `src/components/charts/MatchGrid.tsx` | Geçmiş eşleşmelerin grid'i (sayfalama ile) |
| `src/components/charts/BlueprintChart.tsx` | Mum grafik + blueprint + warp overlay |

---

## Çıkış şartı

- [x] Outcome kartı doğru sayıları gösteriyor, baseline'sız hiçbir oran ekranda yok.
- [x] Rejim kırılımı çalışıyor.
- [x] Sorumluluk reddi ve p-hacking uyarısı görünür.

## Ertelenen / açık noktalar

- **Kanıt tablosu:** N bağımsız olayın listelenmesi (delist ikonu ile) henüz yapılmadı; backend'den event listesi endpoint'i + sanal liste gerekir.
- **1G veri tazeliği:** `test_real_store_is_fresh` 1G için 5.7 bar geride.
