variable "aws_region" {
  description = "AWS region used by the golden-image builder"
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

variable "subnet_id" {
  description = "Subnet ID to launch the EC2 instance in"
  type        = string
}

variable "security_group_id" {
  description = "Security group ID to associate with the EC2 instance"
  type        = string
}

variable "instance_profile_name" {
  description = "IAM instance profile name"
  type        = string
}

variable "key_name" {
  description = "EC2 key pair name"
  type        = string
}

variable "root_snapshot_id" {
  description = "Golden snapshot ID used for the root volume of new demo EC2 instances"
  type        = string
}

variable "instance_type" {
  description = "Instance type for the ephemeral demo EC2 instance"
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

variable "artifacts_bucket_name" {
  type        = string
  description = "S3 bucket used for the RepoIQ golden image readiness marker"
}

variable "source_artifact_key" {
  type        = string
  description = "S3 object key for the local RepoIQ source archive"
}

variable "builder_instance_type" {
  description = "Instance type for the golden image builder"
  type        = string
  default     = "m6i.large"
}
