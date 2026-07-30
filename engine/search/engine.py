"""SearchEngine — tek motor, iki mod (K-15, docs/01-mimari.md §5–§6).

Kaskad (§5):

    Aşama 1  kosinüs, vektörize, maskeli      ~12M → ~5.000
    Pre-NMS  1D-IoU 0,70 (gevşek)             ~5.000 → ~1.000
    Aşama 2  DDTW + Sakoe-Chiba, normalize    ~1.000 → skorlanmış
    Post-NMS IoU 0,50 + max 3/sembol          → nihai sıralı liste

``mode`` **ayrı bir kod yolu değildir**; yalnızca Aşama 1'in maskesini
değiştirir (K-15):

* ``historical`` → tüm kayan pencere matrisi
* ``live``       → her sembolün yalnızca son penceresi

İki ayrı motor yazmak, kullanıcının Radar'da gördüğü bir eşleşmeyi
Backtest'te bulamamasına yol açardı — güveni yok eden tutarsızlık.

**Sıralama** normalize DDTW mesafesine göredir (küçük = benzer, K-14).
Sunumda ayrıca kosinüs (Pearson) skoru taşınır; bu, kalibre edilemeyen bir
"%85 benzerlik" uydurmak yerine anlamı tanımlı bir sayıdır (K-17).

Motor **"iyi eşleşme yok" diyebilmelidir**: hiçbir aday tolerans eşiğini
geçemezse boş sonuç döner (§5.5).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Sequence

import numpy as np

from engine.config import (
    MATRIX_DIR,
    MAX_RESULTS_PER_SYMBOL,
    N_POINTS,
    PAGE_SIZE,
    POST_NMS_IOU,
    PRE_NMS_IOU,
    SAKOE_CHIBA_RADIUS,
    STAGE1_TOPK,
    STAGE2_TOPK,
    TOLERANCE_THRESHOLDS,
    WINDOW_LENGTHS,
)
from engine.matrix.build import META_FILE, VECTORS_FILE, matrix_dir
from engine.matrix.npy_store import load_matrix
from engine.search.ddtw import ddtw_scores
from engine.search.nms import nms_1d
from engine.search.stage1_cosine import prepare_query, top_k

log = logging.getLogger(__name__)

Mode = Literal["live", "historical"]

#: Kaskad boyunca taşınan aday kaydı. ``row`` ilgili matristeki satır.
CANDIDATE_DTYPE = np.dtype(
    [
        ("symbol_id", "i4"),
        ("start_idx", "i4"),
        ("end_idx", "i4"),
        ("end_time", "i8"),
        ("amplitude", "f4"),
        ("atr", "f4"),
        ("length", "i4"),
        ("row", "i8"),
        ("score", "f4"),  # kosinüs (Pearson)
        ("distance", "f4"),  # normalize DDTW — sıralama metriği
    ]
)


@dataclass(frozen=True)
class Match:
    symbol: str
    symbol_id: int
    timeframe: str
    window_length: int
    start_idx: int
    end_idx: int
    end_time: int
    score: float
    distance: float
    amplitude: float
    atr: float

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "window_length": self.window_length,
            "start_idx": self.start_idx,
            "end_idx": self.end_idx,
            "end_time": self.end_time,
            "score": round(float(self.score), 4),
            "distance": round(float(self.distance), 6),
            "amplitude": round(float(self.amplitude), 2),
            "atr": float(self.atr),
        }


@dataclass
class SearchResult:
    results: list[Match] = field(default_factory=list)
    total: int = 0
    elapsed_ms: float = 0.0
    mode: str = "historical"
    timeframe: str = "4h"
    tolerance: str = "medium"
    stage1_candidates: int = 0
    stage2_candidates: int = 0

    def __len__(self) -> int:
        return len(self.results)


class MatrixHandle:
    """Tek bir (timeframe, length) matrisine memmap erişimi + maske önbelleği."""

    def __init__(self, timeframe: str, length: int, root: Path | None = None) -> None:
        d = matrix_dir(timeframe, length, root)
        self.timeframe = timeframe
        self.length = length
        self.vectors = load_matrix(d / VECTORS_FILE)
        meta = load_matrix(d / META_FILE)

        # Meta alanları küçüktür (satır başına ~27 bayt); maskeleme için
        # bir kez okunup RAM'de tutulur, vektör matrisi memmap kalır.
        self.symbol_id = np.asarray(meta["symbol_id"])
        self.start_idx = np.asarray(meta["start_idx"])
        self.end_idx = np.asarray(meta["end_idx"])
        self.end_time = np.asarray(meta["end_time"])
        self.amplitude = np.asarray(meta["amplitude"])
        self.atr = np.asarray(meta["atr"])
        self.liquid = np.asarray(meta["liquid"])
        self._live_mask: np.ndarray | None = None

    def __len__(self) -> int:
        return int(self.vectors.shape[0])

    @property
    def live_mask(self) -> np.ndarray:
        """Her sembolün **son** penceresi (Radar). Bir kez hesaplanır."""
        if self._live_mask is None:
            mask = np.zeros(len(self), dtype=bool)
            if len(self):
                order = np.lexsort((self.end_idx, self.symbol_id))
                sid = self.symbol_id[order]
                last = np.empty(sid.size, dtype=bool)
                last[-1] = True
                last[:-1] = sid[1:] != sid[:-1]
                mask[order[last]] = True
            self._live_mask = mask
        return self._live_mask

    def base_mask(
        self, mode: Mode, min_amplitude: float | None, require_liquid: bool
    ) -> np.ndarray | None:
        """Aşama 1 çarpımından ÖNCE uygulanacak maske (§5.1)."""
        mask: np.ndarray | None = None

        if require_liquid:
            mask = self.liquid.copy()
        if mode == "live":
            mask = self.live_mask.copy() if mask is None else (mask & self.live_mask)
        if min_amplitude is not None:
            amp_ok = self.amplitude >= np.float32(min_amplitude)
            mask = amp_ok if mask is None else (mask & amp_ok)
        return mask


class SearchEngine:
    """Matrisleri tembel yükler; ``search()`` tek giriş noktasıdır."""

    def __init__(
        self,
        matrix_root: Path | None = None,
        symbols: dict[int, str] | Sequence[str] | None = None,
    ) -> None:
        self.matrix_root = Path(matrix_root or MATRIX_DIR)
        self._handles: dict[tuple[str, int], MatrixHandle] = {}
        self.symbols = self._resolve_symbols(symbols)

    # -- semboller --------------------------------------------------------

    def _resolve_symbols(self, symbols) -> dict[int, str]:
        if isinstance(symbols, dict):
            return {int(k): str(v) for k, v in symbols.items()}
        if symbols is not None:
            return {i: s for i, s in enumerate(symbols)}

        path = self.matrix_root / "symbols.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return {int(v): str(k) for k, v in data.items()}

        from engine.ingest.symbol_universe import load_universe

        return {int(r["symbol_id"]): r["symbol"] for r in load_universe()}

    def symbol_name(self, symbol_id: int) -> str:
        return self.symbols.get(int(symbol_id), f"#{int(symbol_id)}")

    # -- matris erişimi ---------------------------------------------------

    def handle(self, timeframe: str, length: int) -> MatrixHandle:
        key = (timeframe, length)
        if key not in self._handles:
            self._handles[key] = MatrixHandle(timeframe, length, self.matrix_root)
        return self._handles[key]

    # -- kaskad -----------------------------------------------------------

    def search(
        self,
        query: np.ndarray,
        mode: Mode = "historical",
        timeframe: str = "4h",
        window_lengths: Sequence[int] = WINDOW_LENGTHS,
        tolerance: str = "medium",
        min_amplitude: float | None = None,
        limit: int = PAGE_SIZE,
        require_liquid: bool = True,
        stage1_topk: int = STAGE1_TOPK,
        stage2_topk: int = STAGE2_TOPK,
        radius: int = SAKOE_CHIBA_RADIUS,
    ) -> SearchResult:
        if tolerance not in TOLERANCE_THRESHOLDS:
            raise ValueError(f"bilinmeyen tolerans: {tolerance}")
        if mode not in ("live", "historical"):
            raise ValueError(f"bilinmeyen mod: {mode}")

        t0 = time.perf_counter()
        q = prepare_query(query)
        lengths = list(window_lengths)

        # Aday bütçesi çözünürlükler arasında paylaştırılır; toplam ~5.000
        # kalsın diye (performans bütçesi §15).
        per_length = max(1, stage1_topk // max(1, len(lengths)))

        # --- Aşama 1 ------------------------------------------------------
        blocks: list[np.ndarray] = []
        for length in lengths:
            h = self.handle(timeframe, length)
            if len(h) == 0:
                continue
            mask = h.base_mask(mode, min_amplitude, require_liquid)
            rows, scores = top_k(h.vectors, q, k=per_length, mask=mask)
            if rows.size == 0:
                continue

            block = np.empty(rows.size, dtype=CANDIDATE_DTYPE)
            block["symbol_id"] = h.symbol_id[rows]
            block["start_idx"] = h.start_idx[rows]
            block["end_idx"] = h.end_idx[rows]
            block["end_time"] = h.end_time[rows]
            block["amplitude"] = h.amplitude[rows]
            block["atr"] = h.atr[rows]
            block["length"] = length
            block["row"] = rows
            block["score"] = scores
            block["distance"] = np.inf
            blocks.append(block)

        result = SearchResult(mode=mode, timeframe=timeframe, tolerance=tolerance)
        if not blocks:
            result.elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return result

        candidates = np.concatenate(blocks)
        result.stage1_candidates = candidates.size

        # --- Pre-NMS (gevşek) --------------------------------------------
        keep = nms_1d(candidates, PRE_NMS_IOU)
        candidates = candidates[keep][:stage2_topk]
        result.stage2_candidates = candidates.size

        # --- Aşama 2: DDTW -----------------------------------------------
        vectors = self._gather_vectors(timeframe, candidates)
        candidates["distance"] = ddtw_scores(q, vectors, radius)

        # Tolerans eşiği: motor "iyi eşleşme yok" diyebilmeli (§5.5)
        threshold = TOLERANCE_THRESHOLDS[tolerance]
        candidates = candidates[candidates["distance"] <= threshold]
        if candidates.size == 0:
            result.elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return result

        # --- Post-NMS (katı) ---------------------------------------------
        keep = nms_1d(
            candidates,
            POST_NMS_IOU,
            max_per_symbol=MAX_RESULTS_PER_SYMBOL,
            score_field="distance",
            higher_is_better=False,
        )
        final = candidates[keep]

        result.total = int(final.size)
        result.results = [self._to_match(c, timeframe) for c in final[: max(0, limit)]]
        result.elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return result

    # -- yardımcılar ------------------------------------------------------

    def _gather_vectors(self, timeframe: str, candidates: np.ndarray) -> np.ndarray:
        """Adayların vektörlerini ilgili matrislerden toplar (yalnız o satırlar)."""
        out = np.empty((candidates.size, N_POINTS), dtype=np.float32)
        for length in np.unique(candidates["length"]):
            sel = candidates["length"] == length
            rows = candidates["row"][sel]
            order = np.argsort(rows, kind="stable")  # memmap'te sıralı okuma
            h = self.handle(timeframe, int(length))
            gathered = np.asarray(h.vectors[rows[order]])
            idx = np.flatnonzero(sel)[order]
            out[idx] = gathered
        return out

    def _to_match(self, c: np.void, timeframe: str) -> Match:
        return Match(
            symbol=self.symbol_name(int(c["symbol_id"])),
            symbol_id=int(c["symbol_id"]),
            timeframe=timeframe,
            window_length=int(c["length"]),
            start_idx=int(c["start_idx"]),
            end_idx=int(c["end_idx"]),
            end_time=int(c["end_time"]),
            score=float(c["score"]),
            distance=float(c["distance"]),
            amplitude=float(c["amplitude"]),
            atr=float(c["atr"]),
        )
