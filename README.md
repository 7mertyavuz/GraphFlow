# GraphFlow

**Grafik formasyonları için görsel arama motoru.**

Kullanıcı bir grafik deseni çizer veya kütüphaneden seçer; GraphFlow gerçek piyasa verisinde bu şekle benzeyen grafikleri bulur ve — tarihsel modda — o formasyondan sonra istatistiksel olarak ne olduğunu dürüstçe raporlar.

---

## İki mod

| Mod | Soru | Kullanıcı |
|---|---|---|
| **Radar** (canlı) | "Şu an hangi coin'ler bu şekli yapıyor?" | İşlem açmak isteyen trader |
| **Backtest** (tarihsel) | "Geçmişte bu şekil oluştuğunda ne olmuş?" | Araştırmacı / strateji geliştirici |

Arka planda **tek motor** vardır; Radar, tarihsel motorun `offset = son bar` özel hâlidir.

---

## Nasıl çalışır

```
Kullanıcı çizimi ──▶ log fiyat → 32 noktaya resample → z-score
                                          │
                                          ▼
        Aşama 1  ·  Kosinüs benzerliği (vektörize)      12M → 5.000   ~0,3 sn
        Pre-NMS  ·  1D-IoU, gevşek (%70)                5.000 → 1.000
        Aşama 2  ·  DDTW + Sakoe-Chiba bandı            1.000 → skorlanmış
        Post-NMS ·  IoU %50 + max 3/sembol              → nihai liste
                                          │
                                          ▼
                    12'li grid  +  "Sonra Ne Oldu?" istatistik kartı
```

**Ölçek gerçeği:** ~12 milyon önceden hesaplanmış pencere vektörü = ~1,5 GB. Tek bir matris çarpımı. Kafka yok, Rust yok, zaman serisi veritabanı yok.

---

## Tasarım ilkeleri

1. **Doğruluk > hız.** Ürünün tek gerçek riski, bir trader'ın sonuçlara bakıp "evet, bu benim çizdiğim şey" diyip diyememesidir.
2. **İstatistiksel dürüstlük.** Sinyal satmıyoruz; ölçülmüş geçmiş dağılım sunuyoruz. Her başarı oranı bir baseline ile birlikte gösterilir.
3. **Motor önce, arayüz sonra.** Notebook göz testi geçilmeden Next.js'e bir satır yazılmaz.
4. **Az parça.** Ölçülmemiş bir problem için erken optimizasyon yapılmaz.

---

## Dokümantasyon

| Belge | İçerik |
|---|---|
| [docs/00-tasarim-kararlari.md](docs/00-tasarim-kararlari.md) | **Karar kaydı** — 18 mimari karar, gerekçeleri ve reddedilen 19 alternatif |
| [docs/01-mimari.md](docs/01-mimari.md) | **Teknik spesifikasyon** — veri katmanı, algoritmalar, API, repo yapısı, yol haritası |
| [docs/07-f46-raporu.md](docs/07-f46-raporu.md) | **F4.6 Vekil Testi Raporu** — Formasyonların şekil mi yoksa momentum vekili mi olduğunun kanıtı |
| [docs/fazlar/](docs/fazlar/README.md) | **Faz belgeleri** — F0…F7 için ayrı ayrı kapsam, ölçümler, bilinen sorunlar, çıkış şartları |

Yeni bir mimari karar alındığında karar kaydına `K-xx` olarak eklenir.

---

## Çalıştırma

Veri deposu (`data/`) commit edilmez; yolu `GRAPHFLOW_DATA_DIR` ile taşıyabilirsiniz.

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt

python -m engine.ingest.download          # F0: Binance klines
python -m tools.backfill --timeframe 4h   # F0: bir dilimi diğerinin evrenine tamamla
python -m engine.matrix.build             # F1: vektör matrisleri
uvicorn engine.api.main:app --reload      # F5: API  → :8000
cd frontend && npm install && npm run dev # F6/F7: arayüz → :3000
pytest -q                                 # testler
```

Matrisler eski bir sürümle üretildiyse sembol haritası eksik olabilir
(eşleşmeler `#897` gibi görünür). Matrisleri yeniden inşa etmeden onarır ve
yazmadan önce Parquet verisine karşı doğrular:

