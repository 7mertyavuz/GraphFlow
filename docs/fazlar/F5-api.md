# F5 — API Katmanı

**Durum:** 🔄 Sırada (F4.6 vekil testiyle birlikte)
**Modül:** `engine/api/`
**Prompt:** [`../02-claude-code-prompt.md`](../02-claude-code-prompt.md) → *Oturum 4*

---

## ⚠️ F4/F4.5'ten gelen zorunlu tasarım kısıtları

Ürünün tek iddiası metodolojik dürüstlük. API bunu **şema düzeyinde** garanti eder.

### B1 — Çıplak sayı döndürmek yasak

Arayüzün bağlamsız bir sayı gösterebilmesi **mümkün olmamalı**. Her oran/beklenti alanı şu zarfla döner:

```json
{ "value": 0.41, "ci95": [0.324, 0.503], "ci_method": "month_block",
  "null": 0.333, "shadow": 0.34,
  "n_events": 112, "n_months": 37,
  "significant": false,
  "verdict": "anlamlı fark ölçülemedi",
  "design_effect": 1.28 }
```

`significant` ve `verdict` **sunucuda** hesaplanır, istemciye bırakılmaz. Bare float dönen hiçbir istatistik alanı olmayacak — bu bir testle zorlanır.

### B2 — Kullanıcı da p-hacking yapabilir

İçeride 52 testlik Bonferroni uygulandı. Ama serbest çizim yapan bir kullanıcı 50 şekil deneyip "anlamlı" birini bulursa **aynı problemi kendisi üretir** ve bizim düzeltmemiz onu kapsamaz.

Oturum başına sorgu sayacı zorunlu:

```json
{ "session_queries": 17, "multiple_comparison_warning": true,
  "adjusted_alpha": 0.0029 }
```

Outcome kartında görünür uyarı: *"Bu oturumda 17 farklı şekil denediniz; şans eseri 'anlamlı' sonuç görme olasılığınız arttı."*

Piyasada hiçbir aracın yapmadığı şey — ve ürünün karakteri.

### B4 — Outcome maliyeti

10.000 tekrarlı blok bootstrap etkileşimli değil (~2 sn+).

| Durum | Çözüm |
|---|---|
| 14 şablon | Önceden hesaplanır, Redis'te |
| Serbest çizim | Asenkron iş: `POST → job_id → poll` |
| Radar | Cron ile 5 dk'da bir |

> **Bootstrap tekrar sayısı düşürülmez.** Farklı tekrar sayısı farklı GA üretir; iki farklı kalitede sayıyı aynı arayüzde göstermek dürüstlük sorunudur. Kullanıcı bekler.
**Spesifikasyon:** [`../01-mimari.md` §10](../01-mimari.md)
**İlgili kararlar:** [K-08](../00-tasarim-kararlari.md#k-08--sayfalama-12li-grid-ve-cachelenmiş-sıralı-liste) · [K-15](../00-tasarim-kararlari.md#k-15--tek-motor-i̇ki-mod)

---

## Amaç

Motoru HTTP üzerinden sunmak ve **sayfalamayı cache'ten** yapmak.

> **F3 geçilmeden F5'e geçilmez** (K-18). Kapı geçildi ✅

---

## Uç noktalar

| Metot | Yol | İşlev |
|---|---|---|
| `POST` | `/api/search` | Arama; tüm matris skorlanır, sıralı liste cache'lenir, ilk 12 döner |
| `GET` | `/api/search/{id}?offset=&limit=` | Cache'ten dilim — **yeniden hesaplama yok** |
| `GET` | `/api/search/{id}/stats` | Outcome kartı (F4) |
| `GET` | `/api/templates` | Şablon kütüphanesi |
| `GET` | `/api/chart/{symbol}` | OHLCV + vurgu sınırları + blueprint overlay noktaları + bükülme miktarı |
| `GET` | `/api/findings` | **Yeni.** F4/F4.5/F4.6 çalışma sonuçları: aşamalı sıkılaşma tablosu (13/26 → 8/26 → 14/52 → **2/52**), tam 14×2×2 tablo, yöntem notları. İç rapor değil, **birinci sınıf ürün sayfası** |

### `POST /api/search` gövdesi

```json
{
  "points": ["... 32 eleman"],
  "template_id": null,
  "mode": "historical",
  "timeframe": "1d",
  "window_lengths": [24, 40, 64, 100],
  "tolerance": "medium",
  "min_amplitude": 15.0,
  "limit": 12
}
```

`points` veya `template_id`'den **biri** verilir.

### Yanıt

```json
{
  "search_id": "b3f2...",
  "total": 1847,
  "elapsed_ms": 51,
  "data_as_of": 1785456000000,
  "results": [{ "symbol": "SOLUSDT", "score": 0.912, "amplitude": 18.4, "...": "..." }]
}
```

`data_as_of` + bayat veri uyarı bayrağı F3.5'te eklendi — motor bayat veride **çalışır ama uyarır**, kırılmaz.

---

## Cache (Redis)

| Anahtar | İçerik | TTL |
|---|---|---|
| `search:{id}` | Sıralı, NMS'ten geçmiş tam liste | 1 saat |
| `search:{id}:stats` | Outcome kartı | 1 saat |
| `radar:{template_id}:{tf}` | Önceden hesaplanmış Radar sonuçları | 5 dakika |

**Sayfalama akışı** (K-08):

```
POST /api/search  → tüm matris skorlanır → liste cache'lenir → ilk 12
GET  .../?offset=12 → cache'ten dilim
```

En iyi 12'yi bulmak için zaten hepsi skorlanmak zorunda; tembel tarama "en benzer 12"yi değil "rastgele bulunan ilk 12"yi verir.

---

## Radar önbelleği

Radar sorguları çok ucuz (23 ms). Kütüphanedeki şablonlar için sonuçlar Cron ile 5 dakikada bir önceden hesaplanır → kullanıcı "OBO" tıkladığında sonuç **anında** gelir. Serbest çizim talep üzerine hesaplanır.

---

## Çıkış şartı

- Tüm uç noktalar çalışıyor, OpenAPI şeması üretiliyor
- Sayfalama cache'ten geliyor (ikinci sayfa < 5 ms)
- Yük testi: eşzamanlı sorgularda bellek şişmesi yok
- `data_as_of` ve bayat uyarısı yanıtta
