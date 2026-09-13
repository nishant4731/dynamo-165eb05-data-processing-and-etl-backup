"""MUX-1 container timeline resolver — the reference.

Structured deliberately unlike tests/_trusted/model.py: this one walks each track's edit list once, carrying
the presentation clock forward and claiming every sample the current edit covers, so "the first edit wins"
falls out of claiming a sample only while it is still unclaimed. The model instead searches the edit list
afresh for each sample.

Seal constants are recovered from /app/data/SEALS.txt at import time using the fold named in SPEC.md.
"""
import collections
import json
import math
import os

def _seals_path():
    """`/app/data/SEALS.txt` in the graded image; fall back for a checkout-side import."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    shipped = os.path.join(root, "data", "SEALS.txt")
    if os.path.isfile(shipped):
        return shipped
    return os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "environment", "data", "SEALS.txt"))


def _read_pairs(path):
    pairs = {}
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#"):
            text, value = line.rsplit(None, 1)
            pairs[text] = int(value)
    return pairs


def _families(pairs):
    grouped = collections.defaultdict(list)
    for text in pairs:
        grouped[text[:-1]].append(text)
    return [sorted(v) for v in grouped.values() if len(v) >= 3]


def _family_multiple(pairs, group, low):
    marks = [ord(t[-1]) for t in group]
    seals = [pairs[t] for t in group]
    found = 0
    for i in range(1, len(group) - 1):
        left = (seals[0] - seals[i]) * ((low ^ marks[0]) - (low ^ marks[i + 1]))
        right = (seals[0] - seals[i + 1]) * ((low ^ marks[0]) - (low ^ marks[i]))
        found = math.gcd(found, abs(left - right))
    return found


def _modulus_candidates(pairs, groups):
    per_family = []
    for group in groups:
        seen = {}
        for low in range(256):
            multiple = _family_multiple(pairs, group, low)
            if multiple > 2 ** 31:
                seen[multiple] = low
        per_family.append(seen)

    support = {}
    for i, left in enumerate(per_family):
        for j, right in enumerate(per_family):
            if i >= j:
                continue
            for a in left:
                for b in right:
                    common = math.gcd(a, b)
                    if common > 2 ** 31:
                        support[common] = support.get(common, 0) + 1
    return [value for value, _ in sorted(support.items(), key=lambda kv: (-kv[1], -kv[0]))]


def _find_seed(pairs, modulus, multiplier):
    text = next(iter(pairs))
    register = pairs[text]
    inverse = pow(multiplier, -1, modulus)
    for byte in reversed(text.encode("utf-8")):
        register = ((register * inverse) % modulus) ^ byte
    return register


def _recover_constants(path):
    pairs = _read_pairs(path)
    groups = _families(pairs)
    for modulus in _modulus_candidates(pairs, groups)[:8]:
        for group in groups:
            marks = [ord(text[-1]) for text in group]
            seals = [pairs[text] for text in group]
            for low in range(256):
                gap = ((low ^ marks[0]) - (low ^ marks[1])) % modulus
                if not gap or math.gcd(gap, modulus) != 1:
                    continue
                multiplier = ((seals[0] - seals[1]) * pow(gap, -1, modulus)) % modulus
                if math.gcd(multiplier, modulus) != 1:
                    continue
                seed = _find_seed(pairs, modulus, multiplier)

                def fold(text, m=modulus, k=multiplier, s=seed):
                    register = s
                    for byte in text.encode("utf-8"):
                        register = ((register ^ byte) * k) % m
                    return register

                if all(fold(text) == value for text, value in pairs.items()):
                    return modulus, multiplier, seed
    raise RuntimeError("no constant set reproduces the published pairs in %s" % path)


SEAL_MOD, SEAL_MULT, SEAL_SEED = _recover_constants(_seals_path())


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
