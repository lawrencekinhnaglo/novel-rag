"""Neo4j client for storing context, timelines, and relationships."""
from typing import Optional, List, Dict, Any
from neo4j import AsyncGraphDatabase, AsyncDriver
from app.config import settings

# Neo4j driver instance
driver: Optional[AsyncDriver] = None


async def init_neo4j():
    """Initialize Neo4j connection."""
    global driver
    driver = AsyncGraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
    )
    # Verify connectivity
    await driver.verify_connectivity()
    
    # Create constraints and indexes
    async with driver.session() as session:
        await session.run("""
            CREATE CONSTRAINT character_name IF NOT EXISTS
            FOR (c:Character) REQUIRE c.name IS UNIQUE
        """)
        await session.run("""
            CREATE CONSTRAINT location_name IF NOT EXISTS
            FOR (l:Location) REQUIRE l.name IS UNIQUE
        """)
        await session.run("""
            CREATE CONSTRAINT event_id IF NOT EXISTS
            FOR (e:Event) REQUIRE e.id IS UNIQUE
        """)
        await session.run("""
            CREATE INDEX chapter_number IF NOT EXISTS
            FOR (ch:Chapter) ON (ch.number)
        """)


async def close_neo4j():
    """Close Neo4j connection."""
    global driver
    if driver:
        await driver.close()


def get_neo4j() -> AsyncDriver:
    """Get Neo4j driver."""
    if not driver:
        raise RuntimeError("Neo4j not initialized")
    return driver


