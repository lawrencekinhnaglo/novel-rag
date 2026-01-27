#!/usr/bin/env python3
"""
Script to clear all databases and insert worldbuilding data for the 紀元遠征 novel.
"""

import json
import os
import sys
import asyncio
from datetime import datetime
from typing import List, Dict, Any
import hashlib
import uuid

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

import asyncpg
import redis
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from neo4j import GraphDatabase

# Configuration - Use Docker internal hostnames when running inside container
POSTGRES_URL = os.getenv("DATABASE_URL", "postgresql://novelrag:novelrag_secret@postgres:5432/novel_rag_db")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://neo4j:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "novelrag_neo4j")

# Embedding configuration - Match database vector(384) dimension
EMBEDDING_DIM = 384

def generate_simple_embedding(text: str, dim: int = EMBEDDING_DIM) -> List[float]:
    """Generate a simple deterministic embedding based on text hash."""
    embeddings = []
    for i in range(dim):
        hash_input = f"{text}_{i}".encode('utf-8')
        hash_value = int(hashlib.md5(hash_input).hexdigest(), 16)
        normalized = (hash_value % 10000) / 5000 - 1.0
        embeddings.append(normalized)
    return embeddings

def embedding_to_pgvector(embedding: List[float]) -> str:
    """Convert embedding list to PostgreSQL vector string format."""
    return '[' + ','.join(map(str, embedding)) + ']'


class DatabaseManager:
    def __init__(self):
        self.pg_pool = None
        self.redis_client = None
        self.qdrant_client = None
        self.neo4j_driver = None
        
    async def connect(self):
        """Connect to all databases."""
        print("🔌 Connecting to databases...")
        
        # PostgreSQL
        try:
            self.pg_pool = await asyncpg.create_pool(POSTGRES_URL)
            print("  ✓ PostgreSQL connected")
        except Exception as e:
            print(f"  ✗ PostgreSQL failed: {e}")
            
        # Redis
        try:
            self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
            self.redis_client.ping()
            print("  ✓ Redis connected")
        except Exception as e:
            print(f"  ✗ Redis failed: {e}")
            
        # Qdrant
        try:
            self.qdrant_client = QdrantClient(url=QDRANT_URL)
            self.qdrant_client.get_collections()
            print("  ✓ Qdrant connected")
        except Exception as e:
            print(f"  ✗ Qdrant failed: {e}")
            
        # Neo4j
        try:
            self.neo4j_driver = GraphDatabase.driver(
                NEO4J_URI, 
                auth=(NEO4J_USER, NEO4J_PASSWORD)
            )
            with self.neo4j_driver.session() as session:
                session.run("RETURN 1")
            print("  ✓ Neo4j connected")
        except Exception as e:
            print(f"  ✗ Neo4j failed: {e}")
            
    async def close(self):
        """Close all database connections."""
        if self.pg_pool:
            await self.pg_pool.close()
        if self.redis_client:
            self.redis_client.close()
        if self.neo4j_driver:
            self.neo4j_driver.close()
            
    async def clear_all(self):
        """Clear all databases."""
        print("\n🗑️  Clearing all databases...")
        
        # Clear PostgreSQL tables (in correct order due to foreign keys)
        if self.pg_pool:
            async with self.pg_pool.acquire() as conn:
                tables_to_clear = [
                    # Dependent tables first
                    "message_feedback",
                    "character_knowledge",
                    "character_states",
                    "story_facts",
                    "foreshadowing_reinforcements",
                    "foreshadowing",
                    "world_rules",
                    "story_analyses",
                    "story_arcs",
                    "character_profiles",
                    "chat_messages",
                    "chat_sessions",
                    "chapters",
                    "document_chunks",
                    "documents",
                    "knowledge_base",
                    "ideas",
                    "books",
                    "series",
                ]
                for table in tables_to_clear:
                    try:
                        await conn.execute(f"DELETE FROM {table}")
                        print(f"    ✓ Cleared {table}")
                    except Exception as e:
                        print(f"    ✗ Failed to clear {table}: {e}")
            print("  ✓ PostgreSQL cleared")
            
        # Clear Redis
        if self.redis_client:
            try:
                self.redis_client.flushdb()
                print("  ✓ Redis cleared")
            except Exception as e:
                print(f"  ✗ Redis failed: {e}")
                
        # Clear Qdrant collections
        if self.qdrant_client:
            collections = ["novel_chapters", "novel_knowledge", "documents"]
            for collection in collections:
                try:
                    self.qdrant_client.delete_collection(collection)
                    print(f"    ✓ Deleted Qdrant collection: {collection}")
                except Exception as e:
                    pass
            for collection in collections:
                try:
                    self.qdrant_client.create_collection(
                        collection_name=collection,
                        vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE)
                    )
                    print(f"    ✓ Created Qdrant collection: {collection}")
                except Exception as e:
                    print(f"    ✗ Failed to create {collection}: {e}")
            print("  ✓ Qdrant cleared and recreated")
            
        # Clear Neo4j
        if self.neo4j_driver:
            try:
                with self.neo4j_driver.session() as session:
                    session.run("MATCH (n) DETACH DELETE n")
                print("  ✓ Neo4j cleared")
            except Exception as e:
                print(f"  ✗ Neo4j failed: {e}")


