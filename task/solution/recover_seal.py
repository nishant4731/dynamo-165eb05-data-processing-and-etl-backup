#!/usr/bin/env python3
"""Recover the seal's three constants from data/SEALS.txt alone.

Not part of the graded deliverable and not run by solve.sh — it exists so a reviewer can confirm the
published pairs really do pin the constants named in SPEC.md.

The step named in SPEC.md is `register = ((register ^ byte) * MULT) % MOD`. Inside one published family the texts are
identical but for their closing byte, so every member carries the same unknown register L into that byte:

    seal_i = ((L ^ b_i) * MULT) mod MOD

Only L's low eight bits matter to `L ^ b_i`, because each b_i is a single byte. So sweep 256 candidates for
those bits. Differencing two members kills L's contribution to the constant term:

    seal_i - seal_j = MULT * ((l ^ b_i) - (l ^ b_j))   (mod MOD)

and cross-multiplying two such differences cancels MULT, leaving an exact multiple of MOD.

Each family carries its OWN register, so the low byte is swept per family rather than once for all of
them — that is the step that makes the sweep work. A gcd across the per-family results gives MOD itself;
MULT then follows by one modular inverse, and the starting register falls out of walking any pair
backwards.
"""
import collections
import math
import pathlib
import sys


def read_pairs(path):
    pairs = {}
    for line in open(path):
        line = line.strip()
        if line and not line.startswith("#"):
            text, value = line.rsplit(None, 1)
            pairs[text] = int(value)
    return pairs


def families(pairs):
    """Group texts that agree everywhere but their final byte."""
    grouped = collections.defaultdict(list)
    for text in pairs:
        grouped[text[:-1]].append(text)
    return [sorted(v) for v in grouped.values() if len(v) >= 3]


def _family_multiple(pairs, group, low):
    """The gcd of this family's cross-products at one candidate low byte."""
    marks = [ord(t[-1]) for t in group]
    seals = [pairs[t] for t in group]
    found = 0
    for i in range(1, len(group) - 1):
        left = (seals[0] - seals[i]) * ((low ^ marks[0]) - (low ^ marks[i + 1]))
        right = (seals[0] - seals[i + 1]) * ((low ^ marks[0]) - (low ^ marks[i]))
        found = math.gcd(found, abs(left - right))
    return found


def modulus_candidates(pairs, groups):
    """Every plausible modulus, best first.

    Per family the low byte is swept and the cross-product gcd taken; the correct candidate is an exact
    multiple of the modulus and the wrong ones are essentially random, so the truth shows up as a value two
    or more families agree on. Taking each family's LARGEST gcd and combining is not enough on its own — on
    this corpus one family's wrong candidate outranks its right one, which drags a plain gcd to 1. So
    collect every family's candidates and rank by how many families support each one.
    """
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
    return [value for value, _ in sorted(support.items(), key=lambda kv: (-kv[1], -kv[0]))], per_family


def low_bytes_for(per_family, modulus):
    """The low byte each family agrees on, once the modulus is known."""
    out = []
    for seen in per_family:
        pick = None
        for multiple, low in seen.items():
            if multiple % modulus == 0:
                pick = low
                break
        out.append((None, pick))
    return out


def find_multiplier(pairs, groups, modulus, per_family):
    for group, (_, low) in zip(groups, per_family):
        if low is None:
            continue
        marks = [ord(t[-1]) for t in group]
        seals = [pairs[t] for t in group]
        for i in range(len(group) - 1):
            gap = ((low ^ marks[i]) - (low ^ marks[i + 1])) % modulus
            if gap and math.gcd(gap, modulus) == 1:
                return ((seals[i] - seals[i + 1]) * pow(gap, -1, modulus)) % modulus
    return None


def find_seed(pairs, modulus, multiplier):
    """Undo the fold over one whole text: each step inverts to (seal * MULT^-1) xor byte."""
    text = next(iter(pairs))
    register = pairs[text]
    inverse = pow(multiplier, -1, modulus)
    for byte in reversed(text.encode("utf-8")):
        register = ((register * inverse) % modulus) ^ byte
    return register


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "task/environment/data/SEALS.txt"
    if not pathlib.Path(path).exists():
        sys.exit("no such file: %s" % path)
    pairs = read_pairs(path)
    groups = families(pairs)
    candidates, _ = modulus_candidates(pairs, groups)

    # With the modulus in hand the multiplier needs the register's low bits, and only the bits the closing
    # bytes actually differ in matter — the members of a family part in one digit, so there are just 16
    # classes to try. Trying all of them and checking every published pair is cheaper than being clever,
    # and it is the same check an agent has available: a candidate is the answer only if it reproduces the
    # whole file.
    for modulus in candidates[:8]:
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
                seed = find_seed(pairs, modulus, multiplier)

                def fold(text, m=modulus, k=multiplier, s=seed):
                    register = s
                    for byte in text.encode("utf-8"):
                        register = ((register ^ byte) * k) % m
                    return register

                if all(fold(text) == value for text, value in pairs.items()):
                    print("pairs read        : %d over %d aligned families" % (len(pairs), len(groups)))
                    print("modulus           : %d" % modulus)
                    print("multiplier        : %d" % multiplier)
                    print("starting register : %d" % seed)
                    print("every published pair reproduces under the recovered constants")
                    return
    sys.exit("no constant set reproduces the pairs")


if __name__ == "__main__":
    main()
