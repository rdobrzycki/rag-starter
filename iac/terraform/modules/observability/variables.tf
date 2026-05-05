variable "name" {
  type = string
}

variable "aws_region" {
  type        = string
  default     = "us-east-1"
  description = "AWS region for CloudWatch resources"
}

variable "cloudwatch_namespace" {
  type        = string
  default     = "RAG/Starter"
  description = "CloudWatch namespace for custom metrics"
}

variable "ecs_cluster_name" {
  type        = string
  description = "ECS cluster name for service-level CloudWatch metrics"
}

variable "ecs_service_name" {
  type        = string
  description = "ECS service name for service-level CloudWatch metrics"
}

variable "sns_topic_arn_oncall" {
  type        = string
  default     = ""
  description = "SNS topic ARN for on-call alerts (optional)"
}

variable "sns_topic_arn_product" {
  type        = string
  default     = ""
  description = "SNS topic ARN for product team alerts (optional)"
}

variable "sns_topic_arn_engineering" {
  type        = string
  default     = ""
  description = "SNS topic ARN for engineering team alerts (optional)"
}

variable "error_rate_threshold" {
  type        = number
  default     = 1.0
  description = "Error rate threshold percentage for alarm"
}

variable "refusal_rate_threshold" {
  type        = number
  default     = 30.0
  description = "Refusal rate threshold percentage for alarm"
}

variable "latency_p95_threshold_ms" {
  type        = number
  default     = 5000
  description = "P95 latency threshold in milliseconds for alarm"
}
