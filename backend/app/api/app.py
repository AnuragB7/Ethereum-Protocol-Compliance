"""
FastAPI Application Factory

Creates and configures the FastAPI application.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.api.routes import (
    health_router,
    config_router,
    codebase_router,
    analysis_router,
    compliance_router,
    specs_router,
    git_router,
    llm_compliance_router,
    pr_analysis_router
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║          Code Analysis API Server                          ║
    ║                                                            ║
    ║  Starting FastAPI server on http://localhost:8000         ║
    ║  Documentation: http://localhost:8000/docs                ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    # Try to auto-configure from environment
    _try_auto_configure()
    
    yield
    
    # Shutdown
    print("Shutting down server...")


def _try_auto_configure():
    """Try to auto-configure from environment variables."""
    import os
    from app.api import dependencies as deps
    
    # Check multiple possible env var names
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY")
    api_base = os.getenv("OPENAI_API_BASE") or os.getenv("API_BASE")
    
    if api_key and api_base:
        try:
            from app.core.indexer import CodeGraphIndexer
            from app.services.analysis import FunctionalAnalyzer
            
            print("🔧 Auto-configuring from environment variables...")
            print(f"🔗 Connecting to API at: {api_base}")
            
            llm_model = os.getenv("LLM_MODEL", "gpt-4")
            embed_model = os.getenv("EMBED_MODEL", "text-embedding-ada-002")
            storage_dir = os.getenv("STORAGE_DIR", "./graph_storage")
            
            # Initialize indexer
            deps.indexer = CodeGraphIndexer(
                api_key=api_key,
                api_base=api_base,
                llm_model=llm_model,
                embed_model=embed_model,
                persist_dir=storage_dir
            )
            
            # Try to load existing data
            deps.indexer._load_persisted_data()
            if deps.indexer.entities:
                deps.entities = deps.indexer.entities
                deps.relationships = deps.indexer.relationships
                print(f"♻️  Loaded existing graph data from: {storage_dir}")
                print(f"   Entities: {len(deps.entities)}, Relationships: {len(deps.relationships)}")
            
            # Initialize analysis engine
            deps.analysis_engine = FunctionalAnalyzer(deps.indexer)
            
            # Store config
            deps.api_config = {
                "api_key": api_key,
                "api_base": api_base,
                "llm_model": llm_model,
                "embed_model": embed_model,
                "storage_dir": storage_dir
            }
            
            print("✅ Auto-configured successfully!")
            print(f"   API Base: {api_base}")
            print(f"   LLM Model: {llm_model}")
            print(f"   Embed Model: {embed_model}")
            print(f"   Storage: {storage_dir}")
            
        except Exception as e:
            print(f"⚠️  Auto-configuration failed: {e}")
            print("   You can manually configure via /api/configure endpoint")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Multi-language codebase analysis powered by Property Graph RAG with Ethereum compliance checking",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins + ["*"],  # Allow all for development
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include routers
    app.include_router(health_router)
    app.include_router(config_router)
    app.include_router(codebase_router)
    app.include_router(analysis_router)
    app.include_router(compliance_router)
    app.include_router(specs_router)
    app.include_router(git_router)
    app.include_router(llm_compliance_router)
    app.include_router(pr_analysis_router)
    
    return app


# Create the application instance
app = create_app()
