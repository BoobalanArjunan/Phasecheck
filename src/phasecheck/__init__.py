"""phasecheck: do the two channels of a stereo file cancel each other when mixed down to mono?"""
from ._version import __version__
from .check import Verdict, check_file, judge

__all__ = ["__version__", "Verdict", "check_file", "judge"]
