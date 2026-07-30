# F2 — Kaskad Arama Motoru

**Durum:** ✅ Bitti
**Modüller:** `engine/search/` · `engine/templates/`
**İlgili kararlar:** [K-03](../00-tasarim-kararlari.md#k-03--kaskad-arama-stratejisi) · [K-04](../00-tasarim-kararlari.md#k-04--kural-motorunun-i̇mhası-kanonik-şablon-vektörleri) · [K-09](../00-tasarim-kararlari.md#k-09--çift-aşamalı-nms-deduplication) · [K-11](../00-tasarim-kararlari.md#k-11--dtw-yerine-ddtw-türev-dtw) · [K-14](../00-tasarim-kararlari.md#k-14--çoklu-çözünürlük-ve-skor-kıyaslanabilirliği) · [K-15](../00-tasarim-kararlari.md#k-15--tek-motor-i̇ki-mod)

---

## Amaç

1,9 milyon pencere içinden, kullanıcının şekline en benzeyenleri **yarım saniyenin altında** bulmak — ve bulduklarının birbirinin kopyası olmamasını sağlamak.

---

## Kaskad

```
Sorgu (32 nokta, normalize)
   │
   ├─ Aşama 1  ·  Kosinüs benzerliği (vektörize)     → STAGE1_TOPK = 5.000
   │              scores = (V @ q) / 32
   │              z-score'lu vektörlerde Pearson korelasyonuna eşdeğer
   │
   ├─ Pre-NMS   ·  1D-IoU, gevşek (0.70)             → STAGE2_TOPK = 1.000
   │              amaç: DTW bütçesini kopyalara harcamamak
   │
   ├─ Aşama 2  ·  DDTW + Sakoe-Chiba (r=5)           → skorlanmış
   │              skor = mesafe / hizalama_yolu_uzunluğu   (K-14)
   │
   └─ Post-NMS  ·  IoU 0.50 + max 3/sembol           → nihai liste
```

| Dosya | Sorumluluk |
|---|---|
| `stage1_cosine.py` | memmap üzerinde chunk'lı skorlama, likidite/genlik maskeleri, `argpartition` |
| `nms.py` | 1D-IoU; pre ve post için tek fonksiyon |
| `ddtw.py` | Keogh-Pazzani türevi + banded DTW |
| `engine.py` | `SearchEngine.search(query, mode, ...)` |

### Vektörize DTW

DP, **aday listesi üzerinde Python döngüsü olmadan** `(n_cand, band)` şeklinde vektörize edildi ve referans DP ile **birebir** doğrulandı.

### Tek motor, iki mod (K-15)

| Mod | Tarama alanı |
|---|---|
| `historical` | Tüm matris |
| `live` | `end_idx == son_bar` maskesi (seyrek maske → gather yolu) |

Radar ayrı bir motor değil, `offset = son bar` özel hâlidir.

---

## Şablon kütüphanesi

**14 kanonik formasyon**, `tools/gen_templates.py` ile **matematiksel olarak üretildi** (elle uydurulmadı).

Kural motoru yoktur — her formasyon 32 noktalık bir vektördür ve aynı pipeline'dan geçer (K-04). Yeni formasyon eklemek = yeni bir JSON dosyası.

---

## Ölçümler

| Metrik | Sonuç | Bütçe |
|---|---|---|
| Aşama 1 (1M satır) | **40 ms** | 300 ms |
| Aşama 2 (1.000 aday) | **8 ms** | 100 ms |
| Uçtan uca `historical` | **51 ms** | 500 ms |
| `live` (80 sembol) | **3,1 ms** | — |
| `live` (1.165 sembol) | 23 ms | 50 ms (F3.5'te güncellendi) |

**Sentetik uçtan uca:** ilk 12'de 11 gerçek OBO; ilk 20'de 16/20 enjeksiyon.
**Negatif kontrol:** white noise ve testere, en gevşek kademede bile 0 sonuç.

> **Not:** Görev tanımındaki *"20 OBO'nun en az 15'i ilk 12 sonuçta"* şartı matematiksel olarak imkânsızdı (12 slota 15 olay sığmaz). Şart `precision@12 ≥ 10` ve `recall@20 ≥ 15` olarak ikiye ayrıldı; gerekçe testin docstring'inde.

---

## Testler

- DDTW vektörize DP ↔ referans DP birebir eşleşme
- NMS: örtüşen pencereler tekilleşiyor, `max_per_symbol` uygulanıyor
- Düz çizgi ↔ çanak ayrımı
- Aşama 1 performans bütçesi

---

## Bilinen açıklar

Hepsi F3'te ölçüldü, F3.5'te kapatılacak:

| # | Sorun | Kök sebep |
|---|---|---|
| S-1 | Rampa sorguları her kademeyi geçiyor (0,0025) | Skor ölçeği sorgunun yapısal karmaşıklığına bağlı |
| S-2 | 14 şablonun 7'si orta kademede ilk sayfayı dolduramıyor | Tek global eşik, bayrak (0,008) ile üçgeni (0,056) idare edemiyor |
| S-3 | Sonuçların %68'i 24 barlık pencerede | Yol uzunluğuna bölme uzunluklar arası adaleti sağlamıyor |
| — | OBO'da yuvarlak tepeler sızıyor | Boyun çizgisi denetlenmiyor (K-04 kural katmanı yok) |
| — | Fincan sonuçlarında kulp yok | Kanonik vektörde kulp çok sığ |

## Çıkış şartı ✅

Kaskad çalışıyor, bütçelerin çok altında, sentetik uçtan uca testler ve negatif kontrol geçiyor.
