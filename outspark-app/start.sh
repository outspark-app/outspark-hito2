#!/bin/sh
set -eu
cd "$(dirname "$0")"
python3 scripts/flutter_project.py build --demo --api http://127.0.0.1:18080/api --landing http://127.0.0.1:5177/
exec python3 scripts/serve_flutter.py
