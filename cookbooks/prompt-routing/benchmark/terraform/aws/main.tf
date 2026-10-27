# A single NVIDIA GPU host with Docker, reachable only through SSM Session
# Manager. No inbound ports, no SSH keys, no secrets in user data.

data "aws_partition" "current" {}

# Deep Learning Base OSS Nvidia Driver GPU AMI (Ubuntu 24.04): NVIDIA driver,
# NVIDIA Container Toolkit, Docker, and the SSM agent are preinstalled.
data "aws_ssm_parameter" "dlami" {
  name = "/aws/service/deeplearning/ami/x86_64/base-oss-nvidia-driver-gpu-ubuntu-24.04/latest/ami-id"
}

# Only consider availability zones that actually offer the instance type.
data "aws_ec2_instance_type_offerings" "gpu" {
  location_type = "availability-zone"

  filter {
    name   = "instance-type"
    values = [var.instance_type]
  }
}

locals {
  azs        = sort(data.aws_ec2_instance_type_offerings.gpu.locations)
  az         = length(local.azs) > 0 ? local.azs[0] : null
  vpc_prefix = tonumber(split("/", var.vpc_cidr)[1])
}

# --- Network -----------------------------------------------------------------

resource "aws_vpc" "this" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "${var.name_prefix}-vpc" }
}

resource "aws_internet_gateway" "this" {
  vpc_id = aws_vpc.this.id

  tags = { Name = "${var.name_prefix}-igw" }
}

# A public subnet gives the host egress (image pulls, model downloads, SSM)
# without a NAT gateway. The security group still blocks all inbound traffic.
resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.this.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 24 - local.vpc_prefix, 0)
  availability_zone       = local.az
  map_public_ip_on_launch = true

  tags = { Name = "${var.name_prefix}-public" }

  lifecycle {
    precondition {
      condition     = local.az != null
      error_message = "No availability zone in ${var.region} offers ${var.instance_type}. Pick another region or instance type."
    }
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.this.id
  }

  tags = { Name = "${var.name_prefix}-public" }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "host" {
  name        = "${var.name_prefix}-host"
  description = "GPU benchmark host: egress only, no inbound"
  vpc_id      = aws_vpc.this.id

  tags = { Name = "${var.name_prefix}-host" }
}

resource "aws_vpc_security_group_egress_rule" "all_ipv4" {
  security_group_id = aws_security_group.host.id
  description       = "All outbound IPv4"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

# --- IAM (SSM Session Manager access only) -----------------------------------

data "aws_iam_policy_document" "ec2_assume" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "host" {
  name               = "${var.name_prefix}-host"
  assume_role_policy = data.aws_iam_policy_document.ec2_assume.json
}

resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.host.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "host" {
  name = "${var.name_prefix}-host"
  role = aws_iam_role.host.name
}

# --- Instance ----------------------------------------------------------------

resource "aws_instance" "host" {
  ami                    = data.aws_ssm_parameter.dlami.insecure_value
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.host.id]
  iam_instance_profile   = aws_iam_instance_profile.host.name

  # One-time Spot instances cannot stop, so they terminate on shutdown.
  instance_initiated_shutdown_behavior = var.use_spot ? "terminate" : "stop"

  dynamic "instance_market_options" {
    for_each = var.use_spot ? [1] : []
    content {
      market_type = "spot"
      spot_options {
        spot_instance_type             = "one-time"
        instance_interruption_behavior = "terminate"
      }
    }
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required"
    http_put_response_hop_limit = 1
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_gb
    encrypted             = true
    delete_on_termination = true
  }

  user_data = templatefile("${path.module}/user_data.sh.tftpl", {
    auto_stop_minutes = var.auto_stop_minutes
  })

  tags        = { Name = "${var.name_prefix}-host" }
  volume_tags = { Name = "${var.name_prefix}-root" }

  depends_on = [aws_route_table_association.public]

  lifecycle {
    # A newer DLAMI release should not replace a running benchmark host.
    ignore_changes = [ami]
  }
}
