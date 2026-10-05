# ─────────────────────────────────────────────
# HTTP API
# ─────────────────────────────────────────────

resource "aws_apigatewayv2_api" "demo" {
  name          = "${var.project_name}-demo-api"
  protocol_type = "HTTP"
  description   = "RepoIQ Demo Infrastructure Control API"

  cors_configuration {
    allow_origins = [
      "http://localhost:3000",
      "http://localhost:5173",
      var.vercel_domain
    ]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["Content-Type", "Authorization", "X-Admin-Token"]
    max_age       = 300
  }

  tags = var.common_tags
}

# ─────────────────────────────────────────────
# Lambda Authorizer
# ─────────────────────────────────────────────

resource "aws_apigatewayv2_authorizer" "token" {
  api_id                            = aws_apigatewayv2_api.demo.id
  authorizer_type                   = "REQUEST"
  authorizer_uri                    = var.authorizer_invoke_arn
  identity_sources                  = ["$request.header.Authorization"]
  name                              = "token-authorizer"
  authorizer_payload_format_version = "2.0"
  enable_simple_responses           = true
}

# ─────────────────────────────────────────────
# Lambda Integrations
# ─────────────────────────────────────────────

resource "aws_apigatewayv2_integration" "start" {
  api_id                 = aws_apigatewayv2_api.demo.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.start_invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "stop" {
  api_id                 = aws_apigatewayv2_api.demo.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.stop_invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_integration" "status" {
  api_id                 = aws_apigatewayv2_api.demo.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.status_invoke_arn
  payload_format_version = "2.0"
}

# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────

resource "aws_apigatewayv2_route" "start" {
  api_id             = aws_apigatewayv2_api.demo.id
  route_key          = "POST /demo/start"
  target             = "integrations/${aws_apigatewayv2_integration.start.id}"
  authorization_type = "CUSTOM"
  authorizer_id      = aws_apigatewayv2_authorizer.token.id
}

resource "aws_apigatewayv2_route" "stop" {
  api_id             = aws_apigatewayv2_api.demo.id
  route_key          = "POST /demo/stop"
  target             = "integrations/${aws_apigatewayv2_integration.stop.id}"
  authorization_type = "CUSTOM"
  authorizer_id      = aws_apigatewayv2_authorizer.token.id
}

resource "aws_apigatewayv2_route" "status" {
  api_id             = aws_apigatewayv2_api.demo.id
  route_key          = "GET /demo/status"
  target             = "integrations/${aws_apigatewayv2_integration.status.id}"
  authorization_type = "CUSTOM"
  authorizer_id      = aws_apigatewayv2_authorizer.token.id
}

# ─────────────────────────────────────────────
# Stage (auto-deploy)
# ─────────────────────────────────────────────

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.demo.id
  name        = "$default"
  auto_deploy = true

  tags = var.common_tags
}

# ─────────────────────────────────────────────
# Lambda Permissions (allow API GW to invoke)
# ─────────────────────────────────────────────

resource "aws_lambda_permission" "authorizer" {
  statement_id  = "AllowAPIGatewayInvokeAuthorizer"
  action        = "lambda:InvokeFunction"
  function_name = var.authorizer_lambda_arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.demo.execution_arn}/*"
}

resource "aws_lambda_permission" "start" {
  statement_id  = "AllowAPIGatewayInvokeStart"
  action        = "lambda:InvokeFunction"
  function_name = var.start_lambda_arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.demo.execution_arn}/*/*/demo/start"
}

resource "aws_lambda_permission" "stop" {
  statement_id  = "AllowAPIGatewayInvokeStop"
  action        = "lambda:InvokeFunction"
  function_name = var.stop_lambda_arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.demo.execution_arn}/*/*/demo/stop"
}

resource "aws_lambda_permission" "status" {
  statement_id  = "AllowAPIGatewayInvokeStatus"
  action        = "lambda:InvokeFunction"
  function_name = var.status_lambda_arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.demo.execution_arn}/*/*/demo/status"
}
