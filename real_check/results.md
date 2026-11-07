# phasecheck real-data check

Files used: 200 from `/Users/mymac/musdb18hq/test`

## 1. The files as they are

PASS 199, WARN 0, FAIL 0, REVIEW 1, SKIP 0 (not two-channel), ERROR 0

| measure (stereo files) | min | median | 90th pct | 99th pct | max |
|---|---|---|---|---|---|
| downmix loss (dB) | -0.0 | 0.4 | 1.2 | 2.9 | 4.2 |
| correlation | -0.24 | 0.83 | 0.98 | 1.00 | 1.00 |

Dual mono (identical channels): 5 of 199. Flagged (WARN or FAIL): 0/199 = 0% (0-2%).

## 2. Planted problems (known truth)

| copy | files tried | detected | median downmix loss |
|---|---|---|---|
| A. right channel inverted (expect FAIL) | 194 | 104/194 = 54% (47-60%) | 10.4 dB |
| B. 2-8 kHz band inverted (expect WARN or FAIL) | 38 | 31/38 = 82% (67-91%) | 0.5 dB |
| C. dual mono (expect recognised, PASS) | 194 | 194/194 = 100% (98-100%) | 0.0 dB |

Ranges are 95% Wilson intervals. They assume independent files; stems and mixtures of the same song are not independent,
so the real uncertainty is wider.
Missed copies are listed in `missed_planted.csv` (97 rows).
