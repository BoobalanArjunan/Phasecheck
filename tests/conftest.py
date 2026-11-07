import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))
import synth  # noqa: E402


@lru_cache(maxsize=None)
def sound(sr, seed=0, seconds=8.0):
    return synth.make_sound(sr, seconds, seed)


def pair(left, right):
    return np.stack([left, right], axis=1)


def write(path, x, sr):
    """16-bit PCM, like most real files. x is (samples,) or (samples, channels)."""
    sf.write(str(path), synth.to_pcm16(x), sr, subtype="PCM_16")
    return path
