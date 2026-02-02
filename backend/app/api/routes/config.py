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
    
    Supports multiple providers:
    - 'openai': OpenAI or OpenAI-compatible APIs (requires api_base)
    - 'anthropic': Anthropic Claude (api_base not required)
    
    Note: Embeddings always use OpenAI API. For Anthropic users, you can provide
    separate embed_api_key and embed_api_base for embedding operations.
    
    This must be called before using any analysis features.
    """
    try:
        # Handle nest_asyncio patching for uvloop compatibility
        try:
            import nest_asyncio
            nest_asyncio.apply()
        except (ValueError, RuntimeError):
            # Already patched or can't patch uvloop - that's OK
            pass
        
        from app.core.indexer import CodeGraphIndexer
        from app.core.rag_engine import HybridSearchRAG
        from app.services.analysis import FunctionalAnalyzer
        
        provider = config.provider.lower() if config.provider else "openai"
        
        # Validate provider
        if provider not in ["openai", "anthropic"]:
            raise HTTPException(
                status_code=400, 
                detail=f"Unsupported provider: {provider}. Use 'openai' or 'anthropic'"
            )
        
        # For OpenAI, api_base is required
        if provider == "openai" and not config.api_base:
            raise HTTPException(
                status_code=400,
                detail="api_base is required for OpenAI provider"
            )
        
        # Initialize the indexer with provider support
        deps.indexer = CodeGraphIndexer(
            api_key=config.api_key,
            api_base=config.api_base,
            llm_model=config.llm_model,
            embed_model=config.embed_model,
            persist_dir=config.storage_dir or "./graph_storage",
            provider=provider,
            embed_api_key=config.embed_api_key,
            embed_api_base=config.embed_api_base
        )
        
        # Initialize RAG engine (uses same provider settings via global Settings)
        deps.rag_engine = HybridSearchRAG(
            api_key=config.api_key,
            api_base=config.api_base or "https://api.openai.com/v1",
            llm_model=config.llm_model,
            embed_model=config.embed_model
        )
        
        # Initialize analysis engine
        deps.analysis_engine = FunctionalAnalyzer(deps.indexer)
        
        # Store configuration
        deps.api_config = {
            "provider": provider,
            "api_key": config.api_key,
            "api_base": config.api_base,
            "llm_model": config.llm_model,
            "embed_model": config.embed_model,
            "embed_api_key": config.embed_api_key,
            "embed_api_base": config.embed_api_base,
            "storage_dir": config.storage_dir
        }
        
        return ConfigureResponse(
            status="success",
            message=f"API configured successfully with {provider} provider"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config/status")
async def get_config_status():
    """Get current configuration status."""
    return {
        "configured": deps.indexer is not None,
        "has_api_key": deps.api_config.get("api_key") is not None if deps.api_config else False,
        "provider": deps.api_config.get("provider", "openai") if deps.api_config else None,
        "llm_model": deps.api_config.get("llm_model") if deps.api_config else None,
        "embed_model": deps.api_config.get("embed_model") if deps.api_config else None
    }


@router.get("/config/providers")
async def get_available_providers():
    """Get list of available LLM providers and their default models."""
    from app.core.indexer import ANTHROPIC_AVAILABLE, DEFAULT_MODELS
    
    providers = {
        "openai": {
            "available": True,
            "name": "OpenAI / OpenAI-compatible",
            "requires_api_base": True,
            "default_model": DEFAULT_MODELS.get("openai", "gpt-4"),
            "example_models": ["gpt-4", "gpt-4-turbo", "gpt-4o", "gpt-3.5-turbo"],
            "description": "Use OpenAI API or any OpenAI-compatible API (Azure, local LLMs, etc.)"
        },
        "anthropic": {
            "available": ANTHROPIC_AVAILABLE,
            "name": "Anthropic Claude",
            "requires_api_base": False,
            "default_model": DEFAULT_MODELS.get("anthropic", "claude-sonnet-4-20250514"),
            "example_models": ["claude-sonnet-4-20250514", "claude-3-5-sonnet-20241022", "claude-3-opus-20240229", "claude-3-haiku-20240307"],
            "description": "Use Anthropic's Claude models directly"
        }
    }
    
    return {
        "providers": providers,
        "note": "Embeddings always use OpenAI API regardless of LLM provider"
    }
