"""Null örneklemi — pencere KİMLİĞİYLE çekilir, satır sırasıyla değil.

Arama eşiği null'un derin bir yüzdeliğidir (K-14.3); hangi pencerelerin
çekildiği eşiği belirler. Eskiden çekiliş satır indeksleri üzerindeydi
(``rng.choice(pool)``): havuzdan tek bir sembol düşse bile indeksler kayar
ve örneklemin **tamamı** yeniden karılırdı. Eylül 2026'da evrenden 4 ikiz
sembol düşünce anlamlı hücre kümesi bu yüzden değişti (docs/12).

**Alt-k örneklemesi.** Her pencereye kimliğinden türeyen sabit bir sözde
rastgele anahtar verilir — ``(symbol_id, end_time, uzunluk, tohum)`` →
64 bit. Örneklem, anahtarı en küçük ``k`` penceredir. Anahtarlar düzgün
dağıldığı için bu, yerine koymadan düzgün bir rastgele örneklemdir; ama:

* havuza pencere **eklenince** eski seçimden yalnız, yeni gelenlerin yerini
  aldığı kadarı düşer;
* havuzdan pencere **çıkınca** yalnız çıkanlar gider, gerisi aynen kalır.

Veri tazelemek ya da bir sembolü evrenden çıkarmak null'u yeniden
çekmez; eşik yalnız gerçekten değişen pencereler kadar oynar.
``symbol_id`` asla yeniden numaralandırılmaz (evren dosyası), ``end_time``
barın açılış zamanıdır — ikisi de matris yeniden kurulsa aynı kalır.
"""

from __future__ import annotations

import numpy as np

_M1 = np.uint64(0x9E3779B97F4A7C15)
_M2 = np.uint64(0xBF58476D1CE4E5B9)
_M3 = np.uint64(0x94D049BB133111EB)


def _mix(x: np.ndarray) -> np.ndarray:
    """splitmix64 son adımı — vektörize, taşma bilerek (mod 2⁶⁴)."""
    x = x.copy()
    x ^= x >> np.uint64(30)
    x *= _M2
    x ^= x >> np.uint64(27)
    x *= _M3
    x ^= x >> np.uint64(31)
    return x


def window_keys(
    symbol_id: np.ndarray, end_time: np.ndarray, length: int, seed: int
) -> np.ndarray:
    """Pencere kimliği → sabit 64 bit anahtar (aynı kimlik, aynı anahtar)."""
    with np.errstate(over="ignore"):
        sid = np.asarray(symbol_id).astype(np.uint64)
        t = np.asarray(end_time).astype(np.int64).view(np.uint64)
        base = np.uint64((int(seed) * 1_000_003 + int(length)) & 0xFFFFFFFFFFFFFFFF)
        return _mix(_mix(t ^ (sid * _M1) ^ base) + sid)


def null_sample(
    symbol_id: np.ndarray,
    end_time: np.ndarray,
    mask: np.ndarray | None,
    size: int,
    length: int,
    seed: int,
) -> np.ndarray:
    """Havuzdan (``mask``) anahtarı en küçük ``size`` pencerenin sıralı indeksleri."""
    pool = np.flatnonzero(mask) if mask is not None else np.arange(np.asarray(symbol_id).size)
    if pool.size <= size:
        return pool
    keys = window_keys(np.asarray(symbol_id)[pool], np.asarray(end_time)[pool], length, seed)
    pick = np.argpartition(keys, size - 1)[:size]
    return np.sort(pool[pick])
