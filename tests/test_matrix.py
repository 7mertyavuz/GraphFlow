"""F1 — matris inşası, likidite maskesi, artımlı append testleri."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from engine.config import LIQUIDITY_TOP_PCT, META_DTYPE, N_POINTS, STRIDE
from engine.ingest.store import read_klines, write_atomic
from engine.matrix.build import (
    META_FILE,
    VECTORS_FILE,
    build_all,
    build_matrix,
    matrix_dir,
    window_starts,
)
from engine.matrix.incremental import last_end_idx, update_matrix
from engine.matrix.liquidity import (
    LiquidityMask,
    build_liquidity_table,
    build_from_klines,
    month_key,
    monthly_volume,
)
from engine.matrix.npy_store import ChunkedNpyWriter, append_rows, load_matrix
from engine.normalize.pipeline import normalize_window
from tools.gen_synthetic import generate_dataset, make_symbol

TF = "4h"


@pytest.fixture(scope="module")
def synthetic(tmp_path_factory):
    root = tmp_path_factory.mktemp("syn")
    truth = generate_dataset(root / "klines", n_symbols=4, n_bars=1_200, seed=11)
    return root, truth


# ---------------------------------------------------------------------------
# .npy akışlı yazım ve append
# ---------------------------------------------------------------------------


def test_chunked_writer_roundtrip(tmp_path):
    path = tmp_path / "v.npy"
    rng = np.random.default_rng(0)
    chunks = [rng.random((7, N_POINTS), dtype=np.float32) for _ in range(3)]

    with ChunkedNpyWriter(path, np.float32, (N_POINTS,)) as w:
        for c in chunks:
            w.append(c)

    loaded = np.load(path, mmap_mode="r")
    assert loaded.shape == (21, N_POINTS)
    np.testing.assert_array_equal(np.asarray(loaded), np.concatenate(chunks))


def test_chunked_writer_abort_leaves_no_files(tmp_path):
    path = tmp_path / "v.npy"
    w = ChunkedNpyWriter(path, np.float32, (N_POINTS,))
    w.append(np.zeros((3, N_POINTS), dtype=np.float32))
    w.abort()
    assert not path.exists()
    assert list(tmp_path.glob("*.tmp")) == []


def test_structured_dtype_roundtrip(tmp_path):
    path = tmp_path / "meta.npy"
    meta = np.zeros(5, dtype=META_DTYPE)
    meta["symbol_id"] = np.arange(5)
    meta["liquid"] = True

    with ChunkedNpyWriter(path, META_DTYPE) as w:
        w.append(meta)

    loaded = np.load(path, mmap_mode="r")
    assert loaded.dtype == META_DTYPE
    assert loaded["symbol_id"].tolist() == [0, 1, 2, 3, 4]


def test_append_rows_grows_file(tmp_path):
    path = tmp_path / "v.npy"
    rng = np.random.default_rng(1)
    a = rng.random((10, N_POINTS), dtype=np.float32)
    b = rng.random((5, N_POINTS), dtype=np.float32)

    append_rows(path, a)
    total = append_rows(path, b)

    loaded = np.load(path, mmap_mode="r")
    assert total == 15 and loaded.shape == (15, N_POINTS)
    np.testing.assert_array_equal(np.asarray(loaded), np.concatenate([a, b]))


def test_append_rows_survives_many_appends(tmp_path):
    """Başlıktaki shape rakam sayısı büyüdüğünde de dosya bozulmamalı."""
    path = tmp_path / "v.npy"
    for _ in range(40):
        append_rows(path, np.ones((7, 4), dtype=np.float32))
    loaded = np.load(path, mmap_mode="r")
    assert loaded.shape == (280, 4)
    assert np.asarray(loaded).sum() == 280 * 4


def test_append_rows_rejects_dtype_mismatch(tmp_path):
    path = tmp_path / "v.npy"
    append_rows(path, np.ones((2, 4), dtype=np.float32))
    with pytest.raises(ValueError):
        append_rows(path, np.ones((2, 4), dtype=np.float64))


# ---------------------------------------------------------------------------
# Kayan pencere ızgarası
# ---------------------------------------------------------------------------


def test_window_starts_respects_stride():
    starts = window_starts(100, 24, stride=STRIDE)
    assert starts[0] == 0
    assert np.all(np.diff(starts) == STRIDE)
    assert starts[-1] + 24 - 1 <= 99


def test_window_starts_too_short_series():
    assert window_starts(10, 24).size == 0


def test_window_starts_from_bar_is_grid_aligned():
    """Artımlı güncelleme aynı ızgarayı kullanmalı — pencere tekrarı olmaz."""
    full = window_starts(200, 40, stride=3)
    tail = window_starts(200, 40, stride=3, from_bar=150)
    assert set(tail.tolist()) <= set(full.tolist())
    assert np.all(tail + 40 - 1 >= 150)


# ---------------------------------------------------------------------------
# Likidite (K-13.2)
# ---------------------------------------------------------------------------


def test_month_key_buckets_by_calendar_month():
    times = np.array([1_704_067_200_000, 1_704_240_000_000, 1_706_745_600_000])  # Oca, Oca, Şub
    months = month_key(times)
    assert months[0] == months[1] != months[2]


def test_liquidity_is_cross_sectional_per_month():
    """Sabit dolar eşiği DEĞİL: her ayın kendi kesiti (K-13.2)."""
    month_a, month_b = 0, 1
    volumes = {
        # 2018 benzeri düşük hacimli ay: mutlak rakamlar küçük ama sıralama var
        "OLD_TOP": pd.Series({month_a: 1_000.0}),
        "OLD_MID": pd.Series({month_a: 500.0}),
        "OLD_LOW": pd.Series({month_a: 10.0}),
        # 2025 benzeri yüksek hacimli ay
        "NEW_TOP": pd.Series({month_b: 1_000_000_000.0}),
        "NEW_LOW": pd.Series({month_b: 1_000.0}),
    }
    table = build_liquidity_table(volumes)
    liquid = set(table.loc[table["liquid"], "symbol"])

    # Düşük hacimli ayın lideri, sabit eşikte elenirdi; burada likit sayılır.
    assert "OLD_TOP" in liquid
    assert "OLD_LOW" not in liquid
    assert "NEW_TOP" in liquid


def test_liquidity_top_pct_share():
    volumes = {f"S{i}": pd.Series({0: float(i)}) for i in range(10)}
    table = build_liquidity_table(volumes)
    assert table["liquid"].sum() == pytest.approx(10 * LIQUIDITY_TOP_PCT, abs=1)


def test_liquidity_mask_lookup(synthetic):
    root, _ = synthetic
    symbols = ["SYN000USDT", "SYN001USDT", "SYN002USDT", "SYN003USDT"]
    table = build_from_klines(symbols, TF, root / "klines")
    mask = LiquidityMask(table)

    months = table["month"].to_numpy()[:3]
    result = mask.lookup(table["symbol"].iloc[0], months)
    assert result.dtype == bool and result.size == 3


def test_monthly_volume_sums_within_month(synthetic):
    root, _ = synthetic
    df = read_klines("SYN000USDT", TF, root / "klines")
    series = monthly_volume(df)
    assert series.sum() == pytest.approx(df["quote_volume"].sum(), rel=1e-9)


# ---------------------------------------------------------------------------
# Matris inşası
# ---------------------------------------------------------------------------


def test_build_all_produces_eight_matrices(tmp_path):
    """2 timeframe × 4 uzunluk = 8 matris (K-14)."""
    generate_dataset(tmp_path / "klines", n_symbols=2, n_bars=400, timeframe="4h", seed=5)
    generate_dataset(tmp_path / "klines", n_symbols=2, n_bars=400, timeframe="1d", seed=6)

    stats = build_all(klines_root=tmp_path / "klines", out_root=tmp_path / "matrix")

    assert len(stats) == 8
    for tf in ("4h", "1d"):
        for length in (24, 40, 64, 100):
            d = matrix_dir(tf, length, tmp_path / "matrix")
            assert (d / VECTORS_FILE).exists() and (d / META_FILE).exists()


def test_matrix_vectors_are_normalized(synthetic, tmp_path):
    root, _ = synthetic
    build_all(timeframes=[TF], lengths=[40], klines_root=root / "klines", out_root=tmp_path)

    V = load_matrix(matrix_dir(TF, 40, tmp_path) / VECTORS_FILE)
    norms = np.linalg.norm(np.asarray(V), axis=1)

    assert V.dtype == np.float32
    np.testing.assert_allclose(norms, np.sqrt(N_POINTS), rtol=1e-4)


def test_matrix_meta_matches_source_window(synthetic, tmp_path):
    """meta[i] gerçekten vectors[i]'nin geldiği pencereyi göstermeli."""
    root, _ = synthetic
    build_all(timeframes=[TF], lengths=[64], klines_root=root / "klines", out_root=tmp_path)

    d = matrix_dir(TF, 64, tmp_path)
    V = np.asarray(load_matrix(d / VECTORS_FILE))
    M = np.asarray(load_matrix(d / META_FILE))

    symbols = sorted({f"SYN{i:03d}USDT" for i in range(4)})
    for i in (0, len(M) // 2, len(M) - 1):
        row = M[i]
        df = read_klines(symbols[int(row["symbol_id"])], TF, root / "klines")
        window = df["close"].to_numpy()[row["start_idx"] : row["end_idx"] + 1]

        assert row["end_idx"] - row["start_idx"] + 1 == 64
        assert row["end_time"] == df["open_time"].to_numpy()[row["end_idx"]]
        np.testing.assert_allclose(V[i], normalize_window(window), atol=1e-5)


def test_matrix_is_memmapped_not_loaded(synthetic, tmp_path):
    root, _ = synthetic
    build_all(timeframes=[TF], lengths=[24], klines_root=root / "klines", out_root=tmp_path)
    V = load_matrix(matrix_dir(TF, 24, tmp_path) / VECTORS_FILE)
    assert isinstance(V, np.memmap)


def test_chunking_does_not_change_result(synthetic, tmp_path):
    """Bellek verimliliği için chunk'lama sonucu değiştirmemeli."""
    root, _ = synthetic
    symbols = [f"SYN{i:03d}USDT" for i in range(4)]
    ids = {s: i for i, s in enumerate(symbols)}

    build_matrix(TF, 40, symbols, ids, klines_root=root / "klines", out_root=tmp_path / "a")
    # Patolojik derecede küçük chunk ile aynı sonuç çıkmalı.
    build_matrix(TF, 40, symbols, ids, klines_root=root / "klines", out_root=tmp_path / "b", chunk=7)

    a = np.asarray(load_matrix(matrix_dir(TF, 40, tmp_path / "a") / VECTORS_FILE))
    b = np.asarray(load_matrix(matrix_dir(TF, 40, tmp_path / "b") / VECTORS_FILE))
    np.testing.assert_array_equal(a, b)


def test_flat_windows_are_dropped(tmp_path):
    """σ < FLAT_EPS penceresi matrise girmez (K-02 kenar durumu)."""
    n = 200
    close = np.full(n, 100.0)  # tamamen düz seri
    df = pd.DataFrame(
        {
            "open_time": np.arange(n, dtype=np.int64) * 14_400_000 + 1_500_000_000_000,
            "open": close,
            "high": close,
            "low": close,
            "close": close,
            "volume": np.ones(n),
            "quote_volume": np.ones(n),
            "trades": np.ones(n, dtype=np.int32),
        }
    )
    write_atomic(df, tmp_path / "klines" / TF / "FLATUSDT.parquet")

    stats = build_matrix(
        TF, 24, ["FLATUSDT"], {"FLATUSDT": 0}, klines_root=tmp_path / "klines", out_root=tmp_path / "m"
    )
    assert stats.windows == 0
    assert stats.dropped_flat > 0
    assert load_matrix(matrix_dir(TF, 24, tmp_path / "m") / VECTORS_FILE).shape[0] == 0


# ---------------------------------------------------------------------------
# Artımlı güncelleme (§4.4)
# ---------------------------------------------------------------------------


def test_incremental_append_matches_full_rebuild(tmp_path):
    """Artımlı sonuç, tam inşa ile BİREBİR aynı olmalı."""
    rng = np.random.default_rng(42)
    df, _ = make_symbol("SYNXUSDT", rng, n_bars=600, n_injections=3)
    root = tmp_path / "klines"

    # 1) İlk 500 barla inşa
    write_atomic(df.iloc[:500], root / TF / "SYNXUSDT.parquet")
    ids = {"SYNXUSDT": 0}
    build_matrix(TF, 40, ["SYNXUSDT"], ids, klines_root=root, out_root=tmp_path / "inc")

    # 2) Kalan barlar gelir → artımlı güncelleme
    write_atomic(df, root / TF / "SYNXUSDT.parquet")
    added = update_matrix(TF, 40, ["SYNXUSDT"], ids, klines_root=root, out_root=tmp_path / "inc")

    # 3) Referans: sıfırdan tam inşa
    build_matrix(TF, 40, ["SYNXUSDT"], ids, klines_root=root, out_root=tmp_path / "full")

    inc_v = np.asarray(load_matrix(matrix_dir(TF, 40, tmp_path / "inc") / VECTORS_FILE))
    inc_m = np.asarray(load_matrix(matrix_dir(TF, 40, tmp_path / "inc") / META_FILE))
    full_v = np.asarray(load_matrix(matrix_dir(TF, 40, tmp_path / "full") / VECTORS_FILE))
    full_m = np.asarray(load_matrix(matrix_dir(TF, 40, tmp_path / "full") / META_FILE))

    assert added > 0
    assert inc_v.shape == full_v.shape
    np.testing.assert_array_equal(np.sort(inc_m["end_idx"]), np.sort(full_m["end_idx"]))
    np.testing.assert_allclose(inc_v, full_v, atol=1e-6)


def test_incremental_is_idempotent(tmp_path):
    """Yeni bar yokken ikinci çalıştırma hiçbir şey eklememeli."""
    rng = np.random.default_rng(9)
    df, _ = make_symbol("SYNYUSDT", rng, n_bars=400, n_injections=2)
    root = tmp_path / "klines"
    write_atomic(df, root / TF / "SYNYUSDT.parquet")
    ids = {"SYNYUSDT": 0}

    build_matrix(TF, 24, ["SYNYUSDT"], ids, klines_root=root, out_root=tmp_path / "m")
    before = load_matrix(matrix_dir(TF, 24, tmp_path / "m") / VECTORS_FILE).shape[0]

    assert update_matrix(TF, 24, ["SYNYUSDT"], ids, klines_root=root, out_root=tmp_path / "m") == 0
    assert load_matrix(matrix_dir(TF, 24, tmp_path / "m") / VECTORS_FILE).shape[0] == before


def test_last_end_idx():
    meta = np.zeros(5, dtype=META_DTYPE)
    meta["symbol_id"] = [0, 0, 1, 1, 1]
    meta["end_idx"] = [10, 40, 7, 99, 55]
    assert last_end_idx(meta) == {0: 40, 1: 99}
