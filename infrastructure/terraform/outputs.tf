output "environment" {
  value = var.environment
}

output "region" {
  value = var.aws_region
}

output "vpc_id" {
  description = "ID of the VPC"
  value       = module.networking.vpc_id
}

output "public_subnet_a_id" {
  description = "ID of public subnet A"
  value       = module.networking.public_subnet_a_id
}

output "public_subnet_b_id" {
  description = "ID of public subnet B"
  value       = module.networking.public_subnet_b_id
}

output "internet_gateway_id" {
  description = "ID of the internet gateway"
  value       = module.networking.internet_gateway_id
}

output "public_route_table_id" {
  description = "ID of the public route table"
  value       = module.networking.public_route_table_id
}

output "s3_bucket_name" {
  description = "Name of the S3 bucket for artifacts"
  value       = module.s3.bucket_name
}

output "s3_bucket_arn" {
  description = "ARN of the S3 bucket for artifacts"
  value       = module.s3.bucket_arn
}

output "cloudwatch_log_group_name" {
  description = "Name of the CloudWatch Log Group"
  value       = module.cloudwatch.log_group_name
}

output "cloudwatch_log_group_arn" {
  description = "ARN of the CloudWatch Log Group"
  value       = module.cloudwatch.log_group_arn
}

output "demo_api_endpoint" {
  description = "Endpoint URL of the HTTP API Gateway for Demo Server Lifecycle"
  value       = module.api_gateway.api_endpoint
}

output "backend_api_endpoint" {
  description = "HTTPS Lambda Function URL for the RepoIQ backend proxy"
  value       = module.lambda.backend_api_endpoint
}

output "golden_snapshot_id" {
  description = "Configured golden snapshot ID used for ephemeral demo EC2 launches"
  value       = var.snapshot_id == "snap-0000000000000000" ? module.ec2.golden_snapshot_id : var.snapshot_id
}

output "security_group_id" {
  description = "Security group ID used for the ephemeral demo EC2 instance"
  value       = module.security_group.security_group_id
}

output "subnet_ids" {
  description = "Subnet IDs used for the ephemeral demo EC2 instance"
  value       = [module.networking.public_subnet_a_id, module.networking.public_subnet_b_id]
}

output "ec2_role_name" {
  description = "IAM role name attached to the ephemeral demo EC2 instance"
  value       = module.iam.ec2_role_name
}

output "ec2_instance_profile_name" {
  description = "IAM instance profile name attached to the ephemeral demo EC2 instance"
  value       = module.iam.ec2_instance_profile_name
}