class WorldbuildingImporter:
    def __init__(self, db_manager: DatabaseManager, data: Dict[str, Any]):
        self.db = db_manager
        self.data = data
        self.series_id = None
        self.character_ids = {}
        
    async def import_all(self):
        """Import all worldbuilding data."""
        print("\n📚 Importing worldbuilding data...")
        
        await self.import_series()
        await self.import_knowledge_base()
        await self.import_characters()
        await self.import_world_rules()
        await self.import_chapters()
        await self.import_ideas()
        await self.import_graph()
        await self.cache_context()
        
        print("\n✨ Import complete!")
        
    async def import_series(self):
        """Import story series."""
        print("\n  📖 Importing story series...")
        series = self.data["story_series"]
        
        async with self.db.pg_pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO series (title, premise, themes, language, metadata)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
            """, series["title"], series["description"], 
                [series["genre"]], series.get("language", "zh-CN"),
                json.dumps({"source": "worldbuilding_import"}))
            self.series_id = row["id"]
            print(f"    ✓ Created series: {series['title']} (ID: {self.series_id})")
            
    async def import_knowledge_base(self):
        """Import knowledge base entries."""
        print("\n  🧠 Importing knowledge base...")
        
        entries = []
        
        # Cultivation realms
        for realm in self.data["cultivation_realms"]:
            entries.append({
                "title": f"境界：{realm['name']}",
                "content": f"第{realm['tier']}境 - {realm['name']}\n\n{realm['description']}",
                "source_type": "manual",
                "category": "cultivation_realm",
                "tags": ["cultivation", "realm", f"tier_{realm['tier']}", f"series:{self.series_id}"]
            })
            
        # Talent categories
        for talent in self.data["talent_categories"]:
            examples_text = "、".join(talent["examples"])
            entries.append({
                "title": f"天賦類型：{talent['category']}",
                "content": f"天賦類型：{talent['category']}\n\n{talent['description']}\n\n常見例子：{examples_text}",
                "source_type": "manual",
                "category": "talent_system",
                "tags": ["talent", talent["category"], f"series:{self.series_id}"]
            })
            
        # Key concepts
        for concept in self.data["key_concepts"]:
            entries.append({
                "title": concept["name"],
                "content": f"{concept['name']}\n\n{concept['description']}",
                "source_type": "manual",
                "category": "world_concept",
                "tags": ["concept", f"series:{self.series_id}"]
            })
            
        # World rules as knowledge
        for rule in self.data["world_rules"]:
            entries.append({
                "title": f"世界規則：{rule['name']}",
                "content": f"{rule['name']}\n\n{rule['description']}",
                "source_type": "manual",
                "category": "world_rule",
                "tags": ["world_rule", f"series:{self.series_id}"]
            })
            
        # Story structure
        for part_key, part in self.data["story_structure"].items():
            protagonists = "、".join(part.get("protagonists", []))
            antagonists = "、".join(part.get("antagonists", []))
            events = "\n".join([f"• {e}" for e in part.get("key_events", [])])
            
            content = f"""# {part['title']} ({part['subtitle']})

## 時間線
{part['timeline']}

## 主角
{protagonists}

## 反派
{antagonists if antagonists else "無明確反派"}

## 劇情摘要
{part['summary']}

