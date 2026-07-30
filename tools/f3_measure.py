"""F3 ölçüm kütüphanesi — notebook'lar ve rapor bunu çağırır.

Ölçüm mantığı notebook hücrelerine gömülmez: aynı sayılar hem
``notebooks/*.ipynb`` içinde hem ``docs/03-f3-dogrulama-raporu.md`` üretilirken
kullanılır, ikisinin ayrışması istenmez.

İş bölümü (metodolojik tuzak — docs/01-mimari.md §16, K-18):

* **AUC / ROC ve K-11 kararı** → bozulmalı sentetik veri (etiket biliniyor).
  Bkz. ``tools/ab_stage2.py``.
* **Eşik değerleri** → GERÇEK veri skor dağılımları. Gerçek veride etiket
  yoktur; AUC hesaplanamaz, eşik dağılımdan okunur.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from engine.config import (
    N_POINTS,
    PAGE_SIZE,
    STAGE2_METRIC,
    TIMEFRAME_MS,
)
from engine.ingest.store import read_klines
from engine.normalize.pipeline import normalize_drawing, resample_to, zscore
from engine.search.engine import SearchEngine
from engine.templates import load_all

#: Negatif kontrol sorguları (K-18 §4). "Düz yatay çizgi" ayrı ele alınır:
#: σ = 0 olduğu için normalizasyon onu zaten reddeder, motora ulaşamaz.
NEGATIVE_KINDS = ("white_noise", "whipsaw", "ramp", "near_flat")


def z(y) -> np.ndarray:
    return zscore(resample_to(np.asarray(y, dtype=float), N_POINTS))


def negative_query(kind: str, rng: np.random.Generator) -> np.ndarray:
    """Eşleşmemesi beklenen sorgular."""
    if kind == "white_noise":
        return z(rng.normal(size=N_POINTS))
    if kind == "whipsaw":
        base = np.tile([0.0, 1.0], N_POINTS // 2)
        return z(base + rng.normal(0, 0.05, N_POINTS))
    if kind == "ramp":
        return z(np.linspace(0.0, 1.0, N_POINTS) + rng.normal(0, 0.01, N_POINTS))
    if kind == "near_flat":
        return z(np.cumsum(rng.normal(0, 1e-3, N_POINTS)))
    raise KeyError(kind)


def flat_line_is_refused() -> bool:
    """Düz yatay çizgi pipeline'da düşer mi? (σ < FLAT_EPS → None)"""
    return normalize_drawing(np.full(64, 250.0)) is None


# ---------------------------------------------------------------------------
# Skor dağılımı
# ---------------------------------------------------------------------------


def query_scores(
    engine: SearchEngine,
    query: np.ndarray,
    timeframe: str = "1d",
    limit: int = 300,
    tolerance: str = "flexible",
    metric: str = STAGE2_METRIC,
    **kwargs,
) -> np.ndarray:
    """Bir sorgunun post-NMS sonrası mesafe dizisi (artan)."""
    result = engine.search(
        query, timeframe=timeframe, tolerance=tolerance, limit=limit, metric=metric, **kwargs
    )
    return np.array([m.distance for m in result.results], dtype=float)


def score_distribution(
    engine: SearchEngine,
    timeframe: str = "1d",
    n_negative: int = 12,
    limit: int = 300,
    metric: str = STAGE2_METRIC,
    seed: int = 7,
) -> pd.DataFrame:
    """14 şablon + negatif kontroller için skor dağılımı tablosu.

    Tüm sorgular aynı bandı veriyorsa metrik ayırt etmiyor demektir; bu tek
    başına F3'ü düşürür (K-18).
    """
    rng = np.random.default_rng(seed)
    rows: list[dict] = []

    for template in load_all().values():
        scores = query_scores(engine, template.vector, timeframe, limit, metric=metric)
        rows.append(_row(template.id, "sablon", scores))

    for kind in NEGATIVE_KINDS:
        for i in range(n_negative):
            scores = query_scores(engine, negative_query(kind, rng), timeframe, limit, metric=metric)
            rows.append(_row(f"{kind}_{i}", "negatif", scores))

    return pd.DataFrame(rows)


def _row(name: str, group: str, scores: np.ndarray) -> dict:
    ordered = np.sort(scores)
    return {
        "sorgu": name,
        "tur": group,
        "sonuc": int(ordered.size),
        "en_iyi": float(ordered[0]) if ordered.size else np.inf,
        "top12": float(ordered[min(PAGE_SIZE, ordered.size) - 1]) if ordered.size else np.inf,
        "medyan": float(np.median(ordered)) if ordered.size else np.inf,
        "p95": float(np.quantile(ordered, 0.95)) if ordered.size else np.inf,
    }


