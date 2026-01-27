"""
Intelligent Entity Extraction Service

Provides LLM-powered entity extraction and Neo4j graph integration:
1. Identifies record types and attributes from content
2. Extracts entities (characters, concepts, terms, relationships)
3. Inserts to PostgreSQL/pgvector and Qdrant
4. Builds Neo4j graph with relationships to existing elements
5. Detects new terms/concepts and links them intelligently
"""

import json
import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from app.services.llm_service import get_llm_service
from app.services.embeddings import generate_embedding
from app.database.postgres import AsyncSessionLocal
from app.database.qdrant_client import get_vector_manager
from app.config import settings
from sqlalchemy import text

# Import async Neo4j driver
try:
    from app.database.neo4j_client import get_neo4j
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False

logger = logging.getLogger(__name__)


def ensure_series_tag(tags: List[str], series_id: Optional[int]) -> List[str]:
    """Ensure tags include series:{id} tag if series_id is provided."""
    if not series_id:
        return tags or []
    series_tag = f"series:{series_id}"
    tag_list = tags or []
    if series_tag not in tag_list:
        return tag_list + [series_tag]
    return tag_list


def get_async_neo4j_driver():
    """Get the async Neo4j driver for extraction operations."""
    if not NEO4J_AVAILABLE:
        return None
    try:
        return get_neo4j()
    except Exception as e:
        logger.warning(f"Neo4j connection failed: {e}")
        return None


