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

output "s3_bucket_arn" {
  description = "S3 bucket ARN (for IAM or cross-account)"
  value       = module.app_ingestion.s3_bucket_arn
}

output "lambda_function_name" {
  description = "Lambda function name for ingestion"
  value       = module.app_ingestion.lambda_function_name
}

output "lambda_function_arn" {
  description = "Lambda function ARN"
  value       = module.app_ingestion.lambda_function_arn
}

output "ingestion_log_group_name" {
  description = "CloudWatch log group for ingestion Lambda (e.g. aws logs tail)"
  value       = module.app_ingestion.log_group_name
}

output "ingestion_pipeline_dashboard_url" {
  description = "CloudWatch dashboard for ingestion pipeline"
  value       = module.app_ingestion.pipeline_dashboard_url
}

output "ingestion_logs_dashboard_url" {
  description = "CloudWatch dashboard for ingestion logs"
  value       = module.app_ingestion.logs_dashboard_url
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
