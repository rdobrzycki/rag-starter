variable "name" { type = string }
variable "aws_region" { type = string }
variable "vpc_id" { type = string }
variable "public_subnet_ids" { type = list(string) }
variable "private_subnet_ids" { type = list(string) }
variable "alb_security_group_id" { type = string }
variable "ecs_tasks_security_group_id" { type = string }
variable "feedback_table_name" {
  type        = string
  description = "DynamoDB table name for feedback records"
  default     = ""
}
variable "dynamodb_feedback_policy_arn" {
  type        = string
  description = "IAM policy ARN granting feedback DynamoDB access for ECS task role"
  default     = ""
}
variable "attach_feedback_dynamodb_policy" {
  type        = bool
  description = "Whether to attach the feedback DynamoDB IAM policy to the ECS task role"
  default     = false
}
variable "rate_limit_enabled" {
  type        = bool
  description = "Enable API rate limiting middleware"
  default     = true
}
variable "rate_limit_query_per_minute" {
  type        = number
  description = "Per-IP query endpoint requests per minute"
  default     = 100
}
variable "rate_limit_ingestion_per_minute" {
  type        = number
  description = "Per-IP ingestion endpoint requests per minute"
  default     = 30
}
variable "rate_limit_collection_per_minute" {
  type        = number
  description = "Per-IP collection endpoint requests per minute"
  default     = 50
}
variable "rate_limit_utility_per_minute" {
  type        = number
  description = "Per-IP utility endpoint requests per minute"
  default     = 60
}