class EntityExtractionService:
    """
    Intelligent entity extraction with Neo4j graph building.
    
    Flow:
    1. Analyze content to determine type and extract attributes
    2. Extract entities (characters, concepts, terms, relationships)
    3. Find connections to existing entities in Neo4j
    4. Insert to PostgreSQL, Qdrant, and Neo4j
    5. Return structured extraction results
    """
    
    ENTITY_TYPES = [
        "character",
        "location",
        "concept",
        "term",
        "event",
        "relationship",
        "world_rule",
        "cultivation_realm",
        "talent",
        "artifact",
        "technique",
        "faction",
        "timeline_event"
    ]
    
    CONTENT_CATEGORIES = [
        "character_profile",
        "world_building",
        "plot_point",
        "dialogue",
        "chapter_content",
        "concept_definition",
        "cultivation_system",
        "power_system",
        "history",
        "geography",
        "culture",
        "technology",
        "notes",
        "other"
    ]
    
    def __init__(self, provider: str = None):
        self.llm = get_llm_service(provider)
        self.vector_manager = get_vector_manager()
    
    async def analyze_and_extract(
        self,
        content: str,
        title: Optional[str] = None,
        series_id: Optional[int] = None,
        source_type: str = "manual",
        existing_tags: List[str] = None,
        language: str = "zh-CN"
    ) -> Dict[str, Any]:
        """
        Main entry point: analyze content and extract all entities.
        
        Returns:
            Dict with:
            - content_analysis: type, category, attributes
            - extracted_entities: list of entities found
            - knowledge_entry_id: ID of the saved knowledge base entry
            - graph_nodes_created: list of Neo4j nodes created
            - graph_relationships_created: list of Neo4j relationships created
        """
        result = {
            "content_analysis": None,
            "extracted_entities": [],
            "knowledge_entry_id": None,
            "graph_nodes_created": [],
            "graph_relationships_created": [],
            "errors": []
        }
        
        try:
            # Step 1: Analyze content to determine type and attributes
            analysis = await self._analyze_content(content, title, language)
            result["content_analysis"] = analysis
            
            # Step 2: Extract entities from content
            entities = await self._extract_entities(content, analysis, language)
            result["extracted_entities"] = entities
            
            # Step 3: Find existing related entities in Neo4j
            existing_connections = await self._find_existing_connections(entities)
            
            # Step 4: Save to PostgreSQL and Qdrant
            knowledge_id = await self._save_to_knowledge_base(
                content=content,
                title=title or analysis.get("suggested_title", "Untitled"),
                category=analysis.get("category", "other"),
                source_type=source_type,
                tags=self._merge_tags(existing_tags, analysis.get("suggested_tags", [])),
                series_id=series_id,
                metadata={
                    "analysis": analysis,
                    "entity_count": len(entities),
                    "language": language
                },
                language=language
            )
            result["knowledge_entry_id"] = knowledge_id
            
            # Step 5: Build Neo4j graph
            graph_result = await self._build_graph(
                entities=entities,
                existing_connections=existing_connections,
                knowledge_id=knowledge_id,
                series_id=series_id
            )
            result["graph_nodes_created"] = graph_result.get("nodes", [])
            result["graph_relationships_created"] = graph_result.get("relationships", [])
            
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            result["errors"].append(str(e))
        
        return result
    
    async def _analyze_content(
        self,
        content: str,
        title: Optional[str],
        language: str
    ) -> Dict[str, Any]:
        """Analyze content to determine its type, category, and attributes."""
        
        sample = content[:4000]
        
        prompt = f"""Analyze this content and determine its type and attributes.

TITLE (if provided): {title or "Not provided"}

CONTENT:
{sample}

Determine:
1. What category does this content belong to?
2. What are the main topics/subjects?
3. What language is it in?
4. Is this about fiction/story-related content?
5. What entities (characters, places, concepts) are mentioned?

Categories: {", ".join(self.CONTENT_CATEGORIES)}

Respond in JSON:
{{
    "category": "one of the categories above",
    "primary_subject": "main topic/subject",
    "is_story_related": true/false,
    "is_character_profile": true/false,
    "is_world_building": true/false,
    "is_cultivation_system": true/false,
    "language": "zh-CN|zh-TW|en|ja|ko",
    "suggested_title": "A good title for this content",
    "suggested_tags": ["tag1", "tag2"],
    "key_entities_preview": ["entity1", "entity2"],
    "summary": "Brief 1-2 sentence summary"
}}
"""
        
        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
        try:
            return self._extract_json(response)
        except:
            return {
                "category": "other",
                "primary_subject": "unknown",
                "is_story_related": True,
                "language": language,
                "suggested_title": title or "Untitled",
                "suggested_tags": []
            }
    
    async def _extract_entities(
        self,
        content: str,
        analysis: Dict[str, Any],
        language: str
    ) -> List[Dict[str, Any]]:
        """Extract all entities from content."""
        
        entities = []
        
        # Chunk content for processing large texts
        chunks = self._chunk_content(content, 4000)
        
        for chunk in chunks[:5]:  # Process up to 5 chunks
            chunk_entities = await self._extract_entities_from_chunk(
                chunk, analysis, language
            )
            entities.extend(chunk_entities)
        
        # Deduplicate entities by name
        seen_names = set()
        unique_entities = []
        for entity in entities:
            name = entity.get("name", "").lower()
            if name and name not in seen_names:
                seen_names.add(name)
                unique_entities.append(entity)
        
        return unique_entities
    
    async def _extract_entities_from_chunk(
        self,
        chunk: str,
        analysis: Dict[str, Any],
        language: str
    ) -> List[Dict[str, Any]]:
        """Extract entities from a single chunk."""
        
        entity_types_str = ", ".join(self.ENTITY_TYPES)
        
        prompt = f"""Extract all ENTITIES from this text.

CONTEXT: This content is about "{analysis.get('primary_subject', 'unknown')}"
Content Category: {analysis.get('category', 'unknown')}

TEXT:
{chunk}

For each entity found, extract:
- name: The entity's name
- type: One of [{entity_types_str}]
- description: Brief description
- attributes: Key attributes as key-value pairs
- relationships: Connections to other entities mentioned

JSON response:
{{
    "entities": [
        {{
            "name": "Entity Name",
            "type": "character|location|concept|term|event|world_rule|cultivation_realm|talent|artifact|technique|faction|timeline_event|relationship",
            "description": "What/who this entity is",
            "attributes": {{"key": "value"}},
            "relationships": [
                {{"target": "Other Entity", "type": "relationship_type", "description": "relationship details"}}
            ],
            "confidence": 0.0-1.0
        }}
    ]
}}

Only include entities with enough detail to be meaningful. Skip vague mentions.
"""
        
        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
        try:
            data = self._extract_json(response)
            return data.get("entities", [])
        except Exception as e:
            logger.warning(f"Entity extraction from chunk failed: {e}")
            return []
    
    async def _find_existing_connections(
        self,
        entities: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Find existing entities in Neo4j that relate to extracted entities."""

        connections = {}
        driver = get_async_neo4j_driver()

        if not driver:
            logger.warning("Neo4j not available for finding connections")
            return connections

        try:
            async with driver.session() as session:
                for entity in entities:
                    name = entity.get("name", "")
                    if not name:
                        continue

                    # Search for similar entities in Neo4j
                    result = await session.run("""
                        MATCH (n)
                        WHERE toLower(n.name) CONTAINS toLower($query)
                        RETURN n.name as name, labels(n) as labels
                        LIMIT 5
                    """, query=name)

                    matches = []
                    async for record in result:
                        matches.append({
                            "name": record["name"],
                            "labels": record["labels"]
                        })

                    if matches:
                        connections[name] = matches

        except Exception as e:
            logger.warning(f"Failed to find existing connections: {e}")

        return connections
    
    async def _save_to_knowledge_base(
        self,
        content: str,
        title: str,
        category: str,
        source_type: str,
        tags: List[str],
        series_id: Optional[int],
        metadata: Dict[str, Any],
        language: str
    ) -> int:
        """Save content to PostgreSQL knowledge_base and Qdrant."""

        # Generate embedding
        embedding = generate_embedding(content[:8000])

        # Ensure series tag is included
        final_tags = ensure_series_tag(tags, series_id)

        async with AsyncSessionLocal() as db:
            # Insert into PostgreSQL
            result = await db.execute(
                text("""
                    INSERT INTO knowledge_base
                    (source_type, category, title, content, language, embedding, tags, metadata)
                    VALUES (:source_type, :category, :title, :content, :language, :embedding, :tags, :metadata)
                    RETURNING id
                """),
                {
                    "source_type": source_type,
                    "category": category,
                    "title": title,
                    "content": content,
                    "language": language,
                    "embedding": str(embedding),
                    "tags": final_tags,
                    "metadata": json.dumps({
                        **metadata,
                        "series_id": series_id
                    })
                }
            )
            await db.commit()
            row = result.fetchone()
            knowledge_id = row.id

        # Insert into Qdrant
        try:
            self.vector_manager.upsert_vectors(
                collection="knowledge",
                points=[{
                    "id": knowledge_id,
                    "vector": embedding,
                    "payload": {
                        "id": knowledge_id,
                        "title": title,
                        "category": category,
                        "source_type": source_type,
                        "tags": final_tags,
                        "content_preview": content[:500],
                        "series_id": series_id
                    }
                }]
            )
        except Exception as e:
            logger.warning(f"Failed to insert into Qdrant: {e}")

        return knowledge_id
    
    async def _build_graph(
        self,
        entities: List[Dict[str, Any]],
        existing_connections: Dict[str, List[Dict[str, Any]]],
        knowledge_id: int,
        series_id: Optional[int]
    ) -> Dict[str, Any]:
        """Build Neo4j graph from extracted entities."""

        nodes_created = []
        relationships_created = []

        driver = get_async_neo4j_driver()
        if not driver:
            logger.warning("Neo4j not available for graph building")
            return {"nodes": nodes_created, "relationships": relationships_created}

        try:
            async with driver.session() as session:
                # Create nodes for each entity
                for entity in entities:
                    entity_name = entity.get("name", "")
                    entity_type = entity.get("type", "concept")

                    if not entity_name:
                        continue

                    # Determine node label based on entity type
                    label = self._get_neo4j_label(entity_type)

                    # Create the node
                    node_result = await self._create_entity_node(
                        session,
                        name=entity_name,
                        label=label,
                        description=entity.get("description", ""),
                        attributes=entity.get("attributes", {}),
                        knowledge_id=knowledge_id,
                        series_id=series_id
                    )

                    if node_result:
                        nodes_created.append({
                            "name": entity_name,
                            "type": entity_type,
                            "label": label
                        })

                    # Create relationships defined in the entity
                    for rel in entity.get("relationships", []):
                        target_name = rel.get("target", "")
                        rel_type = rel.get("type", "RELATED_TO")

                        if target_name:
                            rel_result = await self._create_relationship(
                                session,
                                source_name=entity_name,
                                target_name=target_name,
                                rel_type=rel_type,
                                description=rel.get("description", "")
                            )

                            if rel_result:
                                relationships_created.append({
                                    "source": entity_name,
                                    "target": target_name,
                                    "type": rel_type
                                })

                    # Link to existing entities found earlier
                    existing = existing_connections.get(entity_name, [])
                    for existing_entity in existing[:3]:  # Limit to 3 connections
                        if existing_entity.get("name") != entity_name:
                            rel_result = await self._create_relationship(
                                session,
                                source_name=entity_name,
                                target_name=existing_entity.get("name", ""),
                                rel_type="POSSIBLY_RELATED",
                                description="Auto-detected potential connection"
                            )
                            if rel_result:
                                relationships_created.append({
                                    "source": entity_name,
                                    "target": existing_entity.get("name"),
                                    "type": "POSSIBLY_RELATED",
                                    "auto_detected": True
                                })

                # Link all entities from this extraction together (limit to first 5 to avoid explosion)
                if 1 < len(entities) <= 10:
                    for i, entity1 in enumerate(entities[:5]):
                        for entity2 in entities[i+1:6]:
                            name1 = entity1.get("name", "")
                            name2 = entity2.get("name", "")
                            if name1 and name2:
                                await self._create_relationship(
                                    session,
                                    source_name=name1,
                                    target_name=name2,
                                    rel_type="CO_OCCURS_WITH",
                                    description=f"Both mentioned in knowledge entry {knowledge_id}"
                                )

        except Exception as e:
            logger.error(f"Graph building failed: {e}")

        return {
            "nodes": nodes_created,
            "relationships": relationships_created
        }

    async def _create_entity_node(
        self,
        session,
        name: str,
        label: str,
        description: str,
        attributes: Dict[str, Any],
        knowledge_id: int,
        series_id: Optional[int]
    ) -> bool:
        """Create a node in Neo4j for an entity."""

        try:
            # Sanitize label for Cypher
            safe_label = re.sub(r'[^a-zA-Z0-9_]', '', label) or "Entity"

            # Create node with MERGE to avoid duplicates
            query = f"""
                MERGE (n:{safe_label} {{name: $name}})
                SET n.description = $description,
                    n.knowledge_id = $knowledge_id,
                    n.series_id = $series_id,
                    n.updated_at = datetime()
                RETURN n
            """

            result = await session.run(
                query,
                name=name,
                description=description[:500] if description else "",
                knowledge_id=knowledge_id,
                series_id=series_id
            )

            record = await result.single()
            return record is not None

        except Exception as e:
            logger.warning(f"Failed to create node {name}: {e}")
            return False

    async def _create_relationship(
        self,
        session,
        source_name: str,
        target_name: str,
        rel_type: str,
        description: str = ""
    ) -> bool:
        """Create a relationship between two nodes in Neo4j."""

        try:
            # Sanitize relationship type for Cypher
            safe_rel_type = re.sub(r'[^a-zA-Z0-9_]', '_', rel_type.upper())
            if not safe_rel_type:
                safe_rel_type = "RELATED_TO"

            # First ensure both nodes exist (create as Entity if not)
            await session.run(
                "MERGE (n:Entity {name: $name})",
                name=source_name
            )
            await session.run(
                "MERGE (n:Entity {name: $name})",
                name=target_name
            )

            # Create the relationship
            query = f"""
                MATCH (a {{name: $source}})
                MATCH (b {{name: $target}})
                MERGE (a)-[r:{safe_rel_type}]->(b)
                SET r.description = $description,
                    r.created_at = datetime()
                RETURN r
            """

            result = await session.run(
                query,
                source=source_name,
                target=target_name,
                description=description[:200] if description else ""
            )

            record = await result.single()
            return record is not None

        except Exception as e:
            logger.warning(f"Failed to create relationship {source_name}->{target_name}: {e}")
            return False
    
    def _get_neo4j_label(self, entity_type: str) -> str:
        """Map entity type to Neo4j node label."""
        label_map = {
            "character": "Character",
            "location": "Location",
            "concept": "Concept",
            "term": "Term",
            "event": "Event",
            "world_rule": "WorldRule",
            "cultivation_realm": "CultivationRealm",
            "talent": "Talent",
            "artifact": "Artifact",
            "technique": "Technique",
            "faction": "Faction",
            "timeline_event": "TimelineEvent",
            "relationship": "Relationship"
        }
        return label_map.get(entity_type, "Entity")
    
    def _chunk_content(self, content: str, chunk_size: int = 4000) -> List[str]:
        """Split content into chunks for processing."""
        chunks = []
        words = content.split()
        current_chunk = []
        current_size = 0
        
        for word in words:
            current_chunk.append(word)
            current_size += len(word) + 1
            
            if current_size >= chunk_size:
                chunks.append(' '.join(current_chunk))
                current_chunk = []
                current_size = 0
        
        if current_chunk:
            chunks.append(' '.join(current_chunk))
        
        return chunks
    
    def _merge_tags(
        self,
        existing: Optional[List[str]],
        suggested: List[str]
    ) -> List[str]:
        """Merge existing and suggested tags, removing duplicates."""
        all_tags = set(existing or [])
        all_tags.update(suggested)
        return list(all_tags)
    
    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from LLM response."""
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            return json.loads(json_match.group())
        raise ValueError("No JSON found in response")


class StoryExtractionService(EntityExtractionService):
    """
    Extended extraction service specifically for story/novel documents.
    
    Handles:
    - Series/Book structure extraction
    - Chapter breakdown
    - Full worldbuilding extraction
    - Character relationship mapping
    """
    
    async def extract_story_structure(
        self,
        content: str,
        filename: str,
        series_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Extract complete story structure from a document.
        
        Similar to the setup_worldbuilding.py script, but dynamic.
        """
        result = {
            "series": None,
            "books": [],
            "chapters": [],
            "characters": [],
            "world_rules": [],
            "concepts": [],
            "cultivation_system": None,
            "timeline": [],
            "relationships": [],
            "knowledge_entries": [],
            "graph_summary": {"nodes": 0, "relationships": 0},
            "errors": []
        }
        
        try:
            # Step 1: Analyze document type and extract series info
            doc_analysis = await self._analyze_document_type(content, filename)
            result["document_analysis"] = doc_analysis
            
            # Step 2: Get or create series
            if not series_id:
                series_id = await self._get_or_create_series(content, doc_analysis, filename)
            result["series"] = series_id
            
            # Step 3: Extract all story elements
            
            # Characters
            characters = await self._extract_story_characters(content, series_id)
            result["characters"] = characters
            
            # World rules
            world_rules = await self._extract_world_rules(content, series_id)
            result["world_rules"] = world_rules
            
            # Concepts and terms
            concepts = await self._extract_concepts(content, series_id)
            result["concepts"] = concepts
            
            # Cultivation system (if applicable)
            if doc_analysis.get("is_cultivation_story", False):
                cultivation = await self._extract_cultivation_system(content, series_id)
                result["cultivation_system"] = cultivation
            
            # Timeline events
            timeline = await self._extract_timeline(content, series_id)
            result["timeline"] = timeline
            
            # Step 4: Build comprehensive Neo4j graph
            graph_result = await self._build_story_graph(
                characters=characters,
                world_rules=world_rules,
                concepts=concepts,
                timeline=timeline,
                series_id=series_id
            )
            result["graph_summary"] = graph_result
            
            # Step 5: Create chapter outlines from content structure
            chapters = await self._extract_chapters(content, series_id)
            result["chapters"] = chapters
            
        except Exception as e:
            logger.error(f"Story extraction failed: {e}")
            result["errors"].append(str(e))
        
        return result
    
    async def _analyze_document_type(
        self,
        content: str,
        filename: str
    ) -> Dict[str, Any]:
        """Analyze document to understand story type."""
        
        sample = content[:5000]
        
        prompt = f"""Analyze this story document.

FILENAME: {filename}

CONTENT SAMPLE:
{sample}

Determine:
1. What type of story is this? (novel, xianxia/cultivation, fantasy, sci-fi, etc.)
2. Is this a cultivation/修仙 story?
3. What is the main setting/world?
4. What are the main themes?
5. What language is it in?

JSON response:
{{
    "story_type": "novel|short_story|outline|notes",
    "genre": "cultivation|fantasy|sci-fi|romance|etc",
    "is_cultivation_story": true/false,
    "setting": "description of the world",
    "themes": ["theme1", "theme2"],
    "language": "zh-CN|zh-TW|en",
    "series_title": "detected or suggested series title",
    "series_description": "brief description of the story",
    "estimated_parts": 1-10,
    "key_elements": ["element1", "element2"]
}}
"""
        
        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
        try:
            return self._extract_json(response)
        except:
            return {
                "story_type": "novel",
                "genre": "unknown",
                "is_cultivation_story": False,
                "language": "zh-CN",
                "series_title": filename.rsplit('.', 1)[0]
            }
    
    async def _get_or_create_series(
        self,
        content: str,
        analysis: Dict[str, Any],
        filename: str
    ) -> int:
        """Get existing series or create new one."""
        
        title = analysis.get("series_title", filename.rsplit('.', 1)[0])
        
        async with AsyncSessionLocal() as db:
            # Check for existing series
            result = await db.execute(
                text("SELECT id FROM series WHERE title ILIKE :title LIMIT 1"),
                {"title": f"%{title}%"}
            )
            row = result.fetchone()
            
            if row:
                return row.id
            
            # Create new series
            result = await db.execute(
                text("""
                    INSERT INTO series (title, premise, themes, language, metadata)
                    VALUES (:title, :premise, :themes, :language, :metadata)
                    RETURNING id
                """),
                {
                    "title": title,
                    "premise": analysis.get("series_description", ""),
                    "themes": analysis.get("themes", []),
                    "language": analysis.get("language", "zh-CN"),
                    "metadata": json.dumps({
                        "auto_extracted": True,
                        "source_file": filename,
                        "genre": analysis.get("genre", "unknown")
                    })
                }
            )
            await db.commit()
            row = result.fetchone()
            return row.id
    
    async def _extract_story_characters(
        self,
        content: str,
        series_id: int
    ) -> List[Dict[str, Any]]:
        """Extract characters with full profiles."""
        
        chunks = self._chunk_content(content, 6000)
        all_characters = []
        seen_names = set()
        
        for chunk in chunks[:5]:
            prompt = f"""Extract ALL CHARACTERS from this story text.

TEXT:
{chunk}

For each character, extract:
- name: Full name
- aliases: Other names, titles, nicknames
- role: protagonist|antagonist|supporting|minor
- generation: if multi-generational (e.g., "first generation", "second generation")
- faction: which side/group they belong to
- description: who they are
- personality: personality traits
- abilities: powers, skills, talents
- relationships: connections to other characters
- arc: character development journey

JSON response:
{{
    "characters": [
        {{
            "name": "Character Name",
            "aliases": ["alias1"],
            "role": "protagonist|antagonist|supporting|minor",
            "generation": "first|second|third|fourth|fifth|none",
            "faction": "faction name or null",
            "description": "who they are",
            "personality": "personality description",
            "abilities": ["ability1", "ability2"],
            "relationships": [
                {{"target": "Other Character", "type": "師徒|父子|兄弟|敵人|盟友|etc", "description": "details"}}
            ],
            "arc": "character development",
            "confidence": 0.0-1.0
        }}
    ]
}}
"""
            
            response = await self.llm.generate(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2
            )
            
            try:
                data = self._extract_json(response)
                for char in data.get("characters", []):
                    name = char.get("name", "").lower()
                    if name and name not in seen_names:
                        seen_names.add(name)
                        all_characters.append(char)
            except Exception as e:
                logger.warning(f"Character extraction failed: {e}")
        
        # Save characters to database
        created_characters = []
        async with AsyncSessionLocal() as db:
            for char in all_characters:
                try:
                    description = char.get("description", "")
                    if char.get("personality"):
                        description += f"\n\n**性格**: {char.get('personality')}"
                    if char.get("abilities"):
                        description += f"\n\n**能力**: {', '.join(char.get('abilities', []))}"
                    if char.get("arc"):
                        description += f"\n\n**角色發展**: {char.get('arc')}"
                    
                    embedding = generate_embedding(
                        f"{char.get('name', '')} {description}"
                    )
                    
                    result = await db.execute(
                        text("""
                            INSERT INTO character_profiles 
                            (series_id, name, aliases, description, personality, 
                             goals, embedding, language, metadata)
                            VALUES (:series_id, :name, :aliases, :description, :personality,
                                    :goals, :embedding, :language, :metadata)
                            ON CONFLICT (series_id, name) DO UPDATE 
                            SET description = EXCLUDED.description,
                                aliases = EXCLUDED.aliases,
                                updated_at = NOW()
                            RETURNING id, name
                        """),
                        {
                            "series_id": series_id,
                            "name": char.get("name", "Unknown"),
                            "aliases": char.get("aliases", []),
                            "description": description,
                            "personality": char.get("personality"),
                            "goals": char.get("arc"),
                            "embedding": str(embedding),
                            "language": "zh-CN",
                            "metadata": json.dumps({
                                "role": char.get("role"),
                                "generation": char.get("generation"),
                                "faction": char.get("faction"),
                                "abilities": char.get("abilities", []),
                                "relationships": char.get("relationships", []),
                                "auto_extracted": True
                            })
                        }
                    )
                    row = result.fetchone()
                    if row:
                        char["id"] = row.id
                        created_characters.append(char)
                except Exception as e:
                    logger.warning(f"Failed to save character {char.get('name')}: {e}")
            
            await db.commit()
        
        return created_characters
    
    async def _extract_world_rules(
        self,
        content: str,
        series_id: int
    ) -> List[Dict[str, Any]]:
        """Extract world-building rules."""
        
        prompt = f"""Extract WORLD RULES and LAWS from this story.

TEXT (sample):
{content[:6000]}

Look for:
- Natural laws of the world
- Magic/cultivation rules
- Social/political systems
- Historical constants
- Power systems and limitations

JSON response:
{{
    "rules": [
        {{
            "name": "Rule Name",
            "category": "cultivation|magic|society|nature|history|technology",
            "description": "Full rule description",
            "exceptions": ["exception1"],
            "is_hard_rule": true/false,
            "confidence": 0.0-1.0
        }}
    ]
}}
"""
        
        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
        created_rules = []
        
        try:
            data = self._extract_json(response)
            rules = data.get("rules", [])
            
            async with AsyncSessionLocal() as db:
                for rule in rules:
                    if not rule.get("name"):
                        continue
                    
                    result = await db.execute(
                        text("""
                            INSERT INTO world_rules 
                            (series_id, rule_name, rule_category, rule_description, 
                             exceptions, is_hard_rule, metadata)
                            VALUES (:series_id, :name, :category, :description,
                                    :exceptions, :is_hard, :metadata)
                            ON CONFLICT DO NOTHING
                            RETURNING id, rule_name
                        """),
                        {
                            "series_id": series_id,
                            "name": rule.get("name"),
                            "category": rule.get("category", "other"),
                            "description": rule.get("description", ""),
                            "exceptions": rule.get("exceptions", []),
                            "is_hard": rule.get("is_hard_rule", True),
                            "metadata": json.dumps({"auto_extracted": True})
                        }
                    )
                    row = result.fetchone()
                    if row:
                        rule["id"] = row.id
                        created_rules.append(rule)
                
                await db.commit()
                
        except Exception as e:
            logger.error(f"World rules extraction failed: {e}")
        
        return created_rules
    
    async def _extract_concepts(
        self,
        content: str,
        series_id: int
    ) -> List[Dict[str, Any]]:
        """Extract key concepts and terms."""
        
        prompt = f"""Extract KEY CONCEPTS and SPECIAL TERMS from this story.

TEXT (sample):
{content[:6000]}

Look for:
- Unique terminology
- Philosophical concepts
- Power names/types
- Important objects/artifacts
- Techniques/skills
- Organization names

JSON response:
{{
    "concepts": [
        {{
            "name": "Concept Name",
            "type": "term|technique|artifact|organization|philosophy|power|other",
            "definition": "What this concept means",
            "importance": "critical|major|normal|minor",
            "related_to": ["other concept names"],
            "confidence": 0.0-1.0
        }}
    ]
}}
"""
        
        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
        concepts = []
        
        try:
            data = self._extract_json(response)
            concepts = data.get("concepts", [])
            
            # Save as knowledge base entries
            async with AsyncSessionLocal() as db:
                for concept in concepts:
                    if not concept.get("name"):
                        continue
                    
                    embedding = generate_embedding(
                        f"{concept.get('name', '')} {concept.get('definition', '')}"
                    )
                    
                    result = await db.execute(
                        text("""
                            INSERT INTO knowledge_base 
                            (source_type, category, title, content, language, 
                             embedding, tags, metadata)
                            VALUES ('extracted', :category, :title, :content, 'zh-CN',
                                    :embedding, :tags, :metadata)
                            RETURNING id
                        """),
                        {
                            "category": concept.get("type", "concept"),
                            "title": concept.get("name"),
                            "content": concept.get("definition", ""),
                            "embedding": str(embedding),
                            "tags": [concept.get("type"), f"series:{series_id}"],
                            "metadata": json.dumps({
                                "series_id": series_id,
                                "importance": concept.get("importance"),
                                "related_to": concept.get("related_to", []),
                                "auto_extracted": True
                            })
                        }
                    )
                    row = result.fetchone()
                    if row:
                        concept["id"] = row.id
                
                await db.commit()
                
        except Exception as e:
            logger.error(f"Concepts extraction failed: {e}")
        
        return concepts
    
    async def _extract_cultivation_system(
        self,
        content: str,
        series_id: int
    ) -> Dict[str, Any]:
        """Extract cultivation/power system."""
        
        prompt = f"""Extract the CULTIVATION/POWER SYSTEM from this story.

TEXT (sample):
{content[:8000]}

Look for:
- Cultivation realms/levels
- Talent types
- Power progressions
- Breakthrough requirements
- Special abilities at each level

JSON response:
{{
    "system_name": "Name of the cultivation system",
    "realms": [
        {{
            "tier": 1,
            "name": "Realm Name",
            "description": "What this realm represents",
            "requirements": "What's needed to reach this",
            "abilities": ["abilities gained"]
        }}
    ],
    "talent_types": [
        {{
            "category": "Talent Category",
            "description": "What this talent type is",
            "examples": ["example1", "example2"]
        }}
    ],
    "special_rules": [
        "Rule about the cultivation system"
    ]
}}
"""
        
        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
        cultivation_system = {}
        
        try:
            cultivation_system = self._extract_json(response)
            
            # Save realms to knowledge base and Neo4j
            async with AsyncSessionLocal() as db:
                for realm in cultivation_system.get("realms", []):
                    embedding = generate_embedding(
                        f"{realm.get('name', '')} {realm.get('description', '')}"
                    )
                    
                    await db.execute(
                        text("""
                            INSERT INTO knowledge_base 
                            (source_type, category, title, content, language, 
                             embedding, tags, metadata)
                            VALUES ('extracted', 'cultivation_realm', :title, :content, 'zh-CN',
                                    :embedding, :tags, :metadata)
                        """),
                        {
                            "title": f"境界：{realm.get('name')}",
                            "content": f"第{realm.get('tier')}境 - {realm.get('name')}\n\n{realm.get('description', '')}\n\n要求：{realm.get('requirements', '')}\n\n能力：{', '.join(realm.get('abilities', []))}",
                            "embedding": str(embedding),
                            "tags": ["cultivation", "realm", f"tier_{realm.get('tier')}", f"series:{series_id}"],
                            "metadata": json.dumps({
                                "series_id": series_id,
                                "tier": realm.get("tier"),
                                "auto_extracted": True
                            })
                        }
                    )
                
                await db.commit()
                
        except Exception as e:
            logger.error(f"Cultivation system extraction failed: {e}")
        
        return cultivation_system
    
    async def _extract_timeline(
        self,
        content: str,
        series_id: int
    ) -> List[Dict[str, Any]]:
        """Extract timeline events."""
        
        prompt = f"""Extract MAJOR TIMELINE EVENTS from this story.

TEXT (sample):
{content[:6000]}

Look for:
- Key plot events
- Battles/conflicts
- Character deaths/births
- Major discoveries
- World-changing events

JSON response:
{{
    "events": [
        {{
            "title": "Event Title",
            "description": "What happened",
            "time_period": "When (can be vague like 'Part 1', 'Year 5000')",
            "characters_involved": ["character1", "character2"],
            "importance": "critical|major|normal",
            "order": 1,
            "confidence": 0.0-1.0
        }}
    ]
}}
"""
        
        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        
        events = []
        
        try:
            data = self._extract_json(response)
            events = data.get("events", [])
        except Exception as e:
            logger.error(f"Timeline extraction failed: {e}")
        
        return events
    
    async def _extract_chapters(
        self,
        content: str,
        series_id: int
    ) -> List[Dict[str, Any]]:
        """Extract chapter outlines from content structure."""
        
        prompt = f"""Analyze this content and extract CHAPTER/PART structure.

TEXT (sample):
{content[:8000]}

If the content has clear parts/chapters, extract them.
If not, suggest a logical chapter breakdown based on major events.

JSON response:
{{
    "chapters": [
        {{
            "number": 1,
            "title": "Chapter/Part Title",
            "summary": "What happens in this chapter",
            "key_events": ["event1", "event2"],
            "main_characters": ["char1", "char2"]
        }}
    ]
}}
"""
        
        response = await self.llm.generate(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        
        chapters = []
        
        try:
            data = self._extract_json(response)
            chapter_data = data.get("chapters", [])
            
            async with AsyncSessionLocal() as db:
                for ch in chapter_data:
                    content_text = f"""# {ch.get('title', 'Untitled')}

## 摘要
{ch.get('summary', '')}

## 關鍵事件
{chr(10).join(['• ' + e for e in ch.get('key_events', [])])}

## 主要角色
{', '.join(ch.get('main_characters', []))}

*此為大綱，待詳細創作*
"""
                    
                    embedding = generate_embedding(content_text)
                    
                    result = await db.execute(
                        text("""
                            INSERT INTO chapters 
                            (title, content, chapter_number, word_count, embedding, metadata)
                            VALUES (:title, :content, :number, :word_count, :embedding, :metadata)
                            RETURNING id
                        """),
                        {
                            "title": ch.get("title", f"Chapter {ch.get('number', 0)}"),
                            "content": content_text,
                            "number": ch.get("number", 0),
                            "word_count": len(content_text),
                            "embedding": str(embedding),
                            "metadata": json.dumps({
                                "series_id": series_id,
                                "is_outline": True,
                                "auto_extracted": True
                            })
                        }
                    )
                    row = result.fetchone()
                    if row:
                        ch["id"] = row.id
                        chapters.append(ch)
                
                await db.commit()
                
        except Exception as e:
            logger.error(f"Chapter extraction failed: {e}")
        
        return chapters
    
    async def _build_story_graph(
        self,
        characters: List[Dict[str, Any]],
        world_rules: List[Dict[str, Any]],
        concepts: List[Dict[str, Any]],
        timeline: List[Dict[str, Any]],
        series_id: int
    ) -> Dict[str, Any]:
        """Build comprehensive Neo4j graph for the story."""

        nodes_created = 0
        relationships_created = 0

        driver = get_async_neo4j_driver()
        if not driver:
            logger.warning("Neo4j not available for story graph building")
            return {"nodes": nodes_created, "relationships": relationships_created}

        try:
            async with driver.session() as session:
                # Create character nodes
                for char in characters:
                    await session.run("""
                        MERGE (c:Character {name: $name})
                        SET c.description = $description,
                            c.generation = $generation,
                            c.faction = $faction,
                            c.role = $role,
                            c.series_id = $series_id
                    """,
                        name=char.get("name"),
                        description=char.get("description", "")[:500] if char.get("description") else "",
                        generation=char.get("generation"),
                        faction=char.get("faction"),
                        role=char.get("role"),
                        series_id=series_id
                    )
                    nodes_created += 1

                    # Create character relationships
                    for rel in char.get("relationships", []):
                        if rel.get("target"):
                            # Sanitize relationship type
                            rel_type = re.sub(r'[^a-zA-Z0-9_]', '_', str(rel.get("type", "RELATED_TO")).upper())
                            if not rel_type:
                                rel_type = "RELATED_TO"

                            await session.run(f"""
                                MERGE (a:Character {{name: $source}})
                                MERGE (b:Character {{name: $target}})
                                MERGE (a)-[r:{rel_type}]->(b)
                                SET r.description = $description
                            """,
                                source=char.get("name"),
                                target=rel.get("target"),
                                description=rel.get("description", "")[:200] if rel.get("description") else ""
                            )
                            relationships_created += 1

                # Create concept nodes (world rules removed - Task 3)
                for concept in concepts:
                    await session.run("""
                        MERGE (c:Concept {name: $name})
                        SET c.type = $type,
                            c.definition = $definition,
                            c.series_id = $series_id
                    """,
                        name=concept.get("name"),
                        type=concept.get("type"),
                        definition=concept.get("definition", "")[:500] if concept.get("definition") else "",
                        series_id=series_id
                    )
                    nodes_created += 1

                    # Link concepts to related items
                    for related in concept.get("related_to", [])[:5]:  # Limit to 5
                        await session.run("""
                            MERGE (a:Concept {name: $source})
                            MERGE (b:Entity {name: $target})
                            MERGE (a)-[r:RELATED_TO]->(b)
                        """,
                            source=concept.get("name"),
                            target=related
                        )
                        relationships_created += 1

                # Create timeline event nodes
                for event in timeline:
                    await session.run("""
                        MERGE (e:TimelineEvent {title: $title})
                        SET e.description = $description,
                            e.time_period = $time_period,
                            e.order = $order,
                            e.series_id = $series_id
                    """,
                        title=event.get("title"),
                        description=event.get("description", "")[:500] if event.get("description") else "",
                        time_period=event.get("time_period"),
                        order=event.get("order", 0),
                        series_id=series_id
                    )
                    nodes_created += 1

                    # Link characters to events
                    for char_name in event.get("characters_involved", [])[:10]:  # Limit to 10
                        await session.run("""
                            MATCH (c:Character {name: $char_name})
                            MATCH (e:TimelineEvent {title: $event_title})
                            MERGE (c)-[r:PARTICIPATES_IN]->(e)
                        """,
                            char_name=char_name,
                            event_title=event.get("title")
                        )
                        relationships_created += 1

        except Exception as e:
            logger.error(f"Story graph building failed: {e}")

        return {
            "nodes": nodes_created,
            "relationships": relationships_created
        }


def get_entity_extraction_service(provider: str = None) -> EntityExtractionService:
    """Get entity extraction service instance."""
    return EntityExtractionService(provider)


def get_story_extraction_service(provider: str = None) -> StoryExtractionService:
    """Get story extraction service instance."""
    return StoryExtractionService(provider)

