#!/bin/bash
# Example smoke-test script for an applied environment
# Usage: ./test-environment.sh [command]
# Commands: health, upload-s3, ingest-api, query, logs

set -e

# Get outputs from terraform
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

API_URL=$(terraform output -raw api_url 2>/dev/null || echo "")
BUCKET=$(terraform output -raw s3_bucket_name 2>/dev/null || echo "")
LAMBDA_NAME=$(terraform output -raw lambda_function_name 2>/dev/null || echo "")

if [ -z "$API_URL" ] || [ -z "$BUCKET" ]; then
  echo "Error: Could not get terraform outputs. Make sure you're in this environment directory and terraform has been applied."
  exit 1
fi

# Remove https:// prefix for display
API_HOST="${API_URL#https://}"

case "${1:-help}" in
  health)
    echo "Checking API health..."
    curl -s "${API_URL}/health" | jq .
    echo ""
    echo "Checking readiness..."
    curl -s "${API_URL}/ready" | jq .
    ;;
  
  upload-s3)
    FILE="${2:-}"
    if [ -z "$FILE" ]; then
      echo "Usage: $0 upload-s3 <file-path>"
      exit 1
    fi
    if [ ! -f "$FILE" ]; then
      echo "Error: File not found: $FILE"
      exit 1
    fi
    FILENAME=$(basename "$FILE")
    echo "Uploading $FILE to s3://${BUCKET}/uploads/${FILENAME}..."
    aws s3 cp "$FILE" "s3://${BUCKET}/uploads/${FILENAME}"
    echo "✓ Uploaded. Lambda should process automatically."
    echo "Monitor with: $0 logs"
    ;;
  
  ingest-api)
    TEXT="${2:-}"
    SOURCE_URI="${3:-test-doc-$(date +%s)}"
    if [ -z "$TEXT" ]; then
      echo "Usage: $0 ingest-api <text-content> [source-uri]"
      exit 1
    fi
    echo "Ingesting document via API..."
    curl -s -X POST "${API_URL}/documents" \
      -H "Content-Type: application/json" \
      -d "{
        \"source_uri\": \"${SOURCE_URI}\",
        \"text\": \"${TEXT}\",
        \"metadata\": {\"test\": true}
      }" | jq .
    ;;
  
  query)
    QUERY="${2:-What information is available?}"
    echo "Querying RAG API..."
    curl -s -X POST "${API_URL}/query" \
      -H "Content-Type: application/json" \
      -d "{
        \"query\": \"${QUERY}\",
        \"top_k\": 5
      }" | jq .
    ;;
  
  collections)
    echo "Listing collections..."
    curl -s "${API_URL}/collections" | jq .
    ;;
  
  logs)
    if [ -z "$LAMBDA_NAME" ]; then
      echo "Error: Could not get Lambda function name"
      exit 1
    fi
    echo "Tailing Lambda logs (Ctrl+C to exit)..."
    aws logs tail "/aws/lambda/${LAMBDA_NAME}" --follow
    ;;
  
  info)
    echo "Environment Info:"
    echo "================="
    echo "API URL:     ${API_URL}"
    echo "API Host:    ${API_HOST}"
    echo "S3 Bucket:   ${BUCKET}"
    echo "Lambda:      ${LAMBDA_NAME}"
    echo ""
    echo "Available commands:"
    echo "  $0 health          - Check API health"
    echo "  $0 upload-s3 FILE - Upload file to S3 (triggers Lambda)"
    echo "  $0 ingest-api TEXT [URI] - Ingest document via API"
    echo "  $0 query [QUERY]  - Query RAG API"
    echo "  $0 collections    - List collections"
    echo "  $0 logs           - Tail Lambda logs"
    echo "  $0 info           - Show this info"
    ;;
  
  *)
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  health          - Check API health and readiness"
    echo "  upload-s3 FILE - Upload file to S3 (triggers Lambda ingestion)"
    echo "  ingest-api TEXT [URI] - Ingest document directly via API"
    echo "  query [QUERY]   - Query RAG API (default: 'What information is available?')"
    echo "  collections     - List Qdrant collections"
    echo "  logs            - Tail Lambda ingestion logs"
    echo "  info            - Show environment information"
    echo ""
    echo "Examples:"
    echo "  $0 health"
    echo "  $0 upload-s3 ../test-document.pdf"
    echo "  $0 ingest-api 'This is test content'"
    echo "  $0 query 'What is the privacy policy?'"
    exit 1
    ;;
esac
