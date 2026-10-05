data "archive_file" "repoiq_source" {
  type        = "zip"
  source_dir  = "${path.root}/../../"
  output_path = "${path.root}/.repoiq-source.zip"


  excludes = [
    ".git",
    ".git/**",
    "**/.git",
    "**/.git/**",

    "node_modules",
    "node_modules/**",
    "**/node_modules",
    "**/node_modules/**",

    "dist",
    "dist/**",
    "**/dist",
    "**/dist/**",

    "build",
    "build/**",
    "**/build",
    "**/build/**",

    ".terraform",
    ".terraform/**",
    "**/.terraform",
    "**/.terraform/**",

    "*.tfstate",
    "*.tfstate.*",
    "**/*.tfstate",
    "**/*.tfstate.*",
    "infrastructure/terraform/.terraform.tfstate.lock.info",
    "infrastructure/terraform/.repoiq-source.zip",

    ".env",
    ".env.*",

    ".venv",
    ".venv/**",
    "**/.venv",
    "**/.venv/**",

    "temp_repos",
    "temp_repos/**",

    ".pytest_cache",
    ".pytest_cache/**",
    "**/.pytest_cache",
    "**/.pytest_cache/**",

    "__pycache__",
    "__pycache__/**",
    "**/__pycache__",
    "**/__pycache__/**",

    ".mypy_cache",
    ".mypy_cache/**",
    "**/.mypy_cache",
    "**/.mypy_cache/**",

    "*.zip",
    "*.zip/**",
    "*.tar.gz",
    "*.tar.gz/**"
  ]
}

resource "aws_s3_object" "repoiq_source" {
  bucket       = module.s3.bucket_name
  key          = "artifacts/repoiq-source.zip"
  source       = data.archive_file.repoiq_source.output_path
  source_hash  = data.archive_file.repoiq_source.output_sha
  content_type = "application/zip"
}

module "networking" {
  source = "./modules/networking"

  project_name         = var.project_name
  environment          = var.environment
  common_tags          = var.common_tags
  vpc_cidr             = var.vpc_cidr
  public_subnet_a_cidr = var.public_subnet_a_cidr
  public_subnet_b_cidr = var.public_subnet_b_cidr
  availability_zone_a  = var.availability_zone_a
  availability_zone_b  = var.availability_zone_b
}

module "security_group" {
  source = "./modules/security_group"

  project_name     = var.project_name
  environment      = var.environment
  common_tags      = var.common_tags
  vpc_id           = module.networking.vpc_id
  ssh_allowed_cidr = var.ssh_allowed_cidr
}

module "iam" {
  source = "./modules/iam"

  project_name          = var.project_name
  environment           = var.environment
  common_tags           = var.common_tags
  artifacts_bucket_name = module.s3.bucket_name
}

module "s3" {
  source = "./modules/s3"

  project_name = var.project_name
  environment  = var.environment
  common_tags  = var.common_tags
}

module "cloudwatch" {
  source = "./modules/cloudwatch"

  project_name = var.project_name
  environment  = var.environment
  common_tags  = var.common_tags
}

module "ec2" {
  source = "./modules/ec2"

  aws_region            = var.aws_region
  project_name          = var.project_name
  environment           = var.environment
  common_tags           = var.common_tags
  subnet_id             = module.networking.public_subnet_a_id
  security_group_id     = module.security_group.security_group_id
  instance_profile_name = module.iam.ec2_instance_profile_name
  key_name              = var.key_name
  root_snapshot_id      = var.snapshot_id
  instance_type         = var.instance_type
  root_volume_size      = var.root_volume_size
  root_volume_type      = var.root_volume_type
  artifacts_bucket_name = module.s3.bucket_name
  source_artifact_key   = aws_s3_object.repoiq_source.key
}

# ─────────────────────────────────────────────
# Automation Layer (new — does NOT touch EC2)
# ─────────────────────────────────────────────

module "lambda" {
  source = "./modules/lambda"

  project_name          = var.project_name
  environment           = var.environment
  common_tags           = var.common_tags
  ami_id                = module.ec2.ami_id
  root_snapshot_id      = var.snapshot_id == "snap-0000000000000000" ? module.ec2.golden_snapshot_id : var.snapshot_id
  instance_type         = var.instance_type
  subnet_id             = module.networking.public_subnet_a_id
  security_group_id     = module.security_group.security_group_id
  instance_profile_name = module.iam.ec2_instance_profile_name
  key_name              = var.key_name
  root_volume_size      = var.root_volume_size
  root_volume_type      = var.root_volume_type
  ec2_role_arn          = module.iam.ec2_role_arn
  admin_token           = var.admin_token
  scheduler_role_arn    = module.eventbridge.scheduler_role_arn
  artifacts_bucket_name = module.s3.bucket_name
}

module "eventbridge" {
  source = "./modules/eventbridge"

  project_name    = var.project_name
  stop_lambda_arn = module.lambda.stop_lambda_arn
}

module "api_gateway" {
  source = "./modules/api_gateway"

  project_name          = var.project_name
  common_tags           = var.common_tags
  vercel_domain         = var.vercel_domain
  authorizer_invoke_arn = module.lambda.authorizer_lambda_invoke_arn
  authorizer_lambda_arn = module.lambda.authorizer_lambda_arn
  start_invoke_arn      = module.lambda.start_lambda_invoke_arn
  start_lambda_arn      = module.lambda.start_lambda_arn
  stop_invoke_arn       = module.lambda.stop_lambda_invoke_arn
  stop_lambda_arn       = module.lambda.stop_lambda_arn
  status_invoke_arn     = module.lambda.status_lambda_invoke_arn
  status_lambda_arn     = module.lambda.status_lambda_arn
}