class NovelGraphManager:
    """Manager for novel-related graph operations."""
    
    def __init__(self, neo4j_driver: AsyncDriver):
        self.driver = neo4j_driver
    
    async def create_character(self, name: str, description: str = "", 
                               attributes: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a character node."""
        attrs = attributes or {}
        async with self.driver.session() as session:
            result = await session.run("""
                MERGE (c:Character {name: $name})
                SET c.description = $description,
                    c.attributes = $attributes,
                    c.updated_at = datetime()
                RETURN c
            """, name=name, description=description, attributes=attrs)
            record = await result.single()
            return dict(record["c"]) if record else None
    
    async def create_relationship(self, char1: str, char2: str, 
                                  rel_type: str, properties: Dict[str, Any] = None) -> bool:
        """Create a relationship between two characters."""
        props = properties or {}
        async with self.driver.session() as session:
            await session.run(f"""
                MATCH (c1:Character {{name: $char1}})
                MATCH (c2:Character {{name: $char2}})
                MERGE (c1)-[r:{rel_type}]->(c2)
                SET r += $properties, r.updated_at = datetime()
            """, char1=char1, char2=char2, properties=props)
            return True
    
    async def create_location(self, name: str, description: str = "",
                             attributes: Dict[str, Any] = None) -> Dict[str, Any]:
        """Create a location node."""
        attrs = attributes or {}
        async with self.driver.session() as session:
            result = await session.run("""
                MERGE (l:Location {name: $name})
                SET l.description = $description,
                    l.attributes = $attributes,
                    l.updated_at = datetime()
                RETURN l
            """, name=name, description=description, attributes=attrs)
            record = await result.single()
            return dict(record["l"]) if record else None
    
    async def create_event(self, event_id: str, title: str, description: str,
                          timestamp: str = None, chapter: int = None) -> Dict[str, Any]:
        """Create a timeline event."""
        async with self.driver.session() as session:
            result = await session.run("""
                MERGE (e:Event {id: $event_id})
                SET e.title = $title,
                    e.description = $description,
                    e.story_timestamp = $timestamp,
                    e.chapter = $chapter,
                    e.updated_at = datetime()
                RETURN e
            """, event_id=event_id, title=title, description=description,
                timestamp=timestamp, chapter=chapter)
            record = await result.single()
            return dict(record["e"]) if record else None
    
    async def link_character_to_event(self, character: str, event_id: str, 
                                      role: str = "PARTICIPATES_IN"):
        """Link a character to an event."""
        async with self.driver.session() as session:
            await session.run(f"""
                MATCH (c:Character {{name: $character}})
                MATCH (e:Event {{id: $event_id}})
                MERGE (c)-[r:{role}]->(e)
                SET r.updated_at = datetime()
            """, character=character, event_id=event_id)
    
    async def link_event_to_location(self, event_id: str, location: str):
        """Link an event to a location."""
        async with self.driver.session() as session:
            await session.run("""
                MATCH (e:Event {id: $event_id})
                MATCH (l:Location {name: $location})
                MERGE (e)-[r:OCCURS_AT]->(l)
                SET r.updated_at = datetime()
            """, event_id=event_id, location=location)
    
    async def get_character_network(self, character: str, depth: int = 2) -> Dict[str, Any]:
        """Get a character's relationship network."""
        async with self.driver.session() as session:
            result = await session.run("""
                MATCH path = (c:Character {name: $character})-[*1..$depth]-(related)
                RETURN c, collect(distinct path) as paths
            """, character=character, depth=depth)
            record = await result.single()
            if record:
                return {
                    "character": dict(record["c"]),
                    "paths_count": len(record["paths"])
                }
            return None
    
    async def get_timeline(self, chapter_start: int = None, 
                          chapter_end: int = None) -> List[Dict[str, Any]]:
        """Get timeline events, optionally filtered by chapter range."""
        async with self.driver.session() as session:
            if chapter_start is not None and chapter_end is not None:
                result = await session.run("""
                    MATCH (e:Event)
                    WHERE e.chapter >= $start AND e.chapter <= $end
                    OPTIONAL MATCH (e)-[:OCCURS_AT]->(l:Location)
                    OPTIONAL MATCH (c:Character)-[:PARTICIPATES_IN]->(e)
                    RETURN e, collect(distinct l.name) as locations, 
                           collect(distinct c.name) as characters
                    ORDER BY e.chapter, e.story_timestamp
                """, start=chapter_start, end=chapter_end)
            else:
                result = await session.run("""
                    MATCH (e:Event)
                    OPTIONAL MATCH (e)-[:OCCURS_AT]->(l:Location)
                    OPTIONAL MATCH (c:Character)-[:PARTICIPATES_IN]->(e)
                    RETURN e, collect(distinct l.name) as locations, 
                           collect(distinct c.name) as characters
                    ORDER BY e.chapter, e.story_timestamp
                """)
            
            events = []
            async for record in result:
                event = dict(record["e"])
                event["locations"] = record["locations"]
                event["characters"] = record["characters"]
                events.append(event)
            return events
    
    async def get_all_characters(self) -> List[Dict[str, Any]]:
        """Get all characters with their relationships."""
        async with self.driver.session() as session:
            result = await session.run("""
                MATCH (c:Character)
                OPTIONAL MATCH (c)-[r]-(other:Character)
                RETURN c, collect({type: type(r), target: other.name}) as relationships
            """)
            characters = []
            async for record in result:
                char = dict(record["c"])
                char["relationships"] = [r for r in record["relationships"] if r["target"]]
                characters.append(char)
            return characters
    
    async def get_all_locations(self) -> List[Dict[str, Any]]:
        """Get all locations."""
        async with self.driver.session() as session:
            result = await session.run("""
                MATCH (l:Location)
                OPTIONAL MATCH (e:Event)-[:OCCURS_AT]->(l)
                RETURN l, count(e) as event_count
            """)
            locations = []
            async for record in result:
                loc = dict(record["l"])
                loc["event_count"] = record["event_count"]
                locations.append(loc)
            return locations
    
    async def search_graph(self, query: str) -> Dict[str, Any]:
        """Search across the graph for matching nodes."""
        async with self.driver.session() as session:
            result = await session.run("""
                CALL {
                    MATCH (c:Character)
                    WHERE toLower(c.name) CONTAINS toLower($query)
                       OR toLower(c.description) CONTAINS toLower($query)
                    RETURN c as node, 'Character' as type
                    UNION
                    MATCH (l:Location)
                    WHERE toLower(l.name) CONTAINS toLower($query)
                       OR toLower(l.description) CONTAINS toLower($query)
                    RETURN l as node, 'Location' as type
                    UNION
                    MATCH (e:Event)
                    WHERE toLower(e.title) CONTAINS toLower($query)
                       OR toLower(e.description) CONTAINS toLower($query)
                    RETURN e as node, 'Event' as type
                }
                RETURN node, type
                LIMIT 20
            """, query=query)
            
            results = {"characters": [], "locations": [], "events": []}
            async for record in result:
                node_type = record["type"].lower() + "s"
                results[node_type].append(dict(record["node"]))
            return results
    
    async def get_context_for_response(self, characters: List[str] = None,
                                       locations: List[str] = None,
                                       chapter: int = None) -> Dict[str, Any]:
        """Get comprehensive context from graph for generating responses."""
        context = {"characters": [], "locations": [], "events": [], "relationships": []}
        
        async with self.driver.session() as session:
            # Get character details and relationships
            if characters:
                for char_name in characters:
                    result = await session.run("""
                        MATCH (c:Character {name: $name})
                        OPTIONAL MATCH (c)-[r]-(other:Character)
                        RETURN c, collect({
                            type: type(r), 
                            target: other.name, 
                            direction: CASE WHEN startNode(r) = c THEN 'outgoing' ELSE 'incoming' END
                        }) as rels
                    """, name=char_name)
                    record = await result.single()
                    if record:
                        char_data = dict(record["c"])
                        char_data["relationships"] = [r for r in record["rels"] if r["target"]]
                        context["characters"].append(char_data)
            
            # Get location details
            if locations:
                for loc_name in locations:
                    result = await session.run("""
                        MATCH (l:Location {name: $name})
                        OPTIONAL MATCH (e:Event)-[:OCCURS_AT]->(l)
                        RETURN l, collect(e.title) as events
                    """, name=loc_name)
                    record = await result.single()
                    if record:
                        loc_data = dict(record["l"])
                        loc_data["events"] = record["events"]
                        context["locations"].append(loc_data)
            
            # Get chapter events
            if chapter is not None:
                result = await session.run("""
                    MATCH (e:Event {chapter: $chapter})
                    OPTIONAL MATCH (c:Character)-[:PARTICIPATES_IN]->(e)
                    OPTIONAL MATCH (e)-[:OCCURS_AT]->(l:Location)
                    RETURN e, collect(distinct c.name) as characters, 
                           collect(distinct l.name) as locations
                    ORDER BY e.story_timestamp
                """, chapter=chapter)
                async for record in result:
                    event = dict(record["e"])
                    event["characters"] = record["characters"]
                    event["locations"] = record["locations"]
                    context["events"].append(event)
        
        return context


async def get_graph_manager() -> NovelGraphManager:
    """Get novel graph manager instance."""
    return NovelGraphManager(get_neo4j())

