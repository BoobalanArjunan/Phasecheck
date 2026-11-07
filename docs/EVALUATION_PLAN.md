# PhaseCheck evaluation plan (fixed BEFORE any real-data run)

Write date: 7 Nov 2026. This file, the code and the thresholds are committed and tagged `eval-spec-pc-v1` before
`scripts/real_data_check.py` is run on real audio. Nothing below changes after the run.

## Frozen thresholds (provisional, set on generated audio only)
| Setting | Value |
|---|---|
| WARN: full-band downmix loss at or above | 6 dB |
| FAIL: full-band downmix loss at or above | 10 dB |
| WARN: one band (holding at least 1% of the energy, -20 dB) at or above | 10 dB |
| Bands | 20-250 Hz, 250 Hz-2 kHz, 2-8 kHz, above 8 kHz |
| Loud-frame floor | frames within 30 dB of the loudest |
| "Identical channels" | loss under 0.2 dB, correlation above 0.9999, levels within 0.5 dB |

## Data
MUSDB18-HQ (stereo music; stems and mixtures), kept on the local machine, never published; check the dataset licence.
Up to 200 files, chosen with `--seed 0`. Report anything else used (another stereo set may be added, with its licence).

## Pass criteria
1. **Planted A** (right channel inverted): at least 99% of copies are FAIL.
2. **Planted B** (2-8 kHz band inverted, only for files whose 2-8 kHz band was strongly correlated): at least 90% are WARN or FAIL.
3. **Planted C** (dual mono): at least 99% are recognised as identical channels and PASS.
4. **Originals:** report the share flagged (WARN or FAIL) with its range. Every flagged original is judged by listening to its
   mono mix (does it get quieter or thinner?), and the judgement is reported. A flagged original is a genuine finding if the mono mix
   audibly suffers, and a false alarm if it does not. If more than 2% of the stereo originals are flagged, say so plainly.

## What this cannot show
- The files are stems and mixtures of the same songs, so they are not independent samples. The ranges are optimistic.
- Planted problems are made by one method. Real polarity mistakes may differ.
- It says nothing about how often the problem occurs in other datasets.

## Decision
- Criteria 1-3 pass: publish as an alpha pre-release with the table and these limits. Criterion 4 is reported either way.
- Any of 1-3 fails: do not publish. Look at `missed_planted.csv`, make at most one fix, and test that fix on a different stereo dataset
  or different songs before releasing. No threshold is changed to improve the numbers on the same files.
- One run on this data. A result is not repeated after changes.
