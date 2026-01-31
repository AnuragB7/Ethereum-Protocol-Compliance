"""
Configuration Routes

Endpoints for API configuration and settings.
"""

from fastapi import APIRouter, HTTPException
from app.models.requests import ConfigureRequest
from app.models.responses import ConfigureResponse
from app.api import dependencies as deps

router = APIRouter(prefix="/api", tags=["Configuration"])


@router.post("/configure", response_model=ConfigureResponse)
async def configure_api(config: ConfigureRequest):
    """
    Configure the API with LLM settings.
    
    This must be called before using any analysis features.
    """
    try:
        from app.core.indexer import CodeGraphIndexer
        from app.core.rag_engine import HybridSearchRAG
        from app.services.analysis import FunctionalAnalyzer
        
        # Initialize the indexer
        deps.indexer = CodeGraphIndexer(
            api_key=config.api_key,
            api_base=config.api_base,
            llm_model=config.llm_model,
            embed_model=config.embed_model,
            persist_dir=config.storage_dir or "./graph_storage"
        )
        
        # Initialize RAG engine
        deps.rag_engine = HybridSearchRAG(
            api_key=config.api_key,
            api_base=config.api_base,
            llm_model=config.llm_model,
            embed_model=config.embed_model
        )
        
        # Initialize analysis engine
        deps.analysis_engine = FunctionalAnalyzer(deps.indexer)
        
        # Store configuration
        deps.api_config = {
            "api_key": config.api_key,
            "api_base": config.api_base,
            "llm_model": config.llm_model,
            "embed_model": config.embed_model,
            "storage_dir": config.storage_dir
        }
        
        return ConfigureResponse(
            status="success",
            message="API configured successfully"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config/status")
async def get_config_status():
    """Get current configuration status."""
    return {
        "configured": deps.indexer is not None,
        "has_api_key": deps.api_config.get("api_key") is not None if deps.api_config else False,
        "llm_model": deps.api_config.get("llm_model") if deps.api_config else None,
        "embed_model": deps.api_config.get("embed_model") if deps.api_config else None
    }