## 關鍵事件
{events}
"""
            entries.append({
                "title": f"第{part_key[-1]}部：{part['title']}",
                "content": content,
                "source_type": "manual",
                "category": "story_structure",
                "tags": ["story", "structure", part_key, f"series:{self.series_id}"]
            })
            
        # Insert into PostgreSQL and Qdrant
        async with self.db.pg_pool.acquire() as conn:
            for entry in entries:
                embedding = generate_simple_embedding(entry["content"])
                embedding_str = embedding_to_pgvector(embedding)
                
                row = await conn.fetchrow("""
                    INSERT INTO knowledge_base (title, content, source_type, category, tags, embedding, language, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING id
                """, entry["title"], entry["content"], entry["source_type"], entry["category"],
                    entry["tags"], embedding_str, "zh-CN", json.dumps({"series_id": self.series_id}))
                
                # Insert into Qdrant
                if self.db.qdrant_client:
                    self.db.qdrant_client.upsert(
                        collection_name="novel_knowledge",
                        points=[PointStruct(
                            id=row["id"],
                            vector=embedding,
                            payload={
                                "id": row["id"],
                                "title": entry["title"],
                                "category": entry["category"],
                                "tags": entry["tags"],
                                "content_preview": entry["content"][:500]
                            }
                        )]
                    )
                
        print(f"    ✓ Imported {len(entries)} knowledge base entries")
        
    async def import_characters(self):
        """Import character profiles."""
        print("\n  👥 Importing characters...")
        
        characters = self.data["characters"]
        char_count = 0
        
        async with self.db.pg_pool.acquire() as conn:
            for gen_key, gen_data in characters.items():
                generation = gen_key.replace("generation_", "第") + "代"
                
                for faction, faction_chars in gen_data.items():
                    if not isinstance(faction_chars, list):
                        continue
                        
                    for char in faction_chars:
                        # Build description
                        desc_parts = [char.get("description", "")]
                        
                        if "talents" in char:
                            talents = char["talents"]
                            if isinstance(talents, dict):
                                talents_text = "\n\n## 天賦設定\n"
                                for talent_type, talent_desc in talents.items():
                                    talents_text += f"• **{talent_type}**：{talent_desc}\n"
                                desc_parts.append(talents_text)
                            elif isinstance(talents, str):
                                desc_parts.append(f"\n\n## 天賦\n{talents}")
                            
                        if "mortal_skills" in char:
                            desc_parts.append(f"\n## 凡人技能\n{char['mortal_skills']}")
                            
                        if "core_ability" in char:
                            desc_parts.append(f"\n## 核心能力\n{char['core_ability']}")
                            
                        if "arc" in char:
                            desc_parts.append(f"\n## 角色弧線\n{char['arc']}")
                            
                        if "fate" in char:
                            desc_parts.append(f"\n## 命運\n{char['fate']}")
                            
                        if "evolution" in char:
                            desc_parts.append(f"\n## 進化路線\n{char['evolution']}")
                            
                        full_description = "".join(desc_parts)
                        
                        # Get aliases
                        aliases = char.get("alias", [])
                        
                        # Generate embedding
                        embedding = generate_simple_embedding(full_description)
                        embedding_str = embedding_to_pgvector(embedding)
                        
                        try:
                            row = await conn.fetchrow("""
                                INSERT INTO character_profiles 
                                (series_id, name, aliases, description, background, goals, embedding, language, metadata)
                                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                                RETURNING id
                            """, self.series_id, char["name"], aliases, full_description,
                                f"{generation} - {faction}", char.get("core_ability", ""),
                                embedding_str, "zh-CN",
                                json.dumps({
                                    "generation": gen_key,
                                    "faction": faction,
                                    "original_role": char.get("role", ""),
                                }))
                            
                            self.character_ids[char["name"]] = row["id"]
                            char_count += 1
                        except Exception as e:
                            print(f"    ✗ Failed to insert {char['name']}: {e}")
                            continue
                        
                        # Also add to knowledge base
                        await conn.execute("""
                            INSERT INTO knowledge_base (title, content, source_type, category, tags, embedding, language, metadata)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                        """, f"角色：{char['name']}", full_description, "manual", "character",
                            ["character", generation, faction, f"series:{self.series_id}"],
                            embedding_str, "zh-CN", json.dumps({"character_id": row["id"], "series_id": self.series_id}))
                        
        print(f"    ✓ Imported {char_count} characters")
        
    async def import_world_rules(self):
        """Import world rules to the world_rules table."""
        print("\n  📜 Importing world rules...")
        
        async with self.db.pg_pool.acquire() as conn:
            for rule in self.data["world_rules"]:
                await conn.execute("""
                    INSERT INTO world_rules 
                    (series_id, rule_name, rule_category, rule_description, metadata)
                    VALUES ($1, $2, $3, $4, $5)
                """, self.series_id, rule["name"], "核心設定", rule["description"],
                    json.dumps({"source": "worldbuilding_import"}))
                
        print(f"    ✓ Imported {len(self.data['world_rules'])} world rules")
        
    async def import_chapters(self):
        """Import story structure as chapter outlines."""
        print("\n  📝 Importing chapter outlines...")
        
        async with self.db.pg_pool.acquire() as conn:
            chapter_num = 1
            for part_key, part in self.data["story_structure"].items():
                protagonists = "、".join(part.get("protagonists", []))
                antagonists = "、".join(part.get("antagonists", []))
                events = "\n".join([f"• {e}" for e in part.get("key_events", [])])
                
                content = f"""# {part['title']} ({part['subtitle']})

**時間線**: {part['timeline']}

**主角**: {protagonists}

**反派**: {antagonists if antagonists else "無明確反派"}

---

## 劇情摘要

{part['summary']}

---

## 關鍵事件

{events}

---

*此為故事大綱，待詳細創作*
"""
                embedding = generate_simple_embedding(content)
                embedding_str = embedding_to_pgvector(embedding)
                word_count = len(content)
                
                row = await conn.fetchrow("""
                    INSERT INTO chapters (title, content, chapter_number, word_count, embedding, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6)
                    RETURNING id
                """, f"{part['title']} - {part['subtitle']}", content, chapter_num, word_count,
                    embedding_str, json.dumps({
                        "part_key": part_key,
                        "series_id": self.series_id,
                        "is_outline": True
                    }))
                
                # Insert into Qdrant
                if self.db.qdrant_client:
                    self.db.qdrant_client.upsert(
                        collection_name="chapters",
                        points=[PointStruct(
                            id=row["id"],
                            vector=embedding,
                            payload={
                                "id": row["id"],
                                "title": f"{part['title']} - {part['subtitle']}",
                                "chapter_number": chapter_num,
                                "content_preview": content[:500],
                                "word_count": word_count
                            }
                        )]
                    )
                
                chapter_num += 1
                
        print(f"    ✓ Imported {chapter_num - 1} chapter outlines")
        
    async def import_ideas(self):
        """Import key concepts and talents as ideas for brainstorming."""
        print("\n  💡 Importing ideas...")
        
        ideas = []
        
        # Add cultivation realm ideas
        for realm in self.data["cultivation_realms"]:
            ideas.append({
                "title": f"境界：{realm['name']}",
                "content": realm['description'],
                "category": "cultivation"
            })
            
        # Add talent ideas
        for talent in self.data["talent_categories"]:
            ideas.append({
                "title": f"天賦：{talent['category']}",
                "content": f"{talent['description']}\n範例：{'、'.join(talent['examples'])}",
                "category": "talent"
            })
            
        # Add key concept ideas
        for concept in self.data["key_concepts"]:
            ideas.append({
                "title": concept["name"],
                "content": concept["description"],
                "category": "concept"
            })
            
        async with self.db.pg_pool.acquire() as conn:
            for idea in ideas:
                await conn.execute("""
                    INSERT INTO ideas (title, content, category, metadata)
                    VALUES ($1, $2, $3, $4)
                """, idea["title"], idea["content"], idea["category"],
                    json.dumps({"series_id": self.series_id}))
                    
        print(f"    ✓ Imported {len(ideas)} ideas")
        
    async def import_graph(self):
        """Import relationships into Neo4j."""
        print("\n  🕸️  Importing graph relationships...")
        
        if not self.db.neo4j_driver:
            print("    ✗ Neo4j not available, skipping graph import")
            return
            
        with self.db.neo4j_driver.session() as session:
            # Create character nodes
            for gen_key, gen_data in self.data["characters"].items():
                generation = gen_key.replace("generation_", "")
                
                for faction, faction_chars in gen_data.items():
                    if not isinstance(faction_chars, list):
                        continue
                        
                    for char in faction_chars:
                        session.run("""
                            MERGE (c:Character {name: $name})
                            SET c.generation = $generation,
                                c.faction = $faction,
                                c.role = $role,
                                c.description = $description
                        """, name=char["name"], 
                            generation=generation,
                            faction=faction,
                            role=char.get("role", ""),
                            description=char.get("description", "")[:500])
                        
            # Create relationship edges
            for rel in self.data["relationships"]:
                session.run("""
                    MATCH (a:Character {name: $from_name})
                    MATCH (b:Character {name: $to_name})
                    MERGE (a)-[r:RELATES_TO {type: $rel_type}]->(b)
                    SET r.description = $description
                """, from_name=rel["from"],
                    to_name=rel["to"],
                    rel_type=rel["type"],
                    description=rel["description"])
                    
            # Create story part nodes and connect characters
            for part_key, part in self.data["story_structure"].items():
                session.run("""
                    MERGE (p:StoryPart {key: $key})
                    SET p.title = $title,
                        p.subtitle = $subtitle,
                        p.timeline = $timeline,
                        p.summary = $summary
                """, key=part_key,
                    title=part["title"],
                    subtitle=part["subtitle"],
                    timeline=part["timeline"],
                    summary=part["summary"])
                    
                # Connect protagonists
                for protag in part.get("protagonists", []):
                    session.run("""
                        MATCH (c:Character {name: $name})
                        MATCH (p:StoryPart {key: $part_key})
                        MERGE (c)-[:PROTAGONIST_IN]->(p)
                    """, name=protag, part_key=part_key)
                    
                # Connect antagonists
                for antag in part.get("antagonists", []):
                    session.run("""
                        MATCH (c:Character {name: $name})
                        MATCH (p:StoryPart {key: $part_key})
                        MERGE (c)-[:ANTAGONIST_IN]->(p)
                    """, name=antag, part_key=part_key)
                    
            # Create concept nodes
            for concept in self.data["key_concepts"]:
                session.run("""
                    MERGE (c:Concept {name: $name})
                    SET c.description = $description
                """, name=concept["name"], description=concept["description"])
                
            # Create cultivation realm nodes
            for realm in self.data["cultivation_realms"]:
                session.run("""
                    MERGE (r:CultivationRealm {name: $name})
                    SET r.tier = $tier,
                        r.description = $description
                """, name=realm["name"], tier=realm["tier"], description=realm["description"])
                
            # World rules are stored in PostgreSQL only (not in Neo4j)
                
        print(f"    ✓ Imported graph with {len(self.data['relationships'])} relationships")
        
    async def cache_context(self):
        """Cache important context in Redis."""
        print("\n  💾 Caching context in Redis...")
        
        if not self.db.redis_client:
            print("    ✗ Redis not available, skipping cache")
            return
            
        # Cache series info
        self.db.redis_client.hset(
            f"series:{self.series_id}",
            mapping={
                "title": self.data["story_series"]["title"],
                "description": self.data["story_series"]["description"],
                "genre": self.data["story_series"]["genre"]
            }
        )
        
        # Cache cultivation realms
        realms_json = json.dumps(self.data["cultivation_realms"], ensure_ascii=False)
        self.db.redis_client.set("cultivation_realms", realms_json)
        
        # Cache talent categories
        talents_json = json.dumps(self.data["talent_categories"], ensure_ascii=False)
        self.db.redis_client.set("talent_categories", talents_json)
        
        # Cache key concepts
        concepts_json = json.dumps(self.data["key_concepts"], ensure_ascii=False)
        self.db.redis_client.set("key_concepts", concepts_json)
        
        # Cache character index
        char_index = {}
        for gen_key, gen_data in self.data["characters"].items():
            for faction, faction_chars in gen_data.items():
                if isinstance(faction_chars, list):
                    for char in faction_chars:
                        char_index[char["name"]] = {
                            "generation": gen_key,
                            "faction": faction,
                            "role": char.get("role", ""),
                            "id": self.character_ids.get(char["name"])
                        }
        self.db.redis_client.set("character_index", json.dumps(char_index, ensure_ascii=False))
        
        # Cache world rules
        rules_json = json.dumps(self.data["world_rules"], ensure_ascii=False)
        self.db.redis_client.set("world_rules", rules_json)
        
        print("    ✓ Context cached successfully")


async def main():
    """Main entry point."""
    print("=" * 60)
    print("🌟 紀元遠征 Worldbuilding Data Import")
    print("=" * 60)
    
    # Load data
    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_file = os.path.join(script_dir, "worldbuilding_data.json")
    
    print(f"\n📂 Loading data from {data_file}")
    with open(data_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"   ✓ Loaded worldbuilding data")
    
    # Initialize database manager
    db = DatabaseManager()
    await db.connect()
    
    try:
        # Clear all databases
        await db.clear_all()
        
        # Import worldbuilding data
        importer = WorldbuildingImporter(db, data)
        await importer.import_all()
        
    finally:
        await db.close()
        
    print("\n" + "=" * 60)
    print("✅ All done! Your worldbuilding data has been imported.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
