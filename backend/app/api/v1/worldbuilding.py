"""
Worldbuilding API endpoints for structured novel documents.

Provides specialized extraction for complex Chinese novel worldbuilding documents.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from typing import Optional
import json
import logging

from app.database.postgres import get_db
from app.services.document_service import get_document_processor
from app.services.worldbuilding_parser import get_worldbuilding_parser, WorldbuildingDocument

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_EXTENSIONS = {'.pdf', '.docx', '.txt'}


@router.post("/smart-import")
async def smart_import_worldbuilding_document(
    file: UploadFile = File(...),
    series_id: Optional[int] = Form(None),
    title: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Smart Import: Parse and classify sections WITHOUT altering the original text.
    
    This endpoint:
    1. Parses the document structure (detects sections)
    2. Uses AI to CLASSIFY each section (character, world_rule, artifact, etc.)
    3. Preserves the EXACT original text - no rewriting
    4. Creates one knowledge base item per section with proper categorization
    
    The user can then edit individual items and ask AI for improvements in the Knowledge Base.
    """
    from app.services.document_service import get_document_processor
    from app.services.embeddings import generate_embedding
    from app.services.llm_service import get_llm_service
    from app.database.qdrant_client import get_vector_manager
    import re
    import os
    import uuid
    
    # Validate file
    filename = file.filename or "unknown.txt"
    logger.info(f"Smart import request for file: {filename}")
    
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}. Allowed: {ALLOWED_EXTENSIONS}")
    
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large: {len(content)} bytes (max {MAX_FILE_SIZE})")
    
    # Extract text from document
    processor = get_document_processor()
    text_content = processor.extract_text(content, filename)
    
    if not text_content:
        raise HTTPException(400, "Could not extract text from document")
    
    # Create or get series
    if not series_id:
        doc_title = title or filename.rsplit('.', 1)[0]
        series_result = await db.execute(
            text("""
                INSERT INTO series (title, premise, language, metadata)
                VALUES (:title, :premise, 'zh-TW', :metadata)
                RETURNING id
            """),
            {
                "title": doc_title,
                "premise": "Smart imported worldbuilding document",
                "metadata": json.dumps({
                    "import_type": "smart",
                    "source_file": filename
                })
            }
        )
        row = series_result.fetchone()
        series_id = row.id
        await db.commit()
        logger.info(f"Created series for smart import: {doc_title} with ID {series_id}")
    
    # Parse sections - detect numbered sections and major headings
    # Pattern matches: 1) Title, 2. Title, 1.1 Title, etc.
    section_pattern = r'(?:^|\n)\s*(\d+(?:\.\d+)?[\)\.]\s*[^\n]+)'
    parts = re.split(section_pattern, text_content)
    
    # Build sections list
    sections = []
    current_title = "Introduction"
    current_content = []
    
    for i, part in enumerate(parts):
        if i == 0:
            if part.strip():
                current_content.append(part.strip())
        elif re.match(r'^\d+(?:\.\d+)?[\)\.]\s*', part):
            # Save previous section
            if current_content:
                content_text = '\n'.join(current_content)
                if len(content_text) > 50:  # Minimum content length
                    sections.append({
                        "title": current_title,
                        "content": content_text,
                        "char_count": len(content_text)
                    })
            current_title = part.strip()
            current_content = []
        else:
            if part.strip():
                current_content.append(part.strip())
    
    # Save last section
    if current_content:
        content_text = '\n'.join(current_content)
        if len(content_text) > 50:
            sections.append({
                "title": current_title,
                "content": content_text,
                "char_count": len(content_text)
            })
    
    if not sections:
        sections.append({
            "title": "Complete Document",
            "content": text_content,
            "char_count": len(text_content)
        })
    
    # Use LLM to classify each section (batch for efficiency)
    llm = get_llm_service()
    
    # Classification prompt
    classification_prompt = """You are a document classifier for novel worldbuilding documents.
For each section title below, classify it into ONE of these categories:
- character: Character profiles, roles, relationships
- world_rule: World rules, laws, systems, restrictions
- cultivation: Cultivation/power levels, realms, abilities
- artifact: Items, weapons, tools, magical objects
- geography: Locations, maps, places
- timeline: Time periods, eras, chronology
- plot: Story structure, plot outlines, book summaries
- foreshadowing: Foreshadowing, hints, callbacks
- faction: Organizations, groups, alliances
- concept: Core concepts, themes, worldview
- other: Anything else

Output ONLY a JSON array with classifications. Example:
[{"title": "1) 口徑與命名規範", "category": "concept"}, {"title": "2) 角色設定", "category": "character"}]

Sections to classify:
"""
    
    section_titles = [s["title"] for s in sections]
    classification_prompt += json.dumps(section_titles, ensure_ascii=False)
    
    try:
        classification_response = await llm.generate([
            {"role": "system", "content": "You are a precise classifier. Output only valid JSON."},
            {"role": "user", "content": classification_prompt}
        ], temperature=0.1, max_tokens=2000)
        
        # Parse classification results
        # Extract JSON from response (handle potential markdown code blocks)
        json_match = re.search(r'\[[\s\S]*\]', classification_response)
        if json_match:
            classifications = json.loads(json_match.group())
            # Create title -> category mapping
            category_map = {c["title"]: c["category"] for c in classifications}
        else:
            category_map = {}
    except Exception as e:
        logger.warning(f"Classification failed, using default categories: {e}")
        category_map = {}
    
    # Save sections to knowledge base with classifications
    vector_manager = get_vector_manager()
    saved_items = []
    qdrant_points = []
    
    for section in sections:
        try:
            # Get category from LLM classification or default
            category = category_map.get(section["title"], "worldbuilding")
            
            # Generate embedding
            embedding_text = f"{section['title']}\n{section['content'][:2000]}"
            embedding = generate_embedding(embedding_text)
            
            # Save to PostgreSQL with ORIGINAL text preserved
            result = await db.execute(
                text("""
                    INSERT INTO knowledge_base
                    (source_type, category, title, content, language, embedding, tags, metadata)
                    VALUES ('smart_import', :category, :title, :content, 'zh-TW',
                            :embedding, :tags, :metadata)
                    RETURNING id
                """),
                {
                    "category": category,
                    "title": section['title'],
                    "content": section['content'],  # Original text - NOT modified
                    "embedding": str(embedding),
                    "tags": ["worldbuilding", "smart_import", f"series:{series_id}", category],
                    "metadata": json.dumps({
                        "series_id": series_id,
                        "source_file": filename,
                        "import_type": "smart",
                        "original_char_count": section["char_count"],
                        "ai_classified": section["title"] in category_map
                    })
                }
            )
            kb_id = result.fetchone().id
            
            # Prepare for Qdrant
            qdrant_points.append({
                "id": str(uuid.uuid4()),
                "vector": embedding,
                "payload": {
                    "id": kb_id,
                    "title": section['title'],
                    "content": section['content'][:3000],
                    "category": category,
                    "source_type": "smart_import",
                    "series_id": series_id,
                    "language": "zh-TW"
                }
            })
            
            saved_items.append({
                "id": kb_id,
                "title": section['title'],
                "category": category,
                "char_count": section["char_count"],
                "ai_classified": section["title"] in category_map
            })
            
        except Exception as e:
            logger.error(f"Failed to save section {section['title']}: {e}")
    
    await db.commit()
    
    # Add to Qdrant
    if qdrant_points:
        try:
            vector_manager.upsert_vectors("knowledge", qdrant_points)
            logger.info(f"Added {len(qdrant_points)} smart import points to Qdrant")
        except Exception as e:
            logger.error(f"Failed to add points to Qdrant: {e}")
    
    # Group by category for summary
    category_counts = {}
    for item in saved_items:
        cat = item["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1
    
    return {
        "status": "success",
        "filename": filename,
        "series_id": series_id,
        "total_sections": len(saved_items),
        "total_characters": len(text_content),
        "categories": category_counts,
        "sections": saved_items,
        "message": f"Smart imported {len(saved_items)} sections. Original text preserved. AI classified {sum(1 for i in saved_items if i.get('ai_classified'))} sections.",
        "next_steps": [
            "Visit Knowledge Base to view and edit individual sections",
            "Click 'Ask AI to Improve' on any section for enhancement suggestions",
            "Review AI classifications and adjust categories as needed"
        ]
    }


@router.post("/raw-import")
async def raw_import_worldbuilding_document(
    file: UploadFile = File(...),
    series_id: Optional[int] = Form(None),
    title: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Import a worldbuilding document DIRECTLY to knowledge base WITHOUT LLM interpretation.
    
    This preserves the exact text from your document without any AI summarization or alteration.
    The content is split into sections based on numbered headings (1), 2), 3), etc.)
    """
    from app.services.document_service import get_document_processor
    from app.services.embeddings import generate_embedding
    import re
    import os
    
    # Validate file
    filename = file.filename or "unknown.txt"
    logger.info(f"Raw import request for file: {filename}")
    
    # Use os.path.splitext for robust extension parsing (handles Unicode filenames)
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    logger.info(f"Detected extension: {ext}")
    
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"Unsupported file type: {ext}. Allowed: {ALLOWED_EXTENSIONS}")
    
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large: {len(content)} bytes (max {MAX_FILE_SIZE})")
    
    # Extract text from document
    processor = get_document_processor()
    text_content = processor.extract_text(content, filename)  # Pass filename, not ext
    
    if not text_content:
        raise HTTPException(400, "Could not extract text from document")
    
    # Create or get series
    if not series_id:
        doc_title = title or filename.rsplit('.', 1)[0]
        series_result = await db.execute(
            text("""
                INSERT INTO series (title, premise, language, metadata)
                VALUES (:title, :premise, 'zh-TW', :metadata)
                RETURNING id
            """),
            {
                "title": doc_title,
                "premise": "Raw imported worldbuilding document",
                "metadata": json.dumps({
                    "import_type": "raw",
                    "source_file": filename
                })
            }
        )
        row = series_result.fetchone()
        series_id = row.id
        await db.commit()
        logger.info(f"Created series for raw import: {doc_title} with ID {series_id}")
    
    # Split content by numbered sections (1), 2), 3), etc. or 1. 2. 3. etc.)
    section_pattern = r'(?:^|\n)(\d+[\)\.]\s*[^\n]+)'
    sections = re.split(section_pattern, text_content)
    
    # Group sections with their content
    knowledge_entries = []
    current_section = "Introduction"
    current_content = []
    
    for i, part in enumerate(sections):
        if i == 0:
            # Content before first section
            if part.strip():
                current_content.append(part.strip())
        elif re.match(r'^\d+[\)\.]\s*', part):
            # This is a section header
            if current_content:
                # Save previous section
                content_text = '\n'.join(current_content)
                if len(content_text) > 100:  # Only save meaningful sections
                    knowledge_entries.append({
                        "section": current_section,
                        "content": content_text
                    })
            current_section = part.strip()
            current_content = []
        else:
            # This is content
            if part.strip():
                current_content.append(part.strip())
    
    # Save last section
    if current_content:
        content_text = '\n'.join(current_content)
        if len(content_text) > 100:
            knowledge_entries.append({
                "section": current_section,
                "content": content_text
            })
    
    # If no sections found, save as one large entry
    if not knowledge_entries:
        knowledge_entries.append({
            "section": "Complete Document",
            "content": text_content
        })
    
    # Save to knowledge_base with embeddings AND Qdrant for RAG
    from app.database.qdrant_client import get_vector_manager
    import uuid
    
    vector_manager = get_vector_manager()
    saved_count = 0
    qdrant_points = []
    
    for entry in knowledge_entries:
        try:
            # Generate embedding for the content
            embedding_text = f"{entry['section']}\n{entry['content'][:2000]}"
            embedding = generate_embedding(embedding_text)
            
            # Save to PostgreSQL
            await db.execute(
                text("""
                    INSERT INTO knowledge_base
                    (source_type, category, title, content, language, embedding, tags, metadata)
                    VALUES ('raw_import', 'worldbuilding', :title, :content, 'zh-TW',
                            :embedding, :tags, :metadata)
                """),
                {
                    "title": entry['section'],
                    "content": entry['content'],
                    "embedding": str(embedding),
                    "tags": ["worldbuilding", "raw_import", f"series:{series_id}"],
                    "metadata": json.dumps({
                        "series_id": series_id,
                        "source_file": filename,
                        "import_type": "raw"
                    })
                }
            )
            
            # Prepare for Qdrant insertion
            qdrant_points.append({
                "id": str(uuid.uuid4()),
                "vector": embedding,
                "payload": {
                    "title": entry['section'],
                    "content": entry['content'][:3000],  # Limit content size
                    "category": "worldbuilding",
                    "source_type": "raw_import",
                    "series_id": series_id,
                    "language": "zh-TW",
                    "source_file": filename
                }
            })
            
            saved_count += 1
        except Exception as e:
            logger.error(f"Failed to save section {entry['section']}: {e}")
    
    await db.commit()
    
    # Add to Qdrant vector database for RAG retrieval
    if qdrant_points:
        try:
            vector_manager.upsert_vectors("knowledge", qdrant_points)  # "knowledge" maps to "novel_knowledge"
            logger.info(f"Added {len(qdrant_points)} points to Qdrant novel_knowledge collection")
        except Exception as e:
            logger.error(f"Failed to add points to Qdrant: {e}")
    
    return {
        "status": "success",
        "filename": filename,
        "series_id": series_id,
        "sections_saved": saved_count,
        "total_characters": len(text_content),
        "message": f"Imported {saved_count} sections directly to knowledge base without LLM interpretation"
    }


@router.post("/parse")
async def parse_worldbuilding_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    series_id: Optional[int] = Form(None),
    save_to_database: bool = Form(True),
    db: AsyncSession = Depends(get_db)
):
    """
    Parse a structured worldbuilding document (like《牧羊紀元》設定文檔).
    
    This endpoint is specialized for Chinese novel worldbuilding documents with:
    - Numbered sections (1) 口徑與命名規範, 2) 時間線與代際框架, etc.)
    - Story parts (正傳六部, 外傳, 前傳/牧場編年史)
    - Character generations (第1代, 第2代, etc.)
    - Cultivation systems (十五境)
    - Artifacts and technology tables
    - Foreshadowing recovery tables
    - World rules (天律網)
    
    Returns structured extraction results and optionally saves to database.
    """
    # Validate file
    filename = file.filename
    ext = filename[filename.rfind('.'):].lower() if '.' in filename else ''
    
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    content = await file.read()
    
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE // 1024 // 1024}MB"
        )
    
    # Extract text
    processor = get_document_processor()
    try:
        text_content = processor.extract_text(content, filename)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process document: {str(e)}")
    
    if not text_content.strip():
        raise HTTPException(status_code=400, detail="Document appears to be empty")
    
    token_count = processor.count_tokens(text_content)
    
    # Parse with worldbuilding parser
    parser = get_worldbuilding_parser()
    
    async def run_parsing():
        """Run the worldbuilding parsing."""
        try:
            logger.info(f"🚀 Starting worldbuilding parsing for: {filename}")
            doc = await parser.parse_document(text_content, filename)
            logger.info(f"✅ Document parsed: {doc.title}, {len(doc.characters)} characters, {len(doc.main_story)} story parts")
            
            # Save to database if requested
            db_result = None
            if save_to_database:
                logger.info("💾 Saving to database...")
                db_result = await parser.save_to_database(doc, series_id)
                logger.info(f"✅ Saved to database: series_id={db_result.get('series_id')}, errors={db_result.get('errors', [])}")
            
            logger.info(f"🎉 Worldbuilding parsing completed for: {filename}")
            return {
                "document": {
                    "title": doc.title,
                    "version": doc.version
                },
                "extraction_summary": {
                    "main_story_parts": len(doc.main_story),
                    "spinoffs": len(doc.spinoffs),
                    "prequels": len(doc.prequels),
                    "characters": len(doc.characters),
                    "cultivation_realms": len(doc.cultivation_realms),
                    "artifacts": len(doc.artifacts),
                    "foreshadowing": len(doc.foreshadowing),
                    "world_rules": len(doc.rules)
                },
                "database_result": db_result,
                "details": {
                    "main_story": [
                        {
                            "part_number": p.part_number,
                            "title": p.title,
                            "protagonists": p.protagonists,
                            "themes": p.themes[:3]
                        }
                        for p in doc.main_story
                    ],
                    "characters": [
                        {
                            "name": c.name,
                            "role": c.role,
                            "generation": c.generation,
                            "faction": c.faction
                        }
                        for c in doc.characters[:20]
                    ],
                    "artifacts": [
                        {
                            "name": a.name,
                            "type": a.artifact_type,
                            "first_appearance": a.first_appearance
                        }
                        for a in doc.artifacts
                    ],
                    "cultivation_realms": [
                        {
                            "tier": r.tier,
                            "name": r.name,
                            "group": r.group_name
                        }
                        for r in doc.cultivation_realms
                    ]
                }
            }
        except Exception as e:
            import traceback
            logger.error(f"❌ Worldbuilding parsing failed: {e}")
            logger.error(traceback.format_exc())
            return {"error": str(e)}
    
    # For large documents, run in background (lowered threshold - LLM calls take time)
    if token_count > 3000:
        background_tasks.add_task(run_parsing)
        return {
            "status": "processing",
            "filename": filename,
            "token_count": token_count,
            "message": "Worldbuilding extraction running in background. This document is large and may take several minutes. Check the Story Manager and Verification Hub for results."
        }
    
    # For smaller documents, run synchronously
    result = await run_parsing()
    
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    
    return {
        "status": "completed",
        "filename": filename,
        "token_count": token_count,
        **result,
        "message": "Worldbuilding document parsed successfully. All items created with 'pending' status for review.",
        "next_steps": [
            "Visit Verification Hub to review extracted characters",
            "Check Story Manager for book structure",
            "Review world rules and cultivation system",
            "Use Chat to brainstorm with your worldbuilding context"
        ]
    }


@router.get("/series/{series_id}/worldbuilding")
async def get_series_worldbuilding(
    series_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get complete worldbuilding data for a series.
    
    Returns all extracted worldbuilding elements:
    - Books/parts structure
    - Characters by generation
    - Cultivation realms
    - Artifacts
    - World rules
    - Foreshadowing elements
    """
    result = {
        "series": None,
        "books": [],
        "characters_by_generation": {},
        "cultivation_realms": [],
        "artifacts": [],
        "world_rules": [],
        "foreshadowing": [],
        "core_concepts": []
    }
    
    # Get series info
    series_result = await db.execute(
        text("SELECT id, title, premise, themes, language FROM series WHERE id = :id"),
        {"id": series_id}
    )
    series = series_result.fetchone()
    
    if not series:
        raise HTTPException(status_code=404, detail="Series not found")
    
    result["series"] = {
        "id": series.id,
        "title": series.title,
        "premise": series.premise,
        "themes": series.themes,
        "language": series.language
    }
    
    # Get books with metadata
    books_result = await db.execute(
        text("""
            SELECT id, book_number, title, theme, synopsis, status, metadata
            FROM books 
            WHERE series_id = :series_id
            ORDER BY book_number ASC
        """),
        {"series_id": series_id}
    )
    
    for row in books_result.fetchall():
        metadata = json.loads(row.metadata) if row.metadata else {}
        result["books"].append({
            "id": row.id,
            "part_number": row.book_number,
            "title": row.title,
            "theme": row.theme,
            "synopsis": row.synopsis,
            "status": row.status,
            "book_type": metadata.get("book_type", "main"),
            "era": metadata.get("era", ""),
            "protagonists": metadata.get("protagonists", []),
            "antagonists": metadata.get("antagonists", []),
            "genre_style": metadata.get("genre_style", ""),
            "key_scenes": metadata.get("key_scenes", [])
        })
    
    # Get characters grouped by generation
    chars_result = await db.execute(
        text("""
            SELECT id, name, aliases, description, personality, background, goals,
                   first_appearance_book, verification_status, metadata
            FROM character_profiles
            WHERE series_id = :series_id
            ORDER BY first_appearance_book ASC NULLS LAST, name
        """),
        {"series_id": series_id}
    )
    
    for row in chars_result.fetchall():
        metadata = json.loads(row.metadata) if row.metadata else {}
        generation = metadata.get("generation", "未分類")
        
        if generation not in result["characters_by_generation"]:
            result["characters_by_generation"][generation] = []
        
        result["characters_by_generation"][generation].append({
            "id": row.id,
            "name": row.name,
            "aliases": row.aliases or [],
            "description": row.description,
            "personality": row.personality,
            "role": metadata.get("role", "supporting"),
            "faction": metadata.get("faction", ""),
            "abilities": metadata.get("abilities", []),
            "relationships": metadata.get("relationships", []),
            "first_appearance_book": row.first_appearance_book,
            "verification_status": row.verification_status
        })
    
    # Get cultivation realms from knowledge base
    realms_result = await db.execute(
        text("""
            SELECT id, title, content, metadata
            FROM knowledge_base
            WHERE category = 'cultivation_realm'
            AND :series_tag = ANY(tags)
            ORDER BY (metadata->>'tier')::int ASC NULLS LAST
        """),
        {"series_tag": f"series:{series_id}"}
    )
    
    for row in realms_result.fetchall():
        metadata = json.loads(row.metadata) if row.metadata else {}
        result["cultivation_realms"].append({
            "id": row.id,
            "title": row.title,
            "content": row.content,
            "tier": metadata.get("tier"),
            "harvest_risk": metadata.get("harvest_risk", "")
        })
    
    # Get artifacts from knowledge base
    artifacts_result = await db.execute(
        text("""
            SELECT id, title, content, metadata
            FROM knowledge_base
            WHERE category = 'artifact'
            AND :series_tag = ANY(tags)
            ORDER BY (metadata->>'first_appearance')::int ASC NULLS LAST
        """),
        {"series_tag": f"series:{series_id}"}
    )
    
    for row in artifacts_result.fetchall():
        metadata = json.loads(row.metadata) if row.metadata else {}
        result["artifacts"].append({
            "id": row.id,
            "title": row.title,
            "content": row.content,
            "first_appearance": metadata.get("first_appearance"),
            "aliases": metadata.get("aliases", [])
        })
    
    # Get world rules
    rules_result = await db.execute(
        text("""
            SELECT id, rule_name, rule_category, rule_description, is_hard_rule,
                   exceptions, verification_status
            FROM world_rules
            WHERE series_id = :series_id
            ORDER BY rule_category, rule_name
        """),
        {"series_id": series_id}
    )
    
    for row in rules_result.fetchall():
        result["world_rules"].append({
            "id": row.id,
            "name": row.rule_name,
            "category": row.rule_category,
            "description": row.rule_description,
            "is_hard_rule": row.is_hard_rule,
            "exceptions": row.exceptions or [],
            "verification_status": row.verification_status
        })
    
    # Get foreshadowing
    fs_result = await db.execute(
        text("""
            SELECT id, title, planted_book, planted_text, payoff_book, payoff_text,
                   seed_type, status, verification_status
            FROM foreshadowing
            WHERE series_id = :series_id
            ORDER BY planted_book ASC
        """),
        {"series_id": series_id}
    )
    
    for row in fs_result.fetchall():
        result["foreshadowing"].append({
            "id": row.id,
            "title": row.title,
            "planted_book": row.planted_book,
            "planted_text": row.planted_text,
            "payoff_book": row.payoff_book,
            "payoff_text": row.payoff_text,
            "seed_type": row.seed_type,
            "status": row.status,
            "verification_status": row.verification_status
        })
    
    # Get core concepts from knowledge base
    concepts_result = await db.execute(
        text("""
            SELECT id, title, content, category
            FROM knowledge_base
            WHERE category IN ('world_concept', 'core_concept')
            AND :series_tag = ANY(tags)
            LIMIT 10
        """),
        {"series_tag": f"series:{series_id}"}
    )
    
    for row in concepts_result.fetchall():
        result["core_concepts"].append({
            "id": row.id,
            "title": row.title,
            "content": row.content,
            "category": row.category
        })
    
    return result


