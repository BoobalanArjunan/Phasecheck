# Changelog

## 0.1.0
- First release: downmix loss (full band and four bands), left-right correlation, dual-mono and silent-channel detection.
- Verdicts PASS / WARN / FAIL / REVIEW / SKIP / ERROR; `--json`, `--out` CSV, `--jobs`.
- 57 tests, plus a planted-bug check of the checker itself. Real-data check on MUSDB18-HQ (two runs on different songs; see README and docs/). The first run missed its plan, the corrected v2 plan passed.