# ---------------------------------------------------------------------------
# Eşik kalibrasyonu (ADIM 3)
# ---------------------------------------------------------------------------


#: Eşik tabanını belirleyen "gerçekten anlamsız" sorgular.
#:
#: ``ramp`` ve ``near_flat`` bilinçli olarak DIŞARIDA: gerçek veride bunlar
#: **meşru şekillerdir**. F3 ölçümü, rampa sorgusunun döndürdüğü pencerelerin
#: gerçekten monoton (%81-87 artan adım) ve yüksek genlikli (+%58…+%460)
#: olduğunu gösterdi — yani motor doğru cevap veriyor, "trend" diye bir şekil
#: var. Bunları negatif taban saymak, eşiği pozitiflerin altına çekip motoru
#: susturur. Ayrıntı: docs/03-f3-dogrulama-raporu.md.
MEANINGLESS_KINDS = ("white_noise", "whipsaw")


def calibrate_thresholds(dist: pd.DataFrame, safety: float = 0.9) -> dict:
    """Gerçek veri dağılımlarından ``Katı / Orta / Esnek`` eşikleri.

    * **Katı**  = negatif kontrollerin pratikte hiç geçemediği nokta
      → negatif *en iyi* skorların tabanı × ``safety``
    * **Orta**  = şablon sorgularının ilk 12'sinin rahat geçtiği nokta
      → şablonların 12. skorunun medyanı
    * **Esnek** = pozitif kuyruğun tükendiği nokta
      → şablon skorlarının %95'lik dilimi

    **Üst sınır kuralı:** Hiçbir kademe negatif tabanı aşamaz. K-18, en gevşek
    kademede bile anlamsız sorgunun eşleşmemesini şart koşar; pozitif kuyruk
    negatif tabanın ötesine taşıyorsa kuyruk kırpılır.
    """
    is_meaningless = dist["sorgu"].str.rsplit("_", n=1).str[0].isin(MEANINGLESS_KINDS)
    negatives = dist.loc[(dist["tur"] == "negatif") & is_meaningless, "en_iyi"].to_numpy()
    negatives = negatives[np.isfinite(negatives)]
    templates = dist[dist["tur"] == "sablon"]

    floor = float(negatives.min()) if negatives.size else np.inf
    ceiling = floor * safety

    values = {
        "strict": float(np.nanquantile(templates["top12"], 0.25)),
        "medium": float(np.nanmedian(templates["top12"])),
        "flexible": float(np.nanquantile(templates["p95"], 0.75)),
    }
    capped = {k: min(v, ceiling) for k, v in values.items()}

    return {
        "thresholds": {k: round(v, 4) for k, v in capped.items()},
        "raw": {k: round(v, 4) for k, v in values.items()},
        "negative_floor": round(floor, 4),
        "ceiling": round(ceiling, 4),
        "capped": [k for k in values if capped[k] < values[k] - 1e-12],
        "n_negative": int(negatives.size),
        "n_template": int(len(templates)),
    }


# ---------------------------------------------------------------------------
# Göz testi yardımcıları (ADIM 4)
# ---------------------------------------------------------------------------


def result_window(engine: SearchEngine, match, timeframe: str, pad: float = 0.35):
    """Bir eşleşmenin grafiğini çizmek için OHLCV dilimi döndürür."""
    df = read_klines(match.symbol, timeframe)
    span = match.end_idx - match.start_idx + 1
    pad_bars = int(span * pad)
    lo = max(0, match.start_idx - pad_bars)
    hi = min(len(df), match.end_idx + pad_bars + 1)
    return df.iloc[lo:hi], match.start_idx - lo, match.end_idx - lo


def diversity_report(result) -> dict:
    """K-09 doğrulaması: 12 karo 12 FARKLI olay mı?"""
    from engine.search.nms import iou_1d

    matches = result.results
    symbols = [m.symbol for m in matches]
    per_symbol: dict[str, int] = {}
    for s in symbols:
        per_symbol[s] = per_symbol.get(s, 0) + 1

    overlaps = 0
    for i, a in enumerate(matches):
        for b in matches[i + 1 :]:
            if a.symbol == b.symbol and iou_1d(a.start_idx, a.end_idx, b.start_idx, b.end_idx) > 0:
                overlaps += 1

    lengths: dict[int, int] = {}
    for m in matches:
        lengths[m.window_length] = lengths.get(m.window_length, 0) + 1

    return {
        "sonuc": len(matches),
        "farkli_sembol": len(set(symbols)),
        "max_per_symbol": max(per_symbol.values()) if per_symbol else 0,
        "ortusen_cift": overlaps,
        "uzunluk_dagilimi": dict(sorted(lengths.items())),
        "genlik_medyan": float(np.median([m.amplitude for m in matches])) if matches else np.nan,
    }


