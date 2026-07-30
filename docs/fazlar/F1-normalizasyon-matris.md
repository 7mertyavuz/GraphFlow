# F1 — Normalizasyon ve Matris İnşası

**Durum:** ✅ Bitti
**Modüller:** `engine/normalize/` · `engine/matrix/`
**İlgili kararlar:** [K-01](../00-tasarim-kararlari.md#k-01--ölçek-gerçeği-problem-sanıldığı-kadar-büyük-değil) · [K-02](../00-tasarim-kararlari.md#k-02--projenin-gerçek-kalbi-normalizasyon) · [K-10](../00-tasarim-kararlari.md#k-10--genlik-amplitude-meta-verisi) · [K-13](../00-tasarim-kararlari.md#k-13--survivorship-bias-ve-göreli-likidite-filtresi) · [K-14](../00-tasarim-kararlari.md#k-14--çoklu-çözünürlük-ve-skor-kıyaslanabilirliği)

---

## Amaç

Ham OHLCV'yi, **fiyat seviyesinden ve hareket büyüklüğünden bağımsız** saf geometrik forma çevirip, tek bir bitişik matriste toplamak.

> Projenin gerçek kalbi burasıdır. Başarı-başarısızlık çizgisi algoritmada değil, normalizasyondadır (K-02).

---

## Normalizasyon pipeline'ı

**Sıra önemlidir.**

| # | Adım | Gerekçe |
|---|---|---|
| 1 | `x = ln(p)` | Piyasada anlamlı olan yüzdesel değişim; log uzayında eşit dikey mesafe = eşit yüzdesel hareket |
| 2 | `np.interp` ile **32 noktaya** resample | Farklı uzunluktaki pencereleri tek vektör uzayında kıyaslayabilmek |
| 3 | Z-score (`ddof=0`) | Şeklin kimliğini fiyat seviyesinden ayrıştırır |

**Kenar durum:** `σ < FLAT_EPS` → pencere düşürülür.

**Uygulama notu:** Toplu (batch) yol vektörize; tekil yolla `atol=1e-6` içinde uyumlu olduğu testle doğrulandı.

### `normalize_drawing()` — kullanıcı çizimi

Kanvas noktaları için ayrı yol:

- y ekseni ters çevrilir (canvas y aşağı doğru artar)
- **Log adımı UYGULANMAZ** — çizim zaten lineer/görsel uzaydadır
- Resample + z-score aynı

### Yan modüller

| Dosya | İşlev |
|---|---|
| `amplitude.py` | `(max−min)/min × 100`, **ham fiyatlardan**, normalizasyondan önce (K-10) |
| `atr.py` | Wilder ATR(14) — **lookahead testli** |

> **ATR ve lookahead:** ATR yalnızca `t₀`'a kadarki barlardan hesaplanır. Bu, tüm istatistik katmanının (K-16) geçerliliğini belirleyen tek noktadır ve birim testi vardır.

---

## Matris inşası

| Parametre | Değer |
|---|---|
| Pencere uzunlukları | 24, 40, 64, 100 |
| Stride | 3 |
| Matris sayısı | 8 (2 timeframe × 4 uzunluk) |
| Üretilen pencere | **1.922.776** (1d) |
| Vektör tipi | `float32`, 32 boyut |

### Çıktı yapısı

```
data/matrix/{timeframe}_{window_length}/
    vectors.npy      # (K, 32) float32
    meta.npy         # META_DTYPE: symbol_id, start_idx, end_idx,
                     #   end_time, amplitude, atr, liquid
```

### Bellek disiplini

Matris **chunk'lar hâlinde diske akıtılır** (`MATRIX_CHUNK_WINDOWS = 8192`). Tüm pencereler hiçbir noktada RAM'de tutulmaz. Okuma `numpy.memmap` ile yapılır.

> K-01'in özü: asıl kazanç dilden değil, **bitişik matris yapısından** gelir.

### Artımlı inşa

`incremental.py`, yeni kapanan mumlar için append yapar. **Artımlı sonucun tam inşayla birebir aynı olduğu testle doğrulandı** — bu, cron güncellemesinin sessizce sapmamasını garanti eder.

### Likidite maskesi

`liquidity.py`, her ayın kesitinde hacim sıralaması hesaplar; üst **%40**'ta olmayan pariteler o ayki pencerelerde `liquid=False` işaretlenir (K-13).

Sabit dolar eşiği **kullanılmaz** — 2017–2019 verisini silerdi.

---

## Testler

- **Ölçek değişmezliği:** aynı şekil, farklı fiyat seviyesi → aynı vektör (`atol=1e-6`)
- **Seviye değişmezliği:** aynı şekil, farklı ofset → aynı vektör
- **ATR lookahead:** `t₀` sonrası barlar ATR'yi etkilemiyor
- **Artımlı = tam inşa:** append sonucu tam yeniden inşayla birebir aynı
- Batch ↔ tekil yol tutarlılığı

---

## Bilinen açıklar

| # | Konu | Plan |
|---|---|---|
| 1 | Zaman sürekliliği kontrolü yok — boşluk içeren pencere matrise girebiliyor | F3.5 Adım 3 |
| 2 | 4h matrisleri kurulmadı | F3.5 sonrası |
| 3 | Yol uzunluğuna bölme, uzunluklar arası adaleti tam sağlamıyor (S-3) | F3.5 Adım 1 |

## Çıkış şartı ✅

8 matris üretildi, artımlı inşa tam inşayla eşleşiyor, normalizasyon değişmezlik testleri geçiyor.
