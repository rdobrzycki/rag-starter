#!/bin/bash
# Quick query test script

QUERY="${1:-What is the policy?}"
TOP_K="${2:-5}"

curl -s -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d "{\"query\":\"$QUERY\",\"top_k\":$TOP_K}" | jq
