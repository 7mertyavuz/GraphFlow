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
| [docs/fazlar/](docs/fazlar/README.md) | **Faz belgeleri** — F0…F7 için ayrı ayrı kapsam, ölçümler, bilinen sorunlar, çıkış şartları |

Yeni bir mimari karar alındığında karar kaydına `K-xx` olarak eklenir.

---

## Teknoloji yığını

**Motor:** Python 3.11 · NumPy · `dtaidistance` · FastAPI
**Veri:** Binance REST (klines) · Parquet · PostgreSQL · Redis
**Frontend:** Next.js · TailwindCSS · TradingView Lightweight Charts · düz HTML5 Canvas

**Bilinçli olarak yok:** Kafka, Rust/Go, TimescaleDB, WebSocket, Fabric.js.

---

## Yol haritası

| Faz | İçerik | Durum |
|---|---|---|
| [F0](docs/fazlar/F0-veri-ingest.md) | Veri indirme altyapısı | ✅ 1.165 parite · 1,5M bar |
| [F1](docs/fazlar/F1-normalizasyon-matris.md) | Normalizasyon + matris inşası | ✅ 1,92M pencere |
| [F2](docs/fazlar/F2-arama-motoru.md) | Arama motoru (kaskad) | ✅ 51 ms |
| [**F3**](docs/fazlar/F3-dogrulama.md) | **Notebook doğrulaması** 🚦 zorunlu kapı | ✅ **Geçti** |
| [F3.5](docs/fazlar/F3.5-temizlik.md) | Temizlik (yüzdelik skorlama, evren) | 🔄 Sırada |
| [F4](docs/fazlar/F4-outcome-engine.md) | Outcome Engine (triple-barrier) | ⬜ |
| [F5](docs/fazlar/F5-api.md) | FastAPI + Redis | ⬜ |
| [F6](docs/fazlar/F6-radar-ui.md) | Next.js — Radar (MVP 1) | ⬜ |
| [F7](docs/fazlar/F7-backtest-ui.md) | Next.js — Backtest (MVP 2) | ⬜ |

---

## Sorumluluk reddi

GraphFlow bir **araştırma aracıdır**, yatırım tavsiyesi değildir. Ürettiği tüm istatistikler geçmiş fiyat dağılımlarıdır ve gelecekteki performansın göstergesi değildir.
