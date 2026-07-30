# F7 — Backtest Arayüzü (MVP 2)

**Durum:** ⬜ Planlı
**Modül:** `web/`
**İlgili kararlar:** [K-06](../00-tasarim-kararlari.md#k-06--öldürücü-özellik-sonra-ne-oldu) · [K-12](../00-tasarim-kararlari.md#k-12--zaman-eşleştirmeli-baseline-gölge-dağılım) · [K-16](../00-tasarim-kararlari.md#k-16--triple-barrier-atr-tabanlı-göreli-bariyerler)

---

## Amaç

**"Geçmişte bu şekil oluştuğunda ne olmuş?"**

F6 ile aynı arayüz iskeleti, aynı motor (`mode='historical'`), üzerine **outcome kartı**.

---

## Outcome kartı

```
┌────────────────────────────────────────────────────┐
│  SONRA NE OLDU?                                    │
│                                                    │
│  Hedef: 2R (bu parite için ≈ %7,4)                 │
│  Stop:  1R (≈ %3,7)                                │
│                                                    │
│  Beklenti:  +0,18R          ← başrol metrik        │
│  Başarı:    %41   (null: %33 · gölge: %34)         │
│  N = 112 bağımsız olay                             │
│                                                    │
│  ── Rejim kırılımı ──                              │
│  2021: %55 (n=38)    2022: %29 (n=24)              │
│                                                    │
│  ⓘ Bu veriler geçmiş dağılımlardır, kesin bir      │
│    işlem sinyali değildir.                         │
└────────────────────────────────────────────────────┘
```

### Sunum kuralları

| Kural | Gerekçe |
|---|---|
| **Baseline'sız başarı oranı gösterilmez** | %41 tek başına anlamsız; %33 null ve %34 gölge dağılımla birlikte anlamlı |
| **Beklenti (R) başrolde, kazanma oranı yanında** | Kazanma oranı SL genişleterek manipüle edilebilir |
| **N = bağımsız olay sayısı** | Örtüşen pencereler sayılmaz (K-09) |
| **Rejim kırılımı zorunlu** | Kullanıcı, formasyonun mu yoksa boğa piyasasının mı çalıştığını görebilmeli |
| **1:1 versiyonu da erişilebilir** | Null'u %50 olan saf yön testi; akademik savunması olan sayı |
| **Sorumluluk reddi görünür** | Sinyal satmıyoruz |

---

## Ek arayüz öğeleri

- **Zaman çizelgesi:** eşleşmelerin yıllara dağılımı — kümelenme görünsün
- **Sonuç dökümü:** TP / SL / zaman bariyeri sayıları
- **Eşleşme detayı:** karoya tıklayınca tam grafik + bariyerlerin nerede çarptığı işaretli
- **Bükülme etiketi:** F3.5'te ölçülen hizalama sapması (kanıt biriktikçe filtreye dönüşebilir)

---

## Çıkış şartı

- Outcome kartı doğru sayıları gösteriyor, baseline'sız hiçbir oran ekranda yok
- Rastgele sorgularda beklenti ≈ 0R görünüyor (kullanıcı da doğrulayabiliyor)
- Rejim kırılımı ve zaman çizelgesi çalışıyor
- Kullanıcı testi: sayıların ne anlama geldiği açıklama olmadan anlaşılıyor

---

## Ertelenen kapsam

- 1H / 1W zaman dilimleri
- Nasdaq / BIST100 / Forex (veri lisansı sonrası)
- Kullanıcı hesapları, kaydedilmiş aramalar, uyarı (alert)
- Short yönü için ayna triple-barrier
