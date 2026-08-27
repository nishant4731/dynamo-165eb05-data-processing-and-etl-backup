"""The trusted MUX-1 timeline resolver: what every graded stream is compared against.

Written independently of solution/mux.py. This one asks, for each sample in turn, which edit presents it —
a search per sample. The reference walks the edit list once and collects the samples each edit covers.
Agreement means the rules agree, not that one is a copy.
"""

SEAL_MOD = 2758699511
SEAL_MULT = 1284865837
SEAL_SEED = 1926403913


def seal(text):
    register = SEAL_SEED
    for byte in text.encode("utf-8"):
        register = ((register ^ byte) * SEAL_MULT) % SEAL_MOD
    return register


def canonical(stream, kept, dropped):
    return "%s/%d+%d" % (stream, kept, dropped)


def _millis(units, timescale):
    """Timescale units to whole milliseconds, halves to the even neighbour. Integer arithmetic only."""
    whole, rest = divmod(units * 1000, timescale)
    twice = 2 * rest
    if twice > timescale or (twice == timescale and whole % 2 == 1):
        whole += 1
    return whole


def _edits_of(track):
    """The track's edit list, or the implicit one that presents the whole media timeline unchanged."""
    listed = track.get("edits")
    if listed:
        return [dict(entry) for entry in listed]
    return [{"start": 0, "duration": sum(track["samples"])}]


def _clock_before(edits, position):
    """Where the presentation clock stands when edit `position` begins."""
    return sum(entry["duration"] for entry in edits[:position])


def _presented(track, media_start):
    """The presentation time of a sample starting at `media_start`, or None when nothing presents it.

    A search per sample: the first edit whose window covers the start wins, and an empty edit covers
    nothing at all however long it runs for.
    """
    edits = _edits_of(track)
    for position, entry in enumerate(edits):
        begin = entry["start"]
        if begin < 0:
            continue                                  # an empty edit presents no media
        if begin <= media_start < begin + entry["duration"]:
            return _clock_before(edits, position) + (media_start - begin)
    return None


def resolve(spec):
    timescale = spec["timescale"]
    lines = []
    kept = dropped = 0
    for track in spec["tracks"]:
        running = 0
        for index, duration in enumerate(track["samples"]):
            where = _presented(track, running)
            if where is None:
                lines.append("%d,%d\t-\tdropped" % (track["id"], index))
                dropped += 1
            else:
                lines.append("%d,%d\t%d\tkept" % (track["id"], index, _millis(where, timescale)))
                kept += 1
            running += duration

    empty_edit = any(entry["start"] < 0 for track in spec["tracks"] for entry in _edits_of(track))
    summary = "*\t%d\t%d" % (kept, dropped)
    if empty_edit:
        summary += "\t%d" % seal(canonical(spec["stream"], kept, dropped))
    lines.append(summary)
    return lines
