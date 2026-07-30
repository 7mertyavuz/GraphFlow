# F0 — Veri Boru Hattı (Ingest)

**Durum:** ✅ Bitti
**Modül:** `engine/ingest/`
**İlgili kararlar:** [K-01](../00-tasarim-kararlari.md#k-01--ölçek-gerçeği-problem-sanıldığı-kadar-büyük-değil) · [K-05](../00-tasarim-kararlari.md#k-05--i̇ki-ürün-modu-radar-ve-backtest) · [K-07](../00-tasarim-kararlari.md#k-07--veri-kapsamı-sadece-kripto) · [K-13](../00-tasarim-kararlari.md#k-13--survivorship-bias-ve-göreli-likidite-filtresi)

---

## Amaç

Binance spot klines verisini, **survivorship bias olmadan** ve **yarım mum içermeden** yerel Parquet deposuna indirmek.

## Kapsam

| Parametre | Değer |
|---|---|
| Borsa | Binance spot |
| Parite sayısı | **1.165** (delist edilenler dahil) |
| Zaman dilimi | 1d (4h planlı) |
| Aralık | 2017-08 → 2026-07 |
| Toplam bar | **1.505.471** |
| Kote varlıklar | USDT, BTC |

## Bileşenler

| Dosya | Sorumluluk |
|---|---|
| `binance_client.py` | REST `/api/v3/klines` indirici |
| `symbol_universe.py` | Sembol evreni (delist dahil) |
| `store.py` | Parquet okuma/yazma |
| `download.py` | CLI giriş noktası |

### `binance_client.py`

- 1.000 barlık sayfalama (Binance limiti)
- `X-MBX-USED-WEIGHT-1M` başlığından ağırlık takibi, limitin **%75**'inde duruş (418 ban riski)
- 429/418 yanıtlarında `Retry-After` başlığına uyum
- Ağ hatasında üstel geri çekilme (backoff)

### `symbol_universe.py`

Üç kaynak birleştirilir:

1. `exchangeInfo` — yalnızca **yaşayan** pariteler
2. `data.binance.vision` arşivi — **delist edilenler dahil** (K-13'ün asıl kaynağı)
3. Saklanan `exchangeInfo` anlık görüntüleri

> **Not:** `exchangeInfo` delist edilmiş pariteleri döndürmez. Yalnızca REST'e dayanan bir evren, survivorship bias'ı yapısal olarak içerir.

### `store.py`

- `docs/01-mimari.md` §2.2 Parquet şeması
- Atomik yazım (yarım dosya bırakmaz)
- Artımlı append

### `download.py`

- Kesintiden devam (resume)
- **Devam noktası ayrı bir durum dosyasından değil, Parquet'in kendisinden okunur** — durum dosyası ile gerçek veri arasında tutarsızlık imkânsız hâle gelir
- Kapanmamış mum **diske hiç yazılmaz** (K-05 / K-15)

---

## Ortam bulgusu: `api.binance.com` erişilemez

Geliştirme ağından `api.binance.com` kapalı. Arşiv bucket'ı **S3 adı** üzerinden çalışıyor:

```
https://s3-ap-northeast-1.amazonaws.com/data.binance.vision
```

`data.binance.vision` CNAME'i bazı ağlardan erişilemiyor; bucket aynı içeriği S3 adıyla veriyor.

**Bu bir kayıp değil, kazanç:** arşiv K-13 açısından REST'ten daha iyi bir kaynak — delist edilmiş pariteleri içeriyor.

---

## 🐞 Kritik bug: mikrosaniye zaman damgaları

**F3'ün varlık sebebi olan bulgu.**

Binance arşivi **2025-01'den itibaren** zaman damgalarını mikrosaniye yazıyor; daha eski dosyalar milisaniye.

**Belirti zinciri:**

1. ms varsayan okuyucu, bu barların `close_time`'ını bugünden 1000 kat büyük görüyor
2. Okuyucu bunları **"kapanmamış mum"** sanıp K-05 gereği düşürüyor
3. İndirme **hatasız** bitiyor
4. Tüm semboller 2024-12-31'de kesiliyor
5. 18 yeni parite tamamen boş kalıyor

**Sonuç: 19 aylık veri, tek bir hata mesajı olmadan kayboldu.**

**Düzeltme:** `config.EPOCH_US_THRESHOLD = 1e14` — bu eşiği aşan değer µs kabul edilip 1000'e bölünür. (1e14 ms ≈ 5138 yılı; ms verinin bu değeri aşması imkânsız.)

**Ders:** Bu hata **sentetik veriyle asla yakalanamazdı**. F3.5'te kalıcı bir veri tazeliği invariant'ı eklenecek.

---

## Testler

`tests/` altında ingest ve arşiv testleri. Kapsanan davranışlar:

- Sayfalama sınırları ve resume tutarlılığı
- Ağırlık takibi ve backoff zinciri
- Kapanmamış mumun diske yazılmaması
- Mikrosaniye → milisaniye dönüşümü (regresyon testi)

## Bilinen açıklar

| # | Konu | Plan |
|---|---|---|
| 1 | 4h verisi henüz indirilmedi | F3.5 sonrası |
| 2 | Veri boşlukları (2017–2019 bakım kesintileri) tespit edilmiyor | F3.5 Adım 3 |
| 3 | Veri tazeliği invariant'ı yok | F3.5 Adım 3 |

## Çıkış şartı ✅

Gerçek Binance verisi, delist edilmiş pariteler dahil, yarım mum içermeden diske indi ve F1 matris inşasını besledi.