#: Serbest çizim sorguları (K-18 §2: "20 farklı el çizimi").
#:
#: DÜRÜSTLÜK NOTU: Bunlar gerçek fare/dokunmatik çizimleri değil, kanvas
#: koordinat sistemiyle (y aşağı doğru artar) elle yazılmış polyline'lardır.
#: Amaç, kütüphanede karşılığı olmayan serbest şekillerle motoru sınamak;
#: gerçek kullanıcı çizimi F6'da (arayüz) test edilecek.
FREEHAND_QUERIES: dict[str, list[float]] = {
    "v_dibi": [20, 45, 75, 100, 118, 128, 120, 96, 68, 40, 18],
    "keskin_zirve_ve_sonme": [120, 96, 70, 40, 18, 10, 34, 62, 84, 100, 112, 118],
    "merdiven_yukselis": [130, 128, 110, 108, 90, 88, 68, 66, 46, 44, 24, 22],
    "esitsiz_w": [30, 70, 110, 74, 36, 78, 118, 92, 50, 24, 14],
    "kanca": [110, 86, 60, 36, 20, 14, 16, 26, 44, 40, 22],
    "yatay_sonra_firlama": [96, 98, 95, 99, 96, 97, 94, 78, 52, 28, 12],
}


def freehand_vector(name: str) -> np.ndarray:
    """Serbest çizimi motor sorgusuna çevirir (y ters, log yok)."""
    return normalize_drawing(np.asarray(FREEHAND_QUERIES[name], dtype=float))


def render_top12(
    engine: SearchEngine,
    query: np.ndarray,
    name: str,
    timeframe: str = "1d",
    out_dir=None,
    limit: int = PAGE_SIZE,
    tolerance: str = "medium",
    metric: str = STAGE2_METRIC,
    **kwargs,
):
    """3×4 grid PNG üretir: sembol, tarih, skor, volatilite, vurgulu pencere."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from pathlib import Path

    result = engine.search(
        query, timeframe=timeframe, tolerance=tolerance, limit=limit, metric=metric, **kwargs
    )

    fig, axes = plt.subplots(3, 4, figsize=(15, 8.5))
    fig.suptitle(
        f"{name}  ·  {timeframe}  ·  {tolerance}  ·  {result.total} eşleşme — en iyi {limit}",
        fontsize=13,
    )

    for ax, match in zip(axes.ravel(), result.results):
        window, lo, hi = result_window(engine, match, timeframe)
        close = window["close"].to_numpy()
        ax.plot(close, lw=1.1, color="#1f3a5f")
        ax.axvspan(lo, hi, color="#2b7a78", alpha=0.18)
        ax.plot(range(lo, hi + 1), close[lo : hi + 1], lw=1.7, color="#2b7a78")
        tarih = bar_time(match, timeframe).date()
        ax.set_title(
            f"{match.symbol} · {tarih}\nskor {match.distance:.4f} · vol %{match.amplitude:.0f} · L={match.window_length}",
            fontsize=8.5,
        )
        ax.set_xticks([])
        ax.set_yticks([])

    for ax in axes.ravel()[len(result.results) :]:
        ax.axis("off")
        ax.text(0.5, 0.5, "eşleşme yok", ha="center", va="center", color="#999", fontsize=9)

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    path = None
    if out_dir is not None:
        path = Path(out_dir) / f"goz_testi_{name}.png"
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=100)
    plt.close(fig)
    return path, result


def timeframe_last_bar(symbol: str, timeframe: str) -> pd.Timestamp:
    df = read_klines(symbol, timeframe, columns=["open_time"])
    return pd.to_datetime(df["open_time"].max(), unit="ms", utc=True)


def bar_time(match, timeframe: str) -> pd.Timestamp:
    return pd.to_datetime(match.end_time, unit="ms", utc=True)


def window_span_days(match, timeframe: str) -> float:
    return (match.end_idx - match.start_idx + 1) * TIMEFRAME_MS[timeframe] / 86_400_000
