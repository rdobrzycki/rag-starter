# ECR Repository
resource "aws_ecr_repository" "api" {
  name                 = "${var.name}-api"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${var.name}-api-repo"
  }
}

resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 10 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = {
        type = "expire"
      }
    }]
  })
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.name}-api"
  retention_in_days = 30

  tags = {
    Name = "${var.name}-api-logs"
  }
}

# IAM Role for ECS Task Execution
resource "aws_iam_role" "ecs_task_execution_role" {
  name = "${var.name}-ecs-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_role_policy" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_task_execution_ecr_policy" {
  name = "${var.name}-ecs-task-execution-ecr-policy"
  role = aws_iam_role.ecs_task_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchGetImage",
          "ecr:GetDownloadUrlForLayer"
        ]
        Resource = aws_ecr_repository.api.arn
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:*"
      },
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath"
        ]
        Resource = "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:parameter/${var.name}/*"
      }
    ]
  })
}

# IAM Role for ECS Task (application)
resource "aws_iam_role" "ecs_task_role" {
  name = "${var.name}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

# IAM policy for Bedrock, SSM/Secrets Manager, and CloudWatch Logs access
resource "aws_iam_role_policy" "ecs_task_policy" {
  name = "${var.name}-ecs-task-policy"
  role = aws_iam_role.ecs_task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock:InvokeModel"
        ]
        Resource = [
          "arn:aws:bedrock:*:*:foundation-model/*",
          "arn:aws:bedrock:*:*:inference-profile/*"
        ]
      },
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
        Resource = "arn:aws:secretsmanager:*:*:secret:${var.name}/*"
      },
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "${aws_cloudwatch_log_group.api.arn}:*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_feedback_dynamodb_policy" {
  count      = var.attach_feedback_dynamodb_policy ? 1 : 0
  role       = aws_iam_role.ecs_task_role.name
  policy_arn = var.dynamodb_feedback_policy_arn
}

# ECS Cluster
resource "aws_ecs_cluster" "main" {
  name = "${var.name}-api-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "${var.name}-api-cluster"
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name = aws_ecs_cluster.main.name

  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    base              = 1
    weight            = 100
    capacity_provider = "FARGATE"
  }

  lifecycle {
    create_before_destroy = false
  }
}

# ECS Task Definition
resource "aws_ecs_task_definition" "api" {
  family                   = "${var.name}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_task_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([{
    name      = "${var.name}-api"
    image     = "${aws_ecr_repository.api.repository_url}:latest"
    essential = true
    portMappings = [{
      containerPort = 8000
      hostPort      = 8000
      protocol      = "tcp"
    }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = aws_cloudwatch_log_group.api.name
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
    environment = [
      {
        name  = "AWS_REGION"
        value = var.aws_region
      },
      {
        name  = "FEEDBACK_TABLE_NAME"
        value = var.feedback_table_name != "" ? var.feedback_table_name : "${var.name}-feedback"
      },
      {
        name  = "ENABLE_CLOUDWATCH_METRICS"
        value = "true"
      },
      {
        name  = "ENABLE_PROMETHEUS_METRICS"
        value = "false"
      },
      {
        name  = "CLOUDWATCH_NAMESPACE"
        value = "RAG/Starter"
      },
      {
        name  = "RATE_LIMIT_ENABLED"
        value = tostring(var.rate_limit_enabled)
      },
      {
        name  = "RATE_LIMIT_QUERY_PER_MINUTE"
        value = tostring(var.rate_limit_query_per_minute)
      },
      {
        name  = "RATE_LIMIT_INGESTION_PER_MINUTE"
        value = tostring(var.rate_limit_ingestion_per_minute)
      },
      {
        name  = "RATE_LIMIT_COLLECTION_PER_MINUTE"
        value = tostring(var.rate_limit_collection_per_minute)
      },
      {
        name  = "RATE_LIMIT_UTILITY_PER_MINUTE"
        value = tostring(var.rate_limit_utility_per_minute)
      }
    ]
    secrets = [
      {
        name      = "QDRANT_URL"
        valueFrom = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.name}/qdrant/credentials:url::"
      },
      {
        name      = "QDRANT_API_KEY"
        valueFrom = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret:${var.name}/qdrant/credentials:api_key::"
      },
      {
        name      = "QDRANT_COLLECTION"
        valueFrom = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/${var.name}/qdrant/collection"
      },
      {
        name      = "BEDROCK_EMBED_MODEL_ID"
        valueFrom = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/${var.name}/bedrock/embed-model-id"
      },
      {
        name      = "BEDROCK_LLM_MODEL_ID"
        valueFrom = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/${var.name}/bedrock/llm-model-id"
      }
    ]
  }])

  tags = {
    Name = "${var.name}-api-task-def"
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}
data "aws_elb_service_account" "current" {}

