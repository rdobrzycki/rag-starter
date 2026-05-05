# DynamoDB Table for feedback storage
resource "aws_dynamodb_table" "feedback" {
  name         = var.table_name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "request_id"
  range_key    = "timestamp"
  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  attribute {
    name = "request_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "N"
  }

  attribute {
    name = "trace_id"
    type = "S"
  }

  attribute {
    name = "rating"
    type = "N"
  }

  # GSI for alternative tracing
  global_secondary_index {
    name            = "trace_id-timestamp-gsi"
    hash_key        = "trace_id"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  # GSI for analytics queries (rating distribution)
  global_secondary_index {
    name            = "rating-timestamp-gsi"
    hash_key        = "rating"
    range_key       = "timestamp"
    projection_type = "ALL"
  }

  tags = {
    Name        = var.table_name
    Environment = var.environment
  }
}

# IAM policy for DynamoDB access
resource "aws_iam_policy" "dynamodb_feedback_policy" {
  name        = "${var.table_name}-policy"
  description = "Policy for accessing feedback DynamoDB table"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "dynamodb:PutItem",
        "dynamodb:GetItem",
        "dynamodb:Query",
        "dynamodb:Scan",
        "dynamodb:UpdateItem",
      ]
      Resource = [
        aws_dynamodb_table.feedback.arn,
        "${aws_dynamodb_table.feedback.arn}/index/*"
      ]
    }]
  })
}
