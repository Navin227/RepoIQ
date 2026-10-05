data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_s3_object" "builder_setup" {
  bucket = var.artifacts_bucket_name
  key    = "artifacts/builder_setup.sh"
  content = templatefile("${path.module}/builder_setup.sh", {
    aws_region            = var.aws_region
    artifacts_bucket_name = var.artifacts_bucket_name
    source_artifact_key   = var.source_artifact_key
  })
  content_type = "text/x-shellscript"
  etag = md5(templatefile("${path.module}/builder_setup.sh", {
    aws_region            = var.aws_region
    artifacts_bucket_name = var.artifacts_bucket_name
    source_artifact_key   = var.source_artifact_key
  }))
  tags = merge(var.common_tags, {
    Name    = "RepoIQ Builder Setup Script"
    Project = "RepoIQ"
    Role    = "GoldenImageBuilder"
  })
}

resource "aws_s3_object" "k3s_init_script" {
  bucket       = var.artifacts_bucket_name
  key          = "artifacts/repoiq-k3s-init.sh"
  source       = "${path.module}/repoiq-k3s-init.sh"
  content_type = "text/x-shellscript"
  etag         = md5(file("${path.module}/repoiq-k3s-init.sh"))
  tags = merge(var.common_tags, {
    Name    = "RepoIQ K3s First-Boot Init Script"
    Project = "RepoIQ"
    Role    = "GoldenImageBuilder"
  })
}

resource "aws_s3_object" "k3s_init_service" {
  bucket       = var.artifacts_bucket_name
  key          = "artifacts/repoiq-k3s-init.service"
  source       = "${path.module}/repoiq-k3s-init.service"
  content_type = "text/plain"
  etag         = md5(file("${path.module}/repoiq-k3s-init.service"))
  tags = merge(var.common_tags, {
    Name    = "RepoIQ K3s First-Boot Init Systemd Unit"
    Project = "RepoIQ"
    Role    = "GoldenImageBuilder"
  })
}

locals {
  k8s_source_dir = "${path.module}/../../../kubernetes"
  k8s_artifacts = {
    "configmap.yaml"           = "${local.k8s_source_dir}/configmap.yaml"
    "secret.yaml"              = "${local.k8s_source_dir}/secret.yaml"
    "postgres-pvc.yaml"        = "${local.k8s_source_dir}/postgres/pvc.yaml"
    "postgres-deployment.yaml" = "${local.k8s_source_dir}/postgres/deployment.yaml"
    "postgres-service.yaml"    = "${local.k8s_source_dir}/postgres/service.yaml"
    "backend-deployment.yaml"  = "${local.k8s_source_dir}/backend/deployment.yaml"
    "backend-service.yaml"     = "${local.k8s_source_dir}/backend/service.yaml"
    "frontend-deployment.yaml" = "${local.k8s_source_dir}/frontend/deployment.yaml"
    "frontend-service.yaml"    = "${local.k8s_source_dir}/frontend/service.yaml"
    "ingress.yaml"             = "${local.k8s_source_dir}/ingress/ingress.yaml"
  }
}

resource "aws_s3_object" "k8s_manifests" {
  for_each     = local.k8s_artifacts
  bucket       = var.artifacts_bucket_name
  key          = "artifacts/k8s/${each.key}"
  source       = each.value
  content_type = "application/yaml"
  etag         = md5(file(each.value))
  tags = merge(var.common_tags, {
    Name    = "RepoIQ K8s Manifest ${each.key}"
    Project = "RepoIQ"
    Role    = "GoldenImageBuilder"
  })
}

