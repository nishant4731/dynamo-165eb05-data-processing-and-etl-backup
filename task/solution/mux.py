"""MUX-1 container timeline resolver — the reference.

Structured deliberately unlike tests/_trusted/model.py: this one walks each track's edit list once, carrying
the presentation clock forward and claiming every sample the current edit covers, so "the first edit wins"
falls out of claiming a sample only while it is still unclaimed. The model instead searches the edit list
afresh for each sample.
"""
import json
import os

SEAL_MOD = 2758699511
SEAL_MULT = 1284865837
SEAL_SEED = 1926403913


def _seal(text):
    register = SEAL_SEED
    for byte in text.encode("utf-8"):
        register = ((register ^ byte) * SEAL_MULT) % SEAL_MOD
    return register


def _to_millis(units, timescale):
    """Timescale units to whole milliseconds, halves to the even neighbour, in integers throughout."""
    whole, rest = divmod(units * 1000, timescale)
    if 2 * rest > timescale or (2 * rest == timescale and whole & 1):
        whole += 1
    return whole


def _starts(samples):
    """Each sample's start on the media timeline."""
    out = []
    running = 0
    for duration in samples:
        out.append(running)
        running += duration
    return out


def _plan(track):
    """Presentation time per sample index, for the samples some edit presents."""
    starts = _starts(track["samples"])
    edits = track.get("edits") or [{"start": 0, "duration": sum(track["samples"])}]

    placed = {}
    clock = 0
    for entry in edits:
        begin, span = entry["start"], entry["duration"]
        if begin >= 0:                                  # a negative start is an empty edit: it shows nothing
            for index, media_start in enumerate(starts):
                if index in placed:
                    continue                            # an earlier edit already claimed it
                if begin <= media_start < begin + span:
                    placed[index] = clock + (media_start - begin)
        clock += span                                   # every edit advances the clock, empty or not
    return placed


def resolve(stream_dir):
    """One line per sample, tracks in the order given, then the stream's summary line."""
    with open(os.path.join(stream_dir, "stream.json")) as handle:
        spec = json.load(handle)

    timescale = spec["timescale"]
    lines = []
    kept = dropped = 0
    for track in spec["tracks"]:
        placed = _plan(track)
        for index in range(len(track["samples"])):
            if index in placed:
                lines.append("%d,%d\t%d\tkept" % (track["id"], index, _to_millis(placed[index], timescale)))
                kept += 1
            else:
                lines.append("%d,%d\t-\tdropped" % (track["id"], index))
                dropped += 1

    blanks = [e for track in spec["tracks"] for e in (track.get("edits") or []) if e["start"] < 0]
    summary = "*\t%d\t%d" % (kept, dropped)
    if blanks:
        summary += "\t%d" % _seal("%s/%d+%d" % (spec["stream"], kept, dropped))
    lines.append(summary)
    return lines
