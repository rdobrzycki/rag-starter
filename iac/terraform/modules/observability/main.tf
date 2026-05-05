# CloudWatch Log Group for application logs
resource "aws_cloudwatch_log_group" "application" {
  name              = "/aws/rag-api/${var.name}"
  retention_in_days = 30

  tags = {
    Name = "${var.name}-application-logs"
  }
}

# CloudWatch Log Group for system logs
resource "aws_cloudwatch_log_group" "system" {
  name              = "/aws/system/${var.name}"
  retention_in_days = 14

  tags = {
    Name = "${var.name}-system-logs"
  }
}

# SNS Topics for alarm notifications
resource "aws_sns_topic" "oncall" {
  count = var.sns_topic_arn_oncall == "" ? 1 : 0
  name  = "${var.name}-oncall-alerts"

  tags = {
    Name = "${var.name}-oncall-alerts"
  }
}

resource "aws_sns_topic" "product" {
  count = var.sns_topic_arn_product == "" ? 1 : 0
  name  = "${var.name}-product-alerts"

  tags = {
    Name = "${var.name}-product-alerts"
  }
}

resource "aws_sns_topic" "engineering" {
  count = var.sns_topic_arn_engineering == "" ? 1 : 0
  name  = "${var.name}-engineering-alerts"

  tags = {
    Name = "${var.name}-engineering-alerts"
  }
}

locals {
  sns_oncall_arn      = var.sns_topic_arn_oncall != "" ? var.sns_topic_arn_oncall : aws_sns_topic.oncall[0].arn
  sns_product_arn     = var.sns_topic_arn_product != "" ? var.sns_topic_arn_product : aws_sns_topic.product[0].arn
  sns_engineering_arn = var.sns_topic_arn_engineering != "" ? var.sns_topic_arn_engineering : aws_sns_topic.engineering[0].arn
}

# CloudWatch Metric Alarm for ECS CPU
resource "aws_cloudwatch_metric_alarm" "ecs_cpu_high" {
  alarm_name          = "${var.name}-ecs-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "Alert when ECS CPU exceeds 80%"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = var.ecs_service_name
  }

  tags = {
    Name = "${var.name}-ecs-cpu-alarm"
  }
}

# CloudWatch Metric Alarm for ECS Memory
resource "aws_cloudwatch_metric_alarm" "ecs_memory_high" {
  alarm_name          = "${var.name}-ecs-memory-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/ECS"
  period              = "300"
  statistic           = "Average"
  threshold           = "85"
  alarm_description   = "Alert when ECS Memory exceeds 85%"
  treat_missing_data  = "notBreaching"

  dimensions = {
    ClusterName = var.ecs_cluster_name
    ServiceName = var.ecs_service_name
  }

  tags = {
    Name = "${var.name}-ecs-memory-alarm"
  }
}

# CloudWatch Alarm: Error Rate
resource "aws_cloudwatch_metric_alarm" "error_rate_high" {
  alarm_name          = "${var.name}-error-rate-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  threshold           = var.error_rate_threshold
  alarm_description   = "Alert when error rate exceeds ${var.error_rate_threshold}%"
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "e1"
    expression  = "(m1 / m2) * 100"
    label       = "Error Rate (%)"
    return_data = true
  }

  metric_query {
    id = "m1"
    metric {
      metric_name = "ErrorCount"
      namespace   = var.cloudwatch_namespace
      period      = 300
      stat        = "Sum"
      dimensions = {
        Endpoint = "/query"
      }
    }
  }

  metric_query {
    id = "m2"
    metric {
      metric_name = "QueryCount"
      namespace   = var.cloudwatch_namespace
      period      = 300
      stat        = "Sum"
      dimensions = {
        Endpoint = "/query"
      }
    }
  }

  alarm_actions = [local.sns_oncall_arn]

  tags = {
    Name = "${var.name}-error-rate-alarm"
  }
}

# CloudWatch Alarm: Refusal Rate
resource "aws_cloudwatch_metric_alarm" "refusal_rate_high" {
  alarm_name          = "${var.name}-refusal-rate-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  threshold           = var.refusal_rate_threshold
  alarm_description   = "Alert when refusal rate exceeds ${var.refusal_rate_threshold}%"
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "e1"
    expression  = "(m1 / m2) * 100"
    label       = "Refusal Rate (%)"
    return_data = true
  }

  metric_query {
    id = "m1"
    metric {
      metric_name = "RefusalCount"
      namespace   = var.cloudwatch_namespace
      period      = 300
      stat        = "Sum"
    }
  }

  metric_query {
    id = "m2"
    metric {
      metric_name = "QueryCount"
      namespace   = var.cloudwatch_namespace
      period      = 300
      stat        = "Sum"
    }
  }

  alarm_actions = [local.sns_product_arn]

  tags = {
    Name = "${var.name}-refusal-rate-alarm"
  }
}

# CloudWatch Alarm: Query Latency P95
resource "aws_cloudwatch_metric_alarm" "query_latency_high" {
  alarm_name          = "${var.name}-query-latency-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "QueryLatency"
  namespace           = var.cloudwatch_namespace
  period              = "300"
  statistic           = "Average"
  threshold           = var.latency_p95_threshold_ms
  alarm_description   = "Alert when P95 query latency exceeds ${var.latency_p95_threshold_ms}ms"
  treat_missing_data  = "notBreaching"

  dimensions = {
    Endpoint = "/query"
  }

  alarm_actions = [local.sns_engineering_arn]

  tags = {
    Name = "${var.name}-query-latency-alarm"
  }
}