resource "aws_instance" "golden_image_builder" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.builder_instance_type
  subnet_id              = var.subnet_id
  vpc_security_group_ids = [var.security_group_id]
  iam_instance_profile   = var.instance_profile_name
  key_name               = var.key_name
  user_data = templatefile("${path.module}/user_data.sh", {
    aws_region            = var.aws_region
    artifacts_bucket_name = var.artifacts_bucket_name
    source_artifact_key   = var.source_artifact_key
    READY_DIR             = "/var/lib/repoiq"
  })
  user_data_replace_on_change          = true
  associate_public_ip_address          = true
  instance_initiated_shutdown_behavior = "terminate"

  root_block_device {
    volume_size           = var.root_volume_size
    volume_type           = var.root_volume_type
    delete_on_termination = true
  }

  tags = merge(var.common_tags, {
    Name      = "${var.project_name}-golden-image-builder"
    Project   = "RepoIQ"
    Role      = "GoldenImageBuilder"
    ManagedBy = "Terraform"
  })

  depends_on = [
    aws_s3_object.builder_setup,
    aws_s3_object.k3s_init_script,
    aws_s3_object.k3s_init_service,
    aws_s3_object.k8s_manifests["configmap.yaml"],
    aws_s3_object.k8s_manifests["secret.yaml"],
    aws_s3_object.k8s_manifests["postgres-pvc.yaml"],
    aws_s3_object.k8s_manifests["postgres-deployment.yaml"],
    aws_s3_object.k8s_manifests["postgres-service.yaml"],
    aws_s3_object.k8s_manifests["backend-deployment.yaml"],
    aws_s3_object.k8s_manifests["backend-service.yaml"],
    aws_s3_object.k8s_manifests["frontend-deployment.yaml"],
    aws_s3_object.k8s_manifests["frontend-service.yaml"],
    aws_s3_object.k8s_manifests["ingress.yaml"],
  ]
}

resource "null_resource" "wait_for_builder_ready" {
  triggers = {
    instance_id = aws_instance.golden_image_builder.id
    bucket_name = var.artifacts_bucket_name
    user_data_hash = md5(join("", concat(
      [
        file("${path.module}/user_data.sh"),
        file("${path.module}/builder_setup.sh"),
        file("${path.module}/repoiq-k3s-init.sh"),
        file("${path.module}/repoiq-k3s-init.service"),
      ],
      [
        for k, v in local.k8s_artifacts : file(v)
      ],
    )))
  }

  provisioner "local-exec" {
    command     = "python wait_for_builder_ready.py ${self.triggers.bucket_name} ${self.triggers.instance_id} ${var.aws_region}"
    working_dir = path.module
  }
}

resource "aws_ebs_snapshot" "golden_image" {
  description = "RepoIQ Golden Snapshot"
  volume_id   = aws_instance.golden_image_builder.root_block_device[0].volume_id

  tags = merge(var.common_tags, {
    Name      = "RepoIQ Golden Snapshot"
    Project   = "RepoIQ"
    Role      = "GoldenImageBuilder"
    ManagedBy = "Terraform"
  })

  depends_on = [null_resource.wait_for_builder_ready]
}

resource "aws_ami" "golden_image" {
  name                = "${var.project_name}-${var.environment}-golden"
  description         = "Bootable RepoIQ golden image"
  architecture        = "x86_64"
  ena_support         = true
  virtualization_type = "hvm"
  root_device_name    = "/dev/sda1"

  ebs_block_device {
    device_name           = "/dev/sda1"
    snapshot_id           = var.root_snapshot_id == "snap-0000000000000000" ? aws_ebs_snapshot.golden_image.id : var.root_snapshot_id
    volume_size           = var.root_volume_size
    volume_type           = var.root_volume_type
    delete_on_termination = true
  }

  depends_on = [aws_ebs_snapshot.golden_image]
}

resource "null_resource" "terminate_builder" {
  triggers = {
    snapshot_id = aws_ebs_snapshot.golden_image.id
  }

  depends_on = [aws_ebs_snapshot.golden_image]

  provisioner "local-exec" {
    command     = "python terminate_builder.py ${aws_instance.golden_image_builder.id} ${var.aws_region}"
    working_dir = path.module
  }
}
