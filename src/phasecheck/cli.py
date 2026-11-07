from __future__ import annotations

import argparse
import sys
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from pathlib import Path

from . import __version__
from .check import FAIL_DB, WARN_DB, check_file
from .report import text, to_json, write_csv

AUDIO_EXT = {".wav", ".flac", ".mp3", ".ogg", ".m4a", ".aiff", ".aif"}


def find_audio(source: Path):
    if source.is_file():
        return [source]
    return sorted(p for p in source.rglob("*") if p.suffix.lower() in AUDIO_EXT and not p.name.startswith("._") and "__MACOSX" not in p.parts)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="phasecheck", description="Find stereo audio files whose channels cancel each other in a mono downmix.")
    ap.add_argument("--version", action="version", version=f"phasecheck {__version__}")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check", help="check one file or every audio file in a folder")
    c.add_argument("source", type=Path)
    c.add_argument("--warn-db", type=float, default=WARN_DB, help=f"downmix loss that earns a WARN (default {WARN_DB:g} dB)")
    c.add_argument("--fail-db", type=float, default=FAIL_DB, help=f"downmix loss that earns a FAIL (default {FAIL_DB:g} dB)")
    c.add_argument("--out", type=Path, help="write every verdict to this CSV")
    c.add_argument("--json", action="store_true", help="print the full report as JSON (instead of text)")
    c.add_argument("--show-pass", action="store_true", help="also list files that passed or were skipped")
    c.add_argument("--jobs", type=int, default=1, help="files analysed in parallel (default 1)")
    a = ap.parse_args(argv)

    if not a.source.exists():
        print(f"error: {a.source} not found", file=sys.stderr)
        return 2
    if a.warn_db > a.fail_db:
        print("error: --warn-db must not be larger than --fail-db", file=sys.stderr)
        return 2
    files = find_audio(a.source)
    if not files:
        print("error: no audio files found", file=sys.stderr)
        return 2
    job = partial(check_file, warn_db=a.warn_db, fail_db=a.fail_db)
    if a.jobs > 1:
        with ProcessPoolExecutor(a.jobs) as ex:
            vs = list(ex.map(job, files, chunksize=1))
    else:
        vs = [job(f) for f in files]
    print(to_json(vs) if a.json else text(vs, a.show_pass))
    if a.out:
        write_csv(a.out, vs)
    return 1 if any(v.level == "FAIL" for v in vs) else 0


if __name__ == "__main__":
    sys.exit(main())