# CloudWatch Alarm: Bedrock Failures
resource "aws_cloudwatch_metric_alarm" "bedrock_errors" {
  alarm_name          = "${var.name}-bedrock-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "BedrockErrorCount"
  namespace           = var.cloudwatch_namespace
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "Alert when Bedrock errors occur"
  treat_missing_data  = "notBreaching"

  alarm_actions = [local.sns_engineering_arn]

  tags = {
    Name = "${var.name}-bedrock-error-alarm"
  }
}

# CloudWatch Alarm: Qdrant Failures
resource "aws_cloudwatch_metric_alarm" "qdrant_errors" {
  alarm_name          = "${var.name}-qdrant-errors"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "QdrantErrorCount"
  namespace           = var.cloudwatch_namespace
  period              = "300"
  statistic           = "Sum"
  threshold           = "0"
  alarm_description   = "Alert when Qdrant errors occur"
  treat_missing_data  = "notBreaching"

  alarm_actions = [local.sns_engineering_arn]

  tags = {
    Name = "${var.name}-qdrant-error-alarm"
  }
}

# CloudWatch Dashboard: Product Guarantees
resource "aws_cloudwatch_dashboard" "product_guarantees" {
  dashboard_name = "${var.name}-product-guarantees"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            [var.cloudwatch_namespace, "RefusalCount"],
            [var.cloudwatch_namespace, "QueryCount"]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "Refusal Rate"
          view   = "timeSeries"
          yAxis = {
            left = {
              min = 0
            }
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            [var.cloudwatch_namespace, "RefusalCount", "RefusalReason", "NO_RELEVANT_CONTEXT"],
            [var.cloudwatch_namespace, "RefusalCount", "RefusalReason", "INSUFFICIENT_INFORMATION"]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "Refusal Reasons"
          view   = "timeSeries"
        }
      }
    ]
  })
}

# CloudWatch Dashboard: Application Metrics
resource "aws_cloudwatch_dashboard" "application" {
  dashboard_name = "${var.name}-application"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            [var.cloudwatch_namespace, "QueryLatency", { stat = "p50", label = "P50" }],
            [".", ".", { stat = "p95", label = "P95" }],
            [".", ".", { stat = "p99", label = "P99" }]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "Query Latency (P50, P95, P99)"
          view   = "timeSeries"
          yAxis = {
            left = {
              min   = 0
              label = "Milliseconds"
            }
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            [var.cloudwatch_namespace, "QueryCount", { stat = "Sum", label = "Total Queries" }],
            [".", "ErrorCount", { stat = "Sum", label = "Errors" }]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "Query Volume and Errors"
          view   = "timeSeries"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            [var.cloudwatch_namespace, "BedrockLatency", { stat = "Average", label = "Bedrock" }],
            [".", "QdrantLatency", { stat = "Average", label = "Qdrant" }]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "Component Latency"
          view   = "timeSeries"
          yAxis = {
            left = {
              min   = 0
              label = "Milliseconds"
            }
          }
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            [var.cloudwatch_namespace, "BedrockCallCount", { stat = "Sum", label = "Bedrock Calls" }],
            [".", "QdrantCallCount", { stat = "Sum", label = "Qdrant Calls" }]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "Component Call Volume"
          view   = "timeSeries"
        }
      }
    ]
  })
}

# CloudWatch Dashboard: System Health
resource "aws_cloudwatch_dashboard" "system_health" {
  dashboard_name = "${var.name}-system-health"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ClusterName", var.ecs_cluster_name, "ServiceName", var.ecs_service_name, { stat = "Average" }],
            [".", "MemoryUtilization", "ClusterName", var.ecs_cluster_name, "ServiceName", var.ecs_service_name, { stat = "Average" }]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "ECS Performance Metrics"
          view   = "timeSeries"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            [var.cloudwatch_namespace, "BedrockCallCount", "Status", "success", { label = "Success" }],
            [".", "BedrockErrorCount", { label = "Errors" }]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "Bedrock Success Rate"
          view   = "timeSeries"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            [var.cloudwatch_namespace, "QdrantCallCount", "Status", "success", { label = "Success" }],
            [".", "QdrantErrorCount", { label = "Errors" }]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "Qdrant Success Rate"
          view   = "timeSeries"
        }
      },
      {
        type = "metric"
        properties = {
          metrics = [
            [var.cloudwatch_namespace, "DocumentsIngested", { stat = "Sum", label = "Ingested" }],
            [".", "DocumentIngestionErrors", { stat = "Sum", label = "Errors" }]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "Document Ingestion"
          view   = "timeSeries"
        }
      }
    ]
  })
}

# CloudWatch Dashboard: Main (Legacy - kept for backward compatibility)
resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.name}-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric"
        properties = {
          metrics = [
            ["AWS/ECS", "CPUUtilization", "ClusterName", var.ecs_cluster_name, "ServiceName", var.ecs_service_name, { stat = "Average" }],
            [".", "MemoryUtilization", "ClusterName", var.ecs_cluster_name, "ServiceName", var.ecs_service_name, { stat = "Average" }]
          ]
          period = 300
          stat   = "Average"
          region = var.aws_region
          title  = "ECS Performance Metrics"
        }
      },
      {
        type = "log"
        properties = {
          query  = "fields @timestamp, @message | stats count() by bin(5m)"
          region = var.aws_region
          title  = "Log Event Count"
        }
      }
    ]
  })
}