@router.post("/series/{series_id}/writing-context")
async def get_writing_context(
    series_id: int,
    book_number: int = 1,
    chapter_focus: Optional[str] = None,
    characters_focus: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """
    Get contextual worldbuilding data for writing a specific chapter.
    
    This endpoint provides focused context for the AI writing assistant:
    - Current book's setting and themes
    - Relevant characters for this book/chapter
    - Applicable world rules
    - Relevant foreshadowing to plant or recover
    - Previous chapter summaries (if available)
    
    Use this when writing to ensure consistency with established worldbuilding.
    """
    context = {
        "current_book": None,
        "relevant_characters": [],
        "applicable_rules": [],
        "foreshadowing_to_plant": [],
        "foreshadowing_to_recover": [],
        "key_artifacts": [],
        "cultivation_context": [],
        "writing_guidelines": []
    }
    
    # Get current book info
    book_result = await db.execute(
        text("""
            SELECT id, book_number, title, theme, synopsis, metadata
            FROM books
            WHERE series_id = :series_id AND book_number = :book_number
        """),
        {"series_id": series_id, "book_number": book_number}
    )
    book = book_result.fetchone()
    
    if book:
        metadata = json.loads(book.metadata) if book.metadata else {}
        context["current_book"] = {
            "id": book.id,
            "part_number": book.book_number,
            "title": book.title,
            "theme": book.theme,
            "synopsis": book.synopsis,
            "genre_style": metadata.get("genre_style", ""),
            "protagonists": metadata.get("protagonists", []),
            "antagonists": metadata.get("antagonists", []),
            "key_scenes": metadata.get("key_scenes", []),
            "three_act_summary": metadata.get("three_act_summary", {})
        }
        
        # Get characters for this book
        protagonist_names = metadata.get("protagonists", [])
        antagonist_names = metadata.get("antagonists", [])
        all_names = protagonist_names + antagonist_names
        
        if all_names:
            # Get character details
            chars_result = await db.execute(
                text("""
                    SELECT name, aliases, description, personality, goals, metadata
                    FROM character_profiles
                    WHERE series_id = :series_id
                    AND (name = ANY(:names) OR first_appearance_book = :book_num)
                    AND (verification_status = 'approved' OR verification_status IS NULL OR verification_status = 'pending')
                """),
                {"series_id": series_id, "names": all_names, "book_num": book_number}
            )
            
            for row in chars_result.fetchall():
                char_metadata = json.loads(row.metadata) if row.metadata else {}
                context["relevant_characters"].append({
                    "name": row.name,
                    "aliases": row.aliases or [],
                    "description": row.description,
                    "personality": row.personality,
                    "goals": row.goals,
                    "role": char_metadata.get("role", "supporting"),
                    "abilities": char_metadata.get("abilities", []),
                    "growth_arc": char_metadata.get("growth_arc", ""),
                    "relationships": char_metadata.get("relationships", [])
                })
    
    # Get world rules (all approved ones)
    rules_result = await db.execute(
        text("""
            SELECT rule_name, rule_category, rule_description, is_hard_rule, exceptions
            FROM world_rules
            WHERE series_id = :series_id
            AND (verification_status = 'approved' OR verification_status IS NULL OR verification_status = 'pending')
            ORDER BY is_hard_rule DESC, rule_category
        """),
        {"series_id": series_id}
    )
    
    for row in rules_result.fetchall():
        context["applicable_rules"].append({
            "name": row.rule_name,
            "category": row.rule_category,
            "description": row.rule_description,
            "is_hard_rule": row.is_hard_rule,
            "exceptions": row.exceptions or []
        })
    
    # Get foreshadowing to plant in this book
    plant_result = await db.execute(
        text("""
            SELECT title, planted_text, intended_payoff, payoff_book
            FROM foreshadowing
            WHERE series_id = :series_id
            AND planted_book = :book_number
            AND status = 'planted'
        """),
        {"series_id": series_id, "book_number": book_number}
    )
    
    for row in plant_result.fetchall():
        context["foreshadowing_to_plant"].append({
            "title": row.title,
            "text": row.planted_text,
            "intended_payoff": row.intended_payoff,
            "payoff_book": row.payoff_book
        })
    
    # Get foreshadowing to recover in this book
    recover_result = await db.execute(
        text("""
            SELECT title, planted_text, payoff_text, planted_book
            FROM foreshadowing
            WHERE series_id = :series_id
            AND payoff_book = :book_number
        """),
        {"series_id": series_id, "book_number": book_number}
    )
    
    for row in recover_result.fetchall():
        context["foreshadowing_to_recover"].append({
            "title": row.title,
            "original_text": row.planted_text,
            "recovery_method": row.payoff_text,
            "planted_in_book": row.planted_book
        })
    
    # Get relevant artifacts
    artifacts_result = await db.execute(
        text("""
            SELECT title, content, metadata
            FROM knowledge_base
            WHERE category = 'artifact'
            AND :series_tag = ANY(tags)
            AND (metadata->>'first_appearance')::int <= :book_number
        """),
        {"series_tag": f"series:{series_id}", "book_number": book_number}
    )
    
    for row in artifacts_result.fetchall():
        context["key_artifacts"].append({
            "name": row.title.replace("器物：", ""),
            "description": row.content[:300]
        })
    
    # Add writing guidelines based on book type and style
    if context["current_book"]:
        genre_style = context["current_book"].get("genre_style", "")
        if genre_style:
            context["writing_guidelines"].append(f"寫作風格：{genre_style}")
        
        theme = context["current_book"].get("theme", "")
        if theme:
            context["writing_guidelines"].append(f"本部主題：{theme}")
    
    return context
