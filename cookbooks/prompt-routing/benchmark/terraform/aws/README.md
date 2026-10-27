# Optional: AWS GPU host for the latency benchmark

> This is an optional, paid path. The rest of the recipe runs locally for free.
> Any NVIDIA host with Docker and the NVIDIA Container Toolkit works for the
> benchmark; this Terraform is one way to get such a host on AWS.

This configuration creates one GPU instance with Docker and nothing else. The
[benchmark stack](../../README.md) itself (vLLM, the llm-d router, Valkey,
and the load generator) is host-agnostic and runs on that host.

## What it creates

- A dedicated VPC with one public subnet and an internet gateway, placed in an
  availability zone that offers the chosen instance type.
- A security group with no inbound rules. Outbound traffic is open so the host
  can pull images and model weights.
- An IAM role and instance profile with `AmazonSSMManagedInstanceCore` only.
  You reach the host through SSM Session Manager, so there are no SSH keys or
  open ports.
- One instance from the Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu
  24.04), which ships the NVIDIA driver, the NVIDIA Container Toolkit, Docker,
  and the SSM agent. IMDSv2 is required and the gp3 root volume is encrypted.
- A systemd unit that shuts the host down `auto_stop_minutes` after every boot
  (default 240). On-demand instances stop; Spot instances terminate.
- On first boot, a clone of `repo_url` at `repo_ref` in `/opt/bench/repo`
  (defaults to this repository's `main` branch), and the Docker Compose plugin
  if the AMI lacks it.

The default instance type is `g6.12xlarge` (4x NVIDIA L4, 24 GB each), enough
for two to four vLLM replicas of a small ungated model at TP=1. No Hugging Face
token is needed for ungated models, and the configuration holds no secrets.

## Before you start

- Tools: Terraform 1.6 or later, AWS CLI v2, and the
  [Session Manager plugin](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html).
- Service quotas: new accounts often have a quota of 0 vCPUs for "Running
  On-Demand G and VT instances", and Spot has a separate quota. A
  `g6.12xlarge` needs 48 vCPUs. Request an increase early; approval can take a
  while.
- Permissions: the identity running `terraform apply` needs to manage EC2
  networking (VPC, subnet, internet gateway, route table, security group),
  instances and volumes, IAM roles and instance profiles (including attaching
  a managed policy and `iam:PassRole`), and read SSM parameters.
- Cost: check current rates for your region and instance type in the
  [AWS Pricing Calculator](https://calculator.aws/).

## Usage

```bash
cd cookbooks/prompt-routing/benchmark/terraform/aws
cp terraform.tfvars.example terraform.tfvars   # edit as needed
terraform init
terraform apply

# Shell on the host, then run the benchmark
eval "$(terraform output -raw ssm_shell)"
#   cd /opt/bench/repo/cookbooks/prompt-routing/benchmark
#   sudo ./scripts/run-benchmark.sh
#   cat results/*/summary.md

# Forward a port from the host to your machine
eval "$(terraform output -raw ssm_port_forward_example)"
```

On the host, `/var/log/gpu-bench-bootcheck.log` records the first-boot
setup: the Compose plugin check, the clone, `nvidia-smi`, and the Docker
runtimes.

The run takes longer than a quick shell session, so start it under `nohup`
or `tmux` if your SSM session might drop. Copy any results you want to keep
before you destroy the stack, for example by printing `summary.md` and
`run.yaml` in the session.

When you finish a run, tear everything down:

```bash
terraform destroy
```

The auto-stop timer is a backstop. A stopped instance still bills for its EBS
volume, so destroy the stack rather than relying on the timer.
