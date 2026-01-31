"""
LLM Compliance Routes

Endpoints for:
- Cloning and ingesting Ethereum execution specifications
- Running LLM-powered compliance checks
- Querying specifications
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from app.api import dependencies as deps

router = APIRouter(prefix="/api/llm-compliance", tags=["LLM Compliance"])


# Request/Response Models
class CloneSpecsRequest(BaseModel):
    """Request to clone execution-specs from GitHub"""
    branch: str = Field(default="forks/amsterdam", description="Git branch to clone (default: forks/amsterdam)")
    force: bool = Field(default=False, description="Force re-clone if exists")


class IngestSpecsRequest(BaseModel):
    """Request to ingest specifications"""
    forks: Optional[List[str]] = Field(
        default=None, 
        description="List of forks to ingest (e.g., ['prague', 'cancun']). None = recent forks"
    )
    include_docs: bool = Field(default=True, description="Include documentation files")


class SpecQueryRequest(BaseModel):
    """Request to query specifications"""
    query: str = Field(..., description="Query text")
    top_k: int = Field(default=5, description="Number of results")
    alpha: float = Field(default=0.5, description="Hybrid search balance (0=keyword, 1=semantic)")


class RunComplianceRequest(BaseModel):
    """Request to run LLM compliance check"""
    max_entities: int = Field(default=20, description="Maximum entities to analyze")
    spec_top_k: int = Field(default=5, description="Specs to retrieve per entity")


class AnalyzeCodeRequest(BaseModel):
    """Request to analyze a code snippet"""
    code: str = Field(..., description="Code to analyze")
    language: str = Field(default="go", description="Programming language")
    entity_name: str = Field(default="snippet", description="Name for the code")


# Global state for spec indexer and LLM compliance analyzer
def _get_spec_indexer():
    """Get or create the spec indexer."""
    if deps.spec_indexer is None:
        if not deps.api_config:
            raise HTTPException(
                status_code=400, 
                detail="API not configured. Call /api/configure first."
            )
        
        from app.services.spec_indexer import SpecificationIndexer
        
        deps.spec_indexer = SpecificationIndexer(
            api_key=deps.api_config["api_key"],
            api_base=deps.api_config["api_base"],
            embed_model=deps.api_config.get("embed_model", "text-embedding-ada-002"),
            llm_model=deps.api_config.get("llm_model", "gpt-4"),
        )
    
    return deps.spec_indexer


def _get_llm_compliance_analyzer():
    """Get or create the LLM compliance analyzer."""
    if deps.llm_compliance_analyzer is None:
        spec_indexer = _get_spec_indexer()
        
        from app.services.llm_compliance import LLMComplianceAnalyzer
        
        deps.llm_compliance_analyzer = LLMComplianceAnalyzer(
            spec_indexer=spec_indexer,
            code_indexer=deps.indexer,
            api_key=deps.api_config["api_key"],
            api_base=deps.api_config["api_base"],
            llm_model=deps.api_config.get("llm_model", "gpt-4"),
        )
    
    return deps.llm_compliance_analyzer


# Endpoints
@router.post("/clone-specs")
async def clone_specs(request: CloneSpecsRequest):
    """
    Clone ethereum/execution-specs from GitHub.
    
    This downloads the official Ethereum execution specifications
    which will be used for compliance checking.
    """
    try:
        spec_indexer = _get_spec_indexer()
        
        success = spec_indexer.clone_specs(
            branch=request.branch,
            force=request.force
        )
        
        if success:
            return {
                "status": "success",
                "message": f"Specs cloned successfully (branch: {request.branch})",
                "specs_dir": str(spec_indexer.specs_dir)
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="Failed to clone specifications repository"
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest-specs")
async def ingest_specs(request: IngestSpecsRequest):
    """
    Parse and ingest specifications into Qdrant hybrid search index.
    
    This will:
    1. Parse Python specification files from execution-specs
    2. Extract functions, classes, docstrings
    3. Identify EIP references
    4. Create embeddings (dense + sparse vectors)
    5. Store in Qdrant for hybrid search
    """
    try:
        spec_indexer = _get_spec_indexer()
        
        # Check if specs are cloned
        if not spec_indexer.specs_dir.exists():
            raise HTTPException(
                status_code=400,
                detail="Specs not cloned. Call /api/llm-compliance/clone-specs first."
            )
        
        result = spec_indexer.ingest_specs(
            forks=request.forks,
            include_docs=request.include_docs
        )
        
        return {
            "status": "success",
            "message": "Specifications ingested successfully",
            "stats": {
                "total_files": result.total_files,
                "total_chunks": result.total_chunks,
                "forks_ingested": result.forks_ingested,
                "eips_found": result.eips_found[:20],  # Limit for response
                "total_eips": len(result.eips_found)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/spec-stats")
async def get_spec_stats():
    """
    Get statistics about indexed specifications.
    """
    try:
        spec_indexer = _get_spec_indexer()
        stats = spec_indexer.get_stats()
        
        return {
            "status": "success",
            "stats": stats
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query-specs")
async def query_specs(request: SpecQueryRequest):
    """
    Query specifications using hybrid search.
    
    Uses both semantic (dense vectors) and keyword (sparse vectors)
    search to find relevant specification chunks.
    """
    try:
        spec_indexer = _get_spec_indexer()
        
        if not spec_indexer.index:
            raise HTTPException(
                status_code=400,
                detail="Specs not indexed. Call /api/llm-compliance/ingest-specs first."
            )
        
        results = spec_indexer.query(
            query_text=request.query,
            top_k=request.top_k,
            alpha=request.alpha
        )
        
        # Format results
        formatted_results = []
        for node in results:
            metadata = node.node.metadata if hasattr(node.node, 'metadata') else {}
            formatted_results.append({
                "content": node.node.text[:500] if hasattr(node.node, 'text') else "",
                "score": node.score,
                "fork": metadata.get("fork", ""),
                "file_path": metadata.get("file_path", ""),
                "chunk_type": metadata.get("chunk_type", ""),
                "name": metadata.get("name", ""),
                "eip_references": metadata.get("eip_references", "")
            })
        
        return {
            "status": "success",
            "query": request.query,
            "results": formatted_results,
            "total": len(formatted_results)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search-eip/{eip_number}")
async def search_by_eip(eip_number: str, top_k: int = 10):
    """
    Search specifications by EIP number.
    
    Uses keyword-heavy search for exact EIP matching.
    """
    try:
        spec_indexer = _get_spec_indexer()
        
        if not spec_indexer.index:
            raise HTTPException(
                status_code=400,
                detail="Specs not indexed. Call /api/llm-compliance/ingest-specs first."
            )
        
        results = spec_indexer.search_by_eip(eip_number, top_k=top_k)
        
        formatted_results = []
        for node in results:
            metadata = node.node.metadata if hasattr(node.node, 'metadata') else {}
            formatted_results.append({
                "content": node.node.text[:500] if hasattr(node.node, 'text') else "",
                "score": node.score,
                "fork": metadata.get("fork", ""),
                "file_path": metadata.get("file_path", ""),
                "name": metadata.get("name", ""),
            })
        
        return {
            "status": "success",
            "eip": eip_number,
            "results": formatted_results,
            "total": len(formatted_results)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run-compliance")
async def run_llm_compliance(request: RunComplianceRequest):
    """
    Run LLM-powered compliance check on indexed codebase.
    
    This will:
    1. Get code entities from the Property Graph
    2. For each entity, query specs using hybrid search
    3. Use LLM to analyze code vs specs
    4. Return structured compliance report
    
    Note: This can be expensive for large codebases. Use max_entities to limit.
    """
    try:
        if not deps.entities:
            raise HTTPException(
                status_code=400,
                detail="No codebase indexed. Upload a codebase first."
            )
        
        llm_analyzer = _get_llm_compliance_analyzer()
        
        if not llm_analyzer.spec_indexer.index:
            raise HTTPException(
                status_code=400,
                detail="Specs not indexed. Call /api/llm-compliance/ingest-specs first."
            )
        
        report = llm_analyzer.analyze_codebase(
            entities=deps.entities,
            max_entities=request.max_entities,
            spec_top_k=request.spec_top_k
        )
        
        return {
            "status": "success",
            "report": report.to_dict()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-code")
async def analyze_code_snippet(request: AnalyzeCodeRequest):
    """
    Analyze a code snippet for compliance.
    
    Useful for analyzing individual functions or PR changes.
    """
    try:
        llm_analyzer = _get_llm_compliance_analyzer()
        
        if not llm_analyzer.spec_indexer.index:
            raise HTTPException(
                status_code=400,
                detail="Specs not indexed. Call /api/llm-compliance/ingest-specs first."
            )
        
        deviations = llm_analyzer.analyze_single_code(
            code=request.code,
            language=request.language,
            entity_name=request.entity_name
        )
        
        return {
            "status": "success",
            "entity_name": request.entity_name,
            "language": request.language,
            "deviations": [d.to_dict() for d in deviations],
            "total_deviations": len(deviations)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset-specs")
async def reset_specs():
    """
    Reset/clear all specification data.
    
    This will delete the Qdrant collection and metadata.
    """
    try:
        spec_indexer = _get_spec_indexer()
        spec_indexer.reset()
        
        # Reset the LLM analyzer too
        deps.llm_compliance_analyzer = None
        
        return {
            "status": "success",
            "message": "Specification index reset successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/available-forks")
async def get_available_forks():
    """
    Get list of available forks in the cloned execution-specs.
    """
    try:
        spec_indexer = _get_spec_indexer()
        
        if not spec_indexer.specs_dir.exists():
            return {
                "status": "warning",
                "message": "Specs not cloned yet",
                "forks": []
            }
        
        from app.services.spec_parser import SpecificationParser
        parser = SpecificationParser(str(spec_indexer.specs_dir))
        forks = parser.get_available_forks()
        
        return {
            "status": "success",
            "forks": forks,
            "recent_forks": parser.RECENT_FORKS
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
