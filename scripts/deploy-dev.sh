#!/usr/bin/env bash
# Deploy the dev stage.
#
# Secrets are read from backend/.env rather than passed on the command
# line, so they do not land in shell history. --no-confirm-changeset
# because this script is the review step; run `sam deploy` without it if
# you want to inspect the changeset first.
#
# JwtSecret is read back from the running function and only generated on
# a first deploy, so redeploying does not sign you out. Each stage must
# still have its own: sharing a secret between stages means a token
# minted in dev is valid in production.
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

# Reuse the secret the stack is already running with, and generate one
# only on the first deploy.
#
# This used to mint a fresh secret every run. That was defensible when
# the script was for standing a dev stage up, but it signs every session
# out on each redeploy -- including the Google sign-in you are about to
# test -- which turns an ordinary config change into "I have to log in
# again, did I break auth?". Rotating is still one command when it is
# actually wanted:
#
#   sam deploy ... --parameter-overrides JwtSecret=$(python3 -c \
#     'import secrets; print(secrets.token_urlsafe(48))')
JWT=$(aws lambda get-function-configuration \
  --function-name gatemaster-api-dev --region ap-southeast-1 \
  --query "Environment.Variables.JWT_SECRET" --output text 2>/dev/null || true)
if [ -z "$JWT" ] || [ "$JWT" = "None" ]; then
  JWT=$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')
  echo "jwt secret: generated (first deploy)"
else
  echo "jwt secret: reusing the deployed one, so sessions survive"
fi

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
