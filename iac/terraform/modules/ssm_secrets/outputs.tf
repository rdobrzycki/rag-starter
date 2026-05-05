output "ssm_secrets_access_policy_arn" { value = aws_iam_policy.ssm_secrets_access.arn }
output "qdrant_credentials_secret_arn" { value = aws_secretsmanager_secret.qdrant_credentials.arn }
