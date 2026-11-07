"""Stereo audio -> how much of it survives a mono downmix.

Mixing a stereo file to mono (the average of the two channels) keeps sound that is the same in both channels and
cancels sound that is opposite in the two channels. A file whose channels are partly or wholly out of phase can lose
level or vanish when a training pipeline converts it to mono. phasecheck measures that loss.

downmix_loss_db: 0 dB when the channels are identical (nothing is lost), about 3 dB when they are unrelated (the normal
case for wide stereo), and large when they are in opposite phase (the mono mix is much quieter than the channels).
Light on purpose: numpy, scipy, soundfile only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
import soundfile as sf
from scipy.signal import stft

MAX_SECONDS = 120.0            # long files: only the middle 2 minutes are used
MIN_SECONDS = 2.0
ACTIVE_FLOOR_DB = -30.0        # frames more than 30 dB below the loudest frame are ignored
MIN_ACTIVE_FRAMES = 4
NPERSEG = 2048
BANDS_HZ = ((20.0, 250.0), (250.0, 2000.0), (2000.0, 8000.0), (8000.0, 1e9))
BAND_NAMES = ("20-250 Hz", "250 Hz-2 kHz", "2-8 kHz", "above 8 kHz")
MIN_BAND_SHARE_DB = -20.0      # a band counts only if it holds at least 1% of the energy
SILENT_CHANNEL_DB = -60.0      # a channel this far below the other is treated as silent (wavewash finds dead channels)
LOSS_CAP_DB = 60.0
IDENTICAL_DB = 0.2             # channels are "identical" if the mono mix loses less than this and their correlation is above 0.9999


@dataclass
class PhaseResult:
    sample_rate: int
    seconds: float
    active_seconds: float
    loss_db: float                                   # full-band downmix loss
    correlation: float                               # full-band, -1 (opposite) .. +1 (identical)
    band_loss_db: Dict[str, Optional[float]] = field(default_factory=dict)   # None for a band that is empty or holds too little energy
    dual_mono: bool = False                          # both channels identical (mono stored as stereo)
    silent_channel: Optional[int] = None             # 0 or 1 if one channel is silent next to the other


def load_stereo(path, max_seconds: float = MAX_SECONDS):
    """Reads the file at its own sample rate -> (array of shape (samples, channels), sample rate). Long files: the middle part."""
    x, sr = sf.read(str(path), dtype="float64", always_2d=True)
    n = int(max_seconds * sr)
    if len(x) > n:
        s = (len(x) - n) // 2
        x = x[s:s + n]
    return x, int(sr)


def _loss_db(p_mono: float, p_l: float, p_r: float) -> float:
    mean_ch = (p_l + p_r) / 2
    if mean_ch <= 0:
        return 0.0
    return float(min(LOSS_CAP_DB, -10 * np.log10(max(p_mono, mean_ch * 10 ** (-LOSS_CAP_DB / 10)) / mean_ch)))


def analyse(left: np.ndarray, right: np.ndarray, sr: int) -> Optional[PhaseResult]:
    """Downmix loss of a stereo pair, measured over its loud parts. None if too short, silent or too few loud frames."""
    n = min(len(left), len(right))
    if n < MIN_SECONDS * sr:
        return None
    left, right = left[:n], right[:n]
    if not (np.any(np.abs(left) > 1e-9) or np.any(np.abs(right) > 1e-9)):
        return None
    nper = min(NPERSEG, 2 ** int(np.log2(max(n // 4, 256))))
    f, _, ZL = stft(left, fs=sr, nperseg=nper, noverlap=nper // 2, boundary=None, padded=False)
    _, _, ZR = stft(right, fs=sr, nperseg=nper, noverlap=nper // 2, boundary=None, padded=False)
    PL, PR = np.abs(ZL) ** 2, np.abs(ZR) ** 2
    PM = np.abs(ZL + ZR) ** 2 / 4
    cross = np.real(ZL * np.conj(ZR))
    energy = PL.sum(axis=0) + PR.sum(axis=0)
    if energy.max() <= 0:
        return None
    active = energy > energy.max() * 10 ** (ACTIVE_FLOOR_DB / 10)
    if active.sum() < MIN_ACTIVE_FRAMES:
        return None
    PL, PR, PM, cross = PL[:, active], PR[:, active], PM[:, active], cross[:, active]
    hop = nper // 2
    tl, tr, tm = PL.sum(), PR.sum(), PM.sum()
    silent = None
    if tl > 0 and 10 * np.log10(max(tr, 1e-30) / tl) < SILENT_CHANNEL_DB:
        silent = 1
    elif tr > 0 and 10 * np.log10(max(tl, 1e-30) / tr) < SILENT_CHANNEL_DB:
        silent = 0
    denom = np.sqrt(tl * tr)
    corr = float(cross.sum() / denom) if denom > 0 else 0.0
    loss = _loss_db(tm, tl, tr)
    total = tl + tr
    bands: Dict[str, Optional[float]] = {}
    for (lo, hi), name in zip(BANDS_HZ, BAND_NAMES):
        sel = (f >= lo) & (f < min(hi, sr / 2 + 1))
        if not sel.any():
            bands[name] = None
            continue
        bl, br, bm = PL[sel].sum(), PR[sel].sum(), PM[sel].sum()
        if total <= 0 or 10 * np.log10(max(bl + br, 1e-30) / total) < MIN_BAND_SHARE_DB:
            bands[name] = None
            continue
        bands[name] = _loss_db(bm, bl, br)
    dual = loss < IDENTICAL_DB and corr > 0.9999 and abs(10 * np.log10(max(tl, 1e-30) / max(tr, 1e-30))) < 0.5
    return PhaseResult(sr, n / sr, float(active.sum() * hop / sr), loss, float(np.clip(corr, -1, 1)), bands, bool(dual), silent)
