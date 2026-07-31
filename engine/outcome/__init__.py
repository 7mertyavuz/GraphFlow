"""F4 — Outcome Engine: "Sonra ne oldu?" (K-06, K-12, K-16).

Sinyal satmıyoruz; **ölçülmüş ve dürüstçe raporlanmış geçmiş dağılım**
sunuyoruz. Hiçbir sayı güven aralığı olmadan yayınlanmaz.
"""

from engine.outcome.bars import BarStore
from engine.outcome.metrics import (
    DISCLAIMER,
    OutcomeStats,
    bootstrap_diff_ci,
    bootstrap_mean_ci,
    block_bootstrap_diff_ci,
    bonferroni_level,
    month_of,
    summarize,
    wilson_interval,
)
from engine.outcome.shadow import ShadowPool, sample_shadow
from engine.outcome.triple_barrier import (
    EVENT_DTYPE,
    OUTCOME_NAMES,
    RESULT_DTYPE,
    enforce_forward_separation,
    eligible,
    evaluate,
    evaluate_all_configs,
    theoretical_null,
    time_barrier,
)

__all__ = [
    "BarStore",
    "DISCLAIMER",
    "OutcomeStats",
    "ShadowPool",
    "bootstrap_diff_ci",
    "bootstrap_mean_ci",
    "block_bootstrap_diff_ci",
    "bonferroni_level",
    "month_of",
    "sample_shadow",
    "summarize",
    "wilson_interval",
    "EVENT_DTYPE",
    "RESULT_DTYPE",
    "OUTCOME_NAMES",
    "eligible",
    "enforce_forward_separation",
    "evaluate",
    "evaluate_all_configs",
    "theoretical_null",
    "time_barrier",
]
