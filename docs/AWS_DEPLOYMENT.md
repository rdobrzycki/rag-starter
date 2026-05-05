# AWS Deployment

This is the canonical path for deploying the full stack into your own AWS account.

## Before You Start

You need:

- AWS credentials for `aws` and `terraform`
- Bedrock access in your target region
- a Terraform state bucket
- a managed Qdrant deployment and API key
- Docker
- Terraform `>= 1.6`
- `uv`
- `zip`

Your deployment credentials should be able to manage ECR, ECS, ALB, CloudWatch, Lambda, S3, IAM, SSM, Secrets Manager, DynamoDB, and optionally VPC networking.

## What Gets Deployed

- API service on ECS Fargate behind an ALB
- ingestion Lambda triggered by S3 uploads
- S3 buckets for uploads and Lambda code
- SSM parameters for models and runtime config
- Secrets Manager entry for Qdrant credentials
- CloudWatch logs, dashboards, alarms, and a feedback DynamoDB table

Main Terraform environments:

- `iac/terraform/environments/staging`
- `iac/terraform/environments/prod`

## Fast Path

1. Verify the repo locally.
2. Configure Terraform backend and variables.
3. Package the ingestion Lambda.
4. Run `terraform init`, `plan`, and `apply`.
5. Replace the placeholder Qdrant secret.
6. Build and push the API image.
7. Run smoke tests.

## Step 1: Verify The Repo

From the repository root:

```bash
cp .env.example .env
cd src && uv sync
cd ..
task test:unit
task local:test:integration
```

## Step 2: Configure Terraform

Example using staging:

```bash
cd iac/terraform/environments/staging
cp backend.tf.example backend.tf
cp terraform.tfvars.example terraform.tfvars
```

Set at least:

- `aws_region`
- `name`
- `git_commit_sha`

### Networking Choice

Create new networking:

```hcl
create_networking = true
```

Reuse existing networking:

```hcl
create_networking           = false
existing_vpc_id             = "vpc-..."
existing_public_subnet_ids  = ["subnet-...", "subnet-..."]
existing_private_subnet_ids = ["subnet-...", "subnet-..."]
```

## Step 3: Package The Ingestion Lambda

Terraform expects:

```text
iac/terraform/modules/app_ingestion/lambda.zip
```

Build it from the repository root:

```bash
./scripts/deploy/package_ingestion_lambda.sh
```

Use this any time ingestion code or ingestion dependencies change.

## Step 4: Apply Terraform

From the environment directory:

```bash
terraform init
terraform plan
terraform apply
```

The first apply creates the ECR repository, Qdrant secret, and SSM parameters used by ECS and Lambda.

## Step 5: Replace The Placeholder Qdrant Secret

The initial secret values are placeholders only.

Update them after first apply:

```bash
aws secretsmanager put-secret-value \
  --secret-id rag-starter/qdrant/credentials \
  --secret-string '{"url":"https://YOUR-QDRANT-ENDPOINT","api_key":"YOUR_QDRANT_API_KEY"}' \
  --region us-east-2
```

Replace:

- secret name with your environment `name`
- region with your chosen region
- secret payload with your real Qdrant values

Terraform also creates these SSM parameters, which you can keep or customize later:

- `/${name}/qdrant/collection`
- `/${name}/bedrock/embed-model-id`
- `/${name}/bedrock/llm-model-id`
- `/${name}/rag/similarity-threshold`
- `/${name}/rag/top-k-default`
- `/${name}/rag/top-k-max`

## Step 6: Push The API Image

From the repository root:

```bash
./scripts/deploy/push_api_image.sh iac/terraform/environments/staging
```

Optional tagged push:

```bash
./scripts/deploy/push_api_image.sh iac/terraform/environments/staging "$(git rev-parse --short HEAD)"
```

The script:

- reads Terraform outputs
- logs Docker into ECR
- builds the API image
- pushes `latest` and an optional custom tag
- forces a new ECS deployment

## Step 7: Smoke Test

From the staging environment directory:

```bash
./test-environment.sh info
./test-environment.sh health
./test-environment.sh ingest-api "This is a deployment smoke test."
./test-environment.sh query "What deployment smoke test content is available?"
```

To test the S3-triggered ingestion path:

```bash
./test-environment.sh upload-s3 ../../../../src/ingestion/local-dev/test-documents/sample.txt
./test-environment.sh logs
```

Useful Terraform outputs:

```bash
terraform output -raw api_url
terraform output -raw s3_bucket_name
terraform output -raw lambda_function_name
terraform output -raw ecr_repository_url
```

## Updating An Environment

When code changes:

1. Rebuild the Lambda zip if ingestion changed.
2. Run `terraform plan` and `terraform apply` if infra or parameter values changed.
3. Run `./scripts/deploy/push_api_image.sh ...` if the API changed.

If you only changed the Qdrant secret or ECS runtime config, force a new ECS deployment again with the API push script.

## Teardown

From the environment directory:

```bash
terraform destroy
```

Notes:

- several S3 buckets use `force_destroy = true`
- the Qdrant secret has a destroy-time force-delete helper
- the Terraform state bucket is external and is not destroyed by this stack
