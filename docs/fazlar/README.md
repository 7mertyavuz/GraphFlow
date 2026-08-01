# Fazlar — İndeks

Her faz için ayrı bir belge: kapsam, alınan kararlar, ölçülen sayılar, bilinen sorunlar, çıkış şartı.

| Faz | Belge | Durum | Özet |
|---|---|---|---|
| **F0** | [F0-veri-ingest.md](F0-veri-ingest.md) | ✅ Bitti | Binance veri boru hattı. 1.165 parite, 1.505.471 bar. |
| **F1** | [F1-normalizasyon-matris.md](F1-normalizasyon-matris.md) | ✅ Bitti | log → 32 nokta → z-score; 1.922.776 pencerelik vektör matrisi. |
| **F2** | [F2-arama-motoru.md](F2-arama-motoru.md) | ✅ Bitti | Kaskad: kosinüs → pre-NMS → DDTW → post-NMS. 51 ms. |
| **F3** | [F3-dogrulama.md](F3-dogrulama.md) | ✅ Geçti 🚦 | Göz testi onaylandı, K-11 karara bağlandı, 5 açık sorun. |
| **F3.5** | [F3.5-temizlik.md](F3.5-temizlik.md) | ✅ Geçti | Yüzdelik skorlama (13/14 şablon), evren temizliği, invariantlar. |
| **F4** | [F4-outcome-engine.md](F4-outcome-engine.md) | ✅ Bitti | Triple-barrier + gölge dağılım. Null kapısı geçti; 1 pozitif, 5 negatif, 8 nötr. |
| **F4.5** | [F4.5-istatistiksel-saglamlastirma.md](F4.5-istatistiksel-saglamlastirma.md) | ✅ Bitti | Ay-bloklu bootstrap + short. Korelasyon 0,384; 52 testten **2** anlamlı. |
| **F5** | [F5-api.md](F5-api.md) | 🔄 Sırada | F4.6 vekil testi + FastAPI/Redis. Çıplak sayı yasak, oturum p-hacking sayacı. |
| **F6** | [F6-radar-ui.md](F6-radar-ui.md) | ⬜ Planlı | Canlı tarayıcı arayüzü (MVP 1). |
| **F7** | [F7-backtest-ui.md](F7-backtest-ui.md) | ⬜ Planlı | Tarihsel arama + outcome kartı (MVP 2). |

## Bağımlılık zinciri

```
F0 ──▶ F1 ──▶ F2 ──▶ 🚦F3 ──▶ F3.5 ──▶ F4 ──▶ F5 ──▶ F6 ──▶ F7
veri   matris  arama   kapı    temizlik  outcome  API   Radar  Backtest
```

**F3 bir kapıdır** (K-18): motor göz testinden ve negatif kontrolden geçmeden arayüze geçilmez.

**F3.5, F4'ten önce gelir** çünkü arama önyargısı doğrudan outcome istatistiklerine geçer.

## Diğer belgeler

| Belge | İçerik |
|---|---|
| [../00-tasarim-kararlari.md](../00-tasarim-kararlari.md) | K-01…K-18 karar kaydı, reddedilen alternatifler |
| [../01-mimari.md](../01-mimari.md) | Teknik spesifikasyon |
| [../02-claude-code-prompt.md](../02-claude-code-prompt.md) | Oturum prompt'ları |
| [../03-f3-dogrulama-raporu.md](../03-f3-dogrulama-raporu.md) | F3 ölçüm raporu |
