#!/usr/bin/env bash
# Stage a clean source tree per function, then build.
#
# Two problems this solves.
#
# **CodeUri cannot point at backend/.** SAM copies that whole directory,
# and backend/data/ is 3.1 GB of corpus, OCR cache and vectors, which
# made every artifact 3.2 GB against Lambda's 250 MB unzipped limit.
# .samignore does not help: SAM applies it when packaging the upload,
# not when copying CodeUri.
#
# **Each function needs its own dependency set.** SAM's --manifest flag
# is global, so a single staged tree forced every function to install
# the worker's list. That put pymupdf (54 MB), Pillow and lxml into the
# API package, where no request path imports them -- papers.py imports
# pymupdf lazily inside the upload handler, so the API only needs it
# when a PDF actually arrives, and that route is better served by
# handing the file to the worker. Unpacking those megabytes is what
# made the API's first request take ~17 s while Lambda's own init was
# ~70 ms.
#
# Staging one directory per function, each with its own
# requirements.txt, lets SAM use the default manifest name and gives
# each function only what it imports.
set -euo pipefail

cd "$(dirname "$0")/.."

stage() {
  local name=$1 manifest=$2
  local dir="build/lambda-$name"
  rm -rf "$dir"
  mkdir -p "$dir"
  cp -R backend/app "$dir/app"
  # The default manifest name, so no --manifest flag is needed.
  cp "backend/$manifest" "$dir/requirements.txt"
  find "$dir" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
  find "$dir" -name '*.pyc' -delete 2>/dev/null || true
  echo "  staged $name: $(du -sh "$dir" | cut -f1)"
}

# The worker manifest is `-r requirements-lambda.txt` plus pymupdf,
# lxml, Pillow and beautifulsoup4, so it has to resolve that relative
# include from its own directory.
stage api       requirements-lambda.txt
stage worker    requirements-lambda-worker.txt
cp backend/requirements-lambda.txt build/lambda-worker/
stage killswitch requirements-lambda-killswitch.txt

# --use-container so the wheels are manylinux aarch64 rather than the
# macOS arm64 ones pip would pick on this host.
sam build --use-container "$@"
