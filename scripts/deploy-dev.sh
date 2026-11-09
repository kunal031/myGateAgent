#!/usr/bin/env bash
# Deploy the dev stage.
#
# Secrets are read from backend/.env rather than passed on the command
# line, so they do not land in shell history. --no-confirm-changeset
# because this script is the review step; run `sam deploy` without it if
# you want to inspect the changeset first.
#
# A fresh JwtSecret is generated per run. That signs out any existing dev
# session, which is correct for a dev stage and must NOT be copied to
# prod: sharing a secret between stages means a token minted in dev is
# valid in production.
set -euo pipefail

cd "$(dirname "$0")/.."

ENV_FILE=backend/.env
read_env() { grep "^$1=" "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"'; }

NEON=$(read_env NEON_DATABASE_URL)
GEMINI=$(read_env GEMINI_API_KEY)
GCID=$(read_env GOOGLE_CLIENT_ID)
GCSECRET=$(read_env GOOGLE_CLIENT_SECRET)
FALLBACK=$(read_env FALLBACK_API_KEY)

if [ -z "$NEON" ]; then
  echo "NEON_DATABASE_URL is empty in $ENV_FILE" >&2
  exit 1
fi
case "$NEON" in
  *-pooler*) ;;
  *) echo "NEON_DATABASE_URL has no '-pooler' in its hostname." >&2
     echo "Lambda opens a connection per invocation; the direct endpoint" >&2
     echo "exhausts max_connections under load." >&2
     exit 1 ;;
esac

JWT=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')

# The redirect URI contains the API's own id, which does not exist until
# the stack does. Read it back from the previous deploy when there is
# one, so a second run wires Google sign-in without being told the URL.
# Empty on the very first deploy, which is why startup_checks only
# refuses when the Google client id and secret are also set.
REDIRECT=$(aws cloudformation describe-stacks   --stack-name gateai-dev --region ap-southeast-1   --query "Stacks[0].Outputs[?OutputKey=='GoogleRedirectUri'].OutputValue"   --output text 2>/dev/null || true)
[ "$REDIRECT" = "None" ] && REDIRECT=""
if [ -n "$REDIRECT" ]; then
  echo "google redirect: $REDIRECT"
else
  echo "google redirect: not yet known (first deploy); re-run after this one"
fi

# build-lambda.sh stages one source tree per function and ends with
# `sam build --use-container`, which is the part that must not be
# skipped: a plain `sam build` on this Mac picks macOS arm64 wheels,
# which import fine here and fail on Lambda.
echo "staging and building..."
scripts/build-lambda.sh

sam deploy \
  --stack-name gateai-dev \
  --region ap-southeast-1 \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --no-confirm-changeset \
  --no-fail-on-empty-changeset \
  --parameter-overrides \
    Stage=dev \
    AlertEmail=kunalraj0531@gmail.com \
    NeonDatabaseUrl="$NEON" \
    JwtSecret="$JWT" \
    GeminiApiKey="$GEMINI" \
    GoogleClientId="$GCID" \
    GoogleClientSecret="$GCSECRET" \
    FallbackApiKey="$FALLBACK" \
    GoogleRedirectUri="$REDIRECT" \
    FrontendOrigin=https://gateai-one.vercel.app
