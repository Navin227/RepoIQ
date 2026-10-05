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
