# Contributing to GraphFlow

[English](CONTRIBUTING.md) · [Türkçe](CONTRIBUTING.tr.md)

Thanks for your interest. GraphFlow's value is not the search engine alone — it is that **every number it shows has been measured and can be trusted**. Most of the rules below exist because breaking them once produced a convincing, wrong result. Please read them before opening a pull request.

## Before changing a design decision

Architectural decisions are recorded in [docs/00-tasarim-kararlari.md](docs/00-tasarim-kararlari.md) as `K-01 … K-21`, each with the alternatives that were considered and rejected. If you think a decision should change, read its section first — the alternative you have in mind was very likely evaluated already. If it still should change, open an issue with a measurement.

## Deliberately rejected — please don't reintroduce

These are not missing features; they were chosen against, with reasons.

- **Kafka, Rust/Go workers, TimescaleDB/InfluxDB, WebSocket streaming.** The engine is Python + NumPy; the bottleneck is data layout, not language (K-01).
- **An `if-else` rule engine per formation.** Every formation is a 32-point canonical vector through the same pipeline (K-04). The structural and trend-line filters derive their rule *from the query*, never from per-formation code.
- **Removing the stability gates.** The structural filter runs only when the query's peak/trough reading is stable (K-20), the trend-line filter only when its slope reading is stable (K-21). Without the gates, ground-truth accuracy drops from 70% to 59%; an ungated trend-line filter would gamble on head-and-shoulders queries (stability 41%).
- **Stacking the two filters.** When the trend-line filter applies, the structural filter steps aside: a wedge touches its lines two *or* three times, and demanding an exact peak count removed a third of real falling wedges (recall 67% vs 96%).
- **Sub-stride alignment refinement** (K-19) and **the central-difference derivative** (K-11 addendum) — both implemented, measured, and not connected. Neither improved accuracy.
- **Changing the Stage 2 metric without re-calibrating.** Thresholds are per metric (`TOLERANCE_THRESHOLDS_BY_METRIC`); switching metrics with the wrong thresholds silently empties the results.
- **Single-pass NMS.** Pre-NMS (IoU 0.70) and post-NMS (IoU 0.50, max 3 per symbol) are both required (K-09).
- **Fixed-percentage barriers** (e.g. 5% TP / 3% SL). Barriers are ATR-based; fixed percentages measure volatility, not the pattern (K-16).
- **A fixed-dollar liquidity threshold** in backtests. Liquidity is the monthly cross-sectional top 40%; a fixed threshold erases 2017–2019 (K-13).
- **An all-history baseline.** Use the time-matched shadow distribution (K-12).
- **Canvas libraries** (Fabric.js, Konva.js) and a **"% similarity" slider.** Plain canvas; tolerance is *Strict / Medium / Flexible* because DTW distance is not a percentage (K-17).
- **Separate engines for Radar and Backtest.** One `SearchEngine`, a `mode` parameter (K-15).

## Correctness rules

### Statistics

- **No lookahead.** ATR and every feature use bars up to `t₀` only. One forward-looking line invalidates the whole statistics layer; each such rule has a unit test.
- **No partial candles.** The forming (unclosed) bar is dropped in both modes (K-05, K-15).
- **Independent N.** Only post-NMS, non-overlapping events enter statistics. Counting overlapping windows inflates `n` and fakes narrow intervals (K-09, K-12).
- **The sample is not truncated by a display constant.** `SEARCH_CACHE_MATCHES` is the statistics sample limit, not a page size; truncation keeps the *best* matches and inflates expectancy. A sentinel test guards this.
- **Same-bar TP and SL → assume SL hit first.**
- **Transaction-cost floor.** Windows with `1×ATR / close < 1%` are excluded (K-16.7).
- **Price continuity.** A bar-to-bar ratio above 10× is a redenomination or ticker reuse, not a price move; leveraged tokens are excluded from the universe.
- **Confidence intervals are month-block bootstrapped.** i.i.d. bootstrap treats 20 shadows from the same month as independent and understated uncertainty by ~29% (K-12). Coverage is itself measured (`tools/ci_calibration`): block ~92%, i.i.d. ~80–89% in the real regime — read significance conservatively.
- **Multiple comparisons.** Edge claims are tested with Bonferroni and *all* templates are reported in one table.
- **Replication.** A finding significant on one timeframe is not a finding. Every edge claim must hold on both 1d and 4h — including the proxy (return-matched shadow) test.
- **Borderline findings are fragile.** Adding ten days of data to nine years changed *which* cells passed Bonferroni. Treat a result at the boundary as noise until it replicates.

