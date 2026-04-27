#!/usr/bin/env bash
# Test the Dockerfile locally before deploying to Render

set -e

echo "🐳 Building Docker image..."
docker build -t sentinel-core-api:test .

echo ""
echo "🚀 Running container on port 8000..."
docker run -it --rm \
  -p 8000:8000 \
  -e SENTINEL_GITHUB_TOKEN="${SENTINEL_GITHUB_TOKEN:-test_token}" \
  -e SENTINEL_LOG_LEVEL=INFO \
  -e SENTINEL_JSON_LOGS=true \
  sentinel-core-api:test

echo ""
echo "✅ Container started. Test with:"
echo "   curl http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop."
