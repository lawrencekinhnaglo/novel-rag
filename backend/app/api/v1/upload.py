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


@router.post("/upload/re-extract/{knowledge_id}")
async def re_extract_from_knowledge(
    knowledge_id: int,
    series_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Re-run story extraction on an existing knowledge base entry.

    This is useful when:
    - Initial extraction didn't capture all elements
    - You want to extract from a document that was uploaded without extraction
    - The extraction logic has been improved

    The extraction will:
    - Extract characters, world rules, cultivation systems, story parts, concepts
    - Create entries with verification_status='pending' for review
    - Link all extracted items to the specified series
    """
    # Get the knowledge entry
    result = await db.execute(
        text("SELECT id, title, content, metadata FROM knowledge_base WHERE id = :id"),
        {"id": knowledge_id}
    )
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")

    content = row.content
    title = row.title or "Untitled"

    # Get series_id from metadata if not provided
    if not series_id:
        metadata = json.loads(row.metadata) if row.metadata else {}
        series_id = metadata.get("series_id")

    # Run extraction
    extraction_service = get_document_extraction_service()

    try:
        extraction_result = await extraction_service.extract_from_document(
            content=content,
            filename=title,
            series_id=series_id,
            book_id=None
        )

        return {
            "knowledge_id": knowledge_id,
            "title": title,
            "series_id": extraction_result.get("series"),
            "extraction_result": {
                "document_type": extraction_result.get("document_type"),
                "characters_extracted": len(extraction_result.get("characters", [])),
                "world_rules_extracted": len(extraction_result.get("world_rules", [])),
                "foreshadowing_extracted": len(extraction_result.get("foreshadowing", [])),
                "locations_extracted": len(extraction_result.get("locations", [])),
                "facts_extracted": len(extraction_result.get("facts", [])),
                "story_parts_extracted": len(extraction_result.get("story_parts", [])),
                "concepts_extracted": len(extraction_result.get("concepts", [])),
                "cultivation_system": extraction_result.get("cultivation_system") is not None and extraction_result.get("cultivation_system") != {},
                "total_extracted": extraction_result.get("total_extracted", 0),
                "errors": extraction_result.get("errors", [])
            },
            "details": {
                "characters": [c.get("name") for c in extraction_result.get("characters", [])],
                "world_rules": [r.get("name") for r in extraction_result.get("world_rules", [])],
                "story_parts": [p.get("title") for p in extraction_result.get("story_parts", [])],
                "concepts": [c.get("name") for c in extraction_result.get("concepts", [])][:30]
            },
            "message": "Story elements extracted and saved. Check Verification Hub to review."
        }

    except Exception as e:
        logger.error(f"Re-extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.get("/upload/knowledge-entries")
async def list_knowledge_entries_for_extraction(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db)
):
    """
    List knowledge base entries that can be used for re-extraction.
    Shows entries with substantial content that might contain story elements.
    """
    result = await db.execute(
        text("""
            SELECT id, title, source_type, category,
                   LENGTH(content) as content_length,
                   created_at, metadata
            FROM knowledge_base
            WHERE LENGTH(content) > 1000
            ORDER BY created_at DESC
            LIMIT :limit OFFSET :skip
        """),
        {"limit": limit, "skip": skip}
    )

    entries = []
    for row in result.fetchall():
        metadata = json.loads(row.metadata) if row.metadata else {}
        entries.append({
            "id": row.id,
            "title": row.title,
            "source_type": row.source_type,
            "category": row.category,
            "content_length": row.content_length,
            "series_id": metadata.get("series_id"),
            "created_at": row.created_at.isoformat() if row.created_at else None
        })

    return {
        "entries": entries,
        "skip": skip,
        "limit": limit
    }


# ===== NEW WORKFLOW: Reconcile -> Review -> Extract =====

@router.post("/upload/reconcile/{knowledge_id}")
async def reconcile_document_content(
    knowledge_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Step 1 of extraction workflow: Reconcile messy document content.

    This endpoint uses LLM to:
    - Analyze the document structure
    - Identify conflicting information (e.g., part 1-6 vs part 7-11)
    - Map characters to their story parts
    - Create a canonical structure

    The user should review this reconciliation before proceeding to extraction.

    Workflow:
    1. POST /upload/reconcile/{id} - Get reconciled structure (this endpoint)
    2. User reviews the reconciliation in the UI
    3. POST /upload/extract/{id} - Run extraction with approved reconciliation
    """
    # Get the knowledge entry
    result = await db.execute(
        text("SELECT id, title, content, metadata FROM knowledge_base WHERE id = :id"),
        {"id": knowledge_id}
    )
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")

    content = row.content
    title = row.title or "Untitled"

    # Run reconciliation
    extraction_service = get_document_extraction_service()

    try:
        # Check if this is a setting document
        doc_analysis = await extraction_service._analyze_document_type(content, title)
        is_setting_doc = extraction_service._is_setting_document(content, doc_analysis)
        is_cultivation_story = extraction_service._is_cultivation_story(content, doc_analysis)

        if not is_setting_doc:
            return {
                "knowledge_id": knowledge_id,
                "title": title,
                "needs_reconciliation": False,
                "document_analysis": doc_analysis,
                "message": "This document does not appear to be a story setting document. You can proceed directly to extraction."
            }

        # Run reconciliation
        reconciliation = await extraction_service._reconcile_content(content)

        # Store reconciliation in knowledge_base metadata for later use
        existing_metadata = json.loads(row.metadata) if row.metadata else {}
        existing_metadata["reconciliation"] = reconciliation
        existing_metadata["reconciliation_status"] = "pending_review"

        await db.execute(
            text("UPDATE knowledge_base SET metadata = :metadata WHERE id = :id"),
            {"metadata": json.dumps(existing_metadata), "id": knowledge_id}
        )
        await db.commit()

        return {
            "knowledge_id": knowledge_id,
            "title": title,
            "needs_reconciliation": True,
            "document_analysis": doc_analysis,
            "is_cultivation_story": is_cultivation_story,
            "reconciliation": reconciliation,
            "message": "Document analyzed. Please review the reconciliation below and approve before extraction."
        }

    except Exception as e:
        logger.error(f"Reconciliation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Reconciliation failed: {str(e)}")


@router.post("/upload/extract/{knowledge_id}")
async def extract_with_reconciliation(
    knowledge_id: int,
    series_id: Optional[int] = None,
    use_reconciliation: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """
    Step 2 of extraction workflow: Extract story elements using approved reconciliation.

    This endpoint runs the full extraction:
    - Characters (mapped to their story parts)
    - World rules
    - Cultivation system
    - Story parts/books
    - Concepts and terminology
    - Foreshadowing

    If use_reconciliation=True (default), it uses the reconciliation data
    stored from the previous step to accurately categorize elements.

    All extracted items are created with verification_status='pending'
    for user review in the Verification Hub.
    """
    # Get the knowledge entry
    result = await db.execute(
        text("SELECT id, title, content, metadata FROM knowledge_base WHERE id = :id"),
        {"id": knowledge_id}
    )
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")

    content = row.content
    title = row.title or "Untitled"
    metadata = json.loads(row.metadata) if row.metadata else {}

    # Get series_id from metadata if not provided
    if not series_id:
        series_id = metadata.get("series_id")

    # Get reconciliation data if available
    reconciliation = metadata.get("reconciliation") if use_reconciliation else None

    # Run extraction
    extraction_service = get_document_extraction_service()

    try:
        extraction_result = await extraction_service.extract_from_document(
            content=content,
            filename=title,
            series_id=series_id,
            book_id=None
        )

        # Update metadata to mark extraction complete
        metadata["extraction_status"] = "completed"
        metadata["extraction_result_summary"] = {
            "characters": len(extraction_result.get("characters", [])),
            "world_rules": len(extraction_result.get("world_rules", [])),
            "story_parts": len(extraction_result.get("story_parts", [])),
            "concepts": len(extraction_result.get("concepts", []))
        }

        await db.execute(
            text("UPDATE knowledge_base SET metadata = :metadata WHERE id = :id"),
            {"metadata": json.dumps(metadata), "id": knowledge_id}
        )
        await db.commit()

        return {
            "knowledge_id": knowledge_id,
            "title": title,
            "series_id": extraction_result.get("series"),
            "used_reconciliation": reconciliation is not None,
            "extraction_result": {
                "document_type": extraction_result.get("document_type"),
                "characters_extracted": len(extraction_result.get("characters", [])),
                "world_rules_extracted": len(extraction_result.get("world_rules", [])),
                "foreshadowing_extracted": len(extraction_result.get("foreshadowing", [])),
                "locations_extracted": len(extraction_result.get("locations", [])),
                "facts_extracted": len(extraction_result.get("facts", [])),
                "story_parts_extracted": len(extraction_result.get("story_parts", [])),
                "concepts_extracted": len(extraction_result.get("concepts", [])),
                "cultivation_system": extraction_result.get("cultivation_system") is not None and extraction_result.get("cultivation_system") != {},
                "total_extracted": extraction_result.get("total_extracted", 0),
                "errors": extraction_result.get("errors", [])
            },
            "details": {
                "characters": [c.get("name") for c in extraction_result.get("characters", [])],
                "world_rules": [r.get("name") for r in extraction_result.get("world_rules", [])],
                "story_parts": [p.get("title") for p in extraction_result.get("story_parts", [])],
                "concepts": [c.get("name") for c in extraction_result.get("concepts", [])][:30]
            },
            "reconciliation_used": extraction_result.get("reconciliation") if use_reconciliation else None,
            "message": "Extraction complete! All items created with 'pending' status. Go to Verification Hub to review and approve.",
            "next_steps": [
                "Visit Verification Hub to review extracted characters",
                "Approve or modify character profiles",
                "Review and approve world rules",
                "Check story parts structure",
                "Start writing chapters using the extracted worldbuilding"
            ]
        }

    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Extraction failed: {str(e)}")


@router.get("/upload/reconciliation/{knowledge_id}")
async def get_reconciliation_status(
    knowledge_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get the current reconciliation status and data for a knowledge entry.

    Use this to check if reconciliation has been run and view the results.
    """
    result = await db.execute(
        text("SELECT id, title, metadata FROM knowledge_base WHERE id = :id"),
        {"id": knowledge_id}
    )
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")

    metadata = json.loads(row.metadata) if row.metadata else {}

    return {
        "knowledge_id": knowledge_id,
        "title": row.title,
        "has_reconciliation": "reconciliation" in metadata,
        "reconciliation_status": metadata.get("reconciliation_status", "not_started"),
        "reconciliation": metadata.get("reconciliation"),
        "extraction_status": metadata.get("extraction_status", "not_started"),
        "extraction_result_summary": metadata.get("extraction_result_summary")
    }
