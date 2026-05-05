# SSM Parameter Store for configuration
resource "aws_ssm_parameter" "qdrant_collection" {
  name  = "/${var.name}/qdrant/collection"
  type  = "String"
  value = "documents"

  tags = {
    Name = "${var.name}-qdrant-collection"
  }
}

resource "aws_ssm_parameter" "bedrock_embed_model" {
  name  = "/${var.name}/bedrock/embed-model-id"
  type  = "String"
  value = "amazon.titan-embed-text-v2:0"

  tags = {
    Name = "${var.name}-bedrock-embed-model"
  }
}

resource "aws_ssm_parameter" "bedrock_llm_model" {
  name  = "/${var.name}/bedrock/llm-model-id"
  type  = "String"
  value = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"

  tags = {
    Name = "${var.name}-bedrock-llm-model"
  }
}

resource "aws_ssm_parameter" "similarity_threshold" {
  name  = "/${var.name}/rag/similarity-threshold"
  type  = "String"
  value = "0.70"

  tags = {
    Name = "${var.name}-similarity-threshold"
  }
}

resource "aws_ssm_parameter" "top_k_default" {
  name  = "/${var.name}/rag/top-k-default"
  type  = "String"
  value = "5"

  tags = {
    Name = "${var.name}-top-k-default"
  }
}

resource "aws_ssm_parameter" "top_k_max" {
  name  = "/${var.name}/rag/top-k-max"
  type  = "String"
  value = "20"

  tags = {
    Name = "${var.name}-top-k-max"
  }
}

# Secrets Manager for sensitive credentials
resource "aws_secretsmanager_secret" "qdrant_credentials" {
  name                    = "${var.name}/qdrant/credentials"
  recovery_window_in_days = 7

  tags = {
    Name = "${var.name}-qdrant-credentials"
  }
}

# Force-delete secret on destroy to avoid recovery window blocking immediate recreate
resource "null_resource" "force_delete_secret" {
  depends_on = [aws_secretsmanager_secret.qdrant_credentials]

  triggers = {
    secret_arn = aws_secretsmanager_secret.qdrant_credentials.arn
  }

  provisioner "local-exec" {
    when    = destroy
    command = "aws secretsmanager delete-secret --secret-id ${self.triggers.secret_arn} --force-delete-without-recovery || true"
  }
}

resource "aws_secretsmanager_secret_version" "qdrant_credentials" {
  secret_id = aws_secretsmanager_secret.qdrant_credentials.id
  secret_string = jsonencode({
    # Placeholder values for first apply and local examples only.
    # Replace these with your real managed Qdrant endpoint and API key before
    # relying on the deployed API or ingestion pipeline.
    url     = "http://qdrant:6333"
    api_key = ""
  })
}

# IAM policy for SSM and Secrets Manager access
resource "aws_iam_policy" "ssm_secrets_access" {
  name        = "${var.name}-ssm-secrets-access"
  description = "Policy for accessing SSM parameters and Secrets Manager"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath"
        ]
        Resource = "arn:aws:ssm:*:*:parameter/${var.name}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = aws_secretsmanager_secret.qdrant_credentials.arn
      }
    ]
  })
}
