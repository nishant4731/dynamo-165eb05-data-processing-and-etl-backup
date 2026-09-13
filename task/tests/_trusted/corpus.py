"""The MUX-1 corpus: the streams shipped as worked examples, and the ones the task is graded on.

Built in one place so the sample expectations and the graded ones cannot drift. The published seal pairs
are checked at import: no graded canonical text may be published, every byte a graded text seals must be
witnessed by a published one, and no published text may be a prefix of another.
"""
import model


def _stream(name, timescale, tracks):
    return {"format": "mux-1", "stream": name, "timescale": timescale, "tracks": tracks}


def _t(track_id, samples, edits=None):
    out = {"id": track_id, "samples": list(samples)}
    if edits is not None:
        out["edits"] = [dict(e) for e in edits]
    return out


def _e(start, duration):
    return {"start": start, "duration": duration}


# --- the worked streams --------------------------------------------------------------------------------
# They pin the media timeline, the millisecond conversion and its half-to-even rounding, several tracks,
# and an edit list that presents the whole timeline unchanged. Not one of them holds an empty edit, not one
# trims anything away, and none therefore carries a seal — so the shipped resolver reproduces all five.
def _samples():
    return [
        _stream("atrium", 1000, [_t(1, [40, 40, 40])]),
        _stream("beacon", 600, [_t(1, [20, 20, 20, 20], [_e(0, 80)])]),
        _stream("cadence", 90, [_t(1, [3, 3, 3, 3, 3])]),
        _stream("dossier", 1000, [_t(1, [40, 40], [_e(0, 40), _e(40, 40)]),
                                  _t(2, [80, 80])]),
        _stream("echo", 30000, [_t(1, [1001, 1001, 1001])]),
    ]


SAMPLE_SPECS = _samples()

for _spec in SAMPLE_SPECS:
    _out = model.resolve(_spec)
    assert len(_out[-1].split("\t")) == 3, \
        "worked stream %s carries a seal, which would witness the withheld column" % _spec["stream"]
    assert not any("\tdropped" in line for line in _out[:-1]), \
        "worked stream %s trims a sample away, which is meant to be unobserved" % _spec["stream"]
    for _track in _spec["tracks"]:
        assert all(e["start"] >= 0 for e in _track.get("edits", [])), \
            "worked stream %s holds an empty edit, which is meant to be unobserved" % _spec["stream"]

# Leaving the mechanisms out of a worked stream is NOT enough on its own — what the lure needs is that the
# shipped resolver reproduces every worked stream, and only replaying it says so. prepush.sh measures that.


# --- the graded streams --------------------------------------------------------------------------------
def _graded():
    out = []

    def add(name, timescale, tracks):
        out.append(_stream(name, timescale, tracks))

    # An edit that starts past zero shifts what survives and drops what sits before it.
    add("offset", 1000, [_t(1, [40, 40, 40, 40], [_e(40, 80)])])
    add("offsetlate", 1000, [_t(1, [40, 40, 40, 40], [_e(80, 80)])])
    add("shortedit", 1000, [_t(1, [40, 40, 40, 40], [_e(0, 80)])])
    add("tightedit", 1000, [_t(1, [40, 40, 40, 40], [_e(0, 41)])])
    add("pastmedia", 1000, [_t(1, [40, 40], [_e(400, 80)])])
    add("zerospan", 1000, [_t(1, [40, 40], [_e(0, 0)])])

    # The window is half open: a sample starting exactly at the edit's start is in, one starting exactly at
    # its end is out.
    add("startedge", 1000, [_t(1, [40, 40, 40], [_e(40, 40)])])
    add("endedge", 1000, [_t(1, [40, 40, 40], [_e(0, 80)])])
    add("onepast", 1000, [_t(1, [40, 40, 40], [_e(0, 81)])])

    # Empty edits: they present nothing and still move the presentation clock. These carry a seal.
    add("gaphead", 1000, [_t(1, [40, 40], [_e(-1, 100), _e(0, 80)])])
    add("gapmid", 1000, [_t(1, [40, 40], [_e(0, 40), _e(-1, 60), _e(40, 40)])])
    add("gapzero", 1000, [_t(1, [40, 40], [_e(-1, 0), _e(0, 80)])])
    add("gaponly", 1000, [_t(1, [40, 40], [_e(-1, 120)])])
    add("gaptail", 1000, [_t(1, [40, 40], [_e(0, 80), _e(-1, 90)])])
    add("gaptwice", 1000, [_t(1, [40, 40, 40], [_e(-1, 50), _e(0, 40), _e(-1, 50), _e(40, 80)])])
    add("gapscaled", 600, [_t(1, [20, 20], [_e(-1, 30), _e(0, 40)])])
    add("gapmulti", 1000, [_t(1, [40, 40], [_e(-1, 20)]), _t(2, [40, 40], [_e(0, 80)])])

    # Several edits reorder the media timeline, and the first edit that covers a sample keeps it.
    add("reorder", 1000, [_t(1, [40, 40, 40, 40], [_e(80, 80), _e(0, 80)])])
    add("overlap", 1000, [_t(1, [40, 40, 40], [_e(0, 120), _e(40, 40)])])
    add("overlapback", 1000, [_t(1, [40, 40, 40], [_e(40, 80), _e(0, 120)])])
    add("repeatwin", 1000, [_t(1, [40, 40], [_e(0, 40), _e(0, 40)])])
    add("threeedits", 1000, [_t(1, [40, 40, 40, 40], [_e(120, 40), _e(0, 40), _e(40, 80)])])

    # Millisecond conversion, including values that land exactly on a half.
    add("scale90", 90, [_t(1, [3, 3, 3, 3])])
    add("scale600", 600, [_t(1, [20, 20, 20])])
    add("scale30k", 30000, [_t(1, [1001, 1001, 1001, 1001])])
    add("halfeven", 16, [_t(1, [1, 1, 1, 1, 1, 1, 1, 1])])
    add("halfodd", 32, [_t(1, [1, 1, 1, 1, 1, 1])])
    add("scaleodd", 7, [_t(1, [1, 1, 1, 1])])
    add("scalebig", 90000, [_t(1, [3003, 3003, 3003])])

    # Tracks are independent and reported in the order given.
    add("twotracks", 1000, [_t(1, [40, 40], [_e(40, 40)]), _t(2, [40, 40])])
    add("threetracks", 1000, [_t(3, [40]), _t(1, [40, 40]), _t(2, [40, 40, 40], [_e(0, 40)])])
    add("trackids", 1000, [_t(7, [40, 40], [_e(0, 80)]), _t(2, [40])])
    add("mixededits", 1000, [_t(1, [40, 40], [_e(-1, 40), _e(0, 40)]), _t(2, [40, 40])])

    # Shapes: one sample, uneven durations, a track with nothing in it.
    add("single", 1000, [_t(1, [40])])
    add("uneven", 1000, [_t(1, [17, 41, 3, 512], [_e(17, 44)])])
    add("emptytrack", 1000, [_t(1, []), _t(2, [40, 40])])
    add("emptyedits", 1000, [_t(1, [40, 40], [])])
    add("longrun", 1000, [_t(1, [40] * 10, [_e(120, 200)])])

    # Zero-duration samples stack several indices on the same media start; each index is still reported,
    # and out-of-order edits must place every coincident index independently.
    add("coincident", 1000, [_t(1, [40, 0, 40], [_e(0, 80)])])
    add("triplestack", 1000, [_t(1, [20, 0, 0, 20], [_e(0, 40)])])
    add("coinoverlap", 1000, [_t(1, [40, 0, 40, 40], [_e(40, 80), _e(0, 40)])])

    # Everything at once.
    add("tangled", 600, [_t(1, [20, 20, 20, 20], [_e(-1, 25), _e(40, 40), _e(0, 40)]),
                         _t(2, [30, 30], [_e(30, 30)])])
    add("layered", 90, [_t(1, [3, 3, 3], [_e(3, 6), _e(-1, 9)]), _t(2, [3, 3])])
    add("woven", 1000, [_t(1, [40, 40, 40], [_e(80, 40), _e(-1, 60), _e(0, 40)]),
                        _t(2, [40, 40, 40], [_e(0, 120)]),
                        _t(3, [40], [_e(400, 40)])])
    add("deepmix", 30000, [_t(1, [1001, 1001, 1001, 1001], [_e(1001, 2002)]),
                           _t(2, [1001, 1001], [_e(-1, 500), _e(0, 1001)])])
    add("wide", 1000, [_t(1, [40, 40], [_e(0, 40)]), _t(2, [40, 40], [_e(40, 40)]),
                       _t(3, [40, 40], [_e(-1, 10), _e(0, 80)])])

    return out