### Measurement

- **A "harm" finding needs as much power as a "gain" finding.** A difference of 3 out of 12 is noise (standard error ≈ 1.7). Measure with enough samples before changing architecture.
- **Precision clears a filter; recall convicts it.** `tools/formation_audit` only sees what the engine *returned* — it cannot see true patterns a filter removed. Measure every filter's cost with `tools/gt_benchmark`, which reports recall against injected ground truth.
- **Don't measure a filter with its own criterion.** A slope-based filter will always look good on a slope-based audit. Use ground truth.
- **Audit the auditor.** `tools/formation_audit --cross` must report zero off-diagonal accepts; an auditor that says yes to everything reports 100% and measures nothing.
- **Write invariance tests.** Every function that reads a shape needs mirror / flip / scale / level invariance tests. A prominence bug that made shapes and their mirror images read differently (83% of windows) survived in the core for months because no accuracy metric asks "does the same input give the same answer?".
- **Measurement tables go stale with the engine.** Files under `data/f3` carry a behavioral fingerprint of the engine that produced them, and `/api/findings` reports a mismatch. After any engine change, re-run `tools/run_outcomes` (1d and 4h) and `tools/f46_proxy_test` (1d and 4h) — about 4–5 minutes. Never hard-code a selection list (e.g. "templates significant in F4.5"); encode the definition and compute the value.

### Product

- **No bare numbers.** The API returns `StatEnvelope` (value, interval, unit); the UI formats by unit.
- **Expectancy (R) is the headline metric, not win rate** — win rate can be manipulated by widening the stop.
- **No rate without a baseline.** If a shadow distribution is unavailable, show why instead of the number.
- **Warnings travel in the response.** Distinctiveness, data freshness and multiple-comparison warnings are produced by the engine; the UI neither invents nor hides them.
- **Normalization happens on the server only.** The client sends raw drawing points; there must be exactly one normalization.

## Code conventions

- Python 3.11+, `from __future__ import annotations`, full type hints.
- Identifiers in English; docstrings and comments are currently in Turkish — either language is fine for new code, but keep a file consistent.
- A non-trivial block that implements a recorded decision references it: `# K-16.4: time barrier proportional to window length`.
- **No magic numbers.** Constants live in `engine/config.py` with their rationale and measurement.
- **The hot path is vectorized NumPy.** No Python loops over the candidate list; vectorized and scalar implementations are kept equivalent by tests.
- Keep dependencies minimal (`numpy`, `pandas`, `pyarrow`, `fastapi`). Open an issue before adding one.
- `data/` is never committed.

## Tests

```bash
pytest -q
```

Every engine module has tests. In particular: normalization invariance, DDTW must not match a flat line to a bowl, NMS de-duplication, and triple-barrier sanity on random windows (2:1 win rate ≈ 33%, 1:1 ≈ 50%, expectancy ≈ 0R — any deviation means lookahead or bar-ordering bugs). Tests that need the real corpus skip when `data/` is absent.

Frontend:

```bash
cd frontend
npx tsc --noEmit
npx eslint src
```

API types in `frontend/src/types/api.ts` are generated, never edited by hand:

```bash
python -c "import json, engine.api.main; open('frontend/openapi.json','w',encoding='utf-8').write(json.dumps(engine.api.main.app.openapi(), indent=2, ensure_ascii=False))"
cd frontend && npx openapi-typescript openapi.json -o src/types/api.ts
```

## Pull requests

- One logical change per PR, with the measurement that motivates it in the description.
- If your change affects which windows the engine returns, include a `tools/gt_benchmark` comparison (precision **and** recall) and regenerate the findings.
- Negative results are welcome: a measured "this does not help" with its numbers is a contribution — several of the decisions above are exactly that.
