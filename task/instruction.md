`/app/mux/mux.py` resolves MUX-1 streams: for every sample in every track it says whether the container
presents that sample at all and, if so, at what time, then summarises the stream. It gets that wrong on
anything outside the five worked streams under `/app/data/streams/`, which it still reproduces exactly. Put
it right, keeping this at module level:

    resolve(stream_dir) -> list[str]

`stream_dir` is an absolute path to a directory holding one `stream.json`.

Return one line per sample — every sample of the first track, then every sample of the second, and so on —
each of the exact form

    <track id>,<sample index><TAB><time><TAB><state>

where `state` is `kept` and `time` is the presentation time in whole milliseconds, or `state` is `dropped`
and `time` is a single `-`. Then one summary line

    *<TAB><kept><TAB><dropped>

A stream in which any track holds an empty edit carries a fourth field on that line, the **seal** of its
canonical text. `/app/data/SPEC.md` names the exact byte-wise fold, names the three constants it depends on,
and points at `/app/data/SEALS.txt` as the evidence that pins those constants. Recover the constants from
the pairs before you seal a graded stream — no graded canonical text appears in that file.

`/app/data/SPEC.md` is the contract. It fixes how a track's media timeline is built, what an edit presents
and what it does to the presentation clock, which edit claims a sample when several cover it, when a sample
is dropped instead, how a time converts to milliseconds and how a half rounds, and exactly what a run
prints. Every graded answer follows from it.

`python3 /app/selfcheck.py` replays the five worked streams and reports which ones the module reproduces. It
reports five of five before a line is changed and keeps reporting it through every repair, because the
worked streams are not where the difficulty is: not one of them holds an empty edit, not one trims a sample
away, none carries a seal, and none stacks several sample indices on the same media start through zero-duration
samples. SPEC.md says which rules the worked streams leave untouched. The same trusted tooling resolves
those worked streams and 46 unseen ones, and the unseen streams exercise every omitted rule.

The module must import cleanly. You may add helper modules under `/app` and import them from there. Every
file you leave under `/app`, the deliverable included, must be a regular file and not a symlink. Leave
`/app/data` and `/app/selfcheck.py` unchanged.

Grading is all or nothing, and a run ending with `/app/mux/mux.py` failing to import, not exposing
`resolve`, or raising when it is called, cannot be graded at all. Only what that file contains when the run
ends is graded; work held anywhere else is not. `python3 /app/selfcheck.py` takes under a second, so check
the file still imports as you go.
