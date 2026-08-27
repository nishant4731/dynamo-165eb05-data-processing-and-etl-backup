#!/bin/bash
# The reference solution: drop the corrected resolver into place. Nothing else — no network, no reliance
# on anything under /tests, and the recovery helper is not run here (it exists so a reviewer can confirm
# the seal's constants come out of the published pairs alone).
set -e
install -m 0644 /solution/mux.py /app/mux/mux.py
