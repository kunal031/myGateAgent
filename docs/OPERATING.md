# Running the deployed API

Dev stack, deployed 2026-11-04, account 547390850753, ap-southeast-1.

```
API        https://2ka56t1f86.execute-api.ap-southeast-1.amazonaws.com
stack      gateai-dev
functions  gatemaster-api-dev        512 MB   28 s
           gatemaster-worker-dev    2048 MB  900 s
           gatemaster-killswitch-dev 128 MB   30 s
database   Neon (ap-southeast-1), Alembic head 4208968c1b90
```

## Seeing it in the console

**Region matters.** Everything is in **ap-southeast-1 (Singapore)** — the
region picker is top right, and the consoles look empty if you are in the
wrong one.

| What you want | Where |
|---|---|
| The functions | Lambda → Functions → `gatemaster-api-dev` |
| Errors and print output | that function → **Monitor** → *View CloudWatch logs* |
| Deployment history, why a deploy failed | **CloudFormation** → Stacks → `gateai-dev` → **Events** |
| What exists and how it is wired | CloudFormation → `gateai-dev` → **Resources** |
| The URL and redirect URI | CloudFormation → `gateai-dev` → **Outputs** |
| Alarms | CloudWatch → Alarms (`gatemaster-dev-*`) |
| Who called what | CloudWatch → Log groups → `/aws/http-api/gatemaster-dev` |

CloudFormation Events is the one worth knowing. It is the per-resource
log of a deploy, and a failure there names the resource and the reason.
The Lambda console only shows functions after they exist.

From the terminal, which is usually faster:

```bash
# Is it up?
curl -s https://2ka56t1f86.execute-api.ap-southeast-1.amazonaws.com/api/health

# Live logs, including tracebacks
aws logs tail /aws/lambda/gatemaster-api-dev --region ap-southeast-1 --follow

# Errors only, last hour
aws logs tail /aws/lambda/gatemaster-api-dev --region ap-southeast-1 \
  --since 1h --filter-pattern ERROR

# What is deployed
aws cloudformation describe-stacks --stack-name gateai-dev \
  --region ap-southeast-1 --query 'Stacks[0].Outputs' --output table
```

## Making a change

### Backend code only (app/**)

```bash
./scripts/build-lambda.sh      # ~12 min: 3 functions, 209 MB each
./scripts/deploy-dev.sh        # ~3 min
curl -s $API/api/health        # confirm
```

`sam build` alone is not enough: `CodeUri` points at `build/lambda-src/`,
which `scripts/build-lambda.sh` assembles from `backend/app`. Running
`sam build` without it rebuilds whatever was staged last.

For a one-line change, `sam sync` is far quicker — it pushes code
straight to the function without a changeset:

```bash
./scripts/build-lambda.sh
sam sync --stack-name gateai-dev --region ap-southeast-1 --code
```

Use `sam sync --code` for dev only. It skips CloudFormation, so the
stack's record of itself drifts from reality.

### template.yaml

Same two commands — but **the rebuild is mandatory**, not optional.
`sam deploy` deploys `.aws-sam/build/template.yaml`, a *copy*. Editing
`template.yaml` and deploying without rebuilding silently ships the old
one; three deploys failed on this. To be sure:

```bash
rm -rf .aws-sam && ./scripts/build-lambda.sh
grep "the thing you just added" .aws-sam/build/template.yaml   # must match
./scripts/deploy-dev.sh
```

### A database change (new column, new table)

Alembic does **not** run on Lambda — `lambda_api.py` sets
`lifespan="off"`, so `init_database()` never fires. Migrate first, then
deploy, or the new code meets an old schema:

```bash
cd backend
./venv/bin/alembic revision -m "what changed"      # then edit it by hand
# autogenerate wants to DROP the HNSW and FTS indexes; see migrations/README
DB_TARGET=neon ./venv/bin/alembic -c alembic.ini upgrade head
cd .. && ./scripts/build-lambda.sh && ./scripts/deploy-dev.sh
```

### Frontend

Separate deployment; the backend is untouched.

```bash
cd frontend && npm run build
```

`NEXT_PUBLIC_API_URL` is inlined at **build** time, so pointing the app at
a different API means rebuilding, not just changing an env var. Set
`FrontendOrigin` on the stack to the frontend's origin too, or CORS
blocks the browser.

## Going to prod

The dev stack proves the template. Prod is the same command with a
different stack name, its own `JwtSecret` (never reuse dev's — a token
minted in dev would be valid in prod), and the real frontend origin.
Copy `scripts/deploy-dev.sh` to `deploy-prod.sh` and change
`--stack-name`, `Stage=prod` and `FrontendOrigin`.

## If something breaks

1. `aws logs tail /aws/lambda/gatemaster-api-dev --region ap-southeast-1 --since 15m`
   — a 500 from API Gateway says nothing; the traceback is here.
2. If a *deploy* failed, read CloudFormation → Events, not the logs. The
   failure names a resource and a reason.
3. A failed `CREATE` rolls the whole stack back, so a half-deployed state
   does not survive. A failed `UPDATE` rolls back to the previous
   working version.

## Rolling back

```bash
aws cloudformation cancel-update-stack --stack-name gateai-dev --region ap-southeast-1
```

Once an update has completed, CloudFormation has no "undo": redeploy the
previous commit.

```bash
git checkout <good-sha> -- template.yaml backend/app
./scripts/build-lambda.sh && ./scripts/deploy-dev.sh
```

## Things that will bite

**Cold starts are ~18 s.** 209 MB of dependencies, and Lambda recycles
idle containers, so the first request after a quiet spell is slow. Warm
is ~0.2 s. Neon's free tier also auto-suspends after about five minutes,
adding a database wake on top.

**Caching is off.** `REDIS_URL` is empty on Lambda, so `/api/health`
reports `cache: {enabled: false}` and the per-IP throttle counts
per-container rather than globally. Deliberate — the app degrades rather
than failing — but Upstash's free tier would fix both.

**Reserved concurrency is disabled.** This account's total Lambda
concurrency is 10 and AWS requires all 10 stay unreserved, so
`ApiReservedConcurrency` defaults to 0. The account limit is itself a
hard ceiling, so nothing is lost. When Service Quotas raises "Concurrent
executions", set the parameter and redeploy.

**Google sign-in needs the console.** The redirect URI must appear in
Google Cloud → Credentials → *Authorised redirect URIs*, byte for byte:

```
https://2ka56t1f86.execute-api.ap-southeast-1.amazonaws.com/api/auth/google/callback
```

## The kill switch

If invocations spike past the alarm threshold, a Lambda sets the API's
reserved concurrency to 0 and the API stops serving. That is the
intended trade: a free-tier project should fail closed rather than bill.

It does not re-enable itself, because an alarm cannot tell an attack
from a launch:

```bash
aws lambda put-function-concurrency --region ap-southeast-1 \
  --function-name gatemaster-api-dev --reserved-concurrent-executions 10
```

Alerts go to kunalraj0531@gmail.com (subscription confirmed).
