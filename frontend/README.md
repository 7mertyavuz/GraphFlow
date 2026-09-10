# GraphFlow — Frontend

[English](#english) · [Türkçe](#türkçe)

---

## English

The GraphFlow web interface: Radar (live), Backtest (historical) and Findings pages.

### Stack

- **Framework:** Next.js 16 (App Router, Turbopack in dev), React 19, TypeScript
- **Styling:** Tailwind CSS v4 — design tokens in `src/app/globals.css`
- **UI primitives:** shadcn/ui on top of Base UI
- **Data:** TanStack Query v5 (`useInfiniteQuery` for pagination), axios
- **Charts:** TradingView Lightweight Charts v5
- **API types:** generated from the FastAPI schema with `openapi-typescript`

### Run

```bash
npm install
npm run dev              # http://localhost:3000
npm run build            # production build
npx tsc --noEmit         # type check
npx eslint src           # lint
```

The API is expected at `http://localhost:8000/api`; override with `NEXT_PUBLIC_API_BASE_URL` (see `.env.example`).

### Layout

```
src/app/           pages: / · /radar · /backtest · /bulgular (findings)
src/components/
  layout/          header (live data-freshness badge), footer
  query/           DrawPad, TemplatePicker, ShapeThumb, QueryPanel
  results/         MatchCard, MatchGrid, ResultsHeader
  outcome/         StatCard, RegimeTable, OutcomePanel, SessionNotice
  workspace/       SearchWorkspace — shared body of Radar and Backtest
  ui/              button, slider, tooltip, card, badge, alert, segmented, skeleton
src/hooks/         useDraw, useGraphFlowApi, useSessionId
src/services/      apiClient (session header), endpoints
src/utils/         formatters, shape (display only)
```

### Rules

The UI shows what the engine measured; it never builds its own geometry or its own statistics.

- **No bare numbers.** The backend returns a `StatEnvelope`; `formatStat` / `formatCI` look at its `unit`. Passing a win rate through `formatR` would print "+0.55R" — a meaning error, not a formatting one.
- **Expectancy (R) is the headline metric.** Win rate is shown next to its theoretical null, never alone.
- **No rate without a baseline.** If there is no shadow distribution, the edge card explains why instead of showing a number.
- **The client does not normalize.** The drawing is sent as raw `[x, y]` points; resampling to 32 points and z-scoring happen on the server. The drawing is a function `y = f(x)`: moving back to the left overwrites (last write wins), and vertical strokes update the last point instead of being dropped so sharp peaks survive.
- **Chart geometry comes from the server.** The blueprint and warped blueprint are in the `/api/chart` response; `highlight_start/end` are relative to the returned bar array. Do not compute coordinates on the client.
- **Warnings travel with the data.** Distinctiveness, freshness, multiple-comparison, unstable-reading and stale-findings warnings are part of the responses; the UI neither invents nor hides them.
- **Pagination reads the server cache.** "Load more" asks for the next slice of the search pool; the matrix is not re-scored.

### API types

`src/types/api.ts` is generated — never edit it by hand. When the backend contract changes (from the repository root):

```bash
python -c "import json, engine.api.main; open('frontend/openapi.json','w',encoding='utf-8').write(json.dumps(engine.api.main.app.openapi(), indent=2, ensure_ascii=False))"
cd frontend && npx openapi-typescript openapi.json -o src/types/api.ts
```

---

## Türkçe

GraphFlow web arayüzü: Radar (canlı), Backtest (tarihsel) ve Bulgular sayfaları.

### Teknoloji

- **Çatı:** Next.js 16 (App Router, geliştirmede Turbopack), React 19, TypeScript
- **Stil:** Tailwind CSS v4 — tasarım belirteçleri `src/app/globals.css`
- **Arayüz ilkelleri:** Base UI üzerine shadcn/ui
- **Veri:** TanStack Query v5 (sayfalama için `useInfiniteQuery`), axios
- **Grafik:** TradingView Lightweight Charts v5
- **API tipleri:** FastAPI şemasından `openapi-typescript` ile üretilir

### Çalıştırma

```bash
npm install
npm run dev              # http://localhost:3000
npm run build            # üretim derlemesi
npx tsc --noEmit         # tip kontrolü
npx eslint src           # lint
```

API `http://localhost:8000/api` adresinde beklenir; `NEXT_PUBLIC_API_BASE_URL` ile değiştirilir (bkz. `.env.example`).

### Dizin düzeni

```
src/app/           sayfalar: / · /radar · /backtest · /bulgular
src/components/
  layout/          başlık (canlı veri tazeliği rozeti), altbilgi
  query/           DrawPad, TemplatePicker, ShapeThumb, QueryPanel
  results/         MatchCard, MatchGrid, ResultsHeader
  outcome/         StatCard, RegimeTable, OutcomePanel, SessionNotice
  workspace/       SearchWorkspace — Radar ve Backtest'in ortak gövdesi
  ui/              button, slider, tooltip, card, badge, alert, segmented, skeleton
src/hooks/         useDraw, useGraphFlowApi, useSessionId
src/services/      apiClient (oturum başlığı), endpoints
src/utils/         formatters, shape (yalnız görselleştirme)
```

### Kurallar

Arayüz motorun ölçtüğünü gösterir; kendi geometrisini ya da kendi istatistiğini asla kurmaz.

- **Çıplak sayı yok.** Backend `StatEnvelope` döndürür; `formatStat` / `formatCI` zarfın `unit` alanına bakar. Başarı oranını `formatR`'den geçirmek "+0,55R" yazdırır — bu biçim değil anlam hatasıdır.
- **Beklenti (R) başrol metriktir.** Kazanma oranı teorik null'ıyla birlikte gösterilir, tek başına asla.
- **Baseline'sız oran yok.** Gölge dağılım yoksa edge kartı sayı yerine nedenini yazar.
- **İstemci normalize etmez.** Çizim ham `[x, y]` noktaları olarak gönderilir; 32 noktaya indirgeme ve z-score sunucudadır. Çizim bir `y = f(x)` fonksiyonudur: sola dönmek o bölgenin üstüne yazar (sonra yazan kazanır), dikey darbeler düşürülmez son noktayı günceller — sivri tepeler korunur.
- **Grafik geometrisi sunucudan gelir.** Blueprint ve bükülmüş blueprint `/api/chart` yanıtındadır; `highlight_start/end` dönen bar dizisine görelidir. İstemcide koordinat hesaplamayın.
- **Uyarılar veriyle gelir.** Ayırt edicilik, tazelik, çoklu karşılaştırma, kararsız okuma ve bayat bulgu uyarıları yanıtın parçasıdır; arayüz uydurmaz ve gizlemez.
- **Sayfalama sunucu önbelleğinden.** "Daha fazla", arama havuzunun sonraki dilimini ister; matris yeniden skorlanmaz.

### API tipleri

`src/types/api.ts` üretilir — elle düzenlenmez. Backend sözleşmesi değişince (depo kökünden):

```bash
python -c "import json, engine.api.main; open('frontend/openapi.json','w',encoding='utf-8').write(json.dumps(engine.api.main.app.openapi(), indent=2, ensure_ascii=False))"
cd frontend && npx openapi-typescript openapi.json -o src/types/api.ts
```
