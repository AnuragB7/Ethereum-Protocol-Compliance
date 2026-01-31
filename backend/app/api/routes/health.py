"""
Health Check Routes

Endpoints for service health and status monitoring.
"""

from fastapi import APIRouter, Depends
from app.models.responses import HealthResponse
from app.api.dependencies import get_indexer

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.
    
    Returns the current status of the service and whether the indexer is ready.
    """
    from app.api.dependencies import indexer, entities, relationships
    
    return HealthResponse(
        status="ok",
        indexer_ready=indexer is not None,
        entities_count=len(entities) if entities else 0,
        relationships_count=len(relationships) if relationships else 0
    )


@router.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Code Analysis Platform API",
        "version": "1.0.0",
        "description": "Multi-language codebase analysis powered by Property Graph RAG",
        "docs": "/docs",
        "health": "/health"
    }