# Application Load Balancer
resource "aws_lb" "main" {
  name               = "${var.name}-api-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_security_group_id]
  subnets            = var.public_subnet_ids

  access_logs {
    bucket  = aws_s3_bucket.alb_logs.id
    enabled = true
  }

  tags = {
    Name = "${var.name}-api-alb"
  }

  depends_on = [
    aws_s3_bucket_lifecycle_configuration.alb_logs,
    aws_s3_bucket_policy.alb_logs,
    aws_s3_bucket_public_access_block.alb_logs
  ]
}

# S3 bucket for ALB logs
resource "aws_s3_bucket" "alb_logs" {
  bucket        = "${var.name}-alb-logs-${data.aws_caller_identity.current.account_id}"
  force_destroy = true

  tags = {
    Name = "${var.name}-alb-logs"
  }
}

# Disable block public access (required for ALB logging)
resource "aws_s3_bucket_public_access_block" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  block_public_acls       = true
  block_public_policy     = false
  ignore_public_acls      = true
  restrict_public_buckets = false
}

resource "aws_s3_bucket_lifecycle_configuration" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  rule {
    id     = "delete-old-logs"
    status = "Enabled"

    expiration {
      days = 90
    }
  }
}

# S3 bucket policy for ALB logs
# ELB account IDs by region: https://docs.aws.amazon.com/elasticloadbalancing/latest/application/load-balancer-access-logs.html
resource "aws_s3_bucket_policy" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = data.aws_elb_service_account.current.arn
        }
        Action = [
          "s3:PutObject",
          "s3:GetBucketAcl"
        ]
        Resource = [
          aws_s3_bucket.alb_logs.arn,
          "${aws_s3_bucket.alb_logs.arn}/*"
        ]
      }
    ]
  })
}

# Target Group
resource "aws_lb_target_group" "api" {
  name        = "${var.name}-api-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 3
    interval            = 30
    path                = "/health"
    matcher             = "200"
  }

  tags = {
    Name = "${var.name}-api-tg"
  }
}

# ALB Listener
resource "aws_lb_listener" "main" {
  load_balancer_arn = aws_lb.main.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

# ECS Service
resource "aws_ecs_service" "api" {
  name            = "${var.name}-api-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = 2
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_tasks_security_group_id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "${var.name}-api"
    container_port   = 8000
  }

  depends_on = [aws_lb_listener.main]

  tags = {
    Name = "${var.name}-api-service"
  }

  lifecycle {
    create_before_destroy = true
    ignore_changes        = [desired_count]
  }

  force_new_deployment = true
}

# Auto Scaling Target
resource "aws_appautoscaling_target" "ecs_target" {
  max_capacity       = 4
  min_capacity       = 2
  resource_id        = "service/${aws_ecs_cluster.main.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

# Auto Scaling Policy (CPU-based)
resource "aws_appautoscaling_policy" "ecs_policy_cpu" {
  name               = "${var.name}-cpu-autoscaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.ecs_target.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs_target.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs_target.service_namespace

  target_tracking_scaling_policy_configuration {
    predefined_metric_specification {
      predefined_metric_type = "ECSServiceAverageCPUUtilization"
    }
    target_value = 70.0
  }
}
