#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
node --version >/dev/null
npm --version >/dev/null
echo "Bootstrap complete."
