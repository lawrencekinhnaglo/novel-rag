"""Document upload API endpoints with intelligent story extraction."""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import List, Optional
import json
import uuid
import asyncio
import logging

from app.database.postgres import get_db
from app.database.qdrant_client import get_vector_manager
from app.services.embeddings import generate_embedding
from app.services.document_service import get_document_processor, KNOWLEDGE_CATEGORIES
from app.services.document_extraction import get_document_extraction_service
from app.services.entity_extraction import get_story_extraction_service

logger = logging.getLogger(__name__)

router = APIRouter()

# Max file size: 50MB
MAX_FILE_SIZE = 50 * 1024 * 1024

ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.txt'}


@router.post("/upload")
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    category: str = Form(None),
    title: str = Form(None),
    tags: str = Form(""),
    chunk_size: int = Form(1000),
    chunk_overlap: int = Form(200),
    auto_categorize: bool = Form(True),
    extract_story_elements: bool = Form(True),
    series_id: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a DOCX or PDF document and add it to the knowledge base.
    
    The document will be:
    1. Parsed to extract text
    2. Auto-categorized (if enabled)
    3. Split into chunks for better retrieval
    4. Embedded and stored in vector database
    5. (Optional) Story elements extracted for verification (characters, world rules, etc.)
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
    
    # Trigger story element extraction if enabled
    extraction_result = None
    if extract_story_elements:
        async def run_extraction():
            try:
                extraction_service = get_document_extraction_service()
                return await extraction_service.extract_from_document(
                    content=text_content,
                    filename=filename,
                    series_id=series_id,
                    book_id=None
                )
            except Exception as e:
                return {"error": str(e)}
        
        # Run extraction in background for large documents
        if token_count > 5000:
            background_tasks.add_task(run_extraction)
            extraction_result = {"status": "processing", "message": "Story extraction running in background. Check Verification Hub."}
        else:
            # For smaller documents, run synchronously
            extraction_result = await run_extraction()
    
    return {
        "id": doc_id,
        "title": title,
        "category": category,
        "filename": filename,
        "token_count": token_count,
        "chunk_count": len(chunks),
        "tags": tag_list,
        "message": "Document uploaded and processed successfully",
        "extraction": extraction_result
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


@router.post("/upload/story-extraction")
async def upload_with_story_extraction(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    series_id: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a document and extract complete story structure.
    
    This endpoint performs intelligent extraction similar to the worldbuilding setup:
    - Extracts series information
    - Identifies and creates character profiles
    - Extracts world rules and concepts
    - Builds cultivation/power system if applicable
    - Creates chapter outlines
    - Builds comprehensive Neo4j graph with relationships
    
    All extracted data is inserted into:
    - PostgreSQL (knowledge_base, character_profiles, world_rules, chapters)
    - Qdrant (for vector search)
    - Neo4j (for relationship graph)
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
    
    token_count = processor.count_tokens(text_content)
    
    # Get story extraction service
    extraction_service = get_story_extraction_service()
    
    async def run_story_extraction():
        """Run the full story extraction."""
        try:
            return await extraction_service.extract_story_structure(
                content=text_content,
                filename=filename,
                series_id=series_id
            )
        except Exception as e:
            logger.error(f"Story extraction failed: {e}")
            return {"error": str(e)}
    
    # For large documents, run in background
    if token_count > 10000:
        background_tasks.add_task(run_story_extraction)
        return {
            "status": "processing",
            "filename": filename,
            "token_count": token_count,
            "message": "Story extraction running in background. This may take a few minutes. Check the Story Manager and Verification Hub for results."
        }
    
    # For smaller documents, run synchronously
    extraction_result = await run_story_extraction()
    
    if "error" in extraction_result:
        raise HTTPException(status_code=500, detail=extraction_result["error"])
    
    return {
        "status": "completed",
        "filename": filename,
        "token_count": token_count,
        "extraction_result": {
            "series_id": extraction_result.get("series"),
            "characters_extracted": len(extraction_result.get("characters", [])),
            "world_rules_extracted": len(extraction_result.get("world_rules", [])),
            "concepts_extracted": len(extraction_result.get("concepts", [])),
            "chapters_created": len(extraction_result.get("chapters", [])),
            "timeline_events": len(extraction_result.get("timeline", [])),
            "graph_summary": extraction_result.get("graph_summary", {}),
            "cultivation_system": extraction_result.get("cultivation_system") is not None,
            "errors": extraction_result.get("errors", [])
        },
        "details": {
            "characters": [c.get("name") for c in extraction_result.get("characters", [])],
            "world_rules": [r.get("name") for r in extraction_result.get("world_rules", [])],
            "concepts": [c.get("name") for c in extraction_result.get("concepts", [])][:20]
        },
        "message": "Story structure extracted and saved to all databases"
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

