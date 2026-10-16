#!/usr/bin/env bash
# Run the full vision ingest unattended.
#
# Stops cleanly when the daily quota runs out, so running it on consecutive
# nights continues from where it stopped: transcribed pages are cached per
# page and ingested files are skipped.
#
#   ./app/cli/overnight.sh          # from backend/
#   tail -f data/overnight.log      # watch progress

set -u
cd "$(dirname "${BASH_SOURCE[0]}")/../.." || exit 1

LOG="data/overnight.log"
echo "=== started $(date) ===" >> "$LOG"
./venv/bin/python -m app.cli.build_corpus >> "$LOG" 2>&1
echo "=== finished $(date) ===" >> "$LOG"

echo "Done. Summary:"
tail -8 "$LOG"
