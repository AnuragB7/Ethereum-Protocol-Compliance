"""
Codebase Routes

Endpoints for codebase upload, indexing, and statistics.
"""

import asyncio
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import Optional
from app.models.responses import UploadResponse, StatisticsResponse
from app.api import dependencies as deps

router = APIRouter(prefix="/api", tags=["Codebase"])

# Thread pool for running sync operations
_executor = ThreadPoolExecutor(max_workers=2)


def _run_ingest(indexer, codebase_path: str):
    """Run ingestion in a separate thread to avoid async issues."""
    return indexer.ingest_codebase(codebase_path)


@router.post("/upload-folder", response_model=UploadResponse)
async def upload_folder(codebase_path: str):
    """
    Ingest a codebase from a local folder path.
    
    This will parse all supported files and build the property graph index.
    """
    if not deps.indexer:
        raise HTTPException(status_code=400, detail="API not configured. Call /api/configure first.")
    
    try:
        import os
        if not os.path.exists(codebase_path):
            raise HTTPException(status_code=404, detail=f"Path not found: {codebase_path}")
        
        # Run ingestion in thread pool to handle sync/async properly
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_executor, _run_ingest, deps.indexer, codebase_path)
        
        # Store entities and relationships globally
        deps.entities = deps.indexer.entities
        deps.relationships = deps.indexer.relationships
        
        return UploadResponse(
            status="success",
            message="Codebase ingested successfully",
            files_processed=result.get("files_processed", 0),
            entities_extracted=result.get("entities_count", len(deps.entities)),
            relationships_found=result.get("relationships_count", len(deps.relationships))
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-zip")
async def upload_zip(file: UploadFile = File(...)):
    """
    Upload and ingest a codebase from a ZIP file.
    """
    if not deps.indexer:
        raise HTTPException(status_code=400, detail="API not configured. Call /api/configure first.")
    
    try:
        import tempfile
        import zipfile
        import os
        
        # Save uploaded file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        # Extract to temp directory
        extract_dir = tempfile.mkdtemp()
        with zipfile.ZipFile(tmp_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Run ingestion in thread pool to handle sync/async properly
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(_executor, _run_ingest, deps.indexer, extract_dir)
        
        # Store entities and relationships globally
        deps.entities = deps.indexer.entities
        deps.relationships = deps.indexer.relationships
        
        # Cleanup
        os.unlink(tmp_path)
        
        return UploadResponse(
            status="success",
            message="Codebase uploaded and ingested successfully",
            files_processed=result.get("files_processed", 0),
            entities_extracted=result.get("entities_count", len(deps.entities)),
            relationships_found=result.get("relationships_count", len(deps.relationships))
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics", response_model=StatisticsResponse)
async def get_statistics():
    """
    Get statistics about the indexed codebase.
    """
    if not deps.entities:
        return StatisticsResponse(
            total_files=0,
            total_entities=0,
            total_relationships=0,
            languages={},
            entity_types={},
            relationship_types={}
        )
    
    # Calculate statistics
    languages = {}
    entity_types = {}
    files = set()
    
    for entity in deps.entities:
        # Count by language
        lang = entity.language if hasattr(entity, 'language') else 'unknown'
        languages[lang] = languages.get(lang, 0) + 1
        
        # Count by type
        etype = entity.type if hasattr(entity, 'type') else 'unknown'
        entity_types[etype] = entity_types.get(etype, 0) + 1
        
        # Track files
        if hasattr(entity, 'file_path'):
            files.add(entity.file_path)
    
    # Count relationship types
    relationship_types = {}
    if deps.relationships:
        for rel in deps.relationships:
            rtype = rel.relationship_type if hasattr(rel, 'relationship_type') else 'unknown'
            relationship_types[rtype] = relationship_types.get(rtype, 0) + 1
    
    return StatisticsResponse(
        total_files=len(files),
        total_entities=len(deps.entities),
        total_relationships=len(deps.relationships) if deps.relationships else 0,
        languages=languages,
        entity_types=entity_types,
        relationship_types=relationship_types
    )


@router.get("/entities")
async def list_entities(
    language: Optional[str] = None,
    entity_type: Optional[str] = None,
    limit: int = 100
):
    """
    List indexed entities with optional filtering.
    """
    if not deps.entities:
        return {"entities": [], "total": 0}
    
    entities = deps.entities
    
    # Apply filters
    if language:
        entities = [e for e in entities if hasattr(e, 'language') and e.language == language]
    if entity_type:
        entities = [e for e in entities if hasattr(e, 'type') and e.type == entity_type]
    
    # Convert to dict for JSON response
    entity_list = []
    for e in entities[:limit]:
        entity_list.append({
            "name": e.name,
            "type": e.type if hasattr(e, 'type') else None,
            "file_path": e.file_path if hasattr(e, 'file_path') else None,
            "language": e.language if hasattr(e, 'language') else None,
            "line_start": e.line_start if hasattr(e, 'line_start') else None,
            "line_end": e.line_end if hasattr(e, 'line_end') else None,
            "parent": e.parent if hasattr(e, 'parent') else None
        })
    
    return {"entities": entity_list, "total": len(deps.entities)}


@router.get("/relationships")
async def list_relationships(
    relationship_type: Optional[str] = None,
    limit: int = 100
):
    """
    List indexed relationships with optional filtering.
    """
    if not deps.relationships:
        return {"relationships": [], "total": 0}
    
    relationships = deps.relationships
    
    if relationship_type:
        relationships = [r for r in relationships if hasattr(r, 'relationship_type') and r.relationship_type == relationship_type]
    
    rel_list = []
    for r in relationships[:limit]:
        rel_list.append({
            "source": r.source,
            "target": r.target,
            "relationship_type": r.relationship_type if hasattr(r, 'relationship_type') else None,
            "file_path": r.file_path if hasattr(r, 'file_path') else None
        })
    
    return {"relationships": rel_list, "total": len(deps.relationships)}


@router.get("/graph-data")
async def get_graph_data():
    """
    Get graph data for visualization (nodes and edges).
    """
    if not deps.entities:
        return {"nodes": [], "edges": []}
    
    # Build nodes from entities with UNIQUE IDs
    nodes = []
    seen_ids = {}  # Track seen IDs and their count
    id_mapping = {}  # Map original name to unique ID
    
    for i, entity in enumerate(deps.entities):
        name = entity.name if hasattr(entity, 'name') else f"node_{i}"
        
        # Generate unique ID by appending index if name already exists
        if name in seen_ids:
            seen_ids[name] += 1
            unique_id = f"{name}_{seen_ids[name]}"
        else:
            seen_ids[name] = 0
            unique_id = name
        
        # Store mapping for edge resolution
        id_mapping[i] = unique_id
        
        nodes.append({
            "id": unique_id,
            "name": name,
            "label": name,
            "type": entity.type if hasattr(entity, 'type') else "unknown",
            "language": entity.language if hasattr(entity, 'language') else None,
            "file_path": entity.file_path if hasattr(entity, 'file_path') else None,
            "line_start": entity.line_start if hasattr(entity, 'line_start') else None,
            "line_end": entity.line_end if hasattr(entity, 'line_end') else None,
            "parent": entity.parent if hasattr(entity, 'parent') else None
        })
    
    # Create a set of valid node IDs for edge validation
    valid_node_ids = {node["id"] for node in nodes}
    # Also map names to their first occurrence ID
    name_to_id = {}
    for node in nodes:
        if node["name"] not in name_to_id:
            name_to_id[node["name"]] = node["id"]
    
    # Build edges from relationships
    edges = []
    seen_edges = set()  # Prevent duplicate edges
    
    if deps.relationships:
        for rel in deps.relationships:
            source = rel.source if hasattr(rel, 'source') else None
            target = rel.target if hasattr(rel, 'target') else None
            
            if not source or not target:
                continue
            
            # Map source/target to valid node IDs
            source_id = name_to_id.get(source, source)
            target_id = name_to_id.get(target, target)
            
            # Skip if either node doesn't exist or it's a self-loop
            if source_id == target_id:
                continue
            
            # Create unique edge key to prevent duplicates
            rel_type = rel.relationship_type if hasattr(rel, 'relationship_type') else "related"
            edge_key = f"{source_id}->{target_id}:{rel_type}"
            
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                edges.append({
                    "source": source_id,
                    "from": source_id,
                    "target": target_id,
                    "to": target_id,
                    "relationship": rel_type,
                    "label": rel_type
                })
    
    return {
        "nodes": nodes,
        "edges": edges
    }


@router.post("/reset")
async def reset_graph():
    """
    Reset/clear the graph data to start fresh.
    
    This will:
    - Clear all in-memory entities and relationships
    - Delete persisted graph data from disk
    - Reset the compliance analyzer
    - Allow ingesting a new codebase
    """
    try:
        cleared_items = {
            "entities_cleared": len(deps.entities) if deps.entities else 0,
            "relationships_cleared": len(deps.relationships) if deps.relationships else 0,
            "storage_cleared": False
        }
        
        # Clear in-memory data
        deps.entities = []
        deps.relationships = []
        
        # Reset compliance analyzer so it will be re-initialized
        deps.compliance_analyzer = None
        deps.eth_specification = None
        
        # Clear the indexer's data
        if deps.indexer:
            deps.indexer.entities = []
            deps.indexer.relationships = []
            deps.indexer.index = None
            deps.indexer.query_engine = None
            deps.indexer._data_loaded = False
            
            # Clear persisted data from disk
            persist_dir = deps.indexer.persist_dir
            if persist_dir and persist_dir.exists():
                # Clear LlamaIndex storage
                llamaindex_dir = persist_dir / "llamaindex_storage"
                if llamaindex_dir.exists():
                    shutil.rmtree(llamaindex_dir)
                    llamaindex_dir.mkdir(parents=True, exist_ok=True)
                
                # Clear pickle files
                for pkl_file in persist_dir.glob("*.pkl"):
                    pkl_file.unlink()
                
                # Clear JSON files (but keep directory structure)
                graph_json = persist_dir / "graph_data.json"
                if graph_json.exists():
                    graph_json.unlink()
                
                cleared_items["storage_cleared"] = True
        
        return {
            "status": "success",
            "message": "Graph data has been reset. You can now ingest a new codebase.",
            "details": cleared_items
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset graph: {str(e)}")
