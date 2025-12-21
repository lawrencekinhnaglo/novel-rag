"""Document upload API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Optional
import json
import uuid

from app.database.postgres import get_db
from app.database.qdrant_client import get_vector_manager
from app.services.embeddings import generate_embedding
from app.services.document_service import get_document_processor, KNOWLEDGE_CATEGORIES

router = APIRouter()

# Max file size: 50MB
MAX_FILE_SIZE = 50 * 1024 * 1024

ALLOWED_EXTENSIONS = {'.pdf', '.docx'}


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    category: str = Form(None),
    title: str = Form(None),
    tags: str = Form(""),
    chunk_size: int = Form(1000),
    chunk_overlap: int = Form(200),
    auto_categorize: bool = Form(True),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a DOCX or PDF document and add it to the knowledge base.
    
    The document will be:
    1. Parsed to extract text
    2. Auto-categorized (if enabled)
    3. Split into chunks for better retrieval
    4. Embedded and stored in vector database
    """
    # Validate file extension
    filename = file.filename
    ext = filename[filename.rfind('.'):].lower() if '.' in filename else ''
    
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Read file content
    content = await file.read()
    
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // 1024 // 1024}MB"
        )
    
    # Process document
    processor = get_document_processor()
    
    try:
        text_content = processor.extract_text(content, filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process document: {str(e)}")
    
    if not text_content.strip():
        raise HTTPException(status_code=400, detail="Document appears to be empty")
    
    # Auto-categorize if not specified
    if not category and auto_categorize:
        category = processor.auto_categorize(text_content, filename)
    elif not category:
        category = 'notes'
    
    if category not in KNOWLEDGE_CATEGORIES:
        category = 'notes'
    
    # Parse tags
    tag_list = [t.strip() for t in tags.split(',') if t.strip()] if tags else []
    
    # Use filename as title if not provided
    if not title:
        title = filename.rsplit('.', 1)[0]
    
    # Get token count
    token_count = processor.count_tokens(text_content)
    
    # Chunk the document for better retrieval
    chunks = processor.chunk_text(text_content, chunk_size, chunk_overlap)
    
    # Store the main document
    main_embedding = generate_embedding(text_content[:8000])  # Embed summary/beginning
    
    result = await db.execute(
        text("""
            INSERT INTO knowledge_base (source_type, title, content, embedding, tags, metadata)
            VALUES (:source_type, :title, :content, :embedding, :tags, :metadata)
            RETURNING id, source_type, title, content, tags, created_at
        """),
        {
            "source_type": category,
            "title": title,
            "content": text_content,
            "embedding": str(main_embedding),
            "tags": tag_list,
            "metadata": json.dumps({
                "filename": filename,
                "token_count": token_count,
                "chunk_count": len(chunks),
                "file_type": ext
            })
        }
    )
    await db.commit()
    row = result.fetchone()
    doc_id = row.id
    
    # Store chunks in Qdrant for better retrieval
    vector_manager = get_vector_manager()
    chunk_points = []
    
    for chunk in chunks:
        chunk_embedding = generate_embedding(chunk['text'])
        chunk_id = f"{doc_id}_chunk_{chunk['index']}"
        
        chunk_points.append({
            "id": hash(chunk_id) % (2**63),  # Convert to int for Qdrant
            "vector": chunk_embedding,
            "payload": {
                "doc_id": doc_id,
                "chunk_index": chunk['index'],
                "content": chunk['text'],
                "title": title,
                "category": category,
                "token_count": chunk['token_count']
            }
        })
    
    vector_manager.upsert_vectors(collection="knowledge", points=chunk_points)
    
    return {
        "id": doc_id,
        "title": title,
        "category": category,
        "filename": filename,
        "token_count": token_count,
        "chunk_count": len(chunks),
        "tags": tag_list,
        "message": "Document uploaded and processed successfully"
    }


@router.get("/upload/categories")
async def get_categories():
    """Get available knowledge categories."""
    return {
        "categories": KNOWLEDGE_CATEGORIES,
        "descriptions": {
            "draft": "Draft content, work in progress",
            "concept": "Story concepts and high-level ideas",
            "character": "Character profiles, backstories, traits",
            "chapter": "Chapter content and scenes",
            "settings": "World-building, magic systems, technology",
            "plot": "Plot outlines, story arcs, conflicts",
            "dialogue": "Dialogue snippets and conversations",
            "research": "Research notes and references",
            "notes": "General notes and miscellaneous"
        }
    }


@router.post("/upload/batch")
async def upload_batch(
    files: List[UploadFile] = File(...),
    category: str = Form(None),
    auto_categorize: bool = Form(True),
    db: AsyncSession = Depends(get_db)
):
    """Upload multiple documents at once."""
    results = []
    errors = []
    
    for file in files:
        try:
            # Process each file
            filename = file.filename
            ext = filename[filename.rfind('.'):].lower() if '.' in filename else ''
            
            if ext not in ALLOWED_EXTENSIONS:
                errors.append({"filename": filename, "error": "Unsupported file type"})
                continue
            
            content = await file.read()
            
            if len(content) > MAX_FILE_SIZE:
                errors.append({"filename": filename, "error": "File too large"})
                continue
            
            processor = get_document_processor()
            text_content = processor.extract_text(content, filename)
            
            if not text_content.strip():
                errors.append({"filename": filename, "error": "Document is empty"})
                continue
            
            # Categorize
            doc_category = category
            if not doc_category and auto_categorize:
                doc_category = processor.auto_categorize(text_content, filename)
            elif not doc_category:
                doc_category = 'notes'
            
            title = filename.rsplit('.', 1)[0]
            token_count = processor.count_tokens(text_content)
            chunks = processor.chunk_text(text_content, 1000, 200)
            
            # Store document
            main_embedding = generate_embedding(text_content[:8000])
            
            result = await db.execute(
                text("""
                    INSERT INTO knowledge_base (source_type, title, content, embedding, tags, metadata)
                    VALUES (:source_type, :title, :content, :embedding, :tags, :metadata)
                    RETURNING id
                """),
                {
                    "source_type": doc_category,
                    "title": title,
                    "content": text_content,
                    "embedding": str(main_embedding),
                    "tags": [],
                    "metadata": json.dumps({
                        "filename": filename,
                        "token_count": token_count,
                        "chunk_count": len(chunks),
                        "file_type": ext
                    })
                }
            )
            row = result.fetchone()
            doc_id = row.id
            
            # Store chunks in Qdrant
            vector_manager = get_vector_manager()
            chunk_points = []
            
            for chunk in chunks:
                chunk_embedding = generate_embedding(chunk['text'])
                chunk_id = f"{doc_id}_chunk_{chunk['index']}"
                
                chunk_points.append({
                    "id": hash(chunk_id) % (2**63),
                    "vector": chunk_embedding,
                    "payload": {
                        "doc_id": doc_id,
                        "chunk_index": chunk['index'],
                        "content": chunk['text'],
                        "title": title,
                        "category": doc_category,
                        "token_count": chunk['token_count']
                    }
                })
            
            vector_manager.upsert_vectors(collection="knowledge", points=chunk_points)
            
            results.append({
                "id": doc_id,
                "filename": filename,
                "category": doc_category,
                "token_count": token_count,
                "chunk_count": len(chunks)
            })
            
        except Exception as e:
            errors.append({"filename": file.filename, "error": str(e)})
    
    await db.commit()
    
    return {
        "uploaded": len(results),
        "failed": len(errors),
        "results": results,
        "errors": errors
    }

