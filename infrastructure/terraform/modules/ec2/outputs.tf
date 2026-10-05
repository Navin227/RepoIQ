output "ami_id" {
  description = "Bootable AMI used for the ephemeral demo EC2 launch configuration"
  value       = aws_ami.golden_image.id
}

output "golden_snapshot_id" {
  description = "Root snapshot ID created from the golden image builder EC2 instance"
  value       = aws_ebs_snapshot.golden_image.id
}
