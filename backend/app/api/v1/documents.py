"""Document upload and management API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Optional
import uuid
import json
import os

from app.database.postgres import get_db
from app.database.qdrant_client import get_vector_manager
from app.services.embeddings import generate_embedding, generate_embeddings
from app.services.document_service import (
    DocumentParser, TextChunker, KNOWLEDGE_CATEGORIES, SUPPORTED_LANGUAGES,
    get_document_parser, get_text_chunker
)

router = APIRouter()

# Max file size: 50MB
MAX_FILE_SIZE = 50 * 1024 * 1024


@router.get("/documents/categories")
async def get_categories():
    """Get available knowledge categories."""
    return {
        "categories": KNOWLEDGE_CATEGORIES,
        "languages": SUPPORTED_LANGUAGES
    }


@router.post("/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form("other"),
    language: str = Form("en"),
    db: AsyncSession = Depends(get_db)
):
    """Upload and process a document (PDF, DOCX, TXT)."""
    # Validate category
    if category not in KNOWLEDGE_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category. Must be one of: {KNOWLEDGE_CATEGORIES}")
    
    # Validate language
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Invalid language. Must be one of: {list(SUPPORTED_LANGUAGES.keys())}")
    
    # Validate file type
    filename = file.filename.lower()
    if filename.endswith('.pdf'):
        file_type = 'pdf'
    elif filename.endswith('.docx'):
        file_type = 'docx'
    elif filename.endswith('.txt'):
        file_type = 'txt'
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type. Use PDF, DOCX, or TXT.")
    
    # Read file content
    content = await file.read()
    
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 50MB.")
    
    # Parse document
    parser = get_document_parser()
    try:
        text_content = await parser.parse(content, file_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    if not text_content.strip():
        raise HTTPException(status_code=400, detail="Document appears to be empty or could not be parsed.")
    
    # Generate unique filename
    unique_filename = f"{uuid.uuid4().hex}_{file.filename}"
    
    # Chunk the document for long context support
    chunker = get_text_chunker()
    chunks = chunker.chunk_text(text_content)
    
    # Save document metadata to database
    result = await db.execute(
        text("""
            INSERT INTO documents (filename, original_filename, file_type, file_size, 
                                  category, content, chunk_count, language, metadata)
            VALUES (:filename, :original_filename, :file_type, :file_size,
                    :category, :content, :chunk_count, :language, :metadata)
            RETURNING id, filename, original_filename, file_type, category, chunk_count, language, created_at
        """),
        {
            "filename": unique_filename,
            "original_filename": file.filename,
            "file_type": file_type,
            "file_size": len(content),
            "category": category,
            "content": text_content,
            "chunk_count": len(chunks),
            "language": language,
            "metadata": json.dumps({"word_count": len(text_content.split())})
        }
    )
    doc_row = result.fetchone()
    await db.commit()
    
    # Process and store chunks with embeddings
    vector_manager = get_vector_manager()
    chunk_points = []
    
    for chunk in chunks:
        embedding = generate_embedding(chunk["content"])
        
        # Save chunk to database
        chunk_result = await db.execute(
            text("""
                INSERT INTO document_chunks (document_id, chunk_index, content, token_count, embedding, metadata)
                VALUES (:doc_id, :chunk_index, :content, :token_count, :embedding, :metadata)
                RETURNING id
            """),
            {
                "doc_id": doc_row.id,
                "chunk_index": chunk["chunk_index"],
                "content": chunk["content"],
                "token_count": chunk["token_count"],
                "embedding": str(embedding),
                "metadata": json.dumps({"category": category, "language": language})
            }
        )
        chunk_id = chunk_result.fetchone().id
        
        chunk_points.append({
            "id": f"doc_{doc_row.id}_chunk_{chunk['chunk_index']}",
            "vector": embedding,
            "payload": {
                "document_id": doc_row.id,
                "chunk_id": chunk_id,
                "chunk_index": chunk["chunk_index"],
                "content": chunk["content"][:500],
                "category": category,
                "language": language,
                "filename": file.filename
            }
        })
    
    await db.commit()
    
    # Store in Qdrant for vector search
    if chunk_points:
        # Create document chunks collection if needed
        try:
            vector_manager.upsert_vectors(collection="knowledge", points=chunk_points)
        except Exception as e:
            print(f"Qdrant error: {e}")
    
    return {
        "id": doc_row.id,
        "filename": doc_row.original_filename,
        "file_type": doc_row.file_type,
        "category": doc_row.category,
        "language": doc_row.language,
        "chunk_count": doc_row.chunk_count,
        "created_at": doc_row.created_at.isoformat(),
        "message": f"Document processed successfully with {len(chunks)} chunks"
    }


@router.get("/documents")
async def list_documents(
    category: Optional[str] = None,
    language: Optional[str] = None,
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """List uploaded documents."""
    query = """
        SELECT id, filename, original_filename, file_type, file_size, 
               category, chunk_count, language, metadata, created_at
        FROM documents
        WHERE 1=1
    """
    params = {"limit": limit, "skip": skip}
    
    if category:
        query += " AND category = :category"
        params["category"] = category
    
    if language:
        query += " AND language = :language"
        params["language"] = language
    
    query += " ORDER BY created_at DESC LIMIT :limit OFFSET :skip"
    
    result = await db.execute(text(query), params)
    rows = result.fetchall()
    
    return {
        "documents": [
            {
                "id": row.id,
                "filename": row.original_filename,
                "file_type": row.file_type,
                "file_size": row.file_size,
                "category": row.category,
                "chunk_count": row.chunk_count,
                "language": row.language,
                "metadata": row.metadata,
                "created_at": row.created_at.isoformat()
            }
            for row in rows
        ]
    }


@router.get("/documents/{document_id}")
async def get_document(
    document_id: int,
    include_content: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """Get document details."""
    result = await db.execute(
        text("""
            SELECT id, filename, original_filename, file_type, file_size,
                   category, content, chunk_count, language, metadata, created_at
            FROM documents
            WHERE id = :doc_id
        """),
        {"doc_id": document_id}
    )
    row = result.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc = {
        "id": row.id,
        "filename": row.original_filename,
        "file_type": row.file_type,
        "file_size": row.file_size,
        "category": row.category,
        "chunk_count": row.chunk_count,
        "language": row.language,
        "metadata": row.metadata,
        "created_at": row.created_at.isoformat()
    }
    
    if include_content:
        doc["content"] = row.content
    
    return doc


@router.get("/documents/{document_id}/chunks")
async def get_document_chunks(
    document_id: int,
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """Get chunks for a document."""
    result = await db.execute(
        text("""
            SELECT id, chunk_index, content, token_count, created_at
            FROM document_chunks
            WHERE document_id = :doc_id
            ORDER BY chunk_index
            LIMIT :limit OFFSET :skip
        """),
        {"doc_id": document_id, "limit": limit, "skip": skip}
    )
    rows = result.fetchall()
    
    return {
        "document_id": document_id,
        "chunks": [
            {
                "id": row.id,
                "chunk_index": row.chunk_index,
                "content": row.content,
                "token_count": row.token_count
            }
            for row in rows
        ]
    }


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a document and its chunks."""
    # Get chunk count first
    count_result = await db.execute(
        text("SELECT COUNT(*) FROM document_chunks WHERE document_id = :doc_id"),
        {"doc_id": document_id}
    )
    chunk_count = count_result.scalar()
    
    # Delete from database (chunks will cascade)
    result = await db.execute(
        text("DELETE FROM documents WHERE id = :doc_id RETURNING id"),
        {"doc_id": document_id}
    )
    
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Document not found")
    
    await db.commit()
    
    # Delete from Qdrant
    vector_manager = get_vector_manager()
    chunk_ids = [f"doc_{document_id}_chunk_{i}" for i in range(chunk_count)]
    if chunk_ids:
        try:
            vector_manager.delete_vectors("knowledge", chunk_ids)
        except Exception as e:
            print(f"Qdrant deletion error: {e}")
    
    return {"message": "Document deleted successfully"}


@router.post("/documents/upload-to-chat")
async def upload_to_chat(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    language: str = Form("en"),
    db: AsyncSession = Depends(get_db)
):
    """Upload a document to be included in chat context."""
    # Validate file type
    filename = file.filename.lower()
    if filename.endswith('.pdf'):
        file_type = 'pdf'
    elif filename.endswith('.docx'):
        file_type = 'docx'
    elif filename.endswith('.txt'):
        file_type = 'txt'
    else:
        raise HTTPException(status_code=400, detail="Unsupported file type. Use PDF, DOCX, or TXT.")
    
    # Read and parse file
    content = await file.read()
    
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Maximum size is 50MB.")
    
    parser = get_document_parser()
    try:
        text_content = await parser.parse(content, file_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    # Chunk for context
    chunker = get_text_chunker()
    chunks = chunker.chunk_text(text_content)
    
    # Return parsed content and summary for chat inclusion
    summary = text_content[:1000] + "..." if len(text_content) > 1000 else text_content
    
    return {
        "filename": file.filename,
        "file_type": file_type,
        "content_length": len(text_content),
        "chunk_count": len(chunks),
        "summary": summary,
        "full_content": text_content,
        "language": language,
        "message": "Document parsed successfully. Content is ready for chat."
    }

