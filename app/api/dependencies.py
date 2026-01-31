"""
API Dependencies

Shared state and dependency injection for API routes.
"""

from typing import Optional, List, Dict, Any

# Global state for the application
# These will be initialized when the API is configured

# Core components
indexer = None  # CodeGraphIndexer instance
rag_engine = None  # HybridSearchRAG instance
analysis_engine = None  # AnalysisEngine instance

# Data storage
entities: List[Any] = []  # List of CodeEntity objects
relationships: List[Any] = []  # List of CodeRelationship objects

# Configuration
api_config: Optional[Dict[str, Any]] = None

# Compliance components
eth_specification = None  # EthereumSpecification instance
compliance_analyzer = None  # ComplianceAnalyzer instance
eip_fetcher = None  # EIPFetcher instance

# Git components
git_analyzer = None  # GitAnalyzer instance
webhook_handler = None  # GitWebhookHandler instance

# LLM Compliance components (Qdrant Hybrid Search)
spec_indexer = None  # SpecificationIndexer instance (Qdrant hybrid search)
llm_compliance_analyzer = None  # LLMComplianceAnalyzer instance


def get_indexer():
    """Dependency to get the indexer instance."""
    if indexer is None:
        raise RuntimeError("Indexer not initialized. Call /api/configure first.")
    return indexer


def get_rag_engine():
    """Dependency to get the RAG engine instance."""
    if rag_engine is None:
        raise RuntimeError("RAG engine not initialized. Call /api/configure first.")
    return rag_engine


def get_analysis_engine():
    """Dependency to get the analysis engine instance."""
    if analysis_engine is None:
        raise RuntimeError("Analysis engine not initialized. Call /api/configure first.")
    return analysis_engine


def get_compliance_analyzer():
    """Dependency to get the compliance analyzer instance."""
    global eth_specification, compliance_analyzer
    
    if compliance_analyzer is None:
        from app.services.compliance import EthereumSpecification, ComplianceAnalyzer
        eth_specification = EthereumSpecification()
        compliance_analyzer = ComplianceAnalyzer(eth_specification)
    return compliance_analyzer


def get_git_analyzer():
    """Dependency to get the git analyzer instance."""
    global git_analyzer
    
    if git_analyzer is None:
        from app.services.git_analyzer import GitAnalyzer
        git_analyzer = GitAnalyzer(get_compliance_analyzer())
    return git_analyzer


def reset_state():
    """Reset all global state (useful for testing)."""
    global indexer, rag_engine, analysis_engine, entities, relationships
    global api_config, eth_specification, compliance_analyzer, eip_fetcher
    global git_analyzer, webhook_handler, spec_indexer, llm_compliance_analyzer
    
    indexer = None
    rag_engine = None
    analysis_engine = None
    entities = []
    relationships = []
    api_config = None
    eth_specification = None
    compliance_analyzer = None
    eip_fetcher = None
    git_analyzer = None
    webhook_handler = None
    spec_indexer = None
    llm_compliance_analyzer = None
