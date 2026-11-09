#!/usr/bin/env bash
# Smoke test for the image. image-check passes the image tag as $1.
set -euo pipefail
image=$1

# Importing the app factory loads every runtime dependency, including the compiled wheels
# (pydantic-core, uvloop, httptools, cryptography), on the slim base's interpreter.
docker run --rm "$image" python -c "from src.main import build_app_from_env"

echo "smoke ok"
