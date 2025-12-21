# Novel RAG Chatbot 📚✨

A powerful RAG (Retrieval-Augmented Generation) supported chatbot designed for novel writing and discussion. Built with FastAPI, React, and multiple vector/graph databases.

![Novel RAG](https://img.shields.io/badge/Novel-RAG-purple?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge)
![React](https://img.shields.io/badge/React-18-cyan?style=for-the-badge)

## Features

### 🤖 AI-Powered Chat
- **Local LLM Support**: Connect to LM Studio (Llama 4 Maverick) or any OpenAI-compatible local model
- **DeepSeek API**: Alternative cloud-based LLM option
- **Streaming Responses**: Real-time token streaming for responsive conversations
- **Context-Aware**: Automatically retrieves relevant context from your novel

### 📖 Content Management
- **Chapters**: Store and organize your novel chapters with full-text search
- **Knowledge Base**: Save important conversations, research, and notes
- **Ideas**: Capture plot ideas, character concepts, and story elements

### 🔍 RAG (Retrieval-Augmented Generation)
- **Vector Search**: Semantic search using sentence-transformers embeddings
- **Multiple Collections**: Search across chapters, knowledge, and ideas
- **Configurable**: Enable/disable RAG, adjust similarity thresholds

### 🌐 Web Search
- **DuckDuckGo Integration**: Search the web for research and inspiration
- **News Search**: Find relevant news articles
- **Image Search**: Find reference images for characters/settings

### 🕸️ Story Graph (Neo4j)
- **Characters**: Track all characters with descriptions and attributes
- **Relationships**: Define relationships between characters
- **Locations**: Document story locations and their connections
- **Timeline**: Create a chronological event timeline
- **Context Retrieval**: Automatically include graph data in AI responses

### 💾 Data Persistence
- **PostgreSQL + pgvector**: Structured data with vector similarity search
- **Qdrant**: High-performance vector database for embeddings
- **Neo4j**: Graph database for relationships and timeline
- **Redis**: Conversation caching for fast access

### 💬 Multi-Chat Support
- Multiple conversation sessions
- Chat history persistence
- Save chats to knowledge base

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend (React)                      │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌────────┐ │
│  │  Chat   │ │Chapters │ │Knowledge│ │  Graph  │ │Settings│ │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └───┬────┘ │
└───────┼──────────┼─────────┼─────────┼─────────┼────────────┘
        │          │         │         │         │
        └──────────┴────┬────┴─────────┴─────────┘
                        │
                   HTTP/REST API
                        │
┌───────────────────────┴─────────────────────────────────────┐
│                    Backend (FastAPI)                         │
│  ┌────────────┐  ┌────────────┐  ┌────────────────────────┐ │
│  │LLM Service │  │RAG Service │  │   Graph Manager        │ │
│  │- LM Studio │  │- Embeddings│  │   - Characters         │ │
│  │- DeepSeek  │  │- Search    │  │   - Relationships      │ │
│  └─────┬──────┘  └─────┬──────┘  │   - Timeline           │ │
│        │               │         └───────────┬────────────┘ │
└────────┼───────────────┼─────────────────────┼──────────────┘
         │               │                     │
    ┌────┴────┐    ┌─────┴─────┐         ┌─────┴─────┐
    │LM Studio│    │  Qdrant   │         │   Neo4j   │
    │  API    │    │  Vector   │         │   Graph   │
    └─────────┘    └───────────┘         └───────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
         ┌────┴────┐          ┌─────┴─────┐
         │PostgreSQL│          │   Redis   │
         │+ pgvector│          │   Cache   │
         └──────────┘          └───────────┘
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 18+
- LM Studio (optional, for local LLM)

### 1. Clone and Setup

```bash
cd novel-rag

# Copy environment file
cp backend/env.example backend/.env

# Edit .env with your settings (especially if using DeepSeek)
```

### 2. Start Docker Services

```bash
# Start all databases (PostgreSQL, Qdrant, Neo4j, Redis)
docker-compose up -d

# Wait for services to be healthy
docker-compose ps
```

### 3. Start Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Start Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

### 5. Open the App

Visit [http://localhost:5173](http://localhost:5173)

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LM_STUDIO_URL` | LM Studio API endpoint | `http://localhost:1234/v1` |
| `LM_STUDIO_MODEL` | Model name in LM Studio | `llama-4-maverick` |
| `DEEPSEEK_API_KEY` | DeepSeek API key | (optional) |
| `DEFAULT_LLM_PROVIDER` | Default provider: `lm_studio` or `deepseek` | `lm_studio` |
| `POSTGRES_*` | PostgreSQL connection settings | See env.example |
| `NEO4J_*` | Neo4j connection settings | See env.example |
| `REDIS_*` | Redis connection settings | See env.example |
| `QDRANT_*` | Qdrant connection settings | See env.example |
| `RAG_TOP_K` | Number of RAG results to retrieve | `5` |
| `RAG_SIMILARITY_THRESHOLD` | Minimum similarity score | `0.7` |

### LM Studio Setup

1. Download and install [LM Studio](https://lmstudio.ai/)
2. Download Llama 4 Maverick or your preferred model
3. Start the local server (default port: 1234)
4. The app will auto-connect

## API Documentation

Once the backend is running, access:
- Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

### Key Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/chat` | POST | Send a chat message |
| `/api/v1/chat/stream` | POST | Stream a chat response |
| `/api/v1/sessions` | GET/POST | Manage chat sessions |
| `/api/v1/chapters` | GET/POST | Manage chapters |
| `/api/v1/knowledge` | GET/POST | Manage knowledge base |
| `/api/v1/search` | POST | Semantic search |
| `/api/v1/search/web` | POST | Web search |
| `/api/v1/graph/*` | Various | Graph database operations |

## Usage

### Writing Sessions
1. Start a new chat
2. Enable RAG to include context from your novel
3. Toggle Web Search for research
4. Enable Story Graph for character/timeline context

### Saving Knowledge
1. Have a productive conversation
2. Click "Save to Knowledge" to preserve insights
3. Future chats will reference this knowledge

### Managing Your Novel
1. Add chapters in the Chapters page
2. Create character profiles in Story Graph
3. Define relationships between characters
4. Build your timeline with events

## Development

### Project Structure

```
novel-rag/
├── backend/
│   ├── app/
│   │   ├── api/v1/          # API routes
│   │   ├── database/        # Database clients
│   │   ├── services/        # Business logic
│   │   ├── config.py        # Configuration
│   │   └── main.py          # FastAPI app
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── pages/           # Page components
│   │   ├── store/           # Zustand store
│   │   └── lib/             # Utilities & API
│   └── package.json
├── init-scripts/
│   └── postgres/            # Database init scripts
├── docker-compose.yml
└── README.md
```

## License

MIT License - feel free to use this for your own projects!

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.

---

Built with ❤️ for novel writers and storytellers

