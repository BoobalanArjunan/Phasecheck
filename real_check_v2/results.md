# phasecheck real-data check

Files used: 200 from `/Users/mymac/musdb18hq/train`

## 1. The files as they are

PASS 199, WARN 1, FAIL 0, REVIEW 0, SKIP 0 (not two-channel), ERROR 0

| measure (stereo files) | min | median | 90th pct | 99th pct | max |
|---|---|---|---|---|---|
| downmix loss (dB) | -0.0 | 0.2 | 1.1 | 2.6 | 9.7 |
| correlation | -0.79 | 0.89 | 1.00 | 1.00 | 1.00 |

Dual mono (identical channels): 19 of 200. Flagged (WARN or FAIL): 1/200 = 0% (0-3%).

Flagged files. A flagged original is not automatically a false alarm: make the mono mix and listen.

- WARN Giselle - Moss/vocals.wav: a mono mix is 9.7 dB quieter than the channels (correlation -0.79); partly out of phase

## 2. Planted problems (known truth)

| copy | files tried | detected | median downmix loss |
|---|---|---|---|
| A. right channel inverted (expect FAIL) | 180 | 128/180 = 71% (64-77%) | 12.1 dB |
| B. 2-8 kHz band inverted (expect WARN or FAIL) | 71 | 62/71 = 87% (78-93%) | 0.4 dB |
| C. dual mono (expect recognised, PASS) | 180 | 180/180 = 100% (98-100%) | 0.0 dB |

### A, split by how correlated the channels were before inversion

Inverting a channel pair with correlation c loses about -10*log10((1-c)/2) dB, so FAIL (10 dB) needs c of about 0.8 or more
and WARN (6 dB) needs c of about 0.5 or more. Below that an inversion cannot be seen by downmix loss.

| copies | n | WARN or FAIL | FAIL only |
|---|---|---|---|
| all | 180 | 169/180 = 94% (89-97%) | 128/180 = 71% (64-77%) |
| original correlation >= 0.5 | 169 | 168/169 = 99% (97-100%) | 128/169 = 76% (69-82%) |
| original correlation < 0.5 | 11 | 1/11 = 9% (2-38%) | 0/11 = 0% (0-26%) |
| mixtures only | 39 | 39/39 = 100% (91-100%) | 28/39 = 72% (56-83%) |
| stems only | 141 | 130/141 = 92% (87-96%) | 100/141 = 71% (63-78%) |

Ranges are 95% Wilson intervals. They assume independent files; stems and mixtures of the same song are not independent,
so the real uncertainty is wider.
Missed copies are listed in `missed_planted.csv` (61 rows).
