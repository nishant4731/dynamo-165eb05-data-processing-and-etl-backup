#!/bin/bash
#
# Runs inside the SHARED environment image (environment/Dockerfile) — canonical TB2 has no separate
# verifier image. pytest is baked in at build time, so nothing is installed here.
#
# `python3 -I -m pytest` rather than plain pytest: -m prepends the working directory to sys.path, and the
# agent's WORKDIR is the writable /app, so a planted /app/pytest.py would otherwise shadow the pytest
# package itself and force exit 0. -I drops cwd and the script directory while keeping site-packages, so
# the real pytest still resolves.
python3 -I -m pytest --ctrf /logs/verifier/ctrf.json /tests/test_outputs.py -rA
status=$?

# Reward comes from pytest's own status over assertions against the trusted resolver, never from anything
# the submission controls.
if [ $status -eq 0 ]; then
  echo 1 > /logs/verifier/reward.txt
else
  echo 0 > /logs/verifier/reward.txt
fi
exit 0