```bash
python -m tools.repair_symbol_map
```

Motorun kendini denetleyen araçları:

```bash
python -m tools.verify_stage1 --timeframe 1d   # matris == Parquet? stride bedeli?
python -m tools.ci_calibration                 # %95 aralık gerçekten %95 mi?
python -m tools.f46_proxy_test                 # şekil mi, momentum vekili mi?
python -m tools.run_outcomes --timeframe 1d    # F4/F4.5 tablolarını yeniden üret
python -m tools.measure_amplitude              # genlik eşiğini korpustan ölç
```

---

## Teknoloji yığını

**Motor:** Python 3.11 · NumPy · SciPy · FastAPI
**Veri:** Binance REST (klines) · Parquet · `.npy` memmap matrisler · Redis (opsiyonel, varsayılan süreç içi önbellek)
**Frontend:** Next.js 16 · Tailwind v4 · TanStack Query · TradingView Lightweight Charts · düz HTML5 Canvas

**Bilinçli olarak yok:** Kafka, Rust/Go, TimescaleDB, WebSocket, Fabric.js.

---

## Yol haritası

| Faz | İçerik | Durum |
|---|---|---|
| [F0](docs/fazlar/F0-veri-ingest.md) | Veri indirme altyapısı | ✅ 1.165 parite · 1,5M bar |
| [F1](docs/fazlar/F1-normalizasyon-matris.md) | Normalizasyon + matris inşası | ✅ 1,92M pencere |
| [F2](docs/fazlar/F2-arama-motoru.md) | Arama motoru (kaskad) | ✅ 51 ms |
| [**F3**](docs/fazlar/F3-dogrulama.md) | **Notebook doğrulaması** 🚦 zorunlu kapı | ✅ **Geçti** |
| [F3.5](docs/fazlar/F3.5-temizlik.md) | Temizlik (yüzdelik skorlama, evren) | ✅ **Geçti** |
| [F4](docs/fazlar/F4-outcome-engine.md) | Outcome Engine (triple-barrier) | ✅ **Bitti** |
| [F4.5](docs/fazlar/F4.5-istatistiksel-saglamlastirma.md) | Ay-bloklu bootstrap + short yönü | ✅ **Bitti** |
| [F4.6](docs/07-f46-raporu.md) | Vekil testi & Ön-getiri eşleştirmeli gölge | ✅ **Yeniden koşuldu** (N=242–509) |
| [F4.7](docs/08-zaman-dilimi-caprazlama.md) | Zaman dilimi çaprazlaması (1d ↔ 4h) | ✅ Bitti |
| [F4.8](docs/09-yapisal-filtre-ve-istatistik.md) | Yapısal filtre ve istatistik | ✅ Bitti — örneklem artık gerçekten o formasyon |
| [F4.9](docs/10-formasyon-denetimi.md) | Formasyon denetimi (12 formasyon) | ✅ Bitti — ground truth ölçüm zemini, K-20/K-21 |
| [F4.10](docs/11-yeniden-olcum.md) | Bulgular yeni motorla yeniden ölçüldü | ✅ **Yeni** — iki dilimde sağ çıkan şekil etkisi yok; köken kaydı |
| [F5](docs/fazlar/F5-api.md) | F4.6 entegrasyonu + FastAPI / Önbellek | ✅ **Bitti** |
| [F6](docs/fazlar/F6-radar-ui.md) | Next.js 16 — Radar (MVP 1) | ✅ **Bitti** |
| [F7](docs/fazlar/F7-backtest-ui.md) | Next.js 16 — Backtest (MVP 2) | ✅ **Bitti** |
| — | Doğrulama araçları: Aşama 1 kaba kuvvet, GA kapsaması | ✅ **Bitti** |

---

## Sorumluluk reddi

GraphFlow bir **araştırma aracıdır**, yatırım tavsiyesi değildir. Ürettiği tüm istatistikler geçmiş fiyat dağılımlarıdır ve gelecekteki performansın göstergesi değildir.
