# Optional, AWS-specific: a GPU host for the benchmark

> This is an optional, paid path, and the only AWS-specific part of the
> recipe. The recipe notebook runs locally on CPU. Any Linux host that meets
> the [benchmark's prerequisites](../../README.md#what-you-need) works; this
> Terraform is one way to get such a host on AWS.

This configuration creates one GPU instance with Docker and nothing else. The
[benchmark stack](../../README.md) itself (vLLM, LMCache, the llm-d router,
Valkey, and the load generator) has no AWS-specific code and runs on that
host.

## What it creates

- A dedicated VPC with one public subnet and an internet gateway, placed in
  `availability_zone`, or in the first zone that offers the chosen instance
  type if that's empty.
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
- On first boot, `/etc/llm-d-gpu-bench/host.env` with `BENCH_CLOUD=aws` and
  the instance type and region from instance metadata (IMDSv2).
  `run-benchmark.sh` reads it, so each result's `metadata.json` says where it
  was measured.

The default instance type is `g6e.12xlarge`: four NVIDIA L40S (48 GB each)
and 384 GiB of RAM. The benchmark's default workload needs four GPUs and
about 344 GiB of host RAM, most of it for Valkey and LMCache (see
[Sizing Valkey](../../README.md#sizing-valkey)). A `g6.12xlarge` (4x L4,
24 GB, 192 GiB RAM) needs a smaller workload and `VALKEY_MAXMEMORY`. The
region is a variable (`region`); GPU capacity varies by region and zone. The
default 200 GiB root volume holds the AMI, the images (the vLLM image alone
is about 20 GiB unpacked), the model weights (about 16 GiB) and the results.
No Hugging Face token is needed for the default model, and the configuration
holds no secrets.

## Before you start

- Tools: Terraform 1.6 or later, AWS CLI v2, and the
  [Session Manager plugin](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html).
- Service quotas: new accounts often have a quota of 0 vCPUs for "Running
  On-Demand G and VT instances", and Spot has a separate quota. A
  `g6e.12xlarge` needs 48 vCPUs. Request an increase early; approval can take a
  while.
- Permissions: the identity running `terraform apply` needs to manage EC2
  networking (VPC, subnet, internet gateway, route table, security group),
  instances and volumes, IAM roles and instance profiles (including attaching
  a managed policy and `iam:PassRole`), and read SSM parameters.
- Capacity: GPU instances regularly run out of on-demand capacity in a zone,
  or a whole region. `terraform apply` then sits on "Still creating..." while
  the provider retries `InsufficientInstanceCapacity`. Stop it, pick another
  zone with `availability_zone` (or another region or instance type), and
  apply again. A quick way to find a zone with capacity is to create a
  one-instance capacity reservation there and cancel it straight away (a
  reservation bills like a running instance while it's active):

  ```bash
  aws ec2 create-capacity-reservation --region us-east-1 \
    --availability-zone us-east-1c --instance-type g6e.12xlarge \
    --instance-platform Linux/UNIX --instance-count 1
  ```

  On success, cancel it (or keep it until the instance launches into it),
  with the reservation ID from the output:

  ```bash
  aws ec2 cancel-capacity-reservation --region us-east-1 \
    --capacity-reservation-id <id from the output>
  ```

- Cost: check current rates for your region and instance type in the
  [AWS Pricing Calculator](https://calculator.aws/).

## Usage

Copy the example variables:

```bash
cd cookbooks/llm-d-serving/benchmark/terraform/aws
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars` (region, instance type, zone), then create the host:

```bash
terraform init
terraform apply
```

Open a shell on the host:

```bash
eval "$(terraform output -raw ssm_shell)"
```

and run the benchmark there:

```bash
cd /opt/bench/repo/cookbooks/llm-d-serving/benchmark
sudo ./scripts/run-benchmark.sh
cat results/*/summary.md
```

To reach the router from your machine, forward its port (8081):

```bash
eval "$(terraform output -raw ssm_port_forward_example)"
```

To run your local copy of the stack instead of a clone (for example while
you're changing it), set `repo_url = ""` and push it over SSM. It lands in
`/opt/bench/stack`, and pushing again keeps any results already on the host:

```bash
./push-stack.sh
```

On the host, `/var/log/gpu-bench-bootcheck.log` records the first-boot
setup: the Compose plugin check, the clone, `nvidia-smi`, the Docker
runtimes, and the contents of `/etc/llm-d-gpu-bench/host.env`.

The run takes longer than a quick shell session, so start it under `nohup`
or `tmux` if your SSM session might drop. Copy any results you want to keep
before you destroy the stack, for example by printing `summary.md` and
`metadata.json` in the session.

When you finish a run, tear everything down:

```bash
terraform destroy
```

The auto-stop timer is a backstop. A stopped instance still bills for its EBS
volume, so destroy the stack rather than relying on the timer.
