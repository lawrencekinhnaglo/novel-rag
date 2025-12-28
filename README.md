# Novel RAG Chatbot 📚✨

A powerful RAG (Retrieval-Augmented Generation) supported chatbot designed for novel writing and discussion. Built with FastAPI, React, and multiple vector/graph databases.

![Novel RAG](https://img.shields.io/badge/Novel-RAG-purple?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge)
![React](https://img.shields.io/badge/React-18-cyan?style=for-the-badge)
![Docker](https://img.shields.io/badge/Docker-Ready-blue?style=for-the-badge)

## 🚀 Quick Start (Docker - Recommended)

### Prerequisites
- Docker & Docker Compose
- DeepSeek API key (or local Ollama)

### One-Command Start

```bash
# Clone the repository
git clone https://github.com/lawrencekinhnaglo/novel-rag.git
cd novel-rag/novel-rag

# Start with DeepSeek API
DEEPSEEK_API_KEY=your_api_key docker compose up -d

# Or use the start script
export DEEPSEEK_API_KEY=your_api_key
./start.sh
```

### Access the Application

| Service | URL |
|---------|-----|
| **Frontend** | http://localhost:5173 |
| **Backend API** | http://localhost:8000 |
| **API Docs** | http://localhost:8000/docs |
| **Neo4j Browser** | http://localhost:7474 |
| **Qdrant Dashboard** | http://localhost:6333/dashboard |

## 📦 Docker Services

All services are containerized and managed via docker-compose:

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| `frontend` | Custom (Nginx) | 5173 | React UI |
| `backend` | Custom (Python) | 8000 | FastAPI Server |
| `postgres` | pgvector/pgvector:pg16 | 5432 | Main Database + Vectors |
| `qdrant` | qdrant/qdrant | 6333 | Vector Search |
| `neo4j` | neo4j:5.15.0 | 7474, 7687 | Graph Database |
| `redis` | redis:7-alpine | 6379 | Session Cache |
| `ollama` | ollama/ollama | 11434 | Local LLM (Qwen3) |

## 🐳 Docker Commands Reference

### Start/Stop

```bash
# Start all services (with build)
DEEPSEEK_API_KEY=your_key docker compose up -d --build

# Start all services (without rebuild)
docker compose up -d

# Stop all services (keep data)
docker compose down

# Stop and remove all data
docker compose down -v

# View logs
docker compose logs -f              # All services
docker compose logs -f backend      # Backend only
docker compose logs -f frontend     # Frontend only
```

### Service Management

```bash
# Rebuild specific service
docker compose up -d --build backend
docker compose up -d --build frontend

# Restart specific service
docker compose restart backend

# Check service health
docker compose ps

# View resource usage
docker stats
```

### Database Access

```bash
# PostgreSQL CLI
docker exec -it novel-rag-postgres psql -U novelrag -d novel_rag_db

# Redis CLI
docker exec -it novel-rag-redis redis-cli

# Neo4j Cypher Shell
docker exec -it novel-rag-neo4j cypher-shell -u neo4j -p novelrag_neo4j
```

## 💾 Backup & Restore

### Backup Current State

```bash
# Create backups directory
mkdir -p backups

# Backup PostgreSQL
docker exec novel-rag-postgres pg_dump -U novelrag -d novel_rag_db > backups/postgres_backup.sql

# Backup Redis
docker exec novel-rag-redis redis-cli BGSAVE
docker cp novel-rag-redis:/data/dump.rdb backups/redis_backup.rdb

# Backup Qdrant
curl -X POST 'http://localhost:6333/snapshots'
# Then copy the snapshot from the container
```

### Restore from Backup

The repository includes a pre-configured backup. To restore:

```bash
# Start all containers first
docker compose up -d

# Wait for services to be healthy
sleep 30

# Run the restore script
./backups/restore.sh
```

Or manually:

```bash
# Restore PostgreSQL
docker exec -i novel-rag-postgres psql -U novelrag -d novel_rag_db < backups/postgres_backup.sql

# Restore Redis
docker cp backups/redis_backup.rdb novel-rag-redis:/data/dump.rdb
docker compose restart redis

# Restore Qdrant
docker cp backups/qdrant_backup.snapshot novel-rag-qdrant:/qdrant/snapshots/
curl -X POST "http://localhost:6333/snapshots/recover" \
  -H "Content-Type: application/json" \
  -d '{"location": "/qdrant/snapshots/qdrant_backup.snapshot"}'
```

## 🔧 Configuration

### Environment Variables

Set these before running `docker compose up`:

| Variable | Description | Default |
|----------|-------------|---------|
| `DEEPSEEK_API_KEY` | DeepSeek API key | Required |
| `OLLAMA_URL` | Ollama URL | http://ollama:11434 |
| `OLLAMA_MODEL` | Ollama model | qwen3:8b |
| `DEFAULT_LLM_PROVIDER` | Default LLM | deepseek |

### Using Local Ollama (Instead of DeepSeek)

```bash
# Start with Ollama
docker compose up -d

# Pull Qwen3 model
docker exec novel-rag-ollama ollama pull qwen3:8b

# The system uses Ollama for intent detection by default
```

### CPU-Only Mode (No GPU)

```bash
# For machines without NVIDIA GPU
docker compose -f docker-compose.yml -f docker-compose.cpu.yml up -d
```

## 🌟 Features

### 🤖 AI-Powered Chat
- **DeepSeek API**: Cloud-based LLM for novel writing
- **Ollama + Qwen3**: Local LLM for intent detection
- **Streaming Responses**: Real-time token streaming
- **Intent Detection**: Automatically detects user intent (write chapter, create character, etc.)

### 📖 Story Management
- **Series & Books**: Hierarchical story organization
- **Chapters**: Store and organize novel content
- **Characters**: Track character profiles with verification
- **World Rules**: Define and enforce world-building rules
- **Foreshadowing**: Plant and track story seeds

### 🔍 RAG (Retrieval-Augmented Generation)
- **Vector Search**: Semantic search using all-MiniLM-L6-v2
- **Multiple Collections**: Chapters, knowledge, ideas
- **Smart Context**: Automatically retrieves relevant context

### ✅ Verification Hub
- Auto-extracted story elements need approval before RAG use
- Edit, approve, or reject extracted characters, rules, etc.

### 📤 Document Upload
- Support for PDF, DOCX, TXT files
- Auto-extraction of story elements
- Chunked processing for large documents

## 📁 Project Structure

```
novel-rag/
├── backend/
│   ├── Dockerfile           # Backend container
│   ├── app/
│   │   ├── api/v1/          # API endpoints
│   │   ├── services/        # Business logic
│   │   └── database/        # DB clients
│   └── requirements.txt
├── frontend/
│   ├── Dockerfile           # Frontend container
│   ├── nginx.conf           # Nginx config
│   └── src/                 # React source
├── backups/                 # Database backups
│   ├── postgres_backup.sql
│   ├── qdrant_backup.snapshot
│   ├── redis_backup.rdb
│   └── restore.sh
├── init-scripts/
│   └── postgres/init.sql    # DB schema
├── docker-compose.yml       # Main compose file
├── docker-compose.cpu.yml   # CPU-only override
├── start.sh                 # Start script
└── stop.sh                  # Stop script
```

## 🔌 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/chat` | POST | Send chat message |
| `/api/v1/chat/stream` | POST | Stream response |
| `/api/v1/chat/detect-intent` | POST | Detect user intent |
| `/api/v1/chapters` | GET/POST | Manage chapters |
| `/api/v1/knowledge` | GET/POST | Manage knowledge |
| `/api/v1/story/series` | GET/POST | Manage series |
| `/api/v1/verification/*` | Various | Verification hub |
| `/api/v1/upload` | POST | Upload documents |

Full API docs: http://localhost:8000/docs

## 🛠️ Development Mode

For hot-reload development:

```bash
# Start databases only
docker compose up -d postgres redis qdrant neo4j

# Backend (terminal 1)
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (terminal 2)
cd frontend
npm install
npm run dev
```

Or use the start script:

```bash
./start.sh --dev
```

## 📝 License

MIT License - feel free to use this for your own projects!

## 🤝 Contributing

Contributions welcome! Please feel free to submit a Pull Request.

---

Built with ❤️ for novel writers and storytellers
