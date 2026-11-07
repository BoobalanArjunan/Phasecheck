"""Real-data check for phasecheck. Needs a folder of REAL stereo audio (for example MUSDB18-HQ, or music you may use).

    python scripts/real_data_check.py --audio-dir ~/musdb18hq/test --out real_check

Read docs/EVALUATION_PLAN.md first: the limits and the pass criteria are fixed there BEFORE this is run.

It answers:
  1. WHAT PHASECHECK SAYS ABOUT YOUR FILES AS THEY ARE: PASS / WARN / FAIL / REVIEW / SKIP counts, the spread of the
     downmix loss and of the left-right correlation, and the flagged files. A flagged original is NOT automatically a false
     alarm: some recordings really do cancel in mono. Listen to the mono mix of a few flagged files and decide.
  2. PLANTED PROBLEMS (known truth), made from stereo files that passed and are not dual-mono:
       A. the right channel inverted                       -> expected FAIL
       B. the right channel inverted in the 2-8 kHz band   -> expected WARN or FAIL (only for files whose 2-8 kHz band was
          strongly correlated, because inverting an unrelated band does not change what a mono mix loses)
       C. both channels replaced by their average (dual mono) -> expected: recognised as identical channels
Your original files are never changed. Copies go under <out>/planted/. Writes <out>/results.md, <out>/verdicts.csv and
<out>/missed_planted.csv. Long files are judged on their middle 2 minutes (copies are made from that part).
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
from collections import Counter
from math import sqrt
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfiltfilt

from phasecheck.analysis import analyse, load_stereo
from phasecheck.check import check_file
from phasecheck.cli import find_audio
from phasecheck.report import write_csv

BAND = (2000.0, 8000.0)
CORRELATED_BAND_DB = 0.5      # a band whose downmix loss is at most this was strongly correlated


def wilson(k: int, n: int, z: float = 1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    a = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (c - a) / d, (c + a) / d


def rate(k: int, n: int) -> str:
    if n == 0:
        return "n/a"
    lo, hi = wilson(k, n)
    return f"{k}/{n} = {100 * k / n:.0f}% ({100 * lo:.0f}-{100 * hi:.0f}%)"


def write_pcm16(path: Path, x: np.ndarray, sr: int) -> None:
    sf.write(str(path), np.clip(x, -1, 1), sr, subtype="PCM_16")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audio-dir", type=Path, required=True)
    ap.add_argument("--limit", type=int, default=200, help="files to use (default 200)")
    ap.add_argument("--out", type=Path, default=Path("real_check"))
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()
    files = find_audio(a.audio_dir)
    if len(files) < 10:
        sys.exit(f"only {len(files)} audio files found; need at least 10")
    rng = random.Random(a.seed)
    rng.shuffle(files)
    files = files[: a.limit]
    a.out.mkdir(parents=True, exist_ok=True)
    pl = a.out / "planted"
    pl.mkdir(exist_ok=True)

    base = []
    for i, f in enumerate(files, 1):
        v = check_file(f)
        v.file = str(f.relative_to(a.audio_dir)) if f.is_relative_to(a.audio_dir) else f.name
        base.append(v)
        if i % 25 == 0:
            print(f"  originals {i}/{len(files)}", flush=True)
    write_csv(a.out / "verdicts.csv", base)
    c = Counter(v.level for v in base)
    stereo = [v for v in base if v.level in ("PASS", "WARN", "FAIL")]
    losses = np.array([v.loss_db for v in stereo if v.loss_db is not None])
    corrs = np.array([v.correlation for v in stereo if v.correlation is not None])
    dual = sum(v.dual_mono for v in stereo)

    lines = ["# phasecheck real-data check", "", f"Files used: {len(files)} from `{a.audio_dir}`", "",
             "## 1. The files as they are", "",
             f"PASS {c['PASS']}, WARN {c['WARN']}, FAIL {c['FAIL']}, REVIEW {c['REVIEW']}, SKIP {c['SKIP']} (not two-channel), ERROR {c['ERROR']}", ""]
    if len(losses):
        q = lambda arr, p: float(np.percentile(arr, p))
        lines += ["| measure (stereo files) | min | median | 90th pct | 99th pct | max |", "|---|---|---|---|---|---|",
                  f"| downmix loss (dB) | {losses.min():.1f} | {q(losses, 50):.1f} | {q(losses, 90):.1f} | {q(losses, 99):.1f} | {losses.max():.1f} |",
                  f"| correlation | {corrs.min():.2f} | {q(corrs, 50):.2f} | {q(corrs, 90):.2f} | {q(corrs, 99):.2f} | {corrs.max():.2f} |", "",
                  f"Dual mono (identical channels): {dual} of {len(stereo)}. Flagged (WARN or FAIL): {rate(c['WARN'] + c['FAIL'], len(stereo))}."]
    flagged = [v for v in base if v.level in ("WARN", "FAIL")][:20]
    if flagged:
        lines += ["", "Flagged files. A flagged original is not automatically a false alarm: make the mono mix and listen.", ""]
        lines += [f"- {v.level} {v.file}: {v.reason}" for v in flagged]

    # ---- planted problems
    lines += ["", "## 2. Planted problems (known truth)", "",
              "| copy | files tried | detected | median downmix loss |", "|---|---|---|---|"]
    passed = [(f, v) for f, v in zip(files, base) if v.level == "PASS" and not v.dual_mono and v.channels == 2]
    tried = {"A": 0, "B": 0, "C": 0}
    hit = {"A": 0, "B": 0, "C": 0}
    losses_p = {"A": [], "B": [], "C": []}
    missed = []
    a_rows = []   # (original correlation, is_mixture, verdict of the inverted copy)
    for f, v in passed:
        x, sr = load_stereo(f)
        L, R = x[:, 0], x[:, 1]
        res0 = analyse(L, R, sr)
        if res0 is None:
            continue
        stem = f.stem
        # A: right inverted
        dst = pl / f"{stem}__A_inverted.wav"
        write_pcm16(dst, np.stack([L, -R], axis=1), sr)
        pv = check_file(dst)
        tried["A"] += 1
        a_rows.append((v.correlation, f.stem == "mixture", pv.level))
        ok = pv.level == "FAIL"
        hit["A"] += ok
        losses_p["A"].append(pv.loss_db)
        if not ok:
            missed.append((dst.name, "A", pv.level, pv.loss_db, pv.worst_band, pv.worst_band_loss_db))
        # B: right inverted in 2-8 kHz (only where that band was strongly correlated and exists)
        b0 = res0.band_loss_db.get("2-8 kHz")
        if b0 is not None and b0 <= CORRELATED_BAND_DB and sr / 2 > BAND[1] * 1.1:
            sos = butter(4, list(BAND), btype="bandpass", fs=sr, output="sos")
            Rb = R - 2 * sosfiltfilt(sos, R)
            dst = pl / f"{stem}__B_band.wav"
            write_pcm16(dst, np.stack([L, Rb], axis=1), sr)
            pv = check_file(dst)
            tried["B"] += 1
            ok = pv.level in ("WARN", "FAIL")
            hit["B"] += ok
            losses_p["B"].append(pv.loss_db)
            if not ok:
                missed.append((dst.name, "B", pv.level, pv.loss_db, pv.worst_band, pv.worst_band_loss_db))
        # C: dual mono
        dst = pl / f"{stem}__C_dualmono.wav"
        m = (L + R) / 2
        write_pcm16(dst, np.stack([m, m], axis=1), sr)
        pv = check_file(dst)
        tried["C"] += 1
        ok = pv.dual_mono and pv.level == "PASS"
        hit["C"] += ok
        losses_p["C"].append(pv.loss_db)
        if not ok:
            missed.append((dst.name, "C", pv.level, pv.loss_db, pv.worst_band, pv.worst_band_loss_db))
    names = {"A": "A. right channel inverted (expect FAIL)", "B": "B. 2-8 kHz band inverted (expect WARN or FAIL)",
             "C": "C. dual mono (expect recognised, PASS)"}
    for k in "ABC":
        med = f"{float(np.median([x for x in losses_p[k] if x is not None])):.1f} dB" if losses_p[k] else "n/a"
        lines.append(f"| {names[k]} | {tried[k]} | {rate(hit[k], tried[k])} | {med} |")
    if a_rows:
        lines += ["", "### A, split by how correlated the channels were before inversion", "",
                  "Inverting a channel pair with correlation c loses about -10*log10((1-c)/2) dB, so FAIL (10 dB) needs c of about 0.8 or more",
                  "and WARN (6 dB) needs c of about 0.5 or more. Below that an inversion cannot be seen by downmix loss.", "",
                  "| copies | n | WARN or FAIL | FAIL only |", "|---|---|---|---|"]
        groups = [("all", lambda c, m: True), ("original correlation >= 0.5", lambda c, m: c is not None and c >= 0.5),
                  ("original correlation < 0.5", lambda c, m: c is None or c < 0.5),
                  ("mixtures only", lambda c, m: m), ("stems only", lambda c, m: not m)]
        for name, sel in groups:
            sub = [lv for c, m, lv in a_rows if sel(c, m)]
            fl = sum(lv in ("WARN", "FAIL") for lv in sub)
            fa = sum(lv == "FAIL" for lv in sub)
            lines.append(f"| {name} | {len(sub)} | {rate(fl, len(sub))} | {rate(fa, len(sub))} |")
    lines += ["", "Ranges are 95% Wilson intervals. They assume independent files; stems and mixtures of the same song are not independent,",
              "so the real uncertainty is wider.", f"Missed copies are listed in `missed_planted.csv` ({len(missed)} rows)."]
    with open(a.out / "missed_planted.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["copy", "kind", "verdict", "downmix_loss_db", "worst_band", "worst_band_loss_db"])
        w.writerows(missed)
    (a.out / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
