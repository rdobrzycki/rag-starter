output "application_log_group_name" {
  value = aws_cloudwatch_log_group.application.name
}

output "system_log_group_name" {
  value = aws_cloudwatch_log_group.system.name
}

output "dashboard_url" {
  value = "https://console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.main.dashboard_name}"
}

output "product_guarantees_dashboard_url" {
  value = "https://console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.product_guarantees.dashboard_name}"
}

output "application_dashboard_url" {
  value = "https://console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.application.dashboard_name}"
}

output "system_health_dashboard_url" {
  value = "https://console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#dashboards:name=${aws_cloudwatch_dashboard.system_health.dashboard_name}"
}

output "sns_topic_oncall_arn" {
  value = local.sns_oncall_arn
}

output "sns_topic_product_arn" {
  value = local.sns_product_arn
}

output "sns_topic_engineering_arn" {
  value = local.sns_engineering_arn
}

output "error_rate_alarm_arn" {
  value = aws_cloudwatch_metric_alarm.error_rate_high.arn
}

output "refusal_rate_alarm_arn" {
  value = aws_cloudwatch_metric_alarm.refusal_rate_high.arn
}

output "query_latency_alarm_arn" {
  value = aws_cloudwatch_metric_alarm.query_latency_high.arn
}

output "bedrock_error_alarm_arn" {
  value = aws_cloudwatch_metric_alarm.bedrock_errors.arn
}

output "qdrant_error_alarm_arn" {
  value = aws_cloudwatch_metric_alarm.qdrant_errors.arn
}
