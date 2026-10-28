#!/usr/bin/env python3
"""Refuse deployment unless AWS confirms an active Free plan with credit.

This is a deployment preflight. The account's AWS Free plan provides the
no-charge protection; this script does not change billing settings or create
a spending cap on a Paid plan.
"""

import argparse
from datetime import datetime, timezone
import json
import math
import os
import re
import subprocess


def aws_json(profile, region, *arguments):
    result = subprocess.run(
        ["aws", "--profile", profile, "--region", region,
         "--no-cli-pager", "--output", "json", *arguments],
        env={**os.environ, "AWS_PAGER": ""},
        text=True, capture_output=True, check=True,
    )
    return json.loads(result.stdout) if result.stdout.strip() else {}


def validate_plan(plan, expected_account, minimum_credit=1):
    if plan.get("accountId") != expected_account:
        raise ValueError("AWS account does not match the intended deployment account")
    if plan.get("accountPlanType") != "FREE":
        raise ValueError("AWS has not confirmed the FREE account plan; deployment refused")
    if plan.get("accountPlanStatus") != "ACTIVE":
        raise ValueError("AWS Free plan is not ACTIVE; deployment refused")
    credit = plan.get("accountPlanRemainingCredits", {})
    amount = float(credit.get("amount", 0))
    if credit.get("unit") != "USD" or not math.isfinite(amount) or amount < minimum_credit:
        raise ValueError("AWS Free plan credit is unavailable or below the required reserve")
    expiry = datetime.fromisoformat(plan["accountPlanExpirationDate"].replace("Z", "+00:00"))
    if expiry <= datetime.now(timezone.utc):
        raise ValueError("AWS Free plan has expired; deployment refused")
    return plan


def assert_free_plan(profile, region, expected_account, minimum_credit=1):
    identity = aws_json(profile, region, "sts", "get-caller-identity")
    if identity.get("Account") != expected_account:
        raise ValueError("Authenticated AWS identity belongs to a different account")
    # Free Tier account-plan information is queried through its global endpoint.
    plan = aws_json(profile, "us-east-1", "freetier", "get-account-plan-state")
    return validate_plan(plan, expected_account, minimum_credit)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="neurograph-free")
    parser.add_argument("--region", default="eu-north-1")
    parser.add_argument("--expected-account", required=True)
    parser.add_argument("--minimum-credit", type=float, default=1)
    args = parser.parse_args()
    if not re.fullmatch(r"\d{12}", args.expected_account):
        parser.error("--expected-account must be the intended 12-digit AWS account ID")
    if not math.isfinite(args.minimum_credit) or args.minimum_credit < 1:
        parser.error("--minimum-credit must be at least 1 USD")
    try:
        plan = assert_free_plan(args.profile, args.region, args.expected_account, args.minimum_credit)
    except (subprocess.CalledProcessError, ValueError, KeyError, TypeError, OSError) as exc:
        raise SystemExit(f"Free-plan preflight failed. No deployment is authorized: {exc}") from exc
    print(json.dumps(plan, indent=2))


if __name__ == "__main__":
    main()
