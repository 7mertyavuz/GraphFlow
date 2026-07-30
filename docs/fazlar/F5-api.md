# F5 — API Katmanı

**Durum:** ⬜ Planlı
**Modül:** `engine/api/`
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
| `GET` | `/api/chart/{symbol}` | Sonuç grafiği için OHLCV + vurgu sınırları |

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
