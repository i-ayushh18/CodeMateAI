#!/bin/bash


set -e

echo "🚀 Deploying PR Agentic Workflow..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

if [ ! -f "config.toml" ]; then
    echo "❌ config.toml not found. Please ensure it exists in the current directory."
    exit 1
fi
echo "📁 Creating necessary directories..."
mkdir -p workspace logs

echo "📦 Building and starting containers..."
docker-compose up -d --build

echo "⏳ Waiting for containers to be ready..."
sleep 10

echo "📊 Container status:"
docker-compose ps

echo "📋 Recent logs:"
docker-compose logs --tail=20

echo " PR Agentic Workflow deployed successfully!"
echo ""
echo "Access points:"
echo "   - Agent API: http://localhost:8000"
echo "   - Logs: docker-compose logs -f"
echo "   - Stop: docker-compose down"
echo ""
echo "Usage:"
echo "   - Review mode: docker exec pr-agentic-workflow python run_agent.py --review --pr <PR_NUMBER>"
echo "   - Developer mode: docker exec pr-agentic-workflow python run_agent.py --developer --pr <PR_NUMBER>"
echo ""
echo "Troubleshooting:"
echo "   - Check logs: docker-compose logs -f pr-agent"
echo "   - Restart: docker-compose restart"
echo "   - Rebuild: docker-compose up -d --build"
