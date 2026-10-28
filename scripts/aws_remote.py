#!/usr/bin/env python3
"""Run a deployment command via SSM after checking the AWS Free account plan."""

import argparse
import json
from pathlib import Path
import time

from aws_free_plan import assert_free_plan, aws_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--state-file", type=Path, required=True)
    parser.add_argument("--command-file", type=Path, required=True)
    parser.add_argument("--profile", default="neurograph-free")
    args = parser.parse_args()
    state = json.loads(args.state_file.read_text())
    profile, region = args.profile, state["region"]
    assert_free_plan(profile, region, state["account_id"], minimum_credit=10)
    command = aws_json(profile, region, "ssm", "send-command",
        "--instance-ids", state["InstanceId"],
        "--document-name", "AWS-RunShellScript",
        "--parameters", json.dumps({"commands": [args.command_file.read_text()], "executionTimeout": ["3600"]}))
    command_id = command["Command"]["CommandId"]
    deadline = time.monotonic() + 3700
    while time.monotonic() < deadline:
        time.sleep(3)
        result = aws_json(profile, region, "ssm", "get-command-invocation",
            "--command-id", command_id, "--instance-id", state["InstanceId"])
        if result["Status"] in {"Pending", "InProgress", "Delayed"}:
            continue
        print(result.get("StandardOutputContent", ""), end="")
        print(result.get("StandardErrorContent", ""), end="")
        if result["Status"] != "Success":
            raise SystemExit("SSM command ended with status " + result["Status"])
        return
    raise SystemExit("SSM command timed out")


if __name__ == "__main__":
    main()
