resource "aws_iam_role" "ec2" {
  name = "${var.project_name}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(var.common_tags, {
    Name = "${var.project_name}-ec2-role"
  })
}

resource "aws_iam_role_policy_attachment" "cloudwatch_agent" {
  role       = aws_iam_role.ec2.name
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
}

resource "aws_iam_role_policy" "s3_access" {
  name = "${var.project_name}-ec2-s3-access"
  role = aws_iam_role.ec2.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action   = "s3:ListBucket"
        Effect   = "Allow"
        Resource = "arn:aws:s3:::${var.artifacts_bucket_name}"
      },
      {
        Action = [
          "s3:GetObject",
          "s3:PutObject"
        ]
        Effect = "Allow"
        Resource = [
          "arn:aws:s3:::${var.artifacts_bucket_name}/artifacts/*",
          "arn:aws:s3:::${var.artifacts_bucket_name}/artifacts/demo-init/*",
          "arn:aws:s3:::${var.artifacts_bucket_name}/golden-image-ready/*",
          "arn:aws:s3:::${var.artifacts_bucket_name}/golden-image-failed/*"
        ]
      }
    ]
  })
}

resource "aws_iam_instance_profile" "ec2" {
  name = "${var.project_name}-ec2-instance-profile"
  role = aws_iam_role.ec2.name

  tags = merge(var.common_tags, {
    Name = "${var.project_name}-ec2-instance-profile"
  })
}
