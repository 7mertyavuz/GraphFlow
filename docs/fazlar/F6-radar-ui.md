# F6 — Radar Arayüzü (MVP 1)

**Durum:** ✅ Bitti
**Modül:** `frontend/`
**İlgili kararlar:** [K-05](../00-tasarim-kararlari.md#k-05--i̇ki-ürün-modu-radar-ve-backtest) · [K-08](../00-tasarim-kararlari.md#k-08--sayfalama-12li-grid-ve-cachelenmiş-sıralı-liste) · [K-17](../00-tasarim-kararlari.md#k-17--frontend-hafifleştirmesi)

**Tarih:** 4 Ağustos 2026
**Teknoloji:** Next.js 16 · TypeScript · Tailwind v4 · shadcn/ui (Base UI) · lightweight-charts v5 · React Query v5

---

## Amaç

**"Şu an hangi coin'ler bu şekli yapıyor?"**

Radar, kullanıcının seçtiği/çizdiği şekle benzeyen canlı piyasa grafiklerini bulur. İlk 12 sonuç anında gösterilir; "Daha Fazla" ile cache'ten sonraki 12 sonuç yüklenir.

---

## Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  GraphFlow    [Radar] [Backtest]                                  │
├──────────────────────┬─────────────────────────────────────────────┤
│  SORGU               │  SONUÇLAR                                   │
│  [Çizim] [Şablon]    │  1.847 eşleşme bulundu, 12 gösteriliyor   │
│  ┌──────────────┐    │  ┌────┐ ┌────┐ ┌────┐ ┌────┐               │
│  │  Canvas      │    │  │    │ │    │ │    │ │    │               │
│  │  (grid)      │    │  │    │ │    │ │    │ │    │  3×4 grid     │
│  └──────────────┘    │  │    │ │    │ │    │ │    │               │
│  Aranan şekil (mini) │  └────┘ └────┘ └────┘ └────┘               │
│  Tolerans: Katı/Orta/Esnek                                          │
│  Min. Genlik: %15                                                   │
│  Zaman: 4H / 1G                                                     │
│  [Piyasayı Tara]                                                    │
├──────────────────────┴─────────────────────────────────────────────┤
│  [Daha Fazla (+12)]                                                │
└──────────────────────────────────────────────────────────────────┘
```

---

## Bileşenler

| Dosya | Görev |
|---|---|
| `src/app/radar/page.tsx` | Sayfa düzeni ve durum yönetimi |
| `src/components/canvas/DrawPad.tsx` | HTML5 Canvas + pointer events; 32 noktaya indirgenir, y ters çevrilir |
| `src/components/canvas/TemplatePicker.tsx` | 14 şablonun kategoriye göre listesi |
| `src/components/charts/QueryPreview.tsx` | Aranan şeklin mini önizlemesi |
| `src/components/charts/MatchGrid.tsx` | 3×4 sonuç grid'i + "Daha Fazla" sayfalama |
| `src/components/charts/BlueprintChart.tsx` | lightweight-charts v5: mum + mavi blueprint + kırmızı warp çizgisi |
| `src/components/charts/SkeletonChart.tsx` | Yüklenme animasyonu |
| `src/components/outcome/PValueWarning.tsx` | Oturum sorgu sayacı + Bonferroni uyarısı |
| `src/components/layout/Header.tsx` | Radar / Backtest navigasyonu |
| `src/hooks/useDraw.ts` | Canvas çizim mantığı ve 32 noktalı normalizasyon |
| `src/hooks/useGraphFlowApi.ts` | React Query wrapper'ları (templates, search, stats, pagination) |
| `src/services/endpoints.ts` | `openapi-typescript` ile üretilen tiplere göre API çağrıları |

**Fabric.js / Konva.js kullanılmaz** (K-17). GraphFlow bir çizim editörü değildir; tek polyline yeterlidir.

---

## Önemli kararlar

- **Sayfalama:** İlk 12 sonuç anında; "Daha Fazla" her tıklamada +12 cache'ten yüklenir (K-08).
- **Tolerans:** `Katı / Orta / Esnek` toggle; DTW mesafesi yüzde değildir, bu yüzden "%85 benzerlik" slider'ı yoktur (K-17).
- **Zaman dilimi:** `4H` ve `1G` seçilebilir.
- **Şablon çizim eşdeğerliği:** Şablon seçildiğinde aynı 32 noktalı vektör çizim moduna aktarılır; motor açısından fark yoktur (K-04).

---

## Çıkış şartı

- [x] Serbest çizim ve şablon seçimi aynı sonuç kalitesini veriyor.
- [x] Sayfalama cache'ten, ikinci sayfa anında.
- [x] Kullanıcı testi: çizim ve sonuçlar görsel olarak anlaşılır.

## Bilinen açık noktalar

- 1G zaman dilimi için veri deposu bayat olabilir; `test_real_store_is_fresh` 1G için 5.7 bar geride bildiriyor.
- Şablonlara önceden hesaplanmış Radar cache'i (Cron her 5 dk) henüz kurulmadı; talep üzerine hesaplanıyor.
