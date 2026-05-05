# CloudWatch Log Group for Lambda
resource "aws_cloudwatch_log_group" "ingestion" {
  name              = "/aws/lambda/${var.name}-ingestion"
  retention_in_days = 30

  tags = {
    Name = "${var.name}-ingestion-logs"
  }
}

# IAM Role for Lambda Execution
resource "aws_iam_role" "lambda_role" {
  name = "${var.name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

# Basic Lambda execution policy
resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

# Lambda policy for Bedrock and SSM/Secrets access
resource "aws_iam_role_policy" "lambda_policy" {
  name = "${var.name}-lambda-policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = "arn:aws:bedrock:*:*:foundation-model/*"
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters"
        ]
        Resource = "arn:aws:ssm:*:*:parameter/${var.name}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = "arn:aws:secretsmanager:*:*:secret:${var.name}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:GetObjectVersion"
        ]
        Resource = "arn:aws:s3:::*/*"
      }
    ]
  })
}

# S3 bucket for Lambda deployment package (avoids 50MB direct-upload limit; S3 allows up to 250MB)
resource "aws_s3_bucket" "lambda_code" {
  bucket        = "${var.name}-lambda-code-${data.aws_caller_identity.current.account_id}"
  force_destroy = true

  tags = {
    Name = "${var.name}-lambda-code"
  }
}

resource "aws_s3_object" "lambda_zip" {
  bucket = aws_s3_bucket.lambda_code.id
  key    = "ingestion/lambda.zip"
  source = "${path.module}/lambda.zip"
  etag   = filemd5("${path.module}/lambda.zip")
}

# S3 bucket for document uploads
resource "aws_s3_bucket" "documents" {
  bucket        = "${var.name}-documents-${data.aws_caller_identity.current.account_id}"
  force_destroy = true

  tags = {
    Name = "${var.name}-documents"
  }
}

# Create uploads/ prefix in S3 bucket
resource "aws_s3_object" "uploads_prefix" {
  bucket = aws_s3_bucket.documents.id
  key    = "uploads/"
  source = "/dev/null"
}

# S3 event notification to Lambda
resource "aws_s3_bucket_notification" "document_upload" {
  bucket     = aws_s3_bucket.documents.id
  depends_on = [aws_lambda_permission.allow_s3]

  lambda_function {
    lambda_function_arn = aws_lambda_function.ingestion.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "uploads/"
  }
}

# Lambda Function (S3 source avoids 50MB direct-upload limit)
resource "aws_lambda_function" "ingestion" {
  s3_bucket        = aws_s3_bucket.lambda_code.id
  s3_key           = aws_s3_object.lambda_zip.key
  function_name    = "${var.name}-ingestion"
  role             = aws_iam_role.lambda_role.arn
  handler          = "lambda_handler.handler.handler"
  source_code_hash = filebase64sha256("${path.module}/lambda.zip")
  runtime          = "python3.11"
  timeout          = 300
  memory_size      = 1024

  environment {
    variables = {
      SSM_PREFIX               = "/${var.name}"
      QDRANT_API_KEY_SECRET_ID = "${var.name}/qdrant/credentials"
      QDRANT_COLLECTION        = "documents"
      GIT_COMMIT_SHA           = var.git_commit_sha
      LOG_LEVEL                = "INFO"
    }
  }

  tags = {
    Name         = "${var.name}-ingestion"
    GitCommitSHA = var.git_commit_sha
    DeployedAt   = timestamp()
  }
}

# Lambda permission for S3 invocation
resource "aws_lambda_permission" "allow_s3" {
  statement_id  = "AllowExecutionFromS3"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingestion.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.documents.arn
}

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}
