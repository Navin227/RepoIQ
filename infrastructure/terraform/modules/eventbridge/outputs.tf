output "scheduler_role_arn" {
  description = "ARN of the EventBridge Scheduler IAM role"
  value       = aws_iam_role.scheduler.arn
}
