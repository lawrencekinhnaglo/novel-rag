"""Graph database API endpoints for Neo4j."""
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any

from app.database.neo4j_client import get_graph_manager
from app.api.v1.models import (
    CharacterCreate, RelationshipCreate, LocationCreate, EventCreate
)

router = APIRouter()


# Character endpoints
@router.post("/graph/characters")
async def create_character(character: CharacterCreate):
    """Create a new character."""
    graph_manager = await get_graph_manager()
    result = await graph_manager.create_character(
        name=character.name,
        description=character.description,
        attributes=character.attributes
    )
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create character")
    return {"message": "Character created", "character": result}


@router.get("/graph/characters")
async def list_characters():
    """List all characters with their relationships."""
    graph_manager = await get_graph_manager()
    characters = await graph_manager.get_all_characters()
    return {"characters": characters}


@router.get("/graph/characters/{name}")
async def get_character(name: str, depth: int = 2):
    """Get a character's network."""
    graph_manager = await get_graph_manager()
    result = await graph_manager.get_character_network(name, depth)
    if not result:
        raise HTTPException(status_code=404, detail="Character not found")
    return result


# Relationship endpoints
@router.post("/graph/relationships")
async def create_relationship(relationship: RelationshipCreate):
    """Create a relationship between characters."""
    graph_manager = await get_graph_manager()
    success = await graph_manager.create_relationship(
        char1=relationship.character1,
        char2=relationship.character2,
        rel_type=relationship.relationship_type.upper().replace(" ", "_"),
        properties=relationship.properties
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to create relationship")
    return {"message": "Relationship created"}


# Location endpoints
@router.post("/graph/locations")
async def create_location(location: LocationCreate):
    """Create a new location."""
    graph_manager = await get_graph_manager()
    result = await graph_manager.create_location(
        name=location.name,
        description=location.description,
        attributes=location.attributes
    )
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create location")
    return {"message": "Location created", "location": result}


@router.get("/graph/locations")
async def list_locations():
    """List all locations."""
    graph_manager = await get_graph_manager()
    locations = await graph_manager.get_all_locations()
    return {"locations": locations}


# Event/Timeline endpoints
@router.post("/graph/events")
async def create_event(event: EventCreate):
    """Create a timeline event."""
    graph_manager = await get_graph_manager()
    
    # Create the event
    result = await graph_manager.create_event(
        event_id=event.event_id,
        title=event.title,
        description=event.description,
        timestamp=event.timestamp,
        chapter=event.chapter
    )
    
    if not result:
        raise HTTPException(status_code=500, detail="Failed to create event")
    
    # Link characters to event
    if event.characters:
        for char_name in event.characters:
            await graph_manager.link_character_to_event(char_name, event.event_id)
    
    # Link location to event
    if event.location:
        await graph_manager.link_event_to_location(event.event_id, event.location)
    
    return {"message": "Event created", "event": result}


@router.get("/graph/timeline")
async def get_timeline(start_chapter: int = None, end_chapter: int = None):
    """Get timeline events."""
    graph_manager = await get_graph_manager()
    events = await graph_manager.get_timeline(start_chapter, end_chapter)
    return {"events": events}


# Search and context
@router.get("/graph/search")
async def search_graph(query: str):
    """Search across the graph."""
    graph_manager = await get_graph_manager()
    results = await graph_manager.search_graph(query)
    return results


@router.post("/graph/context")
async def get_context(
    characters: List[str] = None,
    locations: List[str] = None,
    chapter: int = None
):
    """Get comprehensive context for generating responses."""
    graph_manager = await get_graph_manager()
    context = await graph_manager.get_context_for_response(
        characters=characters,
        locations=locations,
        chapter=chapter
    )
    return context


# Visualization data
@router.get("/graph/visualization")
async def get_visualization_data():
    """Get data for graph visualization."""
    graph_manager = await get_graph_manager()
    
    characters = await graph_manager.get_all_characters()
    locations = await graph_manager.get_all_locations()
    
    # Build nodes and edges for visualization
    nodes = []
    edges = []
    
    # Add character nodes
    for char in characters:
        nodes.append({
            "id": f"char_{char.get('name', '')}",
            "label": char.get("name", "Unknown"),
            "type": "character",
            "data": char
        })
        
        # Add relationship edges
        for rel in char.get("relationships", []):
            if rel.get("target"):
                edges.append({
                    "source": f"char_{char.get('name', '')}",
                    "target": f"char_{rel['target']}",
                    "label": rel.get("type", "RELATED_TO"),
                    "type": "relationship"
                })
    
    # Add location nodes
    for loc in locations:
        nodes.append({
            "id": f"loc_{loc.get('name', '')}",
            "label": loc.get("name", "Unknown"),
            "type": "location",
            "data": loc
        })
    
    return {
        "nodes": nodes,
        "edges": edges
    }

