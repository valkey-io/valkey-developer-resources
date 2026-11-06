terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.70.0"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = merge(
      {
        Project   = var.name_prefix
        ManagedBy = "terraform"
        Purpose   = "valkey-prompt-routing-benchmark"
      },
      var.extra_tags,
    )
  }
}
