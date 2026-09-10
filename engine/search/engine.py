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
    DEFAULT_MIN_AMPLITUDE,
    MATRIX_DIR,
    MAX_RESULTS_PER_SYMBOL,
    N_POINTS,
    NULL_CACHE_SIZE,
    NULL_DISCRIMINATIVE_RATIO,
    NULL_MIN_SAMPLES,
    NULL_PERCENTILES,
    NULL_SAMPLE_SIZE,
    NULL_SEED,
    PAGE_SIZE,
    POST_NMS_IOU,
    PRE_NMS_IOU,
    SAKOE_CHIBA_RADIUS,
    STAGE1_TOPK,
    STAGE2_METRIC,
    STAGE2_TOPK,
    ENVELOPE_FILTER,
    ENVELOPE_MIN_SURVIVORS,
    STRUCTURE_FILTER,
    STRUCTURE_MIN_SURVIVORS,
    STRUCTURE_STABILITY_GATE,
    STRUCTURE_YIELDS_TO_ENVELOPE,
    TOLERANCE_THRESHOLDS_BY_METRIC,
    WINDOW_LENGTHS,
)
from engine.matrix.build import (
    LEGACY_SYMBOLS_FILE,
    META_FILE,
    VECTORS_FILE,
    matrix_dir,
    symbols_file,
)
from engine.matrix.npy_store import load_matrix
from engine.search.constraints import (
    filter_plan,
    envelope_mask,
    signature_mask,
)
from engine.search.ddtw import stage2_scores
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
        ("distance", "f4"),  # ham normalize mesafe (metrik ölçeğinde)
        ("percentile", "f4"),  # null dağılımındaki yüzdelik — SIRALAMA BUNA GÖRE
    ]
)


@dataclass(frozen=True)
class NullStats:
    """Bir (sorgu, pencere uzunluğu) çifti için null dağılım özeti."""

    length: int
    n: int
    p001: float
    p01: float
    median: float
    threshold: float
    used_absolute: bool = False

    @property
    def spread(self) -> float:
        """``medyan / p01`` — küçükse rastgele pencereler de sorguya benziyor."""
        return float(self.median / self.p01) if self.p01 > 0 else float("inf")


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
    percentile: float = 1.0
    row: int = 0
    dtw_path: tuple[tuple[int, int], ...] | None = None

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "symbol_id": self.symbol_id,
            "timeframe": self.timeframe,
            "window_length": self.window_length,
            "start_idx": self.start_idx,
            "end_idx": self.end_idx,
            "end_time": self.end_time,
            "score": round(float(self.score), 4),
            "distance": round(float(self.distance), 6),
            "percentile": float(self.percentile),
            "amplitude": round(float(self.amplitude), 2),
            "atr": float(self.atr),
            "warp_path": [list(p) for p in self.dtw_path] if self.dtw_path is not None else None,
        }


