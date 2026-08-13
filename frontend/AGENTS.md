# GraphFlow Frontend — Agent Context

Next.js 16 + TypeScript + Tailwind CSS v4 + App Router + `src/` dizini.

## Teknoloji

- **Framework:** Next.js 16 (App Router, Turbopack dev)
- **Stil:** Tailwind CSS v4 — tasarım belirteçleri `src/app/globals.css`
- **UI kit:** shadcn/ui, Base UI (Radix değil) primitive'leri üzerine
- **State / Cache:** TanStack React Query v5 (`useInfiniteQuery` ile sayfalama)
- **Grafik:** TradingView Lightweight Charts v5
- **API:** `openapi-typescript` ile FastAPI şemalarından üretilen `src/types/api.ts`
- **İkonlar:** lucide-react · **HTTP:** axios

## Dizin düzeni

```
src/app/           sayfalar: / · /radar · /backtest · /bulgular
src/components/
  layout/          Header (canlı veri tazeliği rozeti), Footer
  query/           DrawPad, TemplatePicker, ShapeThumb, QueryPanel
  results/         MatchCard (grafik karosu), MatchGrid, ResultsHeader
  outcome/         StatCard, RegimeTable, OutcomePanel, SessionNotice
  workspace/       SearchWorkspace — Radar ve Backtest'in ortak gövdesi
  ui/              button, slider, tooltip, card, badge, alert, segmented, skeleton
src/hooks/         useDraw, useGraphFlowApi, useSessionId
src/services/      apiClient (oturum başlığı), endpoints
src/utils/         formatters, shape (yalnızca görselleştirme)
```

## Kritik kurallar

- **Çıplak sayı yasak.** Backend `StatEnvelope` döner; `formatStat`/`formatCI`
  zarfın `unit` alanına bakar. Başarı oranını `formatR`'den geçirmek "+0,55R"
  yazdırır — bu bir hatadır, biçim hatası değil anlam hatası.
- **Beklenti (R) başrol metriktir.** Kazanma oranı yanında, teorik null ile
  birlikte gösterilir; tek başına asla.
- **Baseline'sız oran gösterilmez.** Gölge dağılım yoksa edge kartı yerine
  neden gösterilemediği yazılır.
- **Normalizasyonu istemci yapmaz.** Çizim ham nokta olarak gönderilir; 32
  noktaya indirgeme ve z-score sunucudadır (K-02/K-04). `utils/shape.ts`
  yalnızca ekranda eğri çizer.
- **Grafik geometrisi sunucudan gelir.** Blueprint ve bükülmüş blueprint
  `/api/chart` yanıtındadır; `highlight_start/end` dönen bar dizisine
  **görelidir**. İstemcide koordinat hesaplamayın (bkz. `engine/api/chart.py`).
- **Uyarılar veriyle gelir.** Ayırt edicilik (S-1), veri tazeliği ve çoklu
  karşılaştırma uyarıları yanıtın içindedir; arayüz bunları uydurmaz ve
  gizlemez.
- **Sayfalama önbellekten.** "Daha fazla" sunucudaki arama havuzundan sonraki
  dilimi ister; matris yeniden skorlanmaz (K-08).

## Tip üretimi

`src/types/api.ts` elle düzenlenmez. Backend sözleşmesi değişince:

```bash
python -c "import json, engine.api.main; open('frontend/openapi.json','w',encoding='utf-8').write(json.dumps(engine.api.main.app.openapi(), indent=2, ensure_ascii=False))"
cd frontend && npx openapi-typescript openapi.json -o src/types/api.ts
```

## Komutlar

```bash
cd frontend
npm install
npm run dev              # http://localhost:3000
npm run build            # production build
npx tsc --noEmit         # tip kontrolü
npx eslint src           # lint
```

## Bağlı servisler

- Backend: `http://localhost:8000/api` (FastAPI).
- `NEXT_PUBLIC_API_BASE_URL` ile değiştirilir (bkz. `.env.example`).
