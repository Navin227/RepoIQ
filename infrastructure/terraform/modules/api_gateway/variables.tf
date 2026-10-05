variable "project_name" {
  description = "Project name"
  type        = string
}

variable "common_tags" {
  description = "Common resource tags"
  type        = map(string)
  default     = {}
}

variable "vercel_domain" {
  description = "Production Vercel domain for CORS"
  type        = string
}

variable "authorizer_invoke_arn" {
  description = "Invoke ARN of the Authorizer Lambda"
  type        = string
}

variable "authorizer_lambda_arn" {
  description = "ARN of the Authorizer Lambda"
  type        = string
}

variable "start_invoke_arn" {
  description = "Invoke ARN of the Start Lambda"
  type        = string
}

variable "start_lambda_arn" {
  description = "ARN of the Start Lambda"
  type        = string
}

variable "stop_invoke_arn" {
  description = "Invoke ARN of the Stop Lambda"
  type        = string
}

variable "stop_lambda_arn" {
  description = "ARN of the Stop Lambda"
  type        = string
}

variable "status_invoke_arn" {
  description = "Invoke ARN of the Status Lambda"
  type        = string
}

variable "status_lambda_arn" {
  description = "ARN of the Status Lambda"
  type        = string
}
