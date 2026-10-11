data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.region
}

# ─────────────────────────────────────────────
# CloudWatch Log Groups (7-day retention)
# ─────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "authorizer" {
  name              = "/aws/lambda/${var.project_name}-authorizer"
  retention_in_days = 7
  tags              = var.common_tags
}

resource "aws_cloudwatch_log_group" "start" {
  name              = "/aws/lambda/${var.project_name}-start"
  retention_in_days = 7
  tags              = var.common_tags
}

resource "aws_cloudwatch_log_group" "stop" {
  name              = "/aws/lambda/${var.project_name}-stop"
  retention_in_days = 7
  tags              = var.common_tags
}

resource "aws_cloudwatch_log_group" "status" {
  name              = "/aws/lambda/${var.project_name}-status"
  retention_in_days = 7
  tags              = var.common_tags
}

# ─────────────────────────────────────────────
# Lambda Execution IAM Role
# ─────────────────────────────────────────────

resource "aws_iam_role" "lambda_exec" {
  name = "${var.project_name}-lambda-exec-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = var.common_tags
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_ec2_control" {
  name = "${var.project_name}-lambda-ec2-control"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "EC2Control"
        Effect = "Allow"

        Action = [
          "ec2:RunInstances",
          "ec2:StartInstances",
          "ec2:StopInstances",
          "ec2:TerminateInstances",
          "ec2:DescribeInstances",
          "ec2:DescribeInstanceStatus",
          "ec2:DescribeImages",
          "ec2:DescribeSnapshots",
          "ec2:DescribeVolumes",
          "ec2:DescribeSubnets",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeKeyPairs",
          "ec2:CreateTags"
        ]

        Resource = "*"
      },

      {
        Sid    = "SchedulerControl"
        Effect = "Allow"

        Action = [
          "scheduler:CreateSchedule",
          "scheduler:DeleteSchedule",
          "scheduler:GetSchedule"
        ]

        Resource = "arn:aws:scheduler:${local.region}:${local.account_id}:schedule/default/repoiq-stop-*"
      },

      {
        Sid    = "PassSchedulerRole"
        Effect = "Allow"

        Action = "iam:PassRole"

        Resource = var.scheduler_role_arn
      },

      {
        Sid      = "PassEc2Role"
        Effect   = "Allow"
        Action   = "iam:PassRole"
        Resource = var.ec2_role_arn
      },

      {
        Sid    = "ReadDemoInitTelemetry"
        Effect = "Allow"
        Action = [
          "s3:GetObject"
        ]
        Resource = [
          "arn:aws:s3:::${var.artifacts_bucket_name}/artifacts/demo-init/*"
        ]
      },
      {
        Sid    = "ListDemoInitTelemetry"
        Effect = "Allow"
        Action = [
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.artifacts_bucket_name}"
        ]
        Condition = {
          StringLike = {
            "s3:prefix" = [
              "artifacts/demo-init/*"
            ]
          }
        }
      }
    ]
  })
}

# ─────────────────────────────────────────────
# Lambda ZIP Archives (inline from src/)
# ─────────────────────────────────────────────

data "archive_file" "authorizer" {
  type        = "zip"
  source_file = "${path.module}/src/authorizer.py"
  output_path = "${path.module}/dist/authorizer.zip"
}

data "archive_file" "start" {
  type        = "zip"
  source_file = "${path.module}/src/start_controller.py"
  output_path = "${path.module}/dist/start.zip"
}

data "archive_file" "stop" {
  type        = "zip"
  source_file = "${path.module}/src/stop_controller.py"
  output_path = "${path.module}/dist/stop.zip"
}

data "archive_file" "status" {
  type        = "zip"
  source_file = "${path.module}/src/status_controller.py"
  output_path = "${path.module}/dist/status.zip"
}

# ─────────────────────────────────────────────
# Lambda Functions
# ─────────────────────────────────────────────

resource "aws_lambda_function" "authorizer" {
  function_name    = "${var.project_name}-authorizer"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "authorizer.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.authorizer.output_path
  source_code_hash = data.archive_file.authorizer.output_base64sha256
  timeout          = 10

  environment {
    variables = {
      ADMIN_TOKEN = var.admin_token
    }
  }

  depends_on = [aws_cloudwatch_log_group.authorizer]
  tags       = var.common_tags
}

