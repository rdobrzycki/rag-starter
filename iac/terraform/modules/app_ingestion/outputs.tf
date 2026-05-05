output "lambda_function_arn" { value = aws_lambda_function.ingestion.arn }
output "lambda_function_name" { value = aws_lambda_function.ingestion.function_name }
output "s3_bucket_name" { value = aws_s3_bucket.documents.bucket }
output "s3_bucket_arn" { value = aws_s3_bucket.documents.arn }
output "log_group_name" { value = aws_cloudwatch_log_group.ingestion.name }
output "pipeline_dashboard_url" {
  value       = "https://console.aws.amazon.com/cloudwatch/home?region=${data.aws_region.current.name}#dashboards:name=${aws_cloudwatch_dashboard.ingestion_pipeline.dashboard_name}"
  description = "CloudWatch Dashboard for ingestion pipeline monitoring"
}
output "logs_dashboard_url" {
  value       = "https://console.aws.amazon.com/cloudwatch/home?region=${data.aws_region.current.name}#dashboards:name=${aws_cloudwatch_dashboard.ingestion_logs.dashboard_name}"
  description = "CloudWatch Dashboard for ingestion logs"
}
