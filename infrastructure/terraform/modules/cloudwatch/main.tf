resource "aws_cloudwatch_log_group" "ec2" {
  name              = "/repoiq/ec2"
  retention_in_days = 30

  tags = var.common_tags
}
