# MUX-1 — the container timeline

A MUX-1 stream describes what a container holds: each track's samples on its own media timeline, and an
optional edit list saying which parts of that timeline are actually presented and in what order. The
resolver decides, for every sample, whether it is presented at all and at what time. This document is the
whole contract: how the media timeline is built, what an edit does, which edit claims a sample, and exactly
what a run prints.

`/app/mux/mux.py` must expose `resolve(stream_dir)`, taking the path to a directory holding one
`stream.json` and returning the run's lines as a list of strings.

## The stream file

    {"format": "mux-1", "stream": "atrium", "timescale": 1000,
     "tracks": [
       {"id": 1, "samples": [40, 40, 40, 40],
        "edits": [{"start": -1, "duration": 100}, {"start": 40, "duration": 80}]}]}

`stream` names the stream. `timescale` is how many units make one second, and is at least 1. Each track has
an `id`, a list of `samples` giving each sample's duration in those units, and an optional `edits` list.
Every duration is a whole number of units and may be zero. A track may hold no samples at all.

## The media timeline

Within a track, the first sample starts at 0 and each following sample starts where the one before it
ended. So a sample's media start is the sum of every duration before it, and durations of zero leave two
samples starting at the same place.

## What an edit does

The edit list is walked in the order given, carrying a presentation clock that starts at 0. **Every edit
advances that clock by its own `duration`, whatever else it does.**

An edit whose `start` is negative is an **empty edit**: it presents no media at all. It still advances the
clock, which is how a gap is expressed — everything after it is presented that much later.

Any other edit presents the media interval beginning at `start` and running for `duration` units. The
interval is **half open**: a sample whose media start is exactly `start` is presented, and one whose media
start is exactly `start + duration` is not. A sample is placed by its start alone; how long it runs for
does not matter. Its presentation time is

    (the clock as this edit began) + (the sample's media start - this edit's start)

A track with no `edits` key, or with an empty list, is treated as having one edit that begins at 0 and runs
for the total of its sample durations — the whole media timeline, presented unchanged.

## Which edit claims a sample

Edits may overlap, and they may present the media out of order. The **first** edit in the list that covers
a sample is the one that presents it, and later edits that also cover it are ignored. A sample no edit
covers is **dropped**.

## Reporting a time

Presentation times are reported in whole milliseconds. A time of `units` on a stream of `timescale`
converts as `units * 1000 / timescale`, rounded to the nearest whole millisecond; a value landing exactly
halfway is rounded to the **even** neighbour, so at a timescale of 16 a media start of 1 unit reports 62
and one of 3 units reports 188.

## What a run returns

One line per sample — every sample of the first track, then every sample of the second, and so on in the
order the tracks are given. Every line is TAB-delimited, with no trailing blank line.

    <track id>,<sample index><TAB><time><TAB><state>

`sample index` counts from 0 within its own track. For a presented sample `state` is `kept` and `time` is
its presentation time in milliseconds; for a dropped one `state` is `dropped` and `time` is a single `-`.
Then one summary line reporting how many samples were kept and how many dropped, across every track:

    *<TAB><kept><TAB><dropped>

A stream in which **any track holds an empty edit** carries one further field on that line, the **seal** of
the stream's canonical text:

    *<TAB><kept><TAB><dropped><TAB><seal>

## The seal — recover the fold from the published pairs

The seal is taken over the stream's **canonical text**, which is its `stream` name, then `/`, then the kept
count, then `+`, then the dropped count, with nothing else and no padding — a stream `keyframe` keeping 12
samples and dropping 4 has the canonical text `keyframe/12+4`. Only a stream holding an empty edit carries
a seal at all — about a third of the graded streams — while every other rule in this document decides every
stream.

The seal depends on **nothing but the bytes of that canonical text** — not on the tracks, the samples, the
edits, the timescale, or anything else about the stream. Two streams whose canonical texts are equal have
equal seals, and every pair below was produced by the same function you are asked to recover, so the pairs
alone determine it.

Sealing walks that text one byte at a time, left to right. There is a single integer **starting register**
`S`, one update per byte, the same three constants for every stream this tooling has ever sealed, and
whatever the register holds after the last byte is the seal. The update is exactly one expression at every
step — no case analysis, no exception at a particular register or byte value, and no dependence on how far
into the text the walk has reached.

At each byte `b`, read as an unsigned value from 0 through 255, the register becomes

    register ← ((register XOR b) × multiplier) mod modulus

where `modulus` and `multiplier` are fixed positive integers and `modulus` is not a power of two. The three
numbers `(modulus, multiplier, starting register)` are not printed here as literals; they are **uniquely
determined** by the 90 exact `(canonical text → seal)` pairs in `data/SEALS.txt`. Exactly one choice
reproduces every published pair, and that choice is the one the resolver must use.

`data/SEALS.txt` is structured so the constants can be recovered from the pairs alone once the update above
is known. Seventy-two pairs fall into eight families of nine: inside one family the texts are identical but
for their closing byte, so the register arriving at that byte is the same for all nine members, and the nine
seals expose how one byte position is consumed against a single unknown carried register. The eight
families carry eight unrelated registers, and the remaining eighteen pairs share none of them — together
they pin the modulus, the multiplier, and the starting register.

The fold is **not** any of the usual checksums — CRC-32 at any polynomial or reflection, Adler-32,
Fletcher-32, FNV-1, FNV-1a, djb2, sdbm, Jenkins, a plain, weighted or modular sum or XOR of the bytes,
or any leading part of a cryptographic digest — and those names are ruled out because none of them
reproduce the published pairs. It is also **not a linear congruential fold** where the byte is added into
the register and the whole is then multiplied: in that family the byte enters linearly, differencing two
pairs cancels the register, and a gcd over the residuals recovers the modulus directly. That family has
been tried against the pairs below and does not reproduce them.

Not one of the canonical texts a graded stream produces appears in `data/SEALS.txt`, so reading a seal out
of that file cannot answer a single graded stream.

## What the worked streams cover

`/app/data/streams/<name>/stream.json` holds five worked streams and `python3 /app/selfcheck.py` replays
them. They pin the media timeline, the millisecond conversion and its half-to-even rounding, several tracks
in one stream, and an edit list that presents the whole timeline unchanged. **Not one of them holds an
empty edit, not one trims a sample away, none therefore carries a seal, and none stacks several sample indices on the same media start through
zero-duration samples.** So gaps, trimming, the seal, and coincident sample indices are all unobserved
there, and reproducing the worked streams says nothing about any of them — the 46 graded streams exercise
every omitted rule.
