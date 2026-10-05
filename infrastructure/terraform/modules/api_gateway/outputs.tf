output "api_endpoint" {
  description = "Endpoint URL of the HTTP API Gateway"
  value       = aws_apigatewayv2_api.demo.api_endpoint
}

output "api_id" {
  description = "ID of the HTTP API Gateway"
  value       = aws_apigatewayv2_api.demo.id
}
