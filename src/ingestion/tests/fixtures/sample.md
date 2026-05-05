# Sample Markdown Document

## Overview

This is a sample **Markdown** document for testing the Lambda ingestion service.

## Features

- Document chunking
- Vector embeddings
- Metadata preservation
- Semantic search

## Architecture

```
User Upload → S3 → Lambda → Bedrock → Qdrant
```

### Components

1. **S3 Bucket**: Document storage
2. **Lambda Function**: Processing pipeline
3. **AWS Bedrock**: AI embeddings
4. **Qdrant**: Vector database

## Testing

This document tests:
- Markdown parsing
- Code block handling
- Heading structure
- List formatting

## Conclusion

The ingestion service handles Markdown documents seamlessly, preserving formatting information while extracting text for vector embeddings.
