# phasecheck (alpha)

Finds stereo files that lose level or sound thin when played in mono, usually because one channel is polarity-inverted
or partly out of phase with the other.

> **Status: 0.1.0a1 alpha.** Checked on real stereo music (MUSDB18-HQ) with planted problems and untouched originals; results below.
> The thresholds (6 dB and 10 dB) were set on generated audio and are unchanged. They are provisional.

```bash
pip install -e ".[dev]"
phasecheck check my_songs/ --out report.csv
phasecheck check song.wav --json
```

## What it measures
Over the loud parts of the file (frames within 30 dB of the loudest, middle 2 minutes of long files):

- **Downmix loss (dB):** how much quieter the mono sum is than the average of the two channels. 0 dB means identical channels,
  about 3 dB means unrelated channels, large values mean the channels cancel.
- **Correlation** between the channels (-1 to 1), and the loss in four bands (20-250 Hz, 250 Hz-2 kHz, 2-8 kHz, above 8 kHz;
  a band counts only if it holds at least 1% of the energy).
- **Dual mono** (identical channels) and a **silent channel**.

| Verdict | When |
|---|---|
| FAIL | full-band loss of 10 dB or more |
| WARN | loss of 6 dB or more, or one band at 10 dB or more |
| REVIEW | one channel is silent, or too little audio to judge |
| SKIP | mono, or more than two channels |
| PASS | otherwise (identical channels are noted) |

Exit code 1 only when a FAIL exists; 2 for a bad path or settings.

## Real-data results (MUSDB18-HQ, 200 files per run)
Two runs on different songs: `test` split first, then `train`. The plan for each was fixed and tagged before the run
(`eval-spec-pc-v1`, `eval-spec-pc-v2`; see `docs/`). **The first run failed its plan** (inverted-channel copies were expected
to reach FAIL in 99% of cases; they reached 54%). The criterion was wrong, because how much an inversion loses depends on how
correlated the channels were; the v2 plan corrected it and was run once on new songs, with no code or threshold change.

| `train` split (v2 run) | result |
|---|---|
| Untouched originals flagged WARN or FAIL | 1 of 200 (range 0-3%) |
| Right channel inverted, original correlation 0.5 or more: flagged WARN or FAIL | 168 of 169 = 99% (97-100%) |
| Same copies reaching FAIL (10 dB or more) | 128 of 169 = 76% |
| Same inversion, original correlation under 0.5 | 1 of 11 flagged: **not reliably detectable** |
| Right channel inverted, all copies | 169 of 180 = 94% flagged, 128 of 180 = 71% FAIL |
| Only full mixtures | 39 of 39 flagged, 28 of 39 FAIL |
| 2-8 kHz band inverted | 62 of 71 = 87% (78-93%) |
| Dual mono recognised | 180 of 180 |

On the first (`test`) run: 0 of 199 originals flagged; all-copies detection 180 of 194 = 93% flagged, 104 of 194 = 54% FAIL; band 31 of 38 = 82%.

The one flagged original (train: a vocals stem, correlation -0.79) measures 9.7 dB quieter in a mono mix (bass about 19.5 dB quieter); not yet checked by ear.

Ranges are 95% Wilson intervals. Stems and mixtures of the same song are not independent, so the real uncertainty is wider.
The planted copies are made by one method; real polarity mistakes may differ. Only MUSDB18-HQ was used.

## Limits (please read)
- **One dataset.** Tested on MUSDB18-HQ only (western-style studio stems and mixtures). Field recordings, spaced microphones and other styles may behave differently. Wide stereo can have low
  correlation without any mono problem; that is why the verdict uses the downmix loss, not the correlation.
- **Swapped left and right channels cannot be detected.** Nothing in the audio says which side is which.
- **A passage that cancels is averaged into the whole file.** A short out-of-phase section in a long song may not reach WARN.
- A flagged file is not proof of a mistake: some recordings really cancel in mono. Listen to the mono mix.
- Only the middle 2 minutes of a long file are judged.
- Inverted channels whose correlation was under about 0.5 are not reliably caught: the mono mix hardly changes.
- An inverted mixture usually shows as WARN, not FAIL (about 72% of inverted mixtures reached FAIL).
- Thresholds (6 / 10 dB) are provisional and were chosen on generated audio.

## Tests
`pytest -q` (57 tests). The checker itself was also tested by planting 21 deliberate bugs in the code and confirming
the tests catch them (the two that survived the first round now have their own tests).

MIT licence.
