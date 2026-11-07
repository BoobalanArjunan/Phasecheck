# Real-data check (do this before trusting phasecheck)

phasecheck has only been tested on **generated stereo audio with a known channel relationship**. Real recordings have wide
stereo, spaced microphones, reverb and odd mastering. Nothing about real-data accuracy is claimed until this check is run.

Read `docs/EVALUATION_PLAN.md` first. It fixes the pass criteria and the thresholds before the run.

## What you need
A folder of real stereo audio. Check the dataset licence before using it. Good choice: MUSDB18-HQ (stereo stems and mixtures).
Keep the audio on your machine; do not publish it.

## Run it
```bash
pip install -e ".[dev]"
python scripts/real_data_check.py --audio-dir ~/musdb18hq/test --out real_check
```
Send me `real_check/results.md` and `real_check/missed_planted.csv`. It has two parts:
1. **The files as they are:** how many PASS, WARN, FAIL, REVIEW, SKIP, the spread of the downmix loss and the correlation, and the
   flagged files. Make the mono mix of a few flagged files (for example in Audacity: Tracks > Mix > Mix Stereo Down to Mono) and
   say whether it sounds quieter or thinner.
2. **Planted problems:** inverted right channel, an inverted 2-8 kHz band, and dual mono. The truth is known, so this shows
   how many phasecheck catches.

Your original files are never modified. Copies go under `real_check/planted/` and can be deleted afterwards.
