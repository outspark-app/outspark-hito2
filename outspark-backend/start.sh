#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then
  python3.12 -m venv .venv
fi
.venv/bin/python -m pip install -r requirements-dev.txt
exec .venv/bin/python -m outspark.local --prepare
