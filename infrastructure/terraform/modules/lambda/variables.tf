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

variable "frontend_origin" {
  description = "Frontend origin allowed to call the backend Lambda Function URL"
  type        = string
}

variable "ami_id" {
  description = "AMI ID used by the start Lambda when launching a demo EC2 instance"
  type        = string
}

variable "root_snapshot_id" {
  description = "Golden snapshot ID used for the root volume of the demo EC2 instance"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type for the ephemeral demo instance"
  type        = string
  default     = "t3.small"
}

variable "subnet_id" {
  description = "Subnet ID used for the ephemeral demo instance"
  type        = string
}

variable "security_group_id" {
  description = "Security group ID used for the ephemeral demo instance"
  type        = string
}

variable "instance_profile_name" {
  description = "IAM instance profile name attached to the demo EC2 instance"
  type        = string
}

variable "key_name" {
  description = "EC2 key pair name used for the demo EC2 instance"
  type        = string
}

variable "root_volume_size" {
  description = "Root volume size for the ephemeral demo EC2 instance"
  type        = number
}

variable "root_volume_type" {
  description = "Root volume type for the ephemeral demo EC2 instance"
  type        = string
  default     = "gp3"
}

variable "ec2_role_arn" {
  description = "ARN of the IAM role attached to the ephemeral demo EC2 instance"
  type        = string
}

variable "admin_token" {
  description = "Admin token for Lambda authorizer"
  type        = string
  sensitive   = true
}

variable "scheduler_role_arn" {
  description = "IAM role ARN for EventBridge Scheduler"
  type        = string
}

variable "artifacts_bucket_name" {
  description = "S3 bucket that stores the demo stage.json output and build artifacts"
  type        = string
}
