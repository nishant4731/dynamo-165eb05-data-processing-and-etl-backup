"""Grade /app/mux/mux.py against the trusted MUX-1 resolver.

At verify time this process inherits the agent's own /app on its import path, so that goes first, before
anything shadowable is imported.

How the submission is exercised: one unprivileged child resolves every staged stream and writes a single
plain-text transcript, each answer framed by the neutral label its stream was staged under. Reading a
transcript rather than an exit status is what makes a bad stream cheap — the child records its own failures
into the frame, so a stream that raises is that stream's failure and the rest are still judged.
"""
import sys

sys.path[:] = [where for where in sys.path
               if where not in ("", ".", "/app") and not where.startswith("/app/")]

import hashlib                                                                        # noqa: E402
import json                                                                           # noqa: E402
import os                                                                             # noqa: E402
import pathlib                                                                        # noqa: E402
import random                                                                         # noqa: E402
import shutil                                                                         # noqa: E402
import subprocess                                                                     # noqa: E402
import tempfile                                                                       # noqa: E402

import pytest                                                                         # noqa: E402

sys.path.insert(0, "/tests/_trusted")
import corpus                                                                         # noqa: E402
import model                                                                          # noqa: E402

APP = pathlib.Path("/app")
GRADED_FILE = APP / "mux" / "mux.py"
VAULT = pathlib.Path("/tests/_trusted")
NOBODY = 65534
CHILD_SECONDS = 120
STREAMS = corpus.SAMPLE_SPECS + corpus.GRADED_SPECS

OPENS = "@"          # a frame header, followed by the stream's neutral label
CLOSES = "."         # a line of its own, ending the frame
RAISED = "!"         # in place of a frame's body when resolve() blew up

# The child is launched with `python3 -I`, so it inherits no import path and names the two directories it
# needs: the deliverable's own, then /app — instruction.md permits helper modules there, and a permission
# the verifier quietly declines to honour would fail a submission that believed the brief.
WORKER = r'''
import os, sys, traceback
sys.path.insert(0, "/app/mux")
sys.path.insert(1, "/app")
import mux

stage, transcript = sys.argv[1], sys.argv[2]
with open(transcript, "w") as out:
    for label in sorted(os.listdir(stage)):
        out.write("@" + label + "\n")
        try:
            answer = list(mux.resolve(os.path.join(stage, label)))
            if not all(isinstance(line, str) for line in answer):
                raise TypeError("resolve returned something other than strings")
        except Exception:
            out.write("!" + type(sys.exc_info()[1]).__name__ + "\n")
            out.write(".\n")
            continue
        for line in answer:
            out.write(" " + line + "\n")
        out.write(".\n")
'''


def _drop_to_nobody():
    """Become nobody irrevocably before exec. setres* leaves no saved id to climb back to."""
    if os.geteuid():
        return
    os.setgroups([])
    os.setresgid(NOBODY, NOBODY, NOBODY)
    os.setresuid(NOBODY, NOBODY, NOBODY)


def _vault_is_sealed():
    """Try, as nobody, to read the one file that would give the answers away. Fail closed on anything odd."""
    attempt = ("import sys\n"
               "try:\n"
               "    open(%r).read(1)\n"
               "except PermissionError:\n"
               "    sys.exit(11)\n"
               "except Exception:\n"
               "    sys.exit(12)\n"
               "sys.exit(0)\n") % str(VAULT / "model.py")
    ran = subprocess.run([sys.executable, "-I", "-c", attempt], preexec_fn=_drop_to_nobody,
                         capture_output=True, env={"PATH": "/usr/bin:/bin", "PYTHONPATH": ""})
    return ran.returncode in (11, 12)


def _parse(transcript, labels):
    """Split the transcript back into one answer per label. A frame that never closed is not an answer."""
    found, label, body, raised = {}, None, [], False
    for line in transcript.splitlines():
        if line.startswith(OPENS):
            label, body, raised = line[1:], [], False
        elif label is None:
            continue
        elif line.startswith(RAISED):
            raised = True
        elif line == CLOSES:
            found[label] = None if raised else body
            label = None
        elif line.startswith(" "):
            body.append(line[1:])
    return {spec["stream"]: found.get(label) for label, spec in labels.items()}


