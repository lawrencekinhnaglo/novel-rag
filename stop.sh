#!/bin/bash

# Novel RAG Stop Script
echo "🛑 Stopping Novel RAG..."

# Stop Docker services
echo "Stopping Docker services..."
docker compose down

# Kill any running Python/Node processes for this project (dev mode)
pkill -f "uvicorn app.main:app" 2>/dev/null
pkill -f "vite" 2>/dev/null

echo "✅ All services stopped"
echo ""
echo "To remove all data volumes: docker compose down -v"

