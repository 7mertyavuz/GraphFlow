# GraphFlow Frontend — Agent Context

Next.js 16 + TypeScript + Tailwind CSS v4 + App Router + `src/` dizini.

## Teknoloji

- **Framework:** Next.js 16 (App Router, Turbopack dev)
- **Stil:** Tailwind CSS v4
- **UI kit:** shadcn/ui, Base UI (Radix değil) primitive'leri üzerine
- **State / Cache:** TanStack React Query v5
- **Grafik:** TradingView Lightweight Charts v5
- **API:** `openapi-typescript` ile backend FastAPI şemalarından üretilen `src/types/api.ts`
- **İkonlar:** lucide-react
- **HTTP:** axios

## Kod konvansiyonları

- Bileşenler `src/components/` altında alan bazlı klasörlenir: `canvas/`, `charts/`, `outcome/`, `layout/`, `ui/`.
- İş mantığı `src/hooks/` ve `src/services/`'te.
- `src/types/api.ts` elle dokunulmaz; backend değişince yeniden üret:
  ```bash
  python -c "import json, engine.api.main; open('frontend/openapi.json','w',encoding='utf-8').write(json.dumps(engine.api.main.app.openapi(), indent=2, ensure_ascii=False))"
  cd frontend && npx openapi-typescript openapi.json -o src/types/api.ts
  ```
- Canvas ve grafik bileşenleri `'use client'` olmalı.
- Sayfalar (`src/app/**/page.tsx`) istemci state'i kullanıyorsa `'use client'` olmalı.

## Komutlar

```bash
cd frontend
npm install
npm run dev        # http://localhost:3000
npm run build      # production build
npx tsc --noEmit   # type check
```

## Bağlı servisler

- Backend: `http://localhost:8000/api` (FastAPI).
- Ortam değişkeni: `NEXT_PUBLIC_API_BASE_URL` (varsayılan `http://localhost:8000/api`).

## Kritik kurallar

- Backend `StatEnvelope` zarfı kullanıyor; frontend **çıplak sayı göstermemeli**.
- Beklenti (R) başrol metriği; kazanma oranı yanında gösterilir.
- Tüm sayılarda `formatR`, `formatPercent`, `formatDecimal` kullan.
- Sayfalama "Daha Fazla (+12)" ile cache'ten devam eder; tüm matris yeniden skorlanmaz.
