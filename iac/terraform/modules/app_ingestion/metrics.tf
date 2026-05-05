# CloudWatch Metric Filters for Document Ingestion Pipeline

# Metric Filter: File Validation
resource "aws_cloudwatch_log_metric_filter" "file_validated" {
  name           = "${var.name}-ingestion-file-validated"
  log_group_name = aws_cloudwatch_log_group.ingestion.name
  pattern        = "\"File size validated\""

  metric_transformation {
    name          = "IngestionFileValidated"
    namespace     = "DocumentIngestion"
    default_value = 0
    value         = "1"
  }
}

# Metric Filter: Text Extraction Complete (implied by chunking)
resource "aws_cloudwatch_log_metric_filter" "text_extracted" {
  name           = "${var.name}-ingestion-text-extracted"
  log_group_name = aws_cloudwatch_log_group.ingestion.name
  pattern        = "\"Text extracted\""

  metric_transformation {
    name          = "IngestionTextExtracted"
    namespace     = "DocumentIngestion"
    default_value = 0
    value         = "1"
  }
}

# Metric Filter: Embeddings Generated
resource "aws_cloudwatch_log_metric_filter" "embeddings_generated" {
  name           = "${var.name}-ingestion-embeddings-generated"
  log_group_name = aws_cloudwatch_log_group.ingestion.name
  pattern        = "\"embeddings successfully\""

  metric_transformation {
    name          = "IngestionEmbeddingsGenerated"
    namespace     = "DocumentIngestion"
    default_value = 0
    value         = "1"
  }
}

# Metric Filter: Vectors Stored
resource "aws_cloudwatch_log_metric_filter" "vectors_stored" {
  name           = "${var.name}-ingestion-vectors-stored"
  log_group_name = aws_cloudwatch_log_group.ingestion.name
  pattern        = "\"Vectors stored successfully\""

  metric_transformation {
    name          = "IngestionVectorsStored"
    namespace     = "DocumentIngestion"
    default_value = 0
    value         = "1"
  }
}

# Metric Filter: Ingestion Success (doc_id present)
resource "aws_cloudwatch_log_metric_filter" "ingestion_success" {
  name           = "${var.name}-ingestion-success"
  log_group_name = aws_cloudwatch_log_group.ingestion.name
  pattern        = "\"Document ingestion completed\""

  metric_transformation {
    name          = "IngestionSuccess"
    namespace     = "DocumentIngestion"
    default_value = 0
    value         = "1"
  }
}

# Metric Filter: Ingestion Rejected
resource "aws_cloudwatch_log_metric_filter" "ingestion_rejected" {
  name           = "${var.name}-ingestion-rejected"
  log_group_name = aws_cloudwatch_log_group.ingestion.name
  pattern        = "\"rejected\""

  metric_transformation {
    name          = "IngestionRejected"
    namespace     = "DocumentIngestion"
    default_value = 0
    value         = "1"
  }
}

# Metric Filter: Ingestion Errors
resource "aws_cloudwatch_log_metric_filter" "ingestion_errors" {
  name           = "${var.name}-ingestion-errors"
  log_group_name = aws_cloudwatch_log_group.ingestion.name
  pattern        = "\"[ERROR]\""

  metric_transformation {
    name          = "IngestionErrors"
    namespace     = "DocumentIngestion"
    default_value = 0
    value         = "1"
  }
}

# Alarm: High Ingestion Error Rate
resource "aws_cloudwatch_metric_alarm" "ingestion_error_rate_high" {
  alarm_name          = "${var.name}-ingestion-error-rate-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  threshold           = "5"
  alarm_description   = "Alert when ingestion error rate exceeds 5%"
  treat_missing_data  = "notBreaching"

  metric_query {
    id          = "e1"
    expression  = "IF((m1 + m2 + m3) > 0, ((m1 + m2) / (m1 + m2 + m3)) * 100, 0)"
    label       = "Error Rate (%)"
    return_data = true
  }

  metric_query {
    id = "m1"
    metric {
      metric_name = "IngestionErrors"
      namespace   = "DocumentIngestion"
      period      = 300
      stat        = "Sum"
    }
  }

  metric_query {
    id = "m2"
    metric {
      metric_name = "IngestionRejected"
      namespace   = "DocumentIngestion"
      period      = 300
      stat        = "Sum"
    }
  }

  metric_query {
    id = "m3"
    metric {
      metric_name = "IngestionSuccess"
      namespace   = "DocumentIngestion"
      period      = 300
      stat        = "Sum"
    }
  }

  tags = {
    Name = "${var.name}-ingestion-error-rate-alarm"
  }
}
