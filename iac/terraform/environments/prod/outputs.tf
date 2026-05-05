output "name" { value = var.name }

output "aws_region" {
  description = "AWS region for this environment"
  value       = var.aws_region
}

output "api_url" {
  description = "API endpoint URL"
  value       = "https://${module.app_api.alb_dns_name}"
}

output "s3_bucket_name" {
  description = "S3 bucket for document uploads"
  value       = module.app_ingestion.s3_bucket_name
}

output "lambda_function_name" {
  description = "Lambda function name for ingestion"
  value       = module.app_ingestion.lambda_function_name
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = module.app_api.ecs_cluster_name
}

output "ecs_service_name" {
  description = "ECS service name"
  value       = module.app_api.ecs_service_name
}

output "ecr_repository_url" {
  description = "ECR repository URL for API images"
  value       = module.app_api.ecr_repository_url
}

output "ecr_repository_name" {
  description = "ECR repository name"
  value       = module.app_api.ecr_repository_name
}

output "feedback_table_name" {
  description = "DynamoDB table name for feedback storage"
  value       = module.feedback_storage.table_name
}