@pytest.fixture(scope="session")
def transcript():
    """Run the submission over every stream once, and hand each test the same parsed answers."""
    VAULT.chmod(0o700)
    assert _vault_is_sealed(), "an unprivileged process can read the trusted corpus"

    # The child reads the deliverable as `nobody`, and a cache the agent's own runs left behind must never
    # be graded in place of the source it actually shipped.
    if GRADED_FILE.exists():
        GRADED_FILE.chmod(0o644)
    for old in APP.rglob("__pycache__"):
        shutil.rmtree(old, ignore_errors=True)

    workspace = pathlib.Path(tempfile.mkdtemp(prefix="mux-"))
    workspace.chmod(0o777)
    stage = workspace / "stage"
    stage.mkdir()
    stage.chmod(0o755)

    # Neutral labels in a seeded order: reproducible run to run, and telling the child nothing about which
    # stream it is looking at or where the corpus keeps it.
    plan = list(zip(["s%02d" % n for n in range(len(STREAMS))], STREAMS))
    random.Random(165).shuffle(plan)
    for label, spec in plan:
        room = stage / label
        room.mkdir()
        (room / "stream.json").write_text(json.dumps(spec, indent=2) + "\n")
        room.chmod(0o755)
        (room / "stream.json").chmod(0o644)
    labels = dict(plan)

    worker = workspace / "worker.py"
    worker.write_text(WORKER)
    worker.chmod(0o644)
    written = workspace / "transcript.txt"

    try:
        subprocess.run([sys.executable, "-I", str(worker), str(stage), str(written)],
                       preexec_fn=_drop_to_nobody, capture_output=True, timeout=CHILD_SECONDS,
                       cwd=str(workspace), env={"PATH": "/usr/bin:/bin", "PYTHONPATH": ""})
    except subprocess.TimeoutExpired:
        pass                                    # a submission that never finishes leaves a partial file
    text = written.read_text() if written.exists() else ""

    VAULT.chmod(0o755)
    answers = _parse(text, labels)
    shutil.rmtree(workspace, ignore_errors=True)
    return answers


def test_the_shipped_inputs_were_not_edited():
    """A run must never be graded against the agent's own version of the contract or the published pairs."""
    pinned = json.loads(pathlib.Path("/tests/input_hashes.json").read_text())
    touched = [name for name, digest in sorted(pinned.items())
               if hashlib.sha256((APP / name).read_bytes()).hexdigest() != digest]
    assert not touched, "these shipped files changed during the run: %s" % touched


def test_everything_graded_is_contained_under_app():
    """Four separate ways a submission could point grading at code outside /app, reported by name."""
    complaints = []
    if not GRADED_FILE.is_file():
        complaints.append("the deliverable is missing")
    if GRADED_FILE.is_symlink():
        complaints.append("the deliverable is itself a symlink")
    step = GRADED_FILE.parent
    while step != step.parent and step != APP:
        if step.is_symlink():
            complaints.append("a parent directory is a symlink: %s" % step)
        step = step.parent
    if GRADED_FILE.exists() and not str(GRADED_FILE.resolve()).startswith(str(APP) + os.sep):
        complaints.append("the deliverable resolves outside /app: %s" % GRADED_FILE.resolve())
    wandering = sorted(str(found) for found in APP.rglob("*") if found.is_symlink())
    if wandering:
        complaints.append("symlinks under /app: %s" % wandering)
    assert not complaints, "; ".join(complaints)


def test_the_pairs_file_answers_no_graded_stream():
    """A published canonical text belonging to a graded stream would reduce the seal to a lookup."""
    shared = sorted(corpus.GRADED_SEAL_TEXTS & set(corpus.PUBLISHED))
    assert not shared, "these graded canonical texts are published: %s" % shared


def test_the_disclosed_seal_fold_reproduces_every_published_pair():
    """SPEC.md names the byte-wise fold; the published pairs must all agree with that fold under model.seal."""
    pairs = {}
    for line in (APP / "data" / "SEALS.txt").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            text, value = line.rsplit(None, 1)
            pairs[text] = int(value)
    bad = sorted(text for text, value in pairs.items() if model.seal(text) != value)
    assert not bad, "published pairs disagree with the disclosed fold: %s" % bad[:5]


def test_the_transcript_is_not_empty(transcript):
    """Say once that the module never ran, instead of repeating it for all fifty-one streams."""
    assert any(lines is not None for lines in transcript.values()), \
        "no frame in the transcript holds an answer — the submission did not import, or never resolved"


@pytest.mark.parametrize("spec", STREAMS, ids=[entry["stream"] for entry in STREAMS])
def test_each_stream_resolves_exactly(transcript, spec):
    """The whole listing, in order, with the summary and its seal as the final line."""
    wanted = model.resolve(spec)
    given = transcript[spec["stream"]]
    assert given is not None, "the submission produced no listing for this stream"
    if given == wanted:
        return
    parting = next((n for n, pair in enumerate(zip(given, wanted)) if pair[0] != pair[1]), min(len(given), len(wanted)))
    raise AssertionError("listing parts at line %d of %d: got %r, wanted %r"
                         % (parting, len(wanted),
                            given[parting] if parting < len(given) else "<nothing>",
                            wanted[parting] if parting < len(wanted) else "<nothing>"))
