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

variable "artifacts_bucket_name" {
  description = "S3 bucket containing RepoIQ build artifacts and readiness markers"
  type        = string
}
