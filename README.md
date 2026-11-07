# phasecheck (alpha, not released)

Finds stereo files that lose level or sound thin when played in mono, usually because one channel is polarity-inverted
or partly out of phase with the other.

> **Status: 0.1.0a1, tested on generated stereo audio only.** The thresholds are provisional. Nothing is claimed about real
> recordings until `scripts/real_data_check.py` has been run (see `docs/EVALUATION_PLAN.md`, fixed before the run).

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

## Limits (please read)
- **Generated audio only so far.** Real stereo (wide, spaced microphones, reverb) may behave differently. Wide stereo can have low
  correlation without any mono problem; that is why the verdict uses the downmix loss, not the correlation.
- **Swapped left and right channels cannot be detected.** Nothing in the audio says which side is which.
- **A passage that cancels is averaged into the whole file.** A short out-of-phase section in a long song may not reach WARN.
- A flagged file is not proof of a mistake: some recordings really cancel in mono. Listen to the mono mix.
- Only the middle 2 minutes of a long file are judged.
- Thresholds (6 / 10 dB) are provisional and were chosen on generated audio.

## Tests
`pytest -q` (57 tests). The checker itself was also tested by planting 21 deliberate bugs in the code and confirming
the tests catch them (the two that survived the first round now have their own tests).

MIT licence.
