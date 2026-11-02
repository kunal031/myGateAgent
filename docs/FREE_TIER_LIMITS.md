# Staying inside the Lambda free tier

The free tier is **1,000,000 requests and 400,000 GB-seconds per month**,
always free, for new and existing accounts
([AWS](https://aws.amazon.com/free/serverless)).

Both halves matter, and the second one is the trap.

## Why a 1M request cap is not the right target

GB-seconds = memory × duration. Measured on this codebase, importing the
app costs ~0.65–0.85s, so a cold start is ~0.9s of billed time:

| Memory | Cold start cost | GB-seconds exhausted at |
|---|---|---|
| 1024 MB (old default) | 0.90 GB-s | **~490,000 requests** |
| 512 MB (now) | 0.45 GB-s | ~980,000 requests |

A denial-of-service causes *mass cold starts* — every concurrent request
that finds no warm container pays the init. At 1024 MB the GB-second half
of the free tier would have run out at under half the request allowance.

Two consequences, both applied in `template.yaml`:

- `ApiFunction` is **512 MB**, not 1024. These routes wait on Postgres
  and Gemini, so the proportionally slower CPU costs almost nothing.
- `MonthlyRequestBudget` defaults to **700,000**, not 1,000,000, so the
  alarm fires while there is still allowance left under both limits.

## The layers, and what each one actually guarantees

| Layer | Mechanism | Guarantee |
|---|---|---|
| Per-IP throttle | `app/core/throttle.py` middleware | Stops **one** caller. Spoofable; one budget per source |
| Gateway throttle | `DefaultRouteSettings` 20 rps / 40 burst | **Best-effort** — AWS's own word. Stops a burst |
| Reserved concurrency | `ApiReservedConcurrency` = 10 | **Enforced** by Lambda. Caps the *rate of spend* |
| Spike alarm → kill switch | CloudWatch → SNS → `lambda_killswitch` | **The hard stop.** Concurrency to 0 in ~1–5 min |
| Budget alert | AWS Budgets, $1 | Notification only. Cost data lags 8–24 h |

### Be clear about what cannot be guaranteed

No configuration caps requests at exactly 1M/month. Ten concurrent
executions answering in 60ms could in principle serve 432M requests in a
month. 20 rps sustained for 30 days is 51.8M. The arithmetic that keeps a
*full month* inside the free tier is about **0.39 requests/second** —
below any throttle you would want on a real app.

So the design is: throttles and concurrency bound how fast money can be
spent, and the **alarm-driven kill switch is what actually stops it**.
It runs off the Lambda `Invocations` metric, which CloudWatch publishes
within about a minute — not Cost Explorer, which would report the attack
a day after the allowance was gone.

The kill switch does not re-enable itself. An alarm cannot tell a
denial-of-service from a successful launch, so recovery is a human
decision.

## Deploying

```bash
sam build
sam deploy --guided \
  --parameter-overrides \
    AlertEmail=you@example.com \
    NeonDatabaseUrl='postgres://...-pooler...' \
    JwtSecret="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')"
```

`AlertEmail` is not optional in practice. Leave it empty and the alarms,
the budget **and the kill switch** are all created without a subscriber —
monitoring that looks present and reports nothing. Confirm the SNS
subscription email after the first deploy or no alert will arrive.

## When the alarm fires

1. **Confirm it is an attack, not growth.** The access log has the
   client IPs:
   ```bash
   aws logs tail /aws/http-api/gatemaster-prod --since 1h \
     | python -c "import sys,json,collections;c=collections.Counter(json.loads(l.split(None,2)[-1])['ip'] for l in sys.stdin if '{' in l);print(c.most_common(10))"
   ```
   One address dominating is an attack. Many addresses evenly spread is
   either a botnet or real traffic.

2. **Check what the month has cost so far:**
   ```bash
   aws cloudwatch get-metric-statistics --namespace AWS/Lambda \
     --metric-name Invocations --dimensions Name=FunctionName,Value=gatemaster-api-prod \
     --start-time "$(date -u -v-30d +%Y-%m-%dT%H:%M:%SZ)" \
     --end-time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
     --period 86400 --statistics Sum
   ```

3. **Re-enable when it is over:**
   ```bash
   aws lambda put-function-concurrency \
     --function-name gatemaster-api-prod --reserved-concurrent-executions 10
   ```

4. **If one or two IPs are responsible**, lower `RATE_LIMIT_PER_IP`
   (default 120/min) and redeploy. There is no IP blocklist here: AWS WAF
   is the right tool for that and **cannot be attached to an HTTP API**
   — its supported resources are CloudFront, REST API, ALB, AppSync,
   Cognito and App Runner
   ([AWS](https://docs.aws.amazon.com/waf/latest/developerguide/waf-chapter.html)).
   Gaining WAF means fronting the API with CloudFront, which costs about
   $6/month in web ACL fees and defeats the point of the free tier.

## Redis and the per-IP counter

With `REDIS_URL` set, the per-IP counter is shared and exact. Without it
the counter is per-container, so ten concurrent Lambdas each allow the
full budget — a factor-of-ten leak rather than no limit at all. That is
an acceptable default: it costs nothing, and the gateway throttle and
reserved concurrency sit underneath it either way.
