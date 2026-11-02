"""Set the API's reserved concurrency to zero.

The guardrail of last resort, and the only hard stop in the stack.

Everything else bounds a rate, not a month. API Gateway throttling is
"best-effort ... targets rather than guaranteed request ceilings" by
AWS's own documentation. Reserved concurrency is enforced, but 10
concurrent executions can still produce far more than a million requests
in a month if something hammers them continuously. And AWS Budgets reacts
to cost data that lags 8-24 hours, by which time a free tier is long
gone.

So: a CloudWatch alarm on the Lambda Invocations metric -- published
within about a minute -- fires an SNS message, and this function turns
the API off by setting its reserved concurrency to 0. Lambda then
rejects every invocation with a throttle, which costs nothing.

This is deliberately not automatic recovery. Turning the API back on is
a human decision, because the alarm cannot tell a denial-of-service from
a launch. Re-enable with:

    aws lambda put-function-concurrency \\
        --function-name <name> --reserved-concurrent-executions 10

The API being off is a visible outage, which is the intended trade: the
alternative is a bill. A free-tier project should fail closed.
"""

import json
import logging
import os

logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


def handler(event, _context):
    """SNS alarm -> reserved concurrency 0 on the protected function."""
    import boto3

    target = os.environ.get("PROTECTED_FUNCTION_NAME", "")
    if not target:
        logger.error("killswitch: PROTECTED_FUNCTION_NAME is not set")
        return {"disabled": False, "reason": "no target configured"}

    # Logged in full: this is the record of why the API was turned off,
    # and the alarm's own reason is the only evidence of what happened.
    for record in event.get("Records", []):
        try:
            message = json.loads(record["Sns"]["Message"])
            logger.warning(
                "killswitch: alarm=%s reason=%s",
                message.get("AlarmName"), message.get("NewStateReason"),
            )
        except (KeyError, ValueError):
            logger.warning("killswitch: fired by %s", record.get("EventSource"))

    client = boto3.client("lambda")
    try:
        client.put_function_concurrency(
            FunctionName=target,
            ReservedConcurrentExecutions=0,
        )
    except Exception:  # noqa: BLE001 - log and surface, never silently pass
        logger.exception("killswitch: could not disable %s", target)
        raise

    logger.warning(
        "killswitch: %s is now at zero concurrency and is serving nothing. "
        "Re-enable with: aws lambda put-function-concurrency "
        "--function-name %s --reserved-concurrent-executions 10",
        target, target,
    )
    return {"disabled": True, "function": target}
