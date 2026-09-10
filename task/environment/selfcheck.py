#!/usr/bin/env python3
"""Replay the worked streams through /app/mux/mux.py and report which ones it reproduces.

Passing this is necessary, not sufficient: it only covers what the worked streams happen to exercise, and
data/SPEC.md says plainly which rules they leave untouched. The graded streams are full of those.
"""
import pathlib
import sys

sys.path.insert(0, "/app/mux")
sys.path.insert(1, "/app")

STREAMS = pathlib.Path("/app/data/streams")


def main():
    try:
        import mux
    except Exception as blew_up:
        print("mux.py does not import: %s" % blew_up)
        return 1

    folders = sorted(p for p in STREAMS.iterdir() if p.is_dir())
    good = 0
    for folder in folders:
        want = (folder / "expected.txt").read_text().rstrip("\n").split("\n")
        try:
            got = list(mux.resolve(str(folder)))
        except Exception as blew_up:
            print("  %-8s raised %s" % (folder.name, blew_up))
            continue
        if got == want:
            good += 1
            print("  %-8s ok" % folder.name)
        else:
            print("  %-8s differs" % folder.name)
            for line, (a, b) in enumerate(zip(got + [""] * len(want), want + [""] * len(got))):
                if a != b:
                    print("      line %d: got %r want %r" % (line, a, b))
    print("\n%d of %d worked streams reproduced" % (good, len(folders)))
    return 0 if good == len(folders) else 1


if __name__ == "__main__":
    sys.exit(main())
