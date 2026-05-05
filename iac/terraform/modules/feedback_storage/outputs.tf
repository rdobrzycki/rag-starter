output "table_name" {
  description = "DynamoDB table name"
  value       = aws_dynamodb_table.feedback.name
}

output "table_arn" {
  description = "DynamoDB table ARN"
  value       = aws_dynamodb_table.feedback.arn
}

output "policy_arn" {
  description = "IAM policy ARN for DynamoDB access"
  value       = aws_iam_policy.dynamodb_feedback_policy.arn
}
