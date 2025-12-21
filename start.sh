#!/bin/bash

# Novel RAG Startup Script
echo "🚀 Starting Novel RAG..."

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

echo -e "${YELLOW}📦 Starting Docker services...${NC}"
docker-compose up -d

echo "⏳ Waiting for services to be ready..."
sleep 10

# Check service health
echo -e "${GREEN}✅ Services status:${NC}"
docker-compose ps

# Start backend
echo -e "\n${YELLOW}🐍 Starting Backend...${NC}"
cd backend

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

source venv/bin/activate
pip install -r requirements.txt -q

# Copy env file if not exists
if [ ! -f ".env" ]; then
    cp env.example .env
    echo "📝 Created .env file from template"
fi

echo "Starting FastAPI server..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

cd ..

# Start frontend
echo -e "\n${YELLOW}⚛️  Starting Frontend...${NC}"
cd frontend

if [ ! -d "node_modules" ]; then
    echo "Installing dependencies..."
    npm install
fi

echo "Starting Vite dev server..."
npm run dev &
FRONTEND_PID=$!

cd ..

echo -e "\n${GREEN}🎉 Novel RAG is ready!${NC}"
echo "  📖 Frontend: http://localhost:5173"
echo "  🔧 Backend:  http://localhost:8000"
echo "  📚 API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop all services"

# Wait for interrupt
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; docker-compose stop; exit" SIGINT SIGTERM
wait

