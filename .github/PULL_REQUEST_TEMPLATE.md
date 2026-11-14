## Summary

<!-- Briefly describe what this PR changes and why. -->

## Methodological & Engineering Checklist (`CONTRIBUTING.md`)

- [ ] **No naked statistics:** Every estimated metric (`expectancy`, `win_rate`, `edge`) is wrapped in `StatEnvelope` with a confidence interval, `N`, method, and shadow/null comparison.
- [ ] **No lookahead bias:** Features, ATR, and filters use strictly bars at or before $t_0$ (`end_idx`).
- [ ] **Query-driven search (`K-04`):** No template-specific `if template_id == ...` branches inside `engine/search/`; all constraints are derived from the 32-point query vector.
- [ ] **Symmetry invariance:** Search constraints and penalties (`structural_signature`, `envelope_signature`, `pole_body_signature`, `structural_alignment_penalty`) preserve horizontal mirror (`x[::-1]`) and vertical flip (`-x`) invariance.
- [ ] **Measured before wired (`K-19`/`K-20`):** Any search or filter change has been benchmarked with `python -m tools.gt_benchmark --family all` and `python -m tools.formation_audit --cross`.
- [ ] **Provenance & OpenAPI sync:**
  - If engine behavior (`engine/fingerprint.py`) changed, `data/f3/*.json` tables were regenerated.
  - If API schemas (`engine/api/schemas.py` or `engine/api/main.py`) changed, `make openapi` was run to sync `frontend/openapi.json` and `frontend/src/types/api.ts`.

## Verification

- [ ] `pytest -q` passes
- [ ] `cd frontend && npx tsc --noEmit && npx eslint src && npm run build` passes
