# Deploying gate.ai

Current state: `main` has everything merged, Neon holds the full corpus
(2,304 questions, 1,294 cards, 25,074 embeddings, stamped at Alembic head
`4208968c1b90`). What remains is the AWS side, which needs your
credentials and so has to be run by you.

## 1. Install the two missing CLIs

Neither is present on this machine:

```bash
brew install aws-sam-cli awscli
aws configure            # access key, secret, region: ap-southeast-1
```

Use **ap-southeast-1** (Singapore) — your Neon compute is there
(`...c-4.ap-southeast-1.aws.neon.tech`). Deploying Lambda to another
region adds a cross-region round trip to every query. Measured from this
machine the Neon round trip is 300–1800 ms per request; in-region it is a
few milliseconds, and that difference is also GB-seconds.

## 2. Deploy to a dev stage first

Nobody has ever run `sam build` on this stack, and until this week the
template had `Timeout`, `Environment`, `Policies` and `Events` nested
under `Metadata:` where CloudFormation ignored them. That is fixed, but
unproven against real AWS. Do not make prod the first attempt.

```bash
cd /Users/kunal/Desktop/Projects/GateMaster

sam build

sam deploy --guided \
  --stack-name gateai-dev \
  --region ap-southeast-1 \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    Stage=dev \
    AlertEmail='priyanshuraj9595@gmail.com' \
    NeonDatabaseUrl="$(grep '^NEON_DATABASE_URL=' backend/.env | cut -d= -f2-)" \
    JwtSecret="$(python3 -c 'import secrets;print(secrets.token_urlsafe(48))')" \
    GeminiApiKey="$(grep '^GEMINI_API_KEY=' backend/.env | cut -d= -f2- | tr -d '\"')" \
    GoogleClientId="$(grep '^GOOGLE_CLIENT_ID=' backend/.env | cut -d= -f2-)" \
    GoogleClientSecret="$(grep '^GOOGLE_CLIENT_SECRET=' backend/.env | cut -d= -f2-)" \
    FrontendOrigin='http://localhost:3000'
```

**Generate a new `JwtSecret` for each stage.** Sharing the local one
means a token minted on your laptop is valid in production.

### Confirm the SNS email

After the first deploy AWS sends a subscription confirmation to
`AlertEmail`. **Click it.** Until you do, the alarms, the budget *and the
kill switch* exist with no subscriber — monitoring that looks present and
does nothing. This is the single easiest way to end up with a bill.

## 3. Smoke-test the stage

```bash
API=$(aws cloudformation describe-stacks --stack-name gateai-dev \
  --region ap-southeast-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' --output text)

curl -s "$API/api/health"              # {"status":"ok","app":"gate.ai",...}
curl -s -o /dev/null -w '%{http_code}\n' "$API/api/syllabus"   # expect 401
```

`401` on `/api/syllabus` is the correct answer — it proves the auth
guards survived deployment. A `200` would mean the stage is serving the
corpus publicly.

Then sign in through the frontend and confirm the feed loads.

## 4. Google OAuth redirect

The template sets `GOOGLE_REDIRECT_URI` to the deployed API URL. Add that
exact URL to **Authorised redirect URIs** in the Google Cloud console —
byte for byte, or Google refuses with `redirect_uri_mismatch`:

```
https://<api-id>.execute-api.ap-southeast-1.amazonaws.com/api/auth/google/callback
```

## 5. Promote to prod

Same command with `Stage=prod`, `--stack-name gateai-prod`, a fresh
`JwtSecret`, and `FrontendOrigin` set to the real frontend origin.

## 6. Frontend

The backend is on Lambda; the Next.js app still needs hosting. Vercel is
the least work and has a free tier:

```bash
cd frontend
npx vercel --prod   # set NEXT_PUBLIC_API_URL to the deployed API URL
```

`NEXT_PUBLIC_API_URL` is inlined at **build** time, so changing it later
needs a rebuild, not just an env var change. And set `FrontendOrigin` on
the stack to the Vercel URL or CORS will block the browser.

## Things that are deliberately not configured

**Redis.** `REDIS_URL` is empty on Lambda, so caching disables itself and
the per-IP throttle counter becomes per-container — a factor-of-ten leak,
not a breach. The gateway throttle and reserved concurrency sit
underneath either way. Upstash has a free tier if you want it exact;
`docs/FREE_TIER_LIMITS.md` explains the trade.

**Alembic on deploy.** Lambda runs with `lifespan="off"`, so
`init_database()` never fires and migrations do not run on boot. Neon is
already at head. For future changes:

```bash
cd backend && DB_TARGET=neon ./venv/bin/alembic -c alembic.ini upgrade head
```

Run that **before** deploying code that needs the new column.

**An Android APK.** There is no React Native project in this repository —
only the Next.js web app. `frontend/src/lib/client/` is deliberately free
of `window` and `localStorage` so a native app can import it unchanged,
and its README has the twenty lines of storage adapter needed. But the
app itself (15 screens, navigation, an Android SDK toolchain) does not
exist yet and is days of work, not a deploy step.

## If the free-tier alarm fires

See `docs/FREE_TIER_LIMITS.md`. Short version: the kill switch sets the
API's reserved concurrency to 0 within about a minute, and re-enabling is
a deliberate human step:

```bash
aws lambda put-function-concurrency \
  --function-name gateai-api-prod --reserved-concurrent-executions 10
```
