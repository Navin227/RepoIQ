variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
}

variable "project_name" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "common_tags" {
  description = "Common resource tags"
  type        = map(string)
  default     = {}
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
}

variable "public_subnet_a_cidr" {
  description = "CIDR block for public subnet A"
  type        = string
}

variable "public_subnet_b_cidr" {
  description = "CIDR block for public subnet B"
  type        = string
}

variable "availability_zone_a" {
  description = "Availability zone for public subnet A"
  type        = string
}

variable "availability_zone_b" {
  description = "Availability zone for public subnet B"
  type        = string
}

variable "ssh_allowed_cidr" {
  description = "CIDR block allowed for SSH access to the EC2 instance"
  type        = string

  validation {
    condition     = can(cidrhost(var.ssh_allowed_cidr, 0))
    error_message = "ssh_allowed_cidr must be a valid IPv4 CIDR block."
  }
}

variable "key_name" {
  description = "Name of the EC2 key pair for SSH access"
  type        = string
}

variable "snapshot_id" {
  description = "Golden EBS snapshot ID used as the boot source for new demo EC2 instances"
  type        = string
  default     = "snap-0000000000000000"

  validation {
    condition     = can(regex("^snap-[0-9a-fA-F]{8,17}$", var.snapshot_id))
    error_message = "snapshot_id must be a valid AWS snapshot ID such as snap-0123456789abcdef0."
  }
}

variable "instance_type" {
  description = "EC2 instance type for the ephemeral demo environment"
  type        = string
  default     = "t3.small"
}

variable "root_volume_size" {
  description = "Root volume size for the ephemeral demo EC2 instance"
  type        = number
  default     = 20
}

variable "root_volume_type" {
  description = "Root volume type for the ephemeral demo EC2 instance"
  type        = string
  default     = "gp3"
}

variable "admin_token" {
  description = "Security token for admin authorization. Do not save in frontend code."
  type        = string
  sensitive   = true
  default     = "repoiq-demo-admin-token-2026"
}

variable "frontend_origin" {
  description = "Production frontend origin allowed by API Gateway CORS"
  type        = string
  default     = "https://main.d20r18yhh140ff.amplifyapp.com"
}
