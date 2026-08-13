"""Arama sonuçları → outcome raporu (K-06).

Boru hattı:

1. ``SearchEngine.search`` → post-NMS'ten geçmiş **tekil** eşleşmeler (K-09)
2. İleri pencere ayrımı → gerçekten bağımsız N
3. Ön filtreler: işlem maliyeti tabanı, ATR ısınması
4. Triple-barrier, **iki konfigürasyon birlikte** (2:1 ve 1:1)
5. Zaman-eşleştirmeli gölge dağılım (K-12)
6. Güven aralıklarıyla özet

**p-hacking kilidi:** Tolerans kademesi ``OUTCOME_TOLERANCE`` ile sabittir.
Skorlar F3.5'ten beri yüzdelik olduğu için kademe değişince hem ``N`` hem
beklenti değişir; kademe oynatarak sayı güzelleştirmek yasaktır.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence

import numpy as np

from engine.config import (
    BARRIER_CONFIGS,
    OUTCOME_TOLERANCE,
    RETURN_MATCH_BAND_SIGMA,
    SHADOW_SAMPLES_PER_MATCH,
    WINDOW_LENGTHS,
)
from engine.matrix.build import META_FILE, matrix_dir
from engine.matrix.npy_store import load_matrix
from engine.outcome.bars import BarStore
from engine.outcome.metrics import OutcomeStats, summarize
from engine.outcome.shadow import ShadowPool, sample_shadow
from engine.outcome.triple_barrier import (
    EVENT_DTYPE,
    eligible,
    enforce_forward_separation,
    evaluate,
)
from engine.search.engine import SearchEngine

log = logging.getLogger(__name__)


@dataclass
class TemplateOutcome:
    template_id: str
    timeframe: str
    matches: int
    events: int
    dropped_separation: int
    dropped_filters: int
    shadow_report: dict = field(default_factory=dict)
    stats: dict[str, OutcomeStats] = field(default_factory=dict)
    direction: str = "long"

    def as_dict(self) -> dict:
        return {
            "template_id": self.template_id,
            "timeframe": self.timeframe,
            "matches": self.matches,
            "n_independent": self.events,
            "dropped_forward_overlap": self.dropped_separation,
            "dropped_filters": self.dropped_filters,
            "direction": self.direction,
            "shadow": self.shadow_report,
            "configs": {name: s.as_dict() for name, s in self.stats.items()},
        }


def events_from_matches(matches: Sequence) -> np.ndarray:
    """``Match`` listesini outcome olaylarına çevirir."""
    out = np.empty(len(matches), dtype=EVENT_DTYPE)
    for i, m in enumerate(matches):
        out[i] = (m.symbol_id, m.end_idx, m.window_length, m.atr, m.end_time)
    return out


def load_shadow_pools(
    timeframe: str,
    lengths: Sequence[int] = WINDOW_LENGTHS,
    matrix_root: Path | None = None,
    store: BarStore | None = None,
) -> dict[int, ShadowPool]:
    """Gölge havuzlarını yükler.

    ``store`` verilirse her pencere için ön-getiri hesaplanır (F4.6).
    """
    pools: dict[int, ShadowPool] = {}
    klines_close = store.close if store is not None else None
    klines_offsets = store.offset if store is not None else None
    for length in lengths:
        path = matrix_dir(timeframe, length, matrix_root) / META_FILE
        if path.exists():
            pools[int(length)] = ShadowPool.from_meta(
                np.asarray(load_matrix(path)),
                int(length),
                klines_close=klines_close,
                klines_offsets=klines_offsets,
            )
    return pools


def run_events(
    events: np.ndarray,
    store: BarStore,
    pools: dict[int, ShadowPool],
    template_id: str = "query",
    timeframe: str = "1d",
    p: int = SHADOW_SAMPLES_PER_MATCH,
    rng: np.random.Generator | None = None,
    direction: str = "long",
    confidence: float | None = None,
    return_matched_shadow: bool = False,
    return_band_sigma: float = RETURN_MATCH_BAND_SIGMA,
) -> TemplateOutcome:
    """Hazır olay dizisinden outcome — arama adımı olmadan.

    F5 API bu girişi kullanır: kullanıcının ekranda gördüğü eşleşmelerin
    **birebir aynısı** istatistiğe girer. Aramayı içeride yeniden çalıştırmak,
    farklı tolerans/genlik parametreleriyle başka bir olay kümesi üretip
    "gördüğün grafiklerin istatistiği" diye sunmak olurdu.
    """
    from engine.config import CONFIDENCE_LEVEL

    confidence = CONFIDENCE_LEVEL if confidence is None else confidence
    rng = rng if rng is not None else np.random.default_rng(20260731)

    n_matches = int(events.size)

    if events.size:
        keep = enforce_forward_separation(events)
        dropped_sep = int((~keep).sum())
        events = events[keep]
    else:
        dropped_sep = 0

    if events.size:
        ok = eligible(events, store)
        dropped_filters = int((~ok).sum())
        events = events[ok]
    else:
        dropped_filters = 0

    outcome = TemplateOutcome(
        template_id=template_id,
        timeframe=timeframe,
        matches=n_matches,
        events=int(events.size),
        dropped_separation=dropped_sep,
        dropped_filters=dropped_filters,
    )
    if events.size == 0:
        return outcome

    shadow_events, shadow_report = sample_shadow(
        events, pools, p=p, rng=rng,
        match_return=return_matched_shadow,
        return_band_sigma=return_band_sigma,
    )
    shadow_events = shadow_events[eligible(shadow_events, store)] if shadow_events.size else shadow_events
    outcome.shadow_report = shadow_report

    outcome.direction = direction
    for name, (k_tp, k_sl) in BARRIER_CONFIGS.items():
        results = evaluate(events, store, k_tp, k_sl, direction=direction)
        shadow_results = (
            evaluate(shadow_events, store, k_tp, k_sl, direction=direction)
            if shadow_events.size
            else None
        )
        outcome.stats[name] = summarize(
            results, k_tp, k_sl, name, shadow=shadow_results, rng=rng,
            direction=direction, confidence=confidence,
        )

    return outcome


def run_template(
    engine: SearchEngine,
    template_id: str,
    query: np.ndarray,
    store: BarStore,
    pools: dict[int, ShadowPool],
    timeframe: str = "1d",
    limit: int = 5_000,
    p: int = SHADOW_SAMPLES_PER_MATCH,
    rng: np.random.Generator | None = None,
    direction: str = "long",
    confidence: float | None = None,
    return_matched_shadow: bool = False,
    return_band_sigma: float = RETURN_MATCH_BAND_SIGMA,
) -> TemplateOutcome:
    """Tek bir şablon için uçtan uca outcome (long veya short).

    Tolerans ``OUTCOME_TOLERANCE`` ile sabittir — p-hacking kilidi.
    ``return_matched_shadow=True`` ise F4.6 ön-getiri eşleştirmeli gölge
    kullanılır (vekil testi için zorunlu).
    """
    result = engine.search(query, timeframe=timeframe, tolerance=OUTCOME_TOLERANCE, limit=limit)
    return run_events(
        events_from_matches(result.results),
        store,
        pools,
        template_id=template_id,
        timeframe=timeframe,
        p=p,
        rng=rng,
        direction=direction,
        confidence=confidence,
        return_matched_shadow=return_matched_shadow,
        return_band_sigma=return_band_sigma,
    )


def run_all_templates(
    timeframe: str = "1d",
    matrix_root: Path | None = None,
    klines_root: Path | None = None,
    limit: int = 5_000,
    p: int = SHADOW_SAMPLES_PER_MATCH,
    seed: int = 20260731,
    return_matched_shadow: bool = False,
    return_band_sigma: float = RETURN_MATCH_BAND_SIGMA,
) -> list[TemplateOutcome]:
    """**14 şablonun tamamı** tek tabloda — p-hacking kilidi.

    "En iyi 3 formasyon" sunumu çoklu karşılaştırma problemidir; anlamlı
    çıkmayan formasyonlar da raporlanır, asıl bilimsel değer oradadır.
    """
    from engine.templates import load_all

    engine = SearchEngine(matrix_root)
    symbols_dict = engine.symbols
    symbols = list(symbols_dict.values())
    ids = {name: sid for sid, name in symbols_dict.items()}
    store = BarStore.from_klines(symbols, timeframe, ids, klines_root)
    pools = load_shadow_pools(
        timeframe, matrix_root=matrix_root,
        store=store if return_matched_shadow else None,
    )
    log.info("bar deposu: %d sembol, %d bar", len(store.offset), store.close.size)

    rng = np.random.default_rng(seed)
    out = []
    for template_id, template in load_all().items():
        outcome = run_template(
            engine, template_id, template.vector, store, pools, timeframe, limit, p, rng,
            return_matched_shadow=return_matched_shadow,
            return_band_sigma=return_band_sigma,
        )
        out.append(outcome)
        log.info("%s: %d eşleşme → %d bağımsız olay", template_id, outcome.matches, outcome.events)
    return out
