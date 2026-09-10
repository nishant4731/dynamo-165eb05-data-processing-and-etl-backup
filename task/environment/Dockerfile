# The single container image — built for BOTH the agent run and the verifier (canonical
# TB2: there is no separate verifier image). Install every system dependency the task needs
# here, plus the verifier's deps (pytest). Never copy the reference or the trusted corpus into
# this image — Harbor overlays the verify-time tree at /tests only when grading, so ground
# truth stays out of the agent's reach.
#
# apt tips: don't pin apt versions (they go stale); run `apt-get update` before
# install; clean up with `rm -rf /var/lib/apt/lists/*` in the same RUN layer.
# Data: put input files in environment/data/ and copy them in (e.g. COPY data /app/data).
# Never put solution or test/ground-truth data here — the agent can read it.
FROM public.ecr.aws/docker/library/ubuntu:24.04@sha256:0d39fcc8335d6d74d5502f6df2d30119ff4790ebbb60b364818d5112d9e3e932

# Verifier deps, baked at BUILD time (pinned) so the verifier installs nothing at verify time.
RUN apt-get update && apt-get install -y --no-install-recommends python3 python3-pip \
    && pip install --no-cache-dir --break-system-packages pytest==8.4.1 pytest-json-ctrf==0.3.5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# The contract, the published seal pairs and the five worked streams the agent may read, plus the resolver
# it must repair and the self-check that replays those hosts. The reference and the trusted corpus are
# deliberately absent — Harbor overlays them at /tests only when grading, so they stay out of reach.
COPY data /app/data
COPY mux /app/mux
COPY selfcheck.py /app/selfcheck.py