@dataclass
class SearchResult:
    results: list[Match] = field(default_factory=list)
    total: int = 0
    elapsed_ms: float = 0.0
    mode: str = "historical"
    timeframe: str = "4h"
    tolerance: str = "medium"
    metric: str = STAGE2_METRIC  # F3 kalibrasyonunda hangi metrikle üretildiği
    stage1_candidates: int = 0
    stage2_candidates: int = 0
    null_stats: dict[int, "NullStats"] = field(default_factory=dict)
    #: Sıralı null skor dizileri (uzunluk başına). İnce ayar katmanı (F8)
    #: yüzdelik dilimi yeniden hesaplayabilsin diye taşınır — özet
    #: ``null_stats`` eşikleri verir, yeniden hesap için dizinin kendisi gerekir.
    null_dist: dict[int, np.ndarray] = field(default_factory=dict)
    discriminative: bool = True
    #: Yapısal imza filtresi uygulandı mı, ve uygulanamadıysa neden.
    structure_filtered: bool = False
    structure_relaxed: bool = False
    #: Motorun çizimden okuduğu yapı, insan diliyle. Kullanıcı motorun
    #: yorumunu göremezse yanlış yorumu da göremez.
    structure_read: str | None = None
    #: Trend çizgisi (zarf) filtresi uygulandı mı. K-21: ölçüldü, varsayılan
    #: KAPALI — kesinliği artırmıyor, duyarlılığı düşürüyor.
    envelope_filtered: bool = False
    envelope_relaxed: bool = False
    #: Motorun çizimden okuduğu trend çizgisi düzeni, insan diliyle.
    #: Eğimle tanımlı formasyonlarda daralmayı YAPAN okuma budur; yalnız uç
    #: düzeni okumasını göstermek motorun gerçek gerekçesini gizlerdi.
    envelope_read: str | None = None
    #: Okuma sağlam mı: aynı şekil biraz farklı çizilse aynı okunur muydu?
    #: Eğimle tanımlı formasyonlarda (üçgen, takoz, flama) okuma kararsızdır
    #: ve o kararsızlık ölçülen doğrulukla birebir örtüşür: dönüş ailesinde
    #: ilk 50'nin %99'u aranan formasyonken eğim ailesinde %49
    #: (docs/10-formasyon-denetimi.md). Kesinmiş gibi göstermek fazla iddia.
    structure_stable: bool = True

    def __len__(self) -> int:
        return len(self.results)

    @property
    def warning(self) -> str | None:
        """Yapısal benzerlik uyarısı — ölçümden çıkar, elle kodlanmaz.

        Null dağılımı dar olduğunda (``medyan / p01`` küçük), korpustaki tüm
        pencereler sorguya aynı derecede uzaktır: ortada bulunacak bir yapı
        yoktur. Ölçülen: whipsaw 1,3 · white noise 1,4 · OBO 8,1 · bayrak 15,1.
        """
        if self.structure_relaxed:
            return (
                "Çizdiğiniz yapıyı (tepe/dip düzenini) taşıyan yeterli pencere "
                "bulunamadı; sonuçlar yapısal filtre UYGULANMADAN listelendi. "
                "Şekil benzer olabilir ama formasyonun kendisi olmayabilir."
            )
        if self.discriminative:
            return None
        return (
            "Bu çizime yapısal olarak benzeyen bir hareket bulunamadı; "
            "sonuçlar anlamlı olmayabilir. Daha belirgin bir formasyon deneyin."
        )


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

    def null_rows(
        self,
        mask: np.ndarray | None,
        sample_size: int = NULL_SAMPLE_SIZE,
        seed: int = NULL_SEED,
    ) -> np.ndarray:
        """Null dağılımı için rastgele pencere indeksleri.

        Örneklem **aranabilir popülasyondan** çekilir (likidite/genlik maskesi
        uygulanmış hâli) — null, "rastgele bir aday" anlamına gelmeli.
        Tohum sabit: aynı sorgu iki kez çalıştırıldığında aynı eşiği verir.
        """
        pool = np.flatnonzero(mask) if mask is not None else np.arange(len(self))
        if pool.size == 0:
            return pool
        if pool.size <= sample_size:
            return pool
        rng = np.random.default_rng(seed + self.length)
        return np.sort(rng.choice(pool, size=sample_size, replace=False))

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
        self._override = self._as_map(symbols)
        self._symbol_maps: dict[str, dict[int, str]] = {}
        # Null dağılımı (sorgu, uzunluk, metrik, maske) başına sabittir; Radar
        # cron'u aynı şablonları 5 dakikada bir çalıştırdığı için önbelleğe
        # alınması ilk çağrı dışındaki tüm maliyeti kaldırır (§6).
        self._null_cache: dict[tuple, np.ndarray] = {}

    # -- semboller --------------------------------------------------------
    #
    # ``symbol_id`` uzayı **zaman dilimi başınadır**: 4h evreni likit alt
    # kümedir, 1d evreni tüm geçmişi kapsar; aynı id iki dilimde iki farklı
    # sembole düşer. Tek bir global harita tutmak, 1d eşleşmelerinin sembol
    # adı yerine "#897" görünmesine yol açmıştı.

    @staticmethod
    def _as_map(symbols) -> dict[int, str] | None:
        if isinstance(symbols, dict):
            return {int(k): str(v) for k, v in symbols.items()}
        if symbols is not None:
            return {i: s for i, s in enumerate(symbols)}
        return None

    def symbols_for(self, timeframe: str) -> dict[int, str]:
        """``symbol_id → sembol`` haritası (zaman dilimi başına, önbellekli)."""
        if self._override is not None:
            return self._override
        cached = self._symbol_maps.get(timeframe)
        if cached is not None:
            return cached

        for name in (symbols_file(timeframe), LEGACY_SYMBOLS_FILE):
            path = self.matrix_root / name
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                mapping = {int(v): str(k) for k, v in data.items()}
                self._symbol_maps[timeframe] = mapping
                return mapping

        from engine.ingest.symbol_universe import load_universe

        mapping = {int(r["symbol_id"]): r["symbol"] for r in load_universe()}
        self._symbol_maps[timeframe] = mapping
        return mapping

    def symbol_name(self, symbol_id: int, timeframe: str) -> str:
        return self.symbols_for(timeframe).get(int(symbol_id), f"#{int(symbol_id)}")

    def symbol_id_of(self, symbol: str, timeframe: str) -> int | None:
        target = symbol.upper()
        for sid, name in self.symbols_for(timeframe).items():
            if name.upper() == target:
                return sid
        return None

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
        metric: str = STAGE2_METRIC,
        null_sample: int = NULL_SAMPLE_SIZE,
        structure_filter: bool = STRUCTURE_FILTER,
        structure_gate: bool = STRUCTURE_STABILITY_GATE,
        envelope_filter: bool = ENVELOPE_FILTER,
        structure_yields: bool = STRUCTURE_YIELDS_TO_ENVELOPE,
    ) -> SearchResult:
        # Eşikler metrik başına ayrıdır; ham DTW mesafeleri DDTW'ninkinden
        # ~4-8x büyüktür (K-11, F3 kalibrasyonu).
        thresholds = TOLERANCE_THRESHOLDS_BY_METRIC.get(metric)
        if thresholds is None:
            raise ValueError(f"'{metric}' metriği için kalibre edilmiş eşik yok")
        if tolerance not in thresholds:
            raise ValueError(f"bilinmeyen tolerans: {tolerance}")
        if mode not in ("live", "historical"):
            raise ValueError(f"bilinmeyen mod: {mode}")

        t0 = time.perf_counter()
        q = prepare_query(query)
        lengths = list(window_lengths)
        if min_amplitude is None:
            min_amplitude = DEFAULT_MIN_AMPLITUDE.get(timeframe)

        # Aday bütçesi çözünürlükler arasında paylaştırılır; toplam ~5.000
        # kalsın diye (performans bütçesi §15).
        per_length = max(1, stage1_topk // max(1, len(lengths)))

        # --- Aşama 1 ------------------------------------------------------
        blocks: list[np.ndarray] = []
        null_by_length: dict[int, np.ndarray] = {}
        result_null_dist: dict[int, np.ndarray] = {}
        for length in lengths:
            h = self.handle(timeframe, length)
            if len(h) == 0:
                continue
            mask = h.base_mask(mode, min_amplitude, require_liquid)

            # Null dağılımı, tarama maskesiyle AYNI popülasyondan (F3.5).
            # Historical modda maske, live modda tüm aranabilir evren kullanılır:
            # live'da popülasyon zaten "her sembolün son penceresi"dir ve
            # ondan çekilen null, mutlak ölçeği kalibre etmeye yetmez.
            null_mask = mask if mode == "historical" else h.base_mask(
                "historical", min_amplitude, require_liquid
            )
            null = self._null_distribution(
                h, q, null_mask, null_sample, radius, metric, min_amplitude, require_liquid
            )
            if null is not None:
                null_by_length[length] = null
                result_null_dist[length] = null

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
            block["percentile"] = 1.0
            blocks.append(block)

        result = SearchResult(mode=mode, timeframe=timeframe, tolerance=tolerance, metric=metric)
        result.null_dist = result_null_dist
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
        candidates["distance"] = stage2_scores(q, vectors, radius, metric)

        # --- Null kalibrasyonu (F3.5) -------------------------------------
        # Eşik ve sıralama, mutlak mesafeye değil, o sorgunun kendi null
        # dağılımındaki yüzdelik dilime göre — pencere uzunluğu BAŞINA.
        keep_mask = np.zeros(candidates.size, dtype=bool)
        for length in np.unique(candidates["length"]):
            sel = candidates["length"] == length
            null = null_by_length.get(int(length))
            stats = self._null_stats(int(length), null, tolerance, thresholds)
            result.null_stats[int(length)] = stats

            distances = candidates["distance"][sel]
            if stats.used_absolute:
                candidates["percentile"][sel] = np.where(distances <= stats.threshold, 0.0, 1.0)
            else:
                candidates["percentile"][sel] = np.searchsorted(null, distances, side="left") / null.size
            keep_mask[sel] = distances <= stats.threshold

        result.discriminative = self._is_discriminative(result.null_stats)
        candidates = candidates[keep_mask]
        if candidates.size == 0:
            result.elapsed_ms = (time.perf_counter() - t0) * 1000.0
            return result

        # --- Yapısal imza filtresi ---------------------------------------
        # DTW noktaları hizalar, hizalanan noktaların SEVİYELERİNİN mantıklı
        # olup olmadığına bakmaz: "yükseliş-tümsek-düşüş" yakalanır, omuz-baş-
        # omuz olup olmadığı sorulmaz. Ölçüldü: ilk 12'nin yalnız %42'si
        # gerçekten aranan formasyondu (tools/formation_audit).
        #
        # Kural sorgudan türer — formasyon başına kod yok (K-04). Serbest
        # çizimde de çalışmasının sebebi bu: şablon meta-verisi gerekmiyor.
        # Hangi katman uygulanacak: K-20 kapısı, K-21 kapısı ve alternatiflik
        # kuralı tek bir saf fonksiyonda (constraints.filter_plan). Motor
        # parmak izi de onu çağırır — karar burada gömülüyken parmak izi bir
        # davranış değişikliğini kaçırmıştı.
        plan = filter_plan(
            q,
            structure_filter=structure_filter,
            structure_gate=structure_gate,
            envelope_filter=envelope_filter,
            structure_yields=structure_yields,
        )
        result.structure_read = plan.structure_read
        result.structure_stable = plan.structure_stable
        result.envelope_read = plan.envelope_read
        structure_filter = plan.apply_structure
        envelope_filter = plan.apply_envelope

        if structure_filter and candidates.size:
            mask = signature_mask(q, self._gather_vectors(timeframe, candidates))
            if mask is not None:
                if int(mask.sum()) >= min(STRUCTURE_MIN_SURVIVORS, candidates.size):
                    candidates = candidates[mask]
                    result.structure_filtered = True
                else:
                    # "Yapıya uyan yok" ile "hiç sonuç yok" farklı şeylerdir.
                    # Geri düşülür ama SESSİZCE değil: uyarı yanıtta taşınır.
                    result.structure_relaxed = True

        # --- Zarf (trend çizgisi) filtresi --------------------------------
        # Yapısal imza uç DÜZENİNİ okur ve eğimle tanımlı formasyonlarda bilgi
        # taşımaz (K-20). Bu katman trend çizgilerini okur. Kural yine
        # sorgudan türer; formasyon başına kod yoktur (K-04).
        # Varsayılan KAPALI — gerekçe K-21'de ölçümüyle birlikte.
        # Kapı burada da geçerli (K-20 dersi): OBO'nun zarf imzası tanımlıdır
        # ama kararlılığı %41 — kapısız bir zarf filtresi dönüş ailesini
        # yazı-turayla elerdi.
        if envelope_filter and candidates.size:
            mask = envelope_mask(q, self._gather_vectors(timeframe, candidates))
            if mask is not None:
                if int(mask.sum()) >= min(ENVELOPE_MIN_SURVIVORS, candidates.size):
                    candidates = candidates[mask]
                    result.envelope_filtered = True
                else:
                    result.envelope_relaxed = True

        # --- Post-NMS (katı) ---------------------------------------------
        # Sıralama yüzdelik dilime göre: 24 barlık pencereler 100 barlıkları
        # sistematik olarak ezemesin (K-14'ün yol-uzunluğu bölmesi yetmedi).
        keep = nms_1d(
            candidates,
            POST_NMS_IOU,
            max_per_symbol=MAX_RESULTS_PER_SYMBOL,
            score_field="percentile",
            higher_is_better=False,
        )
        final = candidates[keep]

        result.total = int(final.size)
        result.results = [self._to_match(c, timeframe) for c in final[: max(0, limit)]]
        result.elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return result

    # -- yardımcılar ------------------------------------------------------

    def _null_distribution(
        self,
        handle: MatrixHandle,
        query: np.ndarray,
        mask: np.ndarray | None,
        sample_size: int,
        radius: int,
        metric: str,
        min_amplitude: float | None,
        require_liquid: bool,
    ) -> np.ndarray | None:
        """Sıralı null skor dizisi (önbellekli).

        Anahtar sorguyu da içerir: null, sorguya özgüdür — F3.5'in tüm fikri
        eşiği *o sorgunun* dağılımından türetmektir.
        """
        key = (
            handle.timeframe,
            handle.length,
            metric,
            radius,
            sample_size,
            min_amplitude,
            require_liquid,
            query.tobytes(),
        )
        cached = self._null_cache.get(key)
        if cached is not None:
            return cached

        rows = handle.null_rows(mask, sample_size, NULL_SEED)
        if rows.size == 0:
            return None

        null = np.sort(stage2_scores(query, np.asarray(handle.vectors[rows]), radius, metric))
        if len(self._null_cache) >= NULL_CACHE_SIZE:
            self._null_cache.pop(next(iter(self._null_cache)))
        self._null_cache[key] = null
        return null

    def _null_stats(
        self,
        length: int,
        null: np.ndarray | None,
        tolerance: str,
        absolute: dict[str, float],
    ) -> NullStats:
        """Null dağılımından eşik türetir; örneklem küçükse mutlak eşiğe düşer."""
        if null is None or null.size < NULL_MIN_SAMPLES:
            return NullStats(
                length=length,
                n=0 if null is None else int(null.size),
                p001=float("nan"),
                p01=float("nan"),
                median=float("nan"),
                threshold=absolute[tolerance],
                used_absolute=True,
            )

        percentile = NULL_PERCENTILES[tolerance]
        relative = float(np.quantile(null, percentile))
        return NullStats(
            length=length,
            n=int(null.size),
            p001=float(np.quantile(null, 0.001)),
            p01=float(np.quantile(null, 0.01)),
            median=float(np.median(null)),
            # İki koşul birlikte: yüzdelik dilim VE mutlak akıl sağlığı tavanı.
            # Yalnız yüzdelik kalsaydı motor her sorguya sonuç döndürürdü.
            #
            # Tavan ÇAĞRININ metriğinden okunur. Eskiden aktif metriğin
            # (NULL_ABSOLUTE_CAP) sabitiydi: çağrı başına başka bir metrik
            # verildiğinde o metriğin ölçeğine ait olmayan bir tavan
            # uygulanıyordu (merkezi fark hybrid'den ~%20 küçük mesafe verir).
            # Varsayılan metrikte ikisi aynı sayıdır.
            threshold=min(relative, absolute["flexible"]),
        )

    @staticmethod
    def _is_discriminative(stats: dict[int, NullStats]) -> bool:
        """Null dağılımı darsa şekil ayırt edici değildir (S-1)."""
        spreads = [s.spread for s in stats.values() if not s.used_absolute and np.isfinite(s.spread)]
        if not spreads:
            return True
        return float(np.median(spreads)) >= NULL_DISCRIMINATIVE_RATIO

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
            symbol=self.symbol_name(int(c["symbol_id"]), timeframe),
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
            percentile=float(c["percentile"]),
            row=int(c["row"]),
        )

    def compute_warp_paths(
        self,
        matches: Sequence[Match],
        query_vector: np.ndarray,
        radius: int = SAKOE_CHIBA_RADIUS,
    ) -> list[list[list[int]]]:
        """Verilen eşleşmeler için DDTW hizalama yollarını (warp_path) hesaplar."""
        from engine.search.ddtw import warping_path

        paths: list[list[list[int]]] = []
        for m in matches:
            try:
                h = self.handle(m.timeframe, m.window_length)
                cand = np.asarray(h.vectors[m.row])
                path_arr = warping_path(query_vector, cand, radius=radius, use_derivative=True)
                paths.append(path_arr.tolist())
            except Exception:
                paths.append([])
        return paths
