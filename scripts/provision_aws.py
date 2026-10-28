#!/usr/bin/env python3
"""Provision the defense server only on a verified, active AWS Free plan."""

import argparse
import json
from pathlib import Path
import subprocess
import time

from aws_free_plan import assert_free_plan, aws_json


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="neurograph-free")
    parser.add_argument("--region", default="eu-north-1")
    parser.add_argument("--expected-account", required=True)
    parser.add_argument("--stack-name", default="neurograph-defense")
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    def call(*arguments):
        return aws_json(args.profile, args.region, *arguments)

    def guard():
        return assert_free_plan(args.profile, args.region, args.expected_account, 10)

    plan = guard()
    kind = call("ec2", "describe-instance-types", "--instance-types", "m7i-flex.large")["InstanceTypes"][0]
    if kind.get("FreeTierEligible") is not True or kind["MemoryInfo"]["SizeInMiB"] < 8192:
        raise SystemExit("The required 8 GiB instance is not Free Tier eligible; provisioning refused")
    zones = call("ec2", "describe-instance-type-offerings", "--location-type", "availability-zone",
                 "--filters", "Name=instance-type,Values=m7i-flex.large")["InstanceTypeOfferings"]
    if not zones:
        raise SystemExit("The required Free Tier instance is unavailable in this region")
    zone = sorted(entry["Location"] for entry in zones)[0]
    template = "file://" + str(ROOT / "deploy/aws/stack.json")
    call("cloudformation", "validate-template", "--template-body", template)
    print(json.dumps({"plan": plan, "instance": "m7i-flex.large", "availability_zone": zone,
                      "template": str(ROOT / "deploy/aws/stack.json")}, indent=2), flush=True)
    if not args.apply:
        return

    try:
        stack = call("cloudformation", "describe-stacks", "--stack-name", args.stack_name)["Stacks"][0]
    except subprocess.CalledProcessError as exc:
        if "does not exist" not in (exc.stderr or ""):
            raise
        stack = None
    if stack is not None:
        tags = {tag["Key"]: tag["Value"] for tag in stack.get("Tags", [])}
        if tags.get("Project") != "NeuroGraph-DB":
            raise SystemExit("An unrelated stack already uses this name; provisioning refused")
    else:
        guard()
        result = call("cloudformation", "create-stack", "--stack-name", args.stack_name,
                      "--template-body", template,
                      "--parameters", json.dumps([{"ParameterKey": "AvailabilityZone", "ParameterValue": zone}]),
                      "--capabilities", "CAPABILITY_NAMED_IAM",
                      "--tags", "Key=Project,Value=NeuroGraph-DB", "Key=AccountPlan,Value=FREE",
                      "--timeout-in-minutes", "45")
        print("CloudFormation provisioning started:", result["StackId"], flush=True)

    previous = None
    for _ in range(270):
        stack = call("cloudformation", "describe-stacks", "--stack-name", args.stack_name)["Stacks"][0]
        status = stack["StackStatus"]
        if status != previous:
            print("Stack status:", status, flush=True)
            previous = status
        if status in ("CREATE_COMPLETE", "UPDATE_COMPLETE"):
            guard()
            state = {item["OutputKey"]: item["OutputValue"] for item in stack.get("Outputs", [])}
            state.update(account_id=args.expected_account, region=args.region, stack_name=args.stack_name,
                         backend_domain="neurograph-" + state["PublicIp"].replace(".", "-") + ".sslip.io")
            args.state_file.parent.mkdir(parents=True, exist_ok=True)
            args.state_file.write_text(json.dumps(state, indent=2) + "\n")
            args.state_file.chmod(0o600)
            print(json.dumps(state, indent=2), flush=True)
            return
        if "FAILED" in status or "ROLLBACK" in status:
            events = call("cloudformation", "describe-stack-events", "--stack-name", args.stack_name)
            failures = [{k: event.get(k) for k in ("LogicalResourceId", "ResourceStatus", "ResourceStatusReason")}
                        for event in events["StackEvents"] if "FAILED" in event["ResourceStatus"]]
            raise SystemExit("Stack did not finish successfully: " + json.dumps(failures))
        time.sleep(10)
    raise SystemExit("Timed out waiting for the stack. Inspect its state before retrying.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        raise SystemExit((exc.stderr or str(exc)).strip()) from exc
