"""Synthetic stereo material with a KNOWN channel relationship: broadband noise with a falling spectrum (tones optional). Written as 16-bit PCM, like most real files."""
import numpy as np
from scipy.signal import butter, hilbert, sosfiltfilt

TILT = 0.5      # pink-like: about equal energy in every octave, so every band carries some energy


def make_sound(sr, seconds=8.0, seed=0, level=0.3, tones=False):
    rng = np.random.RandomState(seed)
    n = int(seconds * sr)
    X = np.fft.rfft(rng.randn(n))
    f = np.fft.rfftfreq(n, 1 / sr)
    f[0] = f[1]
    x = np.fft.irfft(X * (f / 1000.0) ** -TILT, n)
    t = np.arange(n) / sr
    env = 0.6 + 0.4 * np.sin(2 * np.pi * 0.7 * t + rng.rand() * 6) ** 2
    x = x / np.std(x) * env
    if tones:      # tones at the same frequencies in two seeds are phase-related at random: use only when that is wanted
        for f0 in (110.0, 220.0, 440.0):
            for h in range(1, 12):
                if f0 * h < sr / 2 * 0.9:
                    x += 0.15 / h * np.sin(2 * np.pi * f0 * h * t + rng.rand() * 6)
    return (level * x / np.abs(x).max()).astype(np.float64)


def band(x, sr, lo, hi):
    """The part of x between lo and hi Hz."""
    sos = butter(4, [lo, hi], btype="bandpass", fs=sr, output="sos")
    return sosfiltfilt(sos, x)


def to_pcm16(x):
    return np.round(np.clip(x, -1, 1) * 32767).astype(np.int16)


def rotate(x, degrees):
    """x with every frequency shifted by the same phase angle. Against x itself the two channels then have an exactly known
    relationship: the mono mix loses -10*log10((1 + cos(angle)) / 2) dB (0 dB at 0 degrees, 3.01 dB at 90, infinite at 180)."""
    th = np.deg2rad(degrees)
    return np.real(hilbert(x) * np.exp(1j * th))
