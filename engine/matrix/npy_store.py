""".npy dosyalarına akış hâlinde yazma ve sona ekleme.

Neden bu modül var: matris inşasında tüm pencereleri (~12M × 32 float32) aynı
anda RAM'e almak gereksizdir — asıl kazanç zaten bitişik disk düzeninden gelir
(K-01). Bu yüzden satırlar chunk'lar hâlinde ham bir geçici dosyaya yazılır ve
en sonda başına geçerli bir ``.npy`` başlığı konur. Ortaya çıkan dosya
``np.load(..., mmap_mode="r")`` ile sayfalanarak okunabilir (§4.3).

``append_rows`` artımlı güncelleme içindir (§4.4): başlıktaki ``shape`` alanı
yerinde güncellenir ve yeni satırlar dosyanın sonuna eklenir — 1,5 GB'lık
matrisi her cron çalıştırmasında yeniden yazmamak için.
"""

from __future__ import annotations

import io
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np
from numpy.lib import format as npformat

_COPY_BUF = 8 << 20  # 8 MB


class ChunkedNpyWriter:
    """Satırları parça parça yazar, kapanışta atomik olarak .npy üretir."""

    def __init__(self, path: Path, dtype: np.dtype, row_shape: tuple[int, ...] = ()) -> None:
        self.path = Path(path)
        self.dtype = np.dtype(dtype)
        self.row_shape = tuple(row_shape)
        self.n_rows = 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".raw.tmp")
        os.close(fd)
        self._raw_path = Path(tmp)
        self._raw = open(self._raw_path, "wb")

    def append(self, rows: np.ndarray) -> None:
        if rows.size == 0:
            return
        arr = np.ascontiguousarray(rows, dtype=self.dtype)
        expected = (arr.shape[0],) + self.row_shape
        if arr.shape != expected:
            raise ValueError(f"beklenen satır şekli {self.row_shape}, gelen {arr.shape[1:]}")
        self._raw.write(arr.tobytes())
        self.n_rows += arr.shape[0]

    def close(self) -> Path:
        self._raw.close()
        shape = (self.n_rows,) + self.row_shape

        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), suffix=".npy.tmp")
        os.close(fd)
        tmp_path = Path(tmp)
        try:
            with open(tmp_path, "wb") as out:
                _write_header(out, self.dtype, shape)
                with open(self._raw_path, "rb") as src:
                    shutil.copyfileobj(src, out, _COPY_BUF)
            os.replace(tmp_path, self.path)
        finally:
            if tmp_path.exists():
                tmp_path.unlink()
            if self._raw_path.exists():
                self._raw_path.unlink()
        return self.path

    def abort(self) -> None:
        try:
            self._raw.close()
        finally:
            if self._raw_path.exists():
                self._raw_path.unlink()

    def __enter__(self) -> "ChunkedNpyWriter":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self.close()
        else:
            self.abort()


def _write_header(fobj, dtype: np.dtype, shape: tuple[int, ...]) -> None:
    header = {
        "descr": npformat.dtype_to_descr(dtype),
        "fortran_order": False,
        "shape": shape,
    }
    # 2.0: başlık uzunluğu 4 bayt — büyüyen shape dizesi için bol yer bırakır.
    npformat.write_array_header_2_0(fobj, header)


def read_header(path: Path) -> tuple[tuple[int, ...], np.dtype, int]:
    """(shape, dtype, veri_ofseti) döndürür."""
    with open(path, "rb") as f:
        major, _minor = npformat.read_magic(f)
        reader = npformat.read_array_header_1_0 if major == 1 else npformat.read_array_header_2_0
        shape, fortran, dtype = reader(f)
        if fortran:
            raise ValueError("fortran_order .npy desteklenmiyor")
        return shape, dtype, f.tell()


def append_rows(path: Path, rows: np.ndarray) -> int:
    """Var olan .npy'nin sonuna satır ekler; yeni toplam satır sayısını döner.

    Dosya yoksa sıfırdan oluşturulur. Başlıktaki ``shape`` yerinde güncellenir;
    yeni başlık eskisine sığmazsa (uzunluk değişirse) dosya güvenli biçimde
    yeniden yazılır.
    """
    path = Path(path)
    arr = np.ascontiguousarray(rows)

    if not path.exists():
        writer = ChunkedNpyWriter(path, arr.dtype, arr.shape[1:])
        writer.append(arr)
        writer.close()
        return arr.shape[0]

    shape, dtype, offset = read_header(path)
    if dtype != arr.dtype:
        raise ValueError(f"dtype uyuşmuyor: {dtype} != {arr.dtype}")
    if shape[1:] != arr.shape[1:]:
        raise ValueError(f"satır şekli uyuşmuyor: {shape[1:]} != {arr.shape[1:]}")

    new_shape = (shape[0] + arr.shape[0],) + shape[1:]

    buf = io.BytesIO()
    _write_header(buf, dtype, new_shape)
    new_header = buf.getvalue()

    if len(new_header) == offset:
        # Sıcak yol: başlık aynı uzunlukta → yerinde güncelle, veriyi sona ekle.
        with open(path, "r+b") as f:
            f.seek(0, os.SEEK_END)
            f.write(arr.tobytes())
            f.seek(0)
            f.write(new_header)
        return new_shape[0]

    # Nadir durum: başlık uzunluğu değişti (dolgu sınırı aşıldı) → yeniden yaz.
    old = np.load(path, mmap_mode="r")
    writer = ChunkedNpyWriter(path, dtype, shape[1:])
    try:
        for start in range(0, shape[0], 100_000):
            writer.append(np.asarray(old[start : start + 100_000]))
        writer.append(arr)
    except BaseException:
        writer.abort()
        raise
    finally:
        del old
    writer.close()
    return new_shape[0]


def load_matrix(path: Path, mmap: bool = True) -> np.ndarray:
    """Matrisi memmap ile açar — RAM'e tam yüklenmez (§4.3)."""
    return np.load(path, mmap_mode="r" if mmap else None)
