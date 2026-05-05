variable "table_name" {
  description = "DynamoDB table name for feedback storage"
  type        = string
  default     = "rag-feedback"
}

variable "environment" {
  description = "Environment name (staging, prod)"
  type        = string
}

variable "ttl_days" {
  description = "TTL for feedback records in days (optional)"
  type        = number
  default     = 90
}
