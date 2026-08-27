#!/usr/bin/env python3
"""Regenerate everything shipped under environment/data, and re-check every count the prose asserts.

Run after any change to corpus.py or model.py. The counts in SPEC.md, instruction.md and task.toml are
asserted here rather than trusted: a stale count is a blocking no_contradictions finding, and one has
shipped before on a task where SPEC.md was updated and the metadata was not.
"""
import hashlib
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import corpus
import model

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / "environment" / "data"

SHIPPED = {"data/SPEC.md": DATA / "SPEC.md",
           "data/SEALS.txt": DATA / "SEALS.txt",
           "selfcheck.py": ROOT / "environment" / "selfcheck.py"}

# Spelled out so the header reads as prose, and derived rather than typed — a header that misdescribes a
# SHA-pinned agent-visible file is a deep_review finding.
WORDS = {2: "two", 8: "eight", 9: "nine", 18: "eighteen", 72: "seventy-two", 90: "ninety"}


def spelled(n):
    return WORDS.get(n, str(n))


def write_streams():
    root = DATA / "streams"
    if root.exists():
        for old in sorted(root.rglob("*")):
            if old.is_file():
                old.unlink()
    for spec in corpus.SAMPLE_SPECS:
        folder = root / spec["stream"]
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "stream.json").write_text(json.dumps(spec, indent=2) + "\n")
        # Agent-facing only. selfcheck.py reads this; the verifier never does — every expectation it
        # grades against comes from the trusted model, so editing this file fools nobody but the editor.
        (folder / "expected.txt").write_text("\n".join(model.resolve(spec)) + "\n")
    return len(corpus.SAMPLE_SPECS)


def write_seals():
    texts = corpus.PUBLISHED
    width = max(len(t) for t in texts) + 2
    families = len(corpus._FAMILIES)
    banded = families * 9
    assorted = len(texts) - banded
    header = [
        "# Every stream this tooling has sealed: one exact (canonical text -> seal) pair per line.",
        "# The pairs settle the sealing arithmetic; data/SPEC.md, section The seal, lists what it is not.",
        "#",
        "# How the file is arranged, which is a fact about it rather than advice: the first %s lines"
        % spelled(banded),
        "# are %s families of nine. Within a family the texts are identical but for their closing byte,"
        % spelled(families),
        "# so the register arrives at that byte holding one value for all nine members, and the nine",
        "# seals expose directly how one byte position is consumed against a single unknown carried",
        "# register. Two different families agree nowhere useful — their texts diverge earlier, so the",
        "# registers they carry in are unrelated and one family says nothing about another. The",
        "# remaining %s lines are assorted streams that share none of those registers, spread so that"
        % spelled(assorted),
        "# every byte one of these texts can hold appears somewhere above.",
        "#",
        "# A fact about the constants rather than about the file: each of them is a full-width value",
        "# above a billion, so none lies in a range that trying candidates in order can reach.",
        "",
    ]
    body = ["%-*s %d" % (width, text, model.seal(text)) for text in texts]
    (DATA / "SEALS.txt").write_text("\n".join(header + body) + "\n")
    return len(texts)


def write_pins():
    pins = {target: hashlib.sha256(source.read_bytes()).hexdigest()
            for target, source in sorted(SHIPPED.items())}
    (ROOT / "tests" / "input_hashes.json").write_text(json.dumps(pins, indent=2) + "\n")
    return len(pins)


def check_counts(graded, pairs):
    """Every count the agent-visible prose and the metadata assert, checked against the corpus itself."""
    for name in ("environment/data/SPEC.md", "instruction.md", "task.toml"):
        path = ROOT / name
        if not path.exists():
            continue
        flat = " ".join(path.read_text(encoding="utf-8").split())
        for found in re.findall(r"(\d+) graded streams", flat):
            assert int(found) == graded, "%s says %s graded streams, corpus holds %d" % (name, found, graded)
        for found in re.findall(r"publishes (\d+)", flat):
            assert int(found) == pairs, "%s says publishes %s, corpus holds %d" % (name, found, pairs)
        for found in re.findall(r"reproduces all (\d+)", flat):
            assert int(found) == pairs, "%s says reproduces all %s, corpus holds %d" % (name, found, pairs)


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    streams = write_streams()
    pairs = write_seals()
    check_counts(len(corpus.GRADED_SPECS), pairs)
    pins = write_pins()
    print("streams: %d worked, %d graded   seal pairs: %d   pinned inputs: %d"
          % (streams, len(corpus.GRADED_SPECS), pairs, pins))


if __name__ == "__main__":
    main()
