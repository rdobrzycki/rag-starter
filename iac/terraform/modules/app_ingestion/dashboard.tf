# CloudWatch Dashboard for Document Ingestion Pipeline Monitoring

resource "aws_cloudwatch_dashboard" "ingestion_pipeline" {
  dashboard_name = "${var.name}-ingestion-pipeline"

  dashboard_body = jsonencode({
    widgets = [
      # Title Widget
      {
        type = "text"
        properties = {
          markdown = "# Document Ingestion Pipeline\n\n**Real-time monitoring of ingestion stages: S3 Upload → Lambda → File Validation → Text Extraction → Chunking → Bedrock Embeddings → Qdrant Storage**"
        }
      },

      # Stage 1: File Validation
      {
        type = "metric"
        properties = {
          metrics = [
            ["DocumentIngestion", "IngestionFileValidated", { label = "Files Validated", stat = "Sum" }]
          ]
          period = 60
          stat   = "Sum"
          region = var.aws_region
          title  = "Stage 3: File Validation ✓"
          view   = "singleValue"
          yAxis = {
            left = { min = 0 }
          }
        }
      },

      # Stage 2: Text Extraction
      {
        type = "metric"
        properties = {
          metrics = [
            ["DocumentIngestion", "IngestionTextExtracted", { label = "Texts Extracted", stat = "Sum" }]
          ]
          period = 60
          stat   = "Sum"
          region = var.aws_region
          title  = "Stage 4: Text Extraction ✓"
          view   = "singleValue"
          yAxis = {
            left = { min = 0 }
          }
        }
      },

      # Stage 3: Embeddings Generated
      {
        type = "metric"
        properties = {
          metrics = [
            ["DocumentIngestion", "IngestionEmbeddingsGenerated", { label = "Embeddings Generated", stat = "Sum" }]
          ]
          period = 60
          stat   = "Sum"
          region = var.aws_region
          title  = "Stage 6: Bedrock Embeddings ✓"
          view   = "singleValue"
          yAxis = {
            left = { min = 0 }
          }
        }
      },

      # Stage 4: Vectors Stored
      {
        type = "metric"
        properties = {
          metrics = [
            ["DocumentIngestion", "IngestionVectorsStored", { label = "Vectors Stored", stat = "Sum" }]
          ]
          period = 60
          stat   = "Sum"
          region = var.aws_region
          title  = "Stage 7: Qdrant Storage ✓"
          view   = "singleValue"
          yAxis = {
            left = { min = 0 }
          }
        }
      },

      # Success Rate Timeline
      {
        type = "metric"
        properties = {
          metrics = [
            ["DocumentIngestion", "IngestionSuccess", { label = "Successful", stat = "Sum" }],
            [".", "IngestionRejected", { label = "Rejected", stat = "Sum" }],
            [".", "IngestionErrors", { label = "Errors", stat = "Sum" }]
          ]
          period = 300
          stat   = "Sum"
          region = var.aws_region
          title  = "Ingestion Results Timeline"
          view   = "timeSeries"
          yAxis = {
            left = { min = 0 }
          }
        }
      },

      # Success/Error Distribution
      {
        type = "metric"
        properties = {
          metrics = [
            ["DocumentIngestion", "IngestionSuccess"],
            [".", "IngestionRejected"],
            [".", "IngestionErrors"]
          ]
          period               = 300
          stat                 = "Sum"
          region               = var.aws_region
          title                = "Success vs Rejection vs Error (Last Hour)"
          view                 = "pie"
          setPeriodToTimeRange = true
        }
      },

      # Lambda Invocation Logs
      {
        type = "log"
        properties = {
          query   = "SOURCE '/aws/lambda/${var.name}-ingestion' | fields @timestamp, @message | filter @message like /Processing S3 object|File size validated|Text extracted|Generating embeddings|Generated.*embeddings|Storing.*vectors|Vectors stored|Document ingestion completed/ | stats count() by @message | sort count() desc"
          region  = var.aws_region
          title   = "Pipeline Stage Frequency (Last 4 Hours)"
          stacked = false
        }
      }
    ]
  })
}

# CloudWatch Dashboard for Ingestion Logs
resource "aws_cloudwatch_dashboard" "ingestion_logs" {
  dashboard_name = "${var.name}-ingestion-logs"

  dashboard_body = jsonencode({
    widgets = [
      {
        type = "text"
        properties = {
          markdown = "# Document Ingestion Logs\n\n**Detailed view of pipeline execution logs with correlation IDs**"
        }
      },

      # Recent Success Logs
      {
        type = "log"
        properties = {
          query  = "SOURCE '/aws/lambda/${var.name}-ingestion' | fields @timestamp, @message, @logStream | filter @message like /Document ingestion completed/ | stats count() by @logStream"
          region = var.aws_region
          title  = "Recent Successful Ingestions"
        }
      },

      # Error Logs
      {
        type = "log"
        properties = {
          query  = "SOURCE '/aws/lambda/${var.name}-ingestion' | fields @timestamp, @message, @logStream | filter @message like /ERROR|error|rejected/ | sort @timestamp desc | limit 20"
          region = var.aws_region
          title  = "Recent Errors & Rejections"
        }
      },

      # Performance Timeline
      {
        type = "log"
        properties = {
          query  = "SOURCE '/aws/lambda/${var.name}-ingestion' | fields @timestamp, @message | filter @message like /Processing S3 object|Document ingestion completed/ | stats count() by bin(5m)"
          region = var.aws_region
          title  = "Ingestion Volume Over Time"
        }
      }
    ]
  })
}