GRADED_SPECS = _graded()


# --- the published seal pairs ----------------------------------------------------------------------------
# Eight families of nine whose texts part only in their closing byte, then eighteen assorted streams.
_FAMILIES = [("keyframe", 12), ("muxpoint", 6), ("gopclose", 21), ("waveform", 3),
             ("chapter", 18), ("loudness", 30), ("sidecar", 15), ("timebase", 24)]
_ASSORTED = [("aspect", 5, 2), ("bframe", 14, 7), ("codec", 22, 9), ("dropframe", 4, 1),
             ("envelope", 38, 15), ("fielding", 8, 3), ("gamma", 17, 11), ("hinttrack", 29, 20),
             ("interlace", 44, 26), ("jitter", 9, 4), ("kerning", 16, 10), ("lipsync", 25, 13),
             ("metadata", 2, 1), ("nalunit", 35, 22), ("overscan", 11, 6), ("pulldown", 33, 18),
             ("quantizer", 41, 28), ("rendition", 7, 5)]


def published_pairs():
    texts = []
    for stream, kept in _FAMILIES:
        for dropped in range(1, 10):
            texts.append(model.canonical(stream, kept, dropped))
    for stream, kept, dropped in _ASSORTED:
        texts.append(model.canonical(stream, kept, dropped))
    return texts


def graded_seal_texts():
    out = set()
    for spec in GRADED_SPECS:
        summary = model.resolve(spec)[-1].split("\t")
        if len(summary) == 4:
            out.add(model.canonical(spec["stream"], int(summary[1]), int(summary[2])))
    return out


def _seal_guarantees(texts, graded):
    names = [spec["stream"] for spec in SAMPLE_SPECS + GRADED_SPECS]
    assert len(set(names)) == len(names), "two streams share a name: %s" % sorted(
        {n for n in names if names.count(n) > 1})
    assert len(set(texts)) == len(texts), "a seal text is published twice"
    assert graded, "no graded stream holds an empty edit, so none carries a seal"
    clash = sorted(graded & set(texts))
    assert not clash, "graded seal texts are published, so a lookup answers the column: %s" % clash
    missing = set("".join(sorted(graded)).encode()) - set("".join(texts).encode())
    assert not missing, "graded texts seal bytes no published text does: %r" % sorted(
        chr(b) for b in missing)
    for a in texts:
        for b in texts:
            assert a == b or not a.startswith(b), "%s is a prefix of %s" % (b, a)
    assert max(model.seal(t) for t in texts) >= 2 ** 31, \
        "every published seal is below 2**31, which advertises the modulus"


PUBLISHED = published_pairs()
GRADED_SEAL_TEXTS = graded_seal_texts()
_seal_guarantees(PUBLISHED, GRADED_SEAL_TEXTS)
