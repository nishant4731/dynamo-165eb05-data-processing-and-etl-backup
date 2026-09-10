"""MUX-1 container timeline resolver, as the packaging tooling last ran it.

This predates the current SPEC.md and does not implement it as it now stands.
"""
import json
import os


def _to_millis(units, timescale):
    whole, rest = divmod(units * 1000, timescale)
    if 2 * rest > timescale or (2 * rest == timescale and whole & 1):
        whole += 1
    return whole


def _starts(samples):
    out = []
    running = 0
    for duration in samples:
        out.append(running)
        running += duration
    return out


def resolve(stream_dir):
    """One line per sample, tracks in the order given, then the stream's summary line."""
    with open(os.path.join(stream_dir, "stream.json")) as handle:
        spec = json.load(handle)

    timescale = spec["timescale"]
    lines = []
    kept = dropped = 0
    for track in spec["tracks"]:
        for index, media_start in enumerate(_starts(track["samples"])):
            lines.append("%d,%d\t%d\tkept" % (track["id"], index, _to_millis(media_start, timescale)))
            kept += 1

    lines.append("*\t%d\t%d" % (kept, dropped))
    return lines
