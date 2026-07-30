"""F3 notebook'larını üretir ve çalıştırır (docs/01-mimari.md §16).

Notebook'lar **ince** tutulur: ölçüm mantığı ``tools/f3_measure.py`` ve
``tools/ab_stage2.py`` içindedir. Böylece rapordaki sayılarla notebook'taki
sayılar aynı koddan gelir ve zamanla ayrışmaz.

    python -m tools.build_notebooks            # üret + çalıştır
    python -m tools.build_notebooks --no-exec  # yalnızca üret
"""

from __future__ import annotations

import argparse
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parent.parent
NB_DIR = ROOT / "notebooks"
OUT_DIR = NB_DIR / "output"

HEADER = """import sys, json
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()))
import numpy as np, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
pd.set_option("display.width", 200)
OUT = Path("notebooks/output"); OUT.mkdir(parents=True, exist_ok=True)
TF = "1d"
"""

NOTEBOOKS: dict[str, list[tuple[str, str]]] = {
    "01_veri_kontrol": [
        ("md", """# 01 — Veri Kontrolü (F3 ADIM 0)

Gerçek Binance verisi indirildikten sonraki bütünlük kontrolü. Kontrol edilenler:

1. Bar sayıları ve tarih aralıkları
2. Boşluklar (gerçek piyasa olayı mı, indirme hatası mı?)
3. **Delist edilmiş paritelerin varlığı** (K-13 — survivorship bias)
4. Yarım mum diske yazılmamış mı (K-05 / K-15)
5. **K-13 sağlık kontrolü**: likidite filtresinden sonra yıl bazında pencere sayısı

> Bu defterin yakaladığı en önemli hata: Binance arşivi 2025-01'den itibaren
> zaman damgalarını mikrosaniye yazıyor. Milisaniye varsayan okuyucu bu barları
> "kapanmamış mum" sanıp **sessizce** düşürüyordu (19 aylık veri kaybı)."""),
        ("code", HEADER + """
from engine.config import TIMEFRAME_MS, LIQUIDITY_TOP_PCT
from engine.ingest.store import read_klines, available_symbols

semboller = available_symbols(TF)
satirlar = []
for s in semboller:
    df = read_klines(s, TF)
    ot = df.open_time.to_numpy()
    gaps = np.diff(ot)
    satirlar.append(dict(
        sembol=s, bar=len(df),
        ilk=pd.to_datetime(ot.min(), unit="ms", utc=True).date(),
        son=pd.to_datetime(ot.max(), unit="ms", utc=True).date(),
        bosluk=int((gaps != TIMEFRAME_MS[TF]).sum()),
        max_bosluk_gun=int(gaps.max() // 86_400_000) if len(gaps) else 0,
    ))
veri = pd.DataFrame(satirlar).sort_values("bar", ascending=False)
print(f"{len(veri)} sembol, toplam {veri.bar.sum():,} bar")
veri.head(10)"""),
        ("code", """# Boşluklar — hepsi gerçek piyasa olayı mı?
bosluklu = veri[veri.bosluk > 0]
print(f"boşluklu sembol: {len(bosluklu)}/{len(veri)}")
bosluklu[["sembol", "bar", "bosluk", "max_bosluk_gun", "ilk", "son"]]"""),
        ("code", """# K-13: delist edilmiş pariteler veri setinde mi?
delist_ornek = ["USTUSDT", "BUSDUSDT", "MATICUSDT", "FTMUSDT", "SRMUSDT"]
for s in delist_ornek:
    if s in semboller:
        r = veri[veri.sembol == s].iloc[0]
        print(f"{s:11s} {r.bar:5d} bar  {r.ilk} -> {r.son}   (son bar = delist tarihi)")
    else:
        print(f"{s:11s} veri setinde yok")"""),
        ("code", """# K-05 / K-15: yarım mum diske yazılmamalı
import time
simdi = int(time.time() * 1000)
son_bar = int(max(read_klines(s, TF, columns=["open_time"]).open_time.max() for s in semboller))
kapanis = son_bar + TIMEFRAME_MS[TF]
print("en son bar açılışı :", pd.to_datetime(son_bar, unit="ms", utc=True))
print("o barın kapanışı   :", pd.to_datetime(kapanis, unit="ms", utc=True))
print("şu an              :", pd.to_datetime(simdi, unit="ms", utc=True))
print("YARIM MUM YOK" if kapanis <= simdi else "HATA: kapanmamış mum diske yazılmış!")"""),
        ("code", """# K-13 SAĞLIK KONTROLÜ — likidite filtresinden sonra yıl bazında pencere
from engine.config import WINDOW_LENGTHS
from engine.matrix.build import matrix_dir, META_FILE
from engine.matrix.npy_store import load_matrix

parcalar = []
for L in WINDOW_LENGTHS:
    M = np.asarray(load_matrix(matrix_dir(TF, L) / META_FILE))
    parcalar.append(pd.DataFrame({
        "yil": pd.to_datetime(M["end_time"], unit="ms", utc=True).year,
        "likit": M["liquid"],
    }))
pencere = pd.concat(parcalar)
saglik = pencere.groupby("yil").agg(toplam=("likit", "size"), likit=("likit", "sum"))
saglik["oran_%"] = (100 * saglik.likit / saglik.toplam).round(1)

fig, ax = plt.subplots(figsize=(9, 3.2))
ax.bar(saglik.index, saglik.likit, color="#2b7a78")
ax.set_title(f"Likidite filtresinden geçen pencere (hedef ~%{LIQUIDITY_TOP_PCT*100:.0f} kesitsel)")
ax.set_xlabel("yıl"); ax.set_ylabel("pencere")
fig.tight_layout(); fig.savefig(OUT / "k13_yil_bazinda_pencere.png", dpi=110)
saglik"""),
        ("md", """**Beklenen:** 2017–2019 çökmemeli. Çökmüşse aylık kesitsel filtre yanlış
uygulanmış, sabit eşik gibi davranıyor demektir (K-13.2)."""),
    ],
    "02_normalizasyon_gorsel": [
        ("md", """# 02 — Normalizasyon Görsel Kontrolü (K-02)

Sıra: **log fiyat → 32 noktaya resample → z-score**. Kontrol edilenler:

1. Aynı şekil, 100x farklı fiyat seviyesinde → aynı vektör
2. Farklı bar uzunlukları aynı vektör uzayında buluşuyor mu
3. ‖z‖ = √32 (Aşama 1'in Pearson korelasyonuna eşitliği buna dayanır)
4. Çizim yolu: y ters çevrilir, **log uygulanmaz**"""),
        ("code", HEADER + """
from engine.config import N_POINTS
from engine.normalize.pipeline import normalize_window, normalize_drawing
from tools.shapes import shape

sekil = shape("head_and_shoulders", 64)
ucuz = 0.002 * np.exp(0.3 * sekil)     # penny-coin
pahali = 60_000 * np.exp(0.3 * sekil)  # BTC seviyesi

fig, axes = plt.subplots(1, 3, figsize=(13, 3.4))
axes[0].plot(ucuz, color="#c94f4f"); axes[0].set_title("ham fiyat — 0,002 $")
axes[1].plot(pahali, color="#2b7a78"); axes[1].set_title("ham fiyat — 60.000 $")
axes[2].plot(normalize_window(ucuz), "o-", label="ucuz", color="#c94f4f")
axes[2].plot(normalize_window(pahali), "x--", label="pahalı", color="#2b7a78")
axes[2].set_title("normalize — üst üste"); axes[2].legend()
fig.tight_layout(); fig.savefig(OUT / "normalizasyon_olcek.png", dpi=110)

fark = np.max(np.abs(normalize_window(ucuz) - normalize_window(pahali)))
print(f"maksimum fark: {fark:.2e}  (atol=1e-6 bekleniyor)")
print(f"norm: {np.linalg.norm(normalize_window(ucuz)):.6f}  = sqrt(32) = {np.sqrt(32):.6f}")"""),
        ("code", """# Farklı bar uzunlukları aynı uzayda buluşuyor mu?
fig, ax = plt.subplots(figsize=(7, 3.4))
for L in (24, 40, 64, 100):
    v = normalize_window(100 * np.exp(0.3 * shape("cup_and_handle", L)))
    ax.plot(v, label=f"{L} bar")
ax.set_title("aynı formasyon, farklı pencere uzunlukları → 32 nokta"); ax.legend()
fig.tight_layout(); fig.savefig(OUT / "normalizasyon_uzunluk.png", dpi=110)

taban = normalize_window(100 * np.exp(0.3 * shape("cup_and_handle", 24)))
for L in (40, 64, 100):
    v = normalize_window(100 * np.exp(0.3 * shape("cup_and_handle", L)))
    print(f"24 bar ile {L:3d} bar korelasyonu: {np.corrcoef(taban, v)[0,1]:.4f}")"""),
        ("code", """# Çizim yolu: y ters çevrilir, log UYGULANMAZ
kanvas_y = np.array([180, 150, 120, 140, 90, 60, 95, 130, 70, 40], dtype=float)  # ekran koordinatı
cizim = normalize_drawing(kanvas_y)
fig, axes = plt.subplots(1, 2, figsize=(9, 3.2))
axes[0].plot(kanvas_y, "o-"); axes[0].invert_yaxis(); axes[0].set_title("kanvas (y aşağı artar)")
axes[1].plot(cizim, "o-", color="#2b7a78"); axes[1].set_title("normalize (fiyat mantığı)")
fig.tight_layout(); fig.savefig(OUT / "normalizasyon_cizim.png", dpi=110)
print("düz yatay çizgi reddediliyor mu?", normalize_drawing(np.full(40, 100.0)) is None)"""),
        ("code", """# Gerçek veriden bir pencere: ham vs normalize
from engine.ingest.store import read_klines
df = read_klines("BTCUSDT", TF)
p = df.close.to_numpy()[-100:]
fig, axes = plt.subplots(1, 2, figsize=(10, 3.2))
axes[0].plot(p); axes[0].set_title("BTCUSDT son 100 gün — ham")
axes[1].plot(normalize_window(p), color="#2b7a78"); axes[1].set_title("normalize (32 nokta)")
fig.tight_layout(); fig.savefig(OUT / "normalizasyon_gercek.png", dpi=110)"""),
    ],
    "03_goz_testi": [
        ("md", """# 03 — Göz Testi (F3 ADIM 4) 🚦 ÇIKIŞ KAPISI

20 sorgu (14 kanonik şablon + 6 serbest çizim) için **ilk 12 sonuç** 3×4 grid
olarak render edilir. Her karo: sembol, tarih, normalize skor, volatilite
etiketi ve vurgulanmış eşleşme penceresi.

Kontrol edilecekler:

* **K-09**: 12 karo 12 FARKLI olay mı, yoksa aynı grafiğin kaydırılmış kopyaları mı?
* **Sembol çeşitliliği**: `max 3/sembol` tutuyor mu?
* **Likidite**: ölü pariteler listeyi kirletiyor mu?
* **Uzunluk dengesi**: sonuçlar tek bir pencere uzunluğunda mı kümeleniyor?
  Kümeleniyorsa K-14 yol-uzunluğu normalizasyonu eksik/yanlış.

> **"Evet, bu çalışıyor" kararını bu defter VERMEZ.** Görseller üretilir,
> gözlemler yazılır; karar insana aittir (K-18)."""),
        ("code", HEADER + """
from engine.search.engine import SearchEngine
from engine.templates import load_all
from tools.f3_measure import render_top12, diversity_report, freehand_vector, FREEHAND_QUERIES

motor = SearchEngine()
sorgular = [(t.id, t.vector) for t in load_all().values()]
sorgular += [(f"serbest_{ad}", freehand_vector(ad)) for ad in FREEHAND_QUERIES]
print(f"{len(sorgular)} sorgu: {len(load_all())} şablon + {len(FREEHAND_QUERIES)} serbest çizim")"""),
        ("code", """gozlem = []
for ad, q in sorgular:
    yol, sonuc = render_top12(motor, q, ad, TF, OUT, tolerance="medium")
    rapor = diversity_report(sonuc)
    rapor["sorgu"] = ad
    rapor["toplam"] = sonuc.total
    rapor["sure_ms"] = round(sonuc.elapsed_ms, 1)
    gozlem.append(rapor)
gozlem = pd.DataFrame(gozlem).set_index("sorgu")
gozlem[["toplam", "sonuc", "farkli_sembol", "max_per_symbol", "ortusen_cift", "genlik_medyan", "sure_ms"]]"""),
        ("code", """# K-09 doğrulaması: örtüşen çift SIFIR olmalı (post-NMS çalışıyorsa)
print("örtüşen çift toplamı :", int(gozlem.ortusen_cift.sum()), " (0 bekleniyor)")
print("max/sembol ihlali    :", int((gozlem.max_per_symbol > 3).sum()), " (0 bekleniyor)")
print("boş dönen sorgu      :", int((gozlem.sonuc == 0).sum()), f"/{len(gozlem)}")
print("ortalama farklı sembol:", round(gozlem.farkli_sembol.mean(), 1), "/ 12 karo")"""),
        ("code", """# Uzunluk dengesi — K-14 yol uzunluğu normalizasyonunun kanıtı
uzunluk = pd.DataFrame([g for g in gozlem.uzunluk_dagilimi]).fillna(0).astype(int)
uzunluk.index = gozlem.index
toplam_uzunluk = uzunluk.sum().sort_index()
fig, ax = plt.subplots(figsize=(7, 3.2))
ax.bar([str(c) for c in toplam_uzunluk.index], toplam_uzunluk.values, color="#2b7a78")
ax.set_title("Sonuçların pencere uzunluğuna dağılımı (20 sorgu × 12 sonuç)")
ax.set_xlabel("pencere uzunluğu (bar)")
fig.tight_layout(); fig.savefig(OUT / "uzunluk_dengesi.png", dpi=110)
print(toplam_uzunluk.to_string())
kumelenme = toplam_uzunluk.max() > 0.7 * toplam_uzunluk.sum()
print("tek uzunlukta kümelenme var mı?", "EVET - K-14 normalizasyonu şüpheli" if kumelenme else "hayır")"""),
        ("code", """# Likidite: sonuçlarda ölü parite var mı?
tum_semboller = sorted({s for g in gozlem.index for s in []})
from collections import Counter
sayac = Counter()
for ad, q in sorgular:
    r = motor.search(q, timeframe=TF, tolerance="medium", limit=12)
    sayac.update(m.symbol for m in r.results)
print("sonuçlarda en sık geçen 15 sembol:")
for s, n in sayac.most_common(15):
    print(f"  {s:12s} {n:3d} kez")"""),
        ("md", """### Gözlem notları

Grid PNG'leri: `notebooks/output/goz_testi_*.png`

Karar (insan): _______________"""),
    ],
    "06_radar_duman_testi": [
        ("md", """# 06 — Radar Duman Testi (F3 ADIM 5)

`mode='live'` ile tüm evrende 3 şablon. Hedef: **< 10 ms** (performans
bütçesi §15). Dönen sonuçların grafikleri de render edilir — canlı modda
gelenin makul görünüp görünmediği erken anlaşılsın."""),
        ("code", HEADER + """
import time
from engine.search.engine import SearchEngine
from engine.templates import get
from tools.f3_measure import render_top12

motor = SearchEngine()
sablonlar = ["head_and_shoulders", "cup_and_handle", "bull_flag"]

# Isınma (memmap sayfa cache)
motor.search(get(sablonlar[0]).vector, mode="live", timeframe=TF)

olcum = []
for ad in sablonlar:
    q = get(ad).vector
    t0 = time.perf_counter()
    r = motor.search(q, mode="live", timeframe=TF, tolerance="flexible", limit=12)
    ms = (time.perf_counter() - t0) * 1000
    olcum.append(dict(sablon=ad, sure_ms=round(ms, 2), sonuc=r.total,
                      en_iyi=round(r.results[0].distance, 4) if r.results else None))
pd.DataFrame(olcum)"""),
        ("code", """# Radar sonuçları gerçekten SON pencere mi?
r = motor.search(get("cup_and_handle").vector, mode="live", timeframe=TF, tolerance="flexible", limit=12)
for m in r.results[:6]:
    h = motor.handle(TF, m.window_length)
    son = int(h.end_idx[h.symbol_id == m.symbol_id].max())
    print(f"{m.symbol:11s} L={m.window_length:3d} end_idx={m.end_idx:5d} sembolün son penceresi={son:5d} "
          f"{'OK' if m.end_idx == son else 'HATA'}")"""),
        ("code", """yol, sonuc = render_top12(motor, get("cup_and_handle").vector, "radar_cup_and_handle",
                          TF, OUT, tolerance="flexible", mode="live")
print("render:", yol)
print("radar sonuç sayısı:", sonuc.total)"""),
    ],
    "04_negatif_kontrol": [
        ("md", """# 04 — Negatif Kontrol (F3 ADIM 2) 🚦

K-18'in çoğu projede atlanan yarısı. Sisteme **eşleşmemesi gereken** girdiler verilir:

| Girdi | Beklenen |
|---|---|
| Düz yatay çizgi | Pipeline reddeder (σ = 0) |
| White noise | "Eşleşme yok" ya da belirgin kötü skor |
| Whipsaw (testere) | Aynı |
| Tek yönlü rampa | **Tartışmalı — ölçüme bak** |

Ayrıca **skor dağılımı sağlık kontrolü**: tüm sorgular aynı bandı veriyorsa
metrik ayırt etmiyor demektir; bu tek başına F3'ü düşürür."""),
        ("code", HEADER + """
from engine.search.engine import SearchEngine
from tools.f3_measure import flat_line_is_refused, negative_query, query_scores, NEGATIVE_KINDS
from engine.templates import load_all

print("düz yatay çizgi pipeline'da reddediliyor mu?", flat_line_is_refused())
motor = SearchEngine()
dagilim = pd.read_json("data/f3/score_distribution.json")
sablon = dagilim[dagilim.tur == "sablon"].sort_values("en_iyi")
negatif = dagilim[dagilim.tur == "negatif"].copy()
negatif["tip"] = negatif.sorgu.str.rsplit("_", n=1).str[0]
sablon[["sorgu", "sonuc", "en_iyi", "top12", "medyan", "p95"]]"""),
        ("code", """negatif.groupby("tip")[["sonuc", "en_iyi", "top12", "medyan"]].median().round(4)"""),
        ("code", """# Skor dağılımı histogramı — 14 şablon + negatifler
fig, ax = plt.subplots(figsize=(10, 4))
ax.hist(sablon.en_iyi, bins=14, alpha=0.75, label="şablon (14)", color="#2b7a78")
renk = {"white_noise": "#c94f4f", "whipsaw": "#8e44ad", "ramp": "#e08e0b", "near_flat": "#7f8c8d"}
for tip, g in negatif.groupby("tip"):
    sonlu = g.en_iyi[np.isfinite(g.en_iyi)]
    if len(sonlu):
        ax.hist(sonlu, bins=8, alpha=0.6, label=f"negatif: {tip}", color=renk.get(tip))
    else:
        ax.axvline(0, ls=":", color=renk.get(tip), label=f"negatif: {tip} (hiç sonuç yok)")
ax.set_xlabel("en iyi normalize mesafe (küçük = benzer)"); ax.set_ylabel("sorgu sayısı")
ax.set_title("Skor dağılımı — şablon vs negatif kontrol (gerçek veri, 1d)")
ax.legend(); fig.tight_layout(); fig.savefig(OUT / "negatif_kontrol_histogram.png", dpi=110)
print("şablon en iyi skor aralığı: %.4f - %.4f" % (sablon.en_iyi.min(), sablon.en_iyi.max()))
print("white_noise tabanı        : %.4f" % negatif[negatif.tip=='white_noise'].en_iyi.min())"""),
        ("code", """# Rampa neden negatif sayılmıyor: sonuçları GERÇEKTEN monoton mu?
rng = np.random.default_rng(3)
sonuc = motor.search(negative_query("ramp", rng), timeframe=TF, tolerance="flexible", limit=3)
for m in sonuc.results:
    h = motor.handle(TF, m.window_length)
    satir = int(np.flatnonzero((h.symbol_id == m.symbol_id) & (h.end_idx == m.end_idx))[0])
    v = np.asarray(h.vectors[satir])
    print(f"{m.symbol:10s} L={m.window_length:3d} mesafe={m.distance:.4f} "
          f"genlik=%{m.amplitude:.0f} artan-adım=%{100*np.mean(np.diff(v)>0):.0f}")"""),
        ("md", """**Sonuç:** Rampa sorgusunun döndürdüğü pencereler gerçekten monoton ve yüksek
genlikli. Yani motor doğru cevap veriyor — "trend" gerçek bir şekildir. Bu
yüzden rampa, eşik kalibrasyonunda negatif taban olarak **kullanılmaz**;
kullanılsaydı eşik pozitiflerin altına iner ve motor susardı. Ayrıntı ve açık
soru: `docs/03-f3-dogrulama-raporu.md`."""),
    ],
    "05_esik_kalibrasyon": [
        ("md", """# 05 — Eşik Kalibrasyonu (F3 ADIM 3)

**Metodolojik tuzak:** Gerçek veride etiket yoktur, dolayısıyla gerçek veriden
AUC hesaplanamaz. İş bölümü:

* **AUC / ROC ve K-11 kararı** → bozulmalı sentetik (etiket biliniyor) — `tools/ab_stage2.py`
* **Eşik değerleri** → gerçek veri skor dağılımları:
  * Katı = negatif kontrollerin pratikte hiç geçemediği nokta
  * Orta = şablon sorgularının ilk 12'sinin rahat geçtiği nokta
  * Esnek = pozitif kuyruğun tükendiği nokta"""),
        ("code", HEADER + """
from tools.f3_measure import calibrate_thresholds, MEANINGLESS_KINDS
from engine.config import TOLERANCE_THRESHOLDS, STAGE2_METRIC

dagilim = pd.read_json("data/f3/score_distribution.json")
kal = calibrate_thresholds(dagilim)
print("aktif metrik:", STAGE2_METRIC)
print("anlamsız kabul edilen sorgular:", MEANINGLESS_KINDS)
print(json.dumps(kal, indent=1, ensure_ascii=False))
print("\\nconfig.py'deki değerler:", TOLERANCE_THRESHOLDS)"""),
        ("code", """# K-11 A/B: sentetik, bozulmalı pozitiflerle 3 metrik x 4 uzunluk x 3 gürültü
ab = json.loads(Path("data/f3/ab_stage2.json").read_text(encoding="utf-8"))
satir = pd.DataFrame(ab["rows"])
ozet = satir.pivot_table(index=["noise", "length"], columns="metric", values="auc").round(4)
ozet["kazanan"] = ozet.idxmax(axis=1)
ozet"""),
        ("code", """fig, ax = plt.subplots(figsize=(9, 4))
for metrik, g in satir.groupby("metric"):
    egri = g.groupby("length").auc.mean()
    ax.plot(egri.index, egri.values, "o-", label=metrik)
ax.set_xlabel("pencere uzunluğu (bar)"); ax.set_ylabel("AUC")
ax.set_title("K-11 A/B — pencere uzunluğuna göre kırılım (ortalama)")
ax.legend(); ax.grid(alpha=0.3)
fig.tight_layout(); fig.savefig(OUT / "k11_ab_uzunluk.png", dpi=110)
satir.groupby("metric").auc.mean().round(4)"""),
        ("code", """# Eşiklerin görsel yeri
sablon = dagilim[dagilim.tur == "sablon"]
negatif = dagilim[dagilim.tur == "negatif"].copy()
negatif["tip"] = negatif.sorgu.str.rsplit("_", n=1).str[0]
anlamsiz = negatif[negatif.tip.isin(MEANINGLESS_KINDS)].en_iyi.replace([np.inf], np.nan).dropna()

fig, ax = plt.subplots(figsize=(10, 4))
ax.hist(sablon.top12, bins=14, alpha=0.8, label="şablon — 12. sonuç", color="#2b7a78")
if len(anlamsiz):
    ax.hist(anlamsiz, bins=8, alpha=0.6, label="anlamsız sorgu — en iyi", color="#c94f4f")
for ad, v in TOLERANCE_THRESHOLDS.items():
    ax.axvline(v, ls="--", label=f"{ad} = {v}")
ax.set_xlabel("normalize mesafe"); ax.set_title("Eşiklerin pozitif ve negatif dağılımlar arasındaki yeri")
ax.legend(); fig.tight_layout(); fig.savefig(OUT / "esik_kalibrasyon.png", dpi=110)"""),
        ("code", """# Doğrulama: hangi kademede kim geçiyor?
for ad, v in TOLERANCE_THRESHOLDS.items():
    gecen_sablon = int((sablon.top12 <= v).sum())
    gecen_anlamsiz = int((anlamsiz <= v).sum()) if len(anlamsiz) else 0
    print(f"{ad:9s} {v:.4f} -> ilk 12'si tamamen geçen şablon: {gecen_sablon}/14, "
          f"eşiği geçen anlamsız sorgu: {gecen_anlamsiz}/{len(anlamsiz)}")"""),
    ],
}


def build(name: str, cells: list[tuple[str, str]]) -> Path:
    nb = nbf.v4.new_notebook()
    nb.cells = [
        nbf.v4.new_markdown_cell(src) if kind == "md" else nbf.v4.new_code_cell(src)
        for kind, src in cells
    ]
    nb.metadata = {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"},
    }
    path = NB_DIR / f"{name}.ipynb"
    path.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(nb, path)
    return path


def execute(path: Path, timeout: int = 1800) -> None:
    from nbclient import NotebookClient

    nb = nbf.read(path, as_version=4)
    client = NotebookClient(nb, timeout=timeout, kernel_name="python3", resources={"metadata": {"path": str(ROOT)}})
    client.execute()
    nbf.write(nb, path)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI
    p = argparse.ArgumentParser(prog="python -m tools.build_notebooks")
    p.add_argument("--no-exec", action="store_true")
    p.add_argument("--only", nargs="+", default=None)
    args = p.parse_args(argv)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, cells in NOTEBOOKS.items():
        if args.only and name not in args.only:
            continue
        path = build(name, cells)
        print(f"uretildi: {path.relative_to(ROOT)}")
        if not args.no_exec:
            execute(path)
            print("  calistirildi OK")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
