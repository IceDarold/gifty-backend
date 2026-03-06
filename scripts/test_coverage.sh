#!/usr/bin/env bash
set -euo pipefail

python3 -m pytest \
  -m "not ai_test" \
  --cov \
  --cov-config=.coveragerc \
  --cov-report=term-missing:skip-covered \
  --cov-fail-under=95
