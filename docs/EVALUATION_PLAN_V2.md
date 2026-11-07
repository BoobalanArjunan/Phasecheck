# PhaseCheck evaluation plan v2 (fixed BEFORE the run on new songs)

Date: 7 Nov 2026. Commit this file and tag `eval-spec-pc-v2` before running anything.

## What happened in v1 (kept on record, not changed)
Tag `eval-spec-pc-v1`, MUSDB18-HQ `test` split, 200 files. Originals: 199 PASS, 1 REVIEW, none flagged (worst downmix loss 4.2 dB).
Planted: A (right channel inverted, expected FAIL) 104/194 = 54%; B (2-8 kHz inverted) 31/38 = 82%; C (dual mono) 194/194.
**v1 failed criteria 1 and 2 as written.** That result stands.

## Why criterion 1 was wrong
Inverting one channel of a pair with correlation c loses about -10*log10((1-c)/2) dB. FAIL (10 dB) therefore needs c of about 0.8,
WARN (6 dB) needs about 0.5. Real mixtures usually sit at 0.6-0.8, so an inverted mixture normally shows as WARN, not FAIL, and
an inversion of channels with c below about 0.5 cannot be seen by downmix loss at all. I (the author) wrote "expect FAIL for 99%"
without checking this. The exploratory split of the v1 files (not evidence): 180/194 flagged WARN or FAIL, and 175/175 among
copies whose original correlation was 0.5 or more. The 0.5 cut-off and the "WARN or FAIL" definition come from those files,
so the check below is on different songs.

## Changes from v1 (all disclosed)
- Detection of planted A means WARN or FAIL, counted only for copies whose original correlation is 0.5 or more.
- B is reported with its range, not claimed (82% in v1, no physical reason found yet for the misses).
- **No code change. No threshold change.** 6 dB, 10 dB and the band rules stay as frozen in v1.

## Data
MUSDB18-HQ `train` split (mixtures and stems), not used in v1. Up to 200 files, `--seed 0`. Local only, never published.

## Pass criteria
1. **A, original correlation >= 0.5:** at least 95% flagged WARN or FAIL, and the 95% Wilson lower bound at least 90%.
2. **C (dual mono):** at least 99% recognised as identical channels and PASS (same as v1).
3. **Originals:** at most 2% of stereo originals flagged WARN or FAIL. Each flagged original is judged by listening to its mono mix.
4. **Reported, not claimed:** A for all copies; A FAIL-only; A for correlation below 0.5; A for mixtures and for stems; B; the spread of loss and correlation.

## Limits to keep in the README whatever happens
- Inverted channels whose correlation was below about 0.5 are not reliably caught.
- An inverted mixture usually shows as WARN, not FAIL.
- Swapped left and right cannot be detected. Stems and mixtures of the same song are not independent, so the ranges are optimistic.

## Decision
- 1-3 pass: publish as an alpha pre-release with the full table and these limits.
- Any fails: do not publish; no tuning on this data. One run only.
