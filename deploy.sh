#!/bin/bash

# PR Agentic Workflow - Deployment Script
# This script deploys the PR agent using Docker

set -e

echo "🚀 Deploying PR Agentic Workflow..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check if config.toml exists
if [ ! -f "config.toml" ]; then
    echo "❌ config.toml not found. Please ensure it exists in the current directory."
    exit 1
fi

# Create necessary directories
echo "📁 Creating necessary directories..."
mkdir -p workspace logs

# Build and start the containers
echo "📦 Building and starting containers..."
docker-compose up -d --build

# Wait for containers to be ready
echo "⏳ Waiting for containers to be ready..."
sleep 10

# Check container status
echo "📊 Container status:"
docker-compose ps

# Show logs
echo "📋 Recent logs:"
docker-compose logs --tail=20

echo "✅ PR Agentic Workflow deployed successfully!"
echo ""
echo "🌐 Access points:"
echo "   - Agent API: http://localhost:8000"
echo "   - Logs: docker-compose logs -f"
echo "   - Stop: docker-compose down"
echo ""
echo "🔧 Usage:"
echo "   - Review mode: docker exec pr-agentic-workflow python run_agent.py --review --pr <PR_NUMBER>"
echo "   - Developer mode: docker exec pr-agentic-workflow python run_agent.py --developer --pr <PR_NUMBER>"
echo ""
echo "📝 Environment Variables:"
echo "   - GITHUB_TOKEN: Your GitHub personal access token"
echo "   - PERPLEXITY_API_KEY: Your Perplexity API key"
echo ""
echo "🔍 Troubleshooting:"
echo "   - Check logs: docker-compose logs -f pr-agent"
echo "   - Restart: docker-compose restart"
echo "   - Rebuild: docker-compose up -d --build"
