#!/bin/bash

# Novel RAG Startup Script
echo "🚀 Starting Novel RAG..."

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker first.${NC}"
    exit 1
fi

# Check for .env file and DEEPSEEK_API_KEY
if [ ! -f "backend/.env" ] && [ -z "$DEEPSEEK_API_KEY" ]; then
    echo -e "${YELLOW}⚠️  No .env file found and DEEPSEEK_API_KEY not set.${NC}"
    echo "   You can set it by running: export DEEPSEEK_API_KEY=your_key"
fi

# Parse arguments
DEV_MODE=false
if [ "$1" == "--dev" ] || [ "$1" == "-d" ]; then
    DEV_MODE=true
fi

if [ "$DEV_MODE" = true ]; then
    echo -e "${YELLOW}🔧 Starting in development mode (hot reload)...${NC}"
    
    # Start only database services with Docker
    echo -e "${YELLOW}📦 Starting database services...${NC}"
    docker compose up -d postgres redis neo4j qdrant
    
    echo "⏳ Waiting for services to be ready..."
    sleep 10
    
    # Check service health
    echo -e "${GREEN}✅ Database services status:${NC}"
    docker compose ps
    
    # Start backend
    echo -e "\n${YELLOW}🐍 Starting Backend (dev mode)...${NC}"
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
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --loop asyncio &
    BACKEND_PID=$!
    
    cd ..
    
    # Start frontend
    echo -e "\n${YELLOW}⚛️  Starting Frontend (dev mode)...${NC}"
    cd frontend
    
    if [ ! -d "node_modules" ]; then
        echo "Installing dependencies..."
        npm install
    fi
    
    echo "Starting Vite dev server..."
    npm run dev &
    FRONTEND_PID=$!
    
    cd ..
    
    echo -e "\n${GREEN}🎉 Novel RAG is ready (dev mode)!${NC}"
    echo "  📖 Frontend: http://localhost:5173"
    echo "  🔧 Backend:  http://localhost:8000"
    echo "  📚 API Docs: http://localhost:8000/docs"
    echo ""
    echo "Press Ctrl+C to stop all services"
    
    # Wait for interrupt
    trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; docker compose stop postgres redis neo4j qdrant; exit" SIGINT SIGTERM
    wait
else
    echo -e "${YELLOW}🐳 Starting in Docker mode...${NC}"
    
    # Build and start all services
    docker compose up --build -d
    
    echo "⏳ Waiting for services to be ready..."
    sleep 15
    
    # Check service health
    echo -e "\n${GREEN}✅ Services status:${NC}"
    docker compose ps
    
    echo -e "\n${GREEN}🎉 Novel RAG is ready!${NC}"
    echo "  📖 Frontend: http://localhost:5173"
    echo "  🔧 Backend:  http://localhost:8000"
    echo "  📚 API Docs: http://localhost:8000/docs"
    echo "  🔍 Neo4j:    http://localhost:7474"
    echo ""
    echo "To view logs: docker compose logs -f"
    echo "To stop:      docker compose down"
fi
