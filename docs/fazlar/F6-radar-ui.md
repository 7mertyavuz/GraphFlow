# F6 — Radar Arayüzü (MVP 1)

**Durum:** ⬜ Planlı
**Modül:** `web/`
**İlgili kararlar:** [K-05](../00-tasarim-kararlari.md#k-05--i̇ki-ürün-modu-radar-ve-backtest) · [K-08](../00-tasarim-kararlari.md#k-08--sayfalama-12li-grid-ve-cachelenmiş-sıralı-liste) · [K-17](../00-tasarim-kararlari.md#k-17--frontend-hafifleştirmesi)

---

## Amaç

**"Şu an hangi coin'ler bu şekli yapıyor?"**

Radar MVP 1'dir çünkü çok ucuz (23 ms), anında sonuç verir ve trader'ın işlem açmak için kullanacağı asıl araçtır.

---

## Layout

```
┌───────────────────────────────────────────────────────────────────┐
│  [1D] [4H]              [Radar] [Backtest]                        │
├──────────────┬────────────────────────────────────────────────────┤
│  Dönüş       │            KANVAS                                  │
│   ▸ OBO      │      (Canvas + pointer events)                     │
│   ▸ Ters OBO │      Şablon seçilince şeffaf blueprint             │
│   ▸ İkili... │                                                    │
│   ▸ Fincan   │      Katı ─○───────── Esnek                        │
│              │      Min. Volatilite: %15                          │
│  Devam       │                  [ TARA ]                          │
│   ▸ Flama    │                                                    │
│   ▸ Takoz    │                                                    │
├──────────────┴────────────────────────────────────────────────────┤
│  SONUÇLAR — 1.847 eşleşme bulundu, en iyi 12                      │
│  ┌────┐┌────┐┌────┐┌────┐   ← 3×4 grid, Lightweight Charts        │
│  ┌────┐┌────┐┌────┐┌────┐      sembol · skor · Volatilite %18     │
│  ┌────┐┌────┐┌────┐┌────┐                                         │
│                 [ Daha Fazla (+12) ]                              │
└───────────────────────────────────────────────────────────────────┘
```

---

## Bileşenler

| Bileşen | Not |
|---|---|
| `DrawCanvas.tsx` | **Düz HTML5 Canvas + native pointer events**, ~100 satır |
| `TemplateLibrary.tsx` | Kategorize akordeon, minimalist vektörel ikonlar |
| `ResultGrid.tsx` | 3×4 = 12 karo, "Daha Fazla" ile +12 |
| `ToleranceToggle.tsx` | `Katı / Orta / Esnek` — **yüzde slider değil** |

### Çizim

```
onPointerDown  → çizime başla, nokta biriktir
onPointerMove  → nokta ekle, path'i çiz
onPointerUp    → 32 noktaya indir, y'yi ters çevir, API'ye gönder
```

**Fabric.js / Konva.js kullanılmaz** (K-17). Bunlar çizim *editörü* kütüphaneleridir; GraphFlow editör değil, kullanıcı tek bir polyline çiziyor.

### Esneklik ayarı

"%85 Benzerlik" gibi kalibre edilemez bir metrik **yoktur**. DTW mesafesi yüzde değildir; anlamı olmayan bir sayıyı anlamlıymış gibi sunmak, ürünün geri kalanındaki istatistiksel dürüstlük duruşuyla çelişir.

Toggle arka planda F3.5'te ölçülmüş **yüzdelik dilim eşiklerini** ayarlar.

---

## Sonuç kartı

- TradingView Lightweight Charts ile mini grafik
- Eşleşen pencere **vurgulanmış** (gölgeli bölge)
- Sembol + benzerlik skoru + `Volatilite: %18`
- Opsiyonel: blueprint overlay (F3.5'te üretilen görselin ürün hâli)

---

## Neden 12?

- 4 sonuç kalite yargısı için yetersizdir — kullanıcı motorun iyi mi kötü mü olduğunu anlayamaz
- 12 karo tek ekranda taranabilir ve "evet, bu çalışıyor" hissi verir
- Üstteki `1.847 eşleşme` motorun gücünü hissettirirken 12 grafik görsel kanıt sunar

---

## Çıkış şartı

- Serbest çizim ve şablon seçimi aynı sonuç kalitesini veriyor
- Sayfalama cache'ten, ikinci sayfa anında
- Bayat veri uyarısı görünür
- Kullanıcı testi: bir trader çizip sonuçlara bakınca "evet, bu o" diyor
