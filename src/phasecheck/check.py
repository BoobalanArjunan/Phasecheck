"""Turn a downmix measurement into a verdict."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .analysis import PhaseResult, analyse, load_stereo

WARN_DB = 6.0        # full-band downmix loss at or above this: WARN (provisional; not yet tuned on real recordings)
FAIL_DB = 10.0       # at or above this: FAIL
BAND_FAIL_DB = 10.0  # one frequency band (holding at least 1% of the energy) at or above this: WARN

OK, LIMITED, FAKE, UNSURE, SKIPPED, ERROR = "OK", "LIMITED", "FAKE", "UNSURE", "SKIPPED", "ERROR"


@dataclass
class Verdict:
    file: str
    sample_rate: Optional[int]
    channels: int
    status: str
    reason: str
    loss_db: Optional[float] = None
    correlation: Optional[float] = None
    worst_band: str = ""
    worst_band_loss_db: Optional[float] = None
    dual_mono: bool = False
    seconds: float = 0.0

    @property
    def level(self) -> str:
        return {OK: "PASS", LIMITED: "WARN", UNSURE: "REVIEW", FAKE: "FAIL", SKIPPED: "SKIP", ERROR: "ERROR"}[self.status]


def judge(res: Optional[PhaseResult], file: str = "", sample_rate: Optional[int] = None, channels: int = 2,
          warn_db: float = WARN_DB, fail_db: float = FAIL_DB) -> Verdict:
    if res is None:
        return Verdict(file, sample_rate, channels, UNSURE, "too short, silent or too few loud parts to measure")
    base = dict(file=file, sample_rate=res.sample_rate, channels=channels, loss_db=round(res.loss_db, 1),
                correlation=round(res.correlation, 3), seconds=res.active_seconds)
    present = {k: v for k, v in res.band_loss_db.items() if v is not None}
    wb, wl = max(present.items(), key=lambda kv: kv[1]) if present else ("", None)
    base.update(worst_band=wb, worst_band_loss_db=None if wl is None else round(wl, 1), dual_mono=res.dual_mono)
    if res.silent_channel is not None:
        side = "left" if res.silent_channel == 0 else "right"
        return Verdict(status=UNSURE, reason=f"the {side} channel is silent next to the other, so there is nothing to cancel (a dead channel is wavewash's job)", **base)
    if res.dual_mono:
        return Verdict(status=OK, reason="both channels are identical (mono stored as stereo); the mono mix loses nothing", **base)
    if res.loss_db >= fail_db:
        why = " The channels are close to opposite in phase." if res.correlation <= -0.5 else ""
        return Verdict(status=FAKE, reason=f"a mono mix is {res.loss_db:.1f} dB quieter than the channels (correlation {res.correlation:.2f}).{why}", **base)
    if res.loss_db >= warn_db:
        return Verdict(status=LIMITED, reason=f"a mono mix is {res.loss_db:.1f} dB quieter than the channels (correlation {res.correlation:.2f}); partly out of phase", **base)
    if wl is not None and wl >= BAND_FAIL_DB:
        return Verdict(status=LIMITED, reason=f"the {wb} band cancels in a mono mix ({wl:.1f} dB loss) although the whole file does not", **base)
    return Verdict(status=OK, reason=f"a mono mix loses {res.loss_db:.1f} dB (correlation {res.correlation:.2f}); nothing cancels", **base)


def check_file(path, warn_db: float = WARN_DB, fail_db: float = FAIL_DB) -> Verdict:
    p = Path(path)
    try:
        x, sr = load_stereo(p)
    except Exception as e:  # unreadable audio
        return Verdict(p.name, None, 0, ERROR, f"could not read audio: {e}")
    ch = x.shape[1]
    if ch == 1:
        return Verdict(p.name, sr, 1, SKIPPED, "mono file; nothing to check")
    if ch > 2:
        return Verdict(p.name, sr, ch, SKIPPED, f"{ch} channels; only two-channel files are checked")
    return judge(analyse(x[:, 0], x[:, 1], sr), p.name, sr, 2, warn_db, fail_db)
