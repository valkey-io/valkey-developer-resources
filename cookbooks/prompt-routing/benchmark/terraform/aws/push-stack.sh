#!/usr/bin/env bash
# Copy the benchmark stack from this working tree to the GPU host over SSM,
# with no Git clone and no SSH. Useful when you're changing the stack and want
# to run your local copy. Results, rendered configs, the model cache, and .env
# are not sent, and results already on the host are left alone.
#
# Usage: ./push-stack.sh            (after terraform apply)
# Lands in /opt/bench/stack on the host.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
INSTANCE_ID="$(terraform output -raw instance_id)"
REGION="$(terraform output -raw region)"
BENCH_DIR="$(cd ../.. && pwd)"
DEST=/opt/bench/stack

echo "Waiting for $INSTANCE_ID to register with SSM..."
for _ in $(seq 1 60); do
  status="$(aws ssm describe-instance-information --region "$REGION" \
    --filters "Key=InstanceIds,Values=$INSTANCE_ID" \
    --query 'InstanceInformationList[0].PingStatus' --output text 2>/dev/null || true)"
  [[ "$status" == "Online" ]] && break
  sleep 10
done
[[ "$status" == "Online" ]] || { echo "instance not online in SSM (status: ${status:-none})" >&2; exit 1; }

# COPYFILE_DISABLE keeps macOS tar from adding ._ metadata files.
payload="$(COPYFILE_DISABLE=1 tar -C "$BENCH_DIR" \
  --exclude ./terraform --exclude ./results --exclude ./rendered \
  --exclude ./.hf-cache --exclude ./.env \
  -czf - . | base64 | tr -d '\n')"
echo "Sending ${#payload} bytes (base64) to $INSTANCE_ID:$DEST"

request="$(mktemp)"
trap 'rm -f "$request"' EXIT
python3 - "$INSTANCE_ID" "$DEST" "$payload" > "$request" <<'PY'
import json, sys
instance, dest, payload = sys.argv[1:4]
script = [
    "set -euo pipefail",
    f"mkdir -p {dest}",
    f"echo '{payload}' | base64 -d | tar -xzf - -C {dest} --no-same-owner",
    f"chmod +x {dest}/scripts/*.sh {dest}/scripts/*.py {dest}/vllm/*.sh",
    f"echo synced to {dest}; ls {dest}",
]
print(json.dumps({
    "InstanceIds": [instance],
    "DocumentName": "AWS-RunShellScript",
    "Comment": "push prompt-routing benchmark stack",
    "Parameters": {"commands": script},
}))
PY

command_id="$(aws ssm send-command --region "$REGION" --cli-input-json "file://$request" \
  --query 'Command.CommandId' --output text)"
aws ssm wait command-executed --region "$REGION" --command-id "$command_id" --instance-id "$INSTANCE_ID" || true
aws ssm get-command-invocation --region "$REGION" --command-id "$command_id" --instance-id "$INSTANCE_ID" \
  --query '[Status, StandardOutputContent, StandardErrorContent]' --output text
