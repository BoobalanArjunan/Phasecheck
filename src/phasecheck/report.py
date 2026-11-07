from __future__ import annotations

import csv
import json
from collections import Counter
from typing import List

from . import __version__
from .check import Verdict

EVIDENCE = ("alpha. Tested on generated audio only; not yet measured on real recordings. The 6 dB and 10 dB limits are provisional. "
            "See the README.")
LEVELS = ("PASS", "WARN", "FAIL", "REVIEW", "SKIP", "ERROR")


def summary_line(vs: List[Verdict]) -> str:
    c = Counter(v.level for v in vs)
    return (f"{len(vs)} files: {c['PASS']} pass, {c['WARN']} warn (partly out of phase), {c['FAIL']} fail (cancel in a mono mix), "
            f"{c['REVIEW']} need a look, {c['SKIP']} skipped (not two-channel), {c['ERROR']} unreadable")


def text(vs: List[Verdict], show_pass: bool = False) -> str:
    L = []
    for v in vs:
        if v.level in ("PASS", "SKIP") and not show_pass:
            continue
        L.append(f"{v.level:6} {v.file}  {v.sample_rate or '-'} Hz  {v.reason}")
    return "\n".join(L + ([""] if L else []) + [summary_line(vs)])


def _row(v: Verdict) -> dict:
    return {"file": v.file, "sample_rate": v.sample_rate, "channels": v.channels, "verdict": v.level, "reason": v.reason,
            "downmix_loss_db": v.loss_db, "correlation": v.correlation, "worst_band": v.worst_band,
            "worst_band_loss_db": v.worst_band_loss_db, "dual_mono": v.dual_mono, "seconds_analysed": round(v.seconds, 1)}


def write_csv(path, vs: List[Verdict]) -> None:
    rows = [_row(v) for v in vs]
    cols = list(_row(Verdict("", None, 0, "OK", "")).keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            w.writerow(["" if r[c] is None else r[c] for c in cols])


def to_dict(vs: List[Verdict]) -> dict:
    c = Counter(v.level for v in vs)
    return {"tool": "phasecheck", "version": __version__, "evidence": EVIDENCE,
            "summary": {"files": len(vs), **{k: c[k] for k in LEVELS}}, "files": [_row(v) for v in vs]}


def to_json(vs: List[Verdict]) -> str:
    return json.dumps(to_dict(vs), indent=2)
