#!/usr/bin/env bash
# Stage a clean Lambda source tree, then build it.
#
# CodeUri cannot point at backend/: SAM copies that whole directory, and
# backend/data/ is 3.1 GB of corpus, OCR cache and vectors. That made
# every artifact 3.2 GB against Lambda's 250 MB unzipped limit.
# .samignore does not help -- SAM applies it when packaging the upload,
# not when copying CodeUri. So the source is staged here instead, and it
# comes to about 1 MB.
#
# requirements.txt in the staged tree is a copy of the WORKER manifest,
# which is `-r requirements-lambda.txt` plus pymupdf, lxml, Pillow and
# beautifulsoup4. SAM's --manifest flag is global rather than per
# function, so both functions get this set; building with the API's
# narrower list would leave the worker unable to read a PDF. Naming it
# requirements.txt means no flag is needed at all.
set -euo pipefail

cd "$(dirname "$0")/.."

rm -rf build/lambda-src
mkdir -p build/lambda-src

cp -R backend/app build/lambda-src/app
cp backend/requirements-lambda.txt build/lambda-src/
cp backend/requirements-lambda-worker.txt build/lambda-src/
cp backend/requirements-lambda-killswitch.txt build/lambda-src/
cp backend/requirements-lambda-worker.txt build/lambda-src/requirements.txt

find build/lambda-src -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
find build/lambda-src -name '*.pyc' -delete 2>/dev/null || true

echo "staged $(du -sh build/lambda-src | cut -f1) of source"

# --use-container so the wheels are manylinux aarch64 rather than the
# macOS arm64 ones pip would pick on this host.
sam build --use-container "$@"
