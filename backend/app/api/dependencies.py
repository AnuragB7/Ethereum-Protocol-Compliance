"""
API Dependencies

Shared state and dependency injection for API routes.
"""

import os
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

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

# GitHub/GitLab integration
github_client = None  # GitHubClient instance for posting PR comments

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


def get_github_client():
    """Dependency to get the GitHub client instance."""
    global github_client
    
    if github_client is None:
        github_token = os.getenv("GITHUB_TOKEN")
        if github_token:
            try:
                from app.services.github_client import GitHubClient
                github_client = GitHubClient(github_token)
                logger.info("GitHub client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize GitHub client: {e}")
    return github_client


def init_github_client():
    """Initialize GitHub client from environment variables."""
    global github_client
    
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token and github_client is None:
        try:
            from app.services.github_client import GitHubClient
            github_client = GitHubClient(github_token)
            logger.info("GitHub client initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize GitHub client: {e}")
            return False
    return github_client is not None


def reset_state():
    """Reset all global state (useful for testing)."""
    global indexer, rag_engine, analysis_engine, entities, relationships
    global api_config, eth_specification, compliance_analyzer, eip_fetcher
    global git_analyzer, webhook_handler, spec_indexer, llm_compliance_analyzer
    global github_client
    
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
    github_client = None
