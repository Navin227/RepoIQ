output "authorizer_lambda_arn" {
  description = "ARN of the Authorizer Lambda"
  value       = aws_lambda_function.authorizer.arn
}

output "authorizer_lambda_invoke_arn" {
  description = "Invoke ARN of the Authorizer Lambda"
  value       = aws_lambda_function.authorizer.invoke_arn
}

output "start_lambda_arn" {
  description = "ARN of the Start Lambda"
  value       = aws_lambda_function.start.arn
}

output "start_lambda_invoke_arn" {
  description = "Invoke ARN of the Start Lambda"
  value       = aws_lambda_function.start.invoke_arn
}

output "stop_lambda_arn" {
  description = "ARN of the Stop Lambda"
  value       = aws_lambda_function.stop.arn
}

output "stop_lambda_invoke_arn" {
  description = "Invoke ARN of the Stop Lambda"
  value       = aws_lambda_function.stop.invoke_arn
}

output "status_lambda_arn" {
  description = "ARN of the Status Lambda"
  value       = aws_lambda_function.status.arn
}

output "status_lambda_invoke_arn" {
  description = "Invoke ARN of the Status Lambda"
  value       = aws_lambda_function.status.invoke_arn
}

output "backend_api_endpoint" {
  description = "HTTPS Lambda Function URL for the RepoIQ backend proxy"
  value       = aws_lambda_function_url.backend_proxy.function_url
}

output "lambda_exec_role_arn" {
  description = "ARN of the Lambda execution IAM role"
  value       = aws_iam_role.lambda_exec.arn
}
