"""Main FastAPI application for Novel RAG Chatbot."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from app.config import settings
from app.middleware.error_handler import validation_exception_handler, general_exception_handler
from app.database.postgres import init_db, close_db
from app.database.redis_client import init_redis, close_redis
from app.database.neo4j_client import init_neo4j, close_neo4j
from app.database.qdrant_client import init_qdrant
from app.api.v1 import chat, knowledge, chapters, search, sessions, graph, upload, documents, story, verification
from app.api.v1 import plot, timeline, research, branches, goals, worldbuilding, export, versions, consistency, writing

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("🚀 Starting Novel RAG Chatbot...")
    
    # Initialize databases
    await init_db()
    logger.info("✅ PostgreSQL connected")
    
    await init_redis()
    logger.info("✅ Redis connected")
    
    await init_neo4j()
    logger.info("✅ Neo4j connected")
    
    await init_qdrant()
    logger.info("✅ Qdrant connected")
    
    logger.info("🎉 Novel RAG Chatbot is ready!")
    
    yield
    
    # Cleanup
    logger.info("🛑 Shutting down Novel RAG Chatbot...")
    await close_db()
    await close_redis()
    await close_neo4j()
    logger.info("👋 Goodbye!")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="A RAG-powered chatbot for novel writing and discussion",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://localhost:5174", "http://127.0.0.1:5173", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers for unified error responses
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, general_exception_handler)

# Include API routers
app.include_router(chat.router, prefix=settings.API_V1_PREFIX, tags=["Chat"])
app.include_router(sessions.router, prefix=settings.API_V1_PREFIX, tags=["Sessions"])
app.include_router(knowledge.router, prefix=settings.API_V1_PREFIX, tags=["Knowledge Base"])
app.include_router(chapters.router, prefix=settings.API_V1_PREFIX, tags=["Chapters"])
app.include_router(search.router, prefix=settings.API_V1_PREFIX, tags=["Search"])
app.include_router(graph.router, prefix=settings.API_V1_PREFIX, tags=["Graph"])
app.include_router(upload.router, prefix=settings.API_V1_PREFIX, tags=["Upload"])
app.include_router(documents.router, prefix=settings.API_V1_PREFIX, tags=["Documents"])
app.include_router(story.router, prefix=settings.API_V1_PREFIX, tags=["Story Management"])
app.include_router(verification.router, prefix=settings.API_V1_PREFIX, tags=["Verification Hub"])
app.include_router(plot.router, prefix=settings.API_V1_PREFIX, tags=["Plot Lab"])
app.include_router(timeline.router, prefix=settings.API_V1_PREFIX, tags=["Timeline"])
app.include_router(research.router, prefix=settings.API_V1_PREFIX, tags=["Research"])
app.include_router(branches.router, prefix=settings.API_V1_PREFIX, tags=["Story Branches"])
app.include_router(goals.router, prefix=settings.API_V1_PREFIX, tags=["Writing Goals"])
app.include_router(worldbuilding.router, prefix=settings.API_V1_PREFIX + "/worldbuilding", tags=["Worldbuilding"])
app.include_router(export.router, prefix=settings.API_V1_PREFIX + "/export", tags=["Export"])
app.include_router(versions.router, prefix=settings.API_V1_PREFIX, tags=["Version Control"])
app.include_router(consistency.router, prefix=settings.API_V1_PREFIX + "/consistency", tags=["Consistency Checker"])
app.include_router(writing.router, prefix=settings.API_V1_PREFIX, tags=["Writing Assistant"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to Novel RAG Chatbot API",
        "docs": "/docs",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": settings.APP_NAME}

