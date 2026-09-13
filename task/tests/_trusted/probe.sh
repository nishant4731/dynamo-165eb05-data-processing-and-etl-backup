#!/bin/bash
# The regression gate: every way this task is meant to score 0, proven to score 0.
#
#   bash task/tests/_trusted/probe.sh <image>
#
# Each probe builds a container from the environment image, runs a scenario, and checks the reward. The
# summary line is printed UNINDENTED on purpose — prepush.sh matches it with an anchored ^[0-9]+ regex, and
# an indented one made that gate report FAILED over a suite where every probe had passed.
set -u
IMAGE="${1:-165eb05-env}"
TASK="$(cd -- "$(dirname -- "$0")/../.." && pwd)"
TOOL=/app/mux/mux.py
PASS=0
FAIL=0

grade() {
    got=$(docker run --rm -u 0:0 -v "$TASK:/task:ro" "$IMAGE" bash -c "
        cp -r /task/tests /tests && cp -r /task/solution /solution && mkdir -p /logs/verifier
        $3
        bash /tests/test.sh >/dev/null 2>&1
        cat /logs/verifier/reward.txt" 2>/dev/null | tail -1)
    if [ "$got" = "$2" ]; then
        PASS=$((PASS + 1)); printf '  ok    %-58s reward %s\n' "$1" "$got"
    else
        FAIL=$((FAIL + 1)); printf '  FAIL  %-58s reward %s, wanted %s\n' "$1" "${got:-none}" "$2"
    fi
}

flip() {
    # A label carrying an apostrophe would close the single-quoted python string below, raise a
    # SyntaxError, skip the patch and grade the PRISTINE reference — a false pass, which is the one thing
    # this guard exists to prevent.
    case "$1" in
        *\'*) printf '  ABORT  flip label must not contain an apostrophe: %s\n' "$1"; exit 2 ;;
    esac
    grade "flip: $1" 0 "bash /solution/solve.sh; python3 - <<'PYEOF'
import pathlib, sys
src = original = pathlib.Path('$TOOL').read_text()
$2
if src == original:
    sys.exit('flip pattern no longer matches the reference: $1')
pathlib.Path('$TOOL').write_text(src)
PYEOF"
}

echo "probing $IMAGE"
echo

# --- the reference and harmless variations on it must score 1 ------------------------------------------
grade "reference evaluator" 1 'bash /solution/solve.sh'

echo "probing $IMAGE"
echo

# --- the reference and harmless variations on it must score 1 ------------------------------------------
grade "reference resolver" 1 'bash /solution/solve.sh'
grade "reference with added comments" 1 "bash /solution/solve.sh; printf '\n# reviewed\n' >> $TOOL"
grade "reference plus an unrelated helper module" 1 "bash /solution/solve.sh; printf 'V = 1\n' > /app/helper.py"
grade "reference importing a helper module from /app" 1 "bash /solution/solve.sh; printf 'BONUS = 1\n' > /app/extra.py; sed -i '1i import extra' $TOOL"

# --- nothing, or something structurally wrong, must score 0 --------------------------------------------
grade "no deliverable at all" 0 "rm -f $TOOL"
grade "the shipped resolver, untouched" 0 'true'
grade "a deliverable that fails to import" 0 "printf 'import nosuchmodule\n' > $TOOL"
grade "a deliverable without resolve()" 0 "printf 'V = 1\n' > $TOOL"
grade "resolve() that returns nothing" 0 "printf 'def resolve(d):\n    return []\n' > $TOOL"
grade "resolve() that returns non-strings" 0 "printf 'def resolve(d):\n    return [1, 2]\n' > $TOOL"
grade "resolve() that never returns" 0 "printf 'def resolve(d):\n    while True:\n        pass\n' > $TOOL"

# --- containment ---------------------------------------------------------------------------------------
grade "deliverable behind a symlink" 0 "bash /solution/solve.sh; mv $TOOL /tmp/real.py; ln -s /tmp/real.py $TOOL"
grade "a helper package behind a symlinked parent" 0 "bash /solution/solve.sh; mkdir -p /tmp/out; printf 'V=1\n' > /tmp/out/h.py; ln -s /tmp/out /app/pkg"
grade "the deliverable directory replaced by a symlink" 0 "bash /solution/solve.sh; mv /app/mux /tmp/real_mux; ln -s /tmp/real_mux /app/mux"
grade "a symlinked parent that resolves inside /app" 0 "bash /solution/solve.sh; mkdir -p /app/real_mux; cp $TOOL /app/real_mux/mux.py; rm -rf /app/mux; ln -s /app/real_mux /app/mux"

# --- tampering with the shipped evidence ---------------------------------------------------------------
grade "the spec edited" 0 "bash /solution/solve.sh; printf '\n' >> /app/data/SPEC.md"
grade "a published pair edited" 0 "bash /solution/solve.sh; sed -i '20s/[0-9]*$/1/' /app/data/SEALS.txt"
grade "the self-check edited" 0 "bash /solution/solve.sh; printf '\n' >> /app/selfcheck.py"

# --- the seal is load-bearing --------------------------------------------------------------------------
flip "the seal is always zero" \
  "src = src.replace('_seal(\"%s/%d+%d\" % (spec[\"stream\"], kept, dropped))', '0')"
flip "the seal multiplier is off by one" \
  "src = src.replace('register = ((register ^ byte) * SEAL_MULT) % SEAL_MOD', 'register = ((register ^ byte) * (SEAL_MULT + 1)) % SEAL_MOD')"
flip "the seal modulus is off by one" \
  "src = src.replace('register = ((register ^ byte) * SEAL_MULT) % SEAL_MOD', 'register = ((register ^ byte) * SEAL_MULT) % (SEAL_MOD + 1)')"
flip "the seal starting register is off by one" \
  "src = src.replace('register = SEAL_SEED', 'register = SEAL_SEED + 1')"
flip "the seal uses a power of two modulus" \
  "src = src.replace('register = ((register ^ byte) * SEAL_MULT) % SEAL_MOD', 'register = ((register ^ byte) * SEAL_MULT) % (2 ** 32)')"
flip "the seal text swaps its two counts" \
  "src = src.replace('(spec[\"stream\"], kept, dropped)', '(spec[\"stream\"], dropped, kept)')"
flip "the seal is emitted on every stream" \
  "src = src.replace('if blanks:', 'if True:')"
flip "the seal fires on dropped samples rather than on an empty edit" \
  "src = src.replace('if blanks:', 'if dropped:')"
flip "an implicit edit list is counted as holding an empty edit" \
  "src = src.replace('(track.get(\"edits\") or [])', 'track.get(\"edits\", [{\"start\": -1}])')"

# --- the empty edit is load-bearing --------------------------------------------------------------------
flip "an empty edit is skipped entirely, clock and all" \
  "src = src.replace('        if begin >= 0:', '        if begin < 0:\n            continue\n        if True:')"
flip "an empty edit presents media from zero" \
  "src = src.replace('if begin >= 0:', 'if True:')"
flip "only presenting edits advance the clock" \
  "src = src.replace('        clock += span', '        if begin >= 0:\n            clock += span')"
flip "the clock advances by the media covered rather than the edit duration" \
  "src = src.replace('clock += span', 'clock += span if begin >= 0 else 0')"

# --- the window and the claim rules are load-bearing ---------------------------------------------------
flip "the window is closed at its end" \
  "src = src.replace('begin <= media_start < begin + span', 'begin <= media_start <= begin + span')"
flip "the window is open at its start" \
  "src = src.replace('begin <= media_start < begin + span', 'begin < media_start < begin + span')"
flip "the last edit claims a sample rather than the first" \
  "src = src.replace('if index in placed:', 'if False:')"
flip "a sample is placed by where it ends rather than where it starts" \
  "src = src.replace('for index, media_start in enumerate(starts):', 'for index, media_start in enumerate(starts[1:] + [sum(track[\"samples\"])]):')"
flip "the offset within the edit is dropped" \
  "src = src.replace('placed[index] = clock + (media_start - begin)', 'placed[index] = clock')"
flip "a track with no edits presents nothing" \
  "src = src.replace('edits = track.get(\"edits\") or [{\"start\": 0, \"duration\": sum(track[\"samples\"])}]', 'edits = track.get(\"edits\") or []')"

# --- the media timeline and the conversion are load-bearing --------------------------------------------
flip "sample starts are shifted by one sample" \
  "src = src.replace('        out.append(running)\n        running += duration', '        running += duration\n        out.append(running)')"
flip "milliseconds truncate instead of rounding" \
  "src = src.replace('    if 2 * rest > timescale or (2 * rest == timescale and whole & 1):\n        whole += 1\n', '')"
flip "a half rounds away from zero rather than to even" \
  "src = src.replace('2 * rest > timescale or (2 * rest == timescale and whole & 1)', '2 * rest >= timescale')"
flip "the conversion uses seconds rather than milliseconds" \
  "src = src.replace('divmod(units * 1000, timescale)', 'divmod(units, timescale)')"
flip "a dropped sample is reported as kept" \
  "src = src.replace('\\\\t-\\\\tdropped', '\\\\t0\\\\tkept')"
flip "the two summary counts are swapped" \
  "src = src.replace('summary = \"*\\\\t%d\\\\t%d\" % (kept, dropped)', 'summary = \"*\\\\t%d\\\\t%d\" % (dropped, kept)')"
flip "tracks are reported in reverse order" \
  "src = src.replace('for track in spec[\"tracks\"]:', 'for track in reversed(spec[\"tracks\"]):')"

echo
printf '\n%d ok, %d failed\n' "$PASS" "$FAIL"
[ "$FAIL" = 0 ]
