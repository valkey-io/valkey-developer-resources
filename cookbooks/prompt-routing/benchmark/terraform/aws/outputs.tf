output "instance_id" {
  description = "ID of the GPU host."
  value       = aws_instance.host.id
}

output "availability_zone" {
  description = "Availability zone the host landed in."
  value       = aws_subnet.public.availability_zone
}

output "ami_id" {
  description = "Deep Learning AMI the host was launched from."
  value       = aws_instance.host.ami
}

output "ssm_shell" {
  description = "Open a shell on the host (needs the AWS CLI and Session Manager plugin)."
  value       = "aws ssm start-session --region ${var.region} --target ${aws_instance.host.id}"
}

output "ssm_port_forward_example" {
  description = "Forward the host's port 8000 (e.g. the Envoy router) to localhost:8000."
  value       = "aws ssm start-session --region ${var.region} --target ${aws_instance.host.id} --document-name AWS-StartPortForwardingSession --parameters 'portNumber=[\"8000\"],localPortNumber=[\"8000\"]'"
}

output "region" {
  description = "Region the host runs in."
  value       = var.region
}