resource "aws_lambda_function" "start" {
  function_name    = "${var.project_name}-start"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "start_controller.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.start.output_path
  source_code_hash = data.archive_file.start.output_base64sha256
  timeout          = 60

  environment {
    variables = {
      PROJECT_NAME          = var.project_name
      ENVIRONMENT           = var.environment
      AMI_ID                = var.ami_id
      ROOT_SNAPSHOT_ID      = var.root_snapshot_id
      INSTANCE_TYPE         = var.instance_type
      SUBNET_ID             = var.subnet_id
      SECURITY_GROUP_ID     = var.security_group_id
      INSTANCE_PROFILE_NAME = var.instance_profile_name
      KEY_NAME              = var.key_name
      ROOT_VOLUME_SIZE      = tostring(var.root_volume_size)
      ROOT_VOLUME_TYPE      = var.root_volume_type
      SCHEDULER_ROLE_ARN    = var.scheduler_role_arn
      STOP_LAMBDA_ARN       = aws_lambda_function.stop.arn
    }
  }

  depends_on = [aws_cloudwatch_log_group.start]
  tags       = var.common_tags
}

resource "aws_lambda_function" "stop" {
  function_name    = "${var.project_name}-stop"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "stop_controller.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.stop.output_path
  source_code_hash = data.archive_file.stop.output_base64sha256
  timeout          = 60

  environment {
    variables = {
      PROJECT_NAME = var.project_name
      ENVIRONMENT  = var.environment
    }
  }

  depends_on = [aws_cloudwatch_log_group.stop]
  tags       = var.common_tags
}

resource "aws_lambda_function" "status" {
  function_name    = "${var.project_name}-status"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "status_controller.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.status.output_path
  source_code_hash = data.archive_file.status.output_base64sha256
  timeout          = 15

  environment {
    variables = {
      PROJECT_NAME             = var.project_name
      ENVIRONMENT              = var.environment
      REPOIQ_ARTIFACTS_BUCKET  = var.artifacts_bucket_name
      REPOIQ_INIT_STAGE_PREFIX = "artifacts/demo-init"
    }
  }

  depends_on = [aws_cloudwatch_log_group.status]
  tags       = var.common_tags
}

resource "aws_cloudwatch_log_group" "backend_proxy" {
  name              = "/aws/lambda/${var.project_name}-backend-proxy"
  retention_in_days = 7
  tags              = var.common_tags
}

resource "aws_iam_role" "backend_proxy_exec" {
  name = "${var.project_name}-backend-proxy-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = var.common_tags
}

resource "aws_iam_role_policy" "backend_proxy" {
  name = "${var.project_name}-backend-proxy"
  role = aws_iam_role.backend_proxy_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "FindRunningDemoInstance"
        Effect   = "Allow"
        Action   = ["ec2:DescribeInstances"]
        Resource = "*"
      },
      {
        Sid      = "WriteBackendProxyLogs"
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.backend_proxy.arn}:*"
      }
    ]
  })
}

data "archive_file" "backend_proxy" {
  type        = "zip"
  source_file = "${path.module}/src/backend_proxy.py"
  output_path = "${path.module}/dist/backend_proxy.zip"
}

resource "aws_lambda_function" "backend_proxy" {
  function_name    = "${var.project_name}-backend-proxy"
  role             = aws_iam_role.backend_proxy_exec.arn
  handler          = "backend_proxy.lambda_handler"
  runtime          = "python3.12"
  filename         = data.archive_file.backend_proxy.output_path
  source_code_hash = data.archive_file.backend_proxy.output_base64sha256
  memory_size      = 128
  timeout          = 900

  environment {
    variables = {
      PROJECT_NAME = var.project_name
      ENVIRONMENT  = var.environment
      BACKEND_PORT = "80"
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.backend_proxy,
    aws_iam_role_policy.backend_proxy,
  ]
  tags = var.common_tags
}

resource "aws_lambda_function_url" "backend_proxy" {
  function_name      = aws_lambda_function.backend_proxy.function_name
  authorization_type = "NONE"
  invoke_mode        = "BUFFERED"

  cors {
    allow_origins = [var.frontend_origin]
    allow_methods = ["GET", "POST"]
    allow_headers = ["Authorization", "Content-Type"]
    max_age       = 300
  }
}

resource "aws_lambda_permission" "backend_proxy_function_url" {
  statement_id           = "AllowPublicBackendFunctionUrl"
  action                 = "lambda:InvokeFunctionUrl"
  function_name          = aws_lambda_function.backend_proxy.function_name
  principal              = "*"
  function_url_auth_type = "NONE"
}

resource "aws_lambda_permission" "backend_proxy_invoke_via_url" {
  statement_id             = "AllowBackendFunctionUrlInvoke"
  action                   = "lambda:InvokeFunction"
  function_name            = aws_lambda_function.backend_proxy.function_name
  principal                = "*"
  invoked_via_function_url = true
}
