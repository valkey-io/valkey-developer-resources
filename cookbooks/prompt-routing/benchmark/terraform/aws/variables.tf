variable "region" {
  description = "AWS region to deploy into."
  type        = string
  default     = "us-east-1"
}

variable "name_prefix" {
  description = "Prefix for resource names and the Project tag."
  type        = string
  default     = "prompt-routing-bench"

  validation {
    condition     = can(regex("^[a-z0-9-]{1,32}$", var.name_prefix))
    error_message = "name_prefix must be 1-32 characters of lowercase letters, digits, or hyphens."
  }
}

variable "instance_type" {
  description = "NVIDIA GPU instance type. The default (4x L4 24 GB) fits 2-4 vLLM replicas at TP=1."
  type        = string
  default     = "g6.12xlarge"

  validation {
    condition     = can(regex("^(g4dn|g5|g6|g6e|p4d|p4de|p5|p5e|p5en)\\.", var.instance_type))
    error_message = "instance_type must be an NVIDIA GPU family supported by the Deep Learning Base OSS Nvidia Driver AMI (g4dn, g5, g6, g6e, p4d, p4de, p5, p5e, p5en)."
  }
}

variable "use_spot" {
  description = "Launch as a one-time Spot instance. Spot capacity can be reclaimed at any time, and the instance terminates (not stops) when it shuts down."
  type        = bool
  default     = false
}

variable "root_volume_gb" {
  description = "Size of the encrypted gp3 root volume, in GiB. Needs room for container images and model weights."
  type        = number
  default     = 200

  validation {
    condition     = var.root_volume_gb >= 100 && var.root_volume_gb <= 2000
    error_message = "root_volume_gb must be between 100 and 2000."
  }
}

variable "auto_stop_minutes" {
  description = "Shut the host down this many minutes after every boot, as a cost backstop. 0 disables it. This is not a substitute for terraform destroy."
  type        = number
  default     = 240

  validation {
    condition     = var.auto_stop_minutes >= 0 && floor(var.auto_stop_minutes) == var.auto_stop_minutes
    error_message = "auto_stop_minutes must be a non-negative whole number."
  }
}

variable "vpc_cidr" {
  description = "CIDR block for the dedicated VPC. The public subnet uses the first /24."
  type        = string
  default     = "10.42.0.0/16"

  validation {
    condition     = can(cidrhost(var.vpc_cidr, 0)) && tonumber(split("/", var.vpc_cidr)[1]) >= 16 && tonumber(split("/", var.vpc_cidr)[1]) <= 23
    error_message = "vpc_cidr must be an IPv4 CIDR between /16 and /23 (e.g. 10.42.0.0/16)."
  }
}

variable "extra_tags" {
  description = "Additional tags applied to every resource."
  type        = map(string)
  default     = {}
}
