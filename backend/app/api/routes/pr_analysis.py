"""
PR Analysis Routes

Endpoints for analyzing GitHub Pull Requests with dual-mode support.
Supports both synchronous (quick) and async background (deep) analysis.
"""

import os
import logging
import asyncio
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from enum import Enum

from app.api import dependencies as deps

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pr-analysis", tags=["PR Analysis"])


# =============================================================================
# Background Job Management
# =============================================================================

class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisJob:
    """Represents a background analysis job"""
    def __init__(self, job_id: str, owner: str, repo: str, pr_number: int, mode: str):
        self.job_id = job_id
        self.owner = owner
        self.repo = repo
        self.pr_number = pr_number
        self.mode = mode
        self.status = JobStatus.PENDING
        self.progress = 0
        self.message = "Initializing..."
        self.result = None
        self.error = None
        self.created_at = datetime.utcnow()
        self.started_at = None
        self.completed_at = None


# In-memory job storage (for simplicity - could use Redis in production)
_analysis_jobs: Dict[str, AnalysisJob] = {}


class PRAnalysisRequest(BaseModel):
    """Request model for PR analysis"""
    owner: str
    repo: str
    pr_number: int
    mode: str = "quick"  # quick, deep, or both
    github_token: Optional[str] = None


class DeviationResponse(BaseModel):
    """Single deviation in response"""
    rule_id: Optional[str] = None
    severity: str = "info"
    description: str
    file: Optional[str] = None
    line: Optional[int] = None
    recommendation: Optional[str] = None
    spec_reference: Optional[str] = None


class GraphStatsResponse(BaseModel):
    """Graph statistics from deep analysis"""
    total_entities: int = 0
    total_relationships: int = 0
    total_files: int = 0
    languages: List[str] = []
    entity_types: Dict[str, int] = {}
    relationship_types: Dict[str, int] = {}


class ModeResult(BaseModel):
    """Result from a single analysis mode"""
    mode: str
    success: bool
    duration_seconds: float
    deviations: List[Dict[str, Any]] = []
    files_analyzed: int = 0
    entities_analyzed: int = 0
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    error: Optional[str] = None
    graph_stats: Optional[GraphStatsResponse] = None
    graph_persisted: bool = False


class PRAnalysisResponse(BaseModel):
    """Response model for PR analysis"""
    pr: str
    timestamp: str
    quick: Optional[ModeResult] = None
    deep: Optional[ModeResult] = None
    combined_deviations: List[Dict[str, Any]] = []
    total_critical: int = 0
    total_warning: int = 0
    compliance_passed: bool = True
    commit_sha: Optional[str] = None
    base_sha: Optional[str] = None
    graph_id: Optional[str] = None  # ID for accessing persisted graph


def _init_components():
    """Initialize required components."""
    # Get API credentials from environment
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("API_KEY")
    api_base = os.getenv("OPENAI_API_BASE") or os.getenv("API_BASE")
    
    # Initialize spec indexer first if needed (required for LLM analyzer)
    if deps.spec_indexer is None and api_key and api_base:
        try:
            from app.services.spec_indexer import SpecificationIndexer
            
            # Use ./spec_storage in the backend directory
            storage_dir = "./spec_storage"
            specs_dir = "./execution-specs"
            
            deps.spec_indexer = SpecificationIndexer(
                api_key=api_key,
                api_base=api_base,
                embed_model=os.getenv("EMBED_MODEL", "text-embedding-ada-002"),
                llm_model=os.getenv("LLM_MODEL", "gpt-4"),
                storage_dir=storage_dir,
                specs_dir=specs_dir
            )
            
            if deps.spec_indexer.index is not None:
                logger.info(f"Specification Indexer initialized with {deps.spec_indexer.ingestion_result.total_chunks} chunks")
            else:
                logger.info("Specification Indexer initialized (no existing index found)")
        except ImportError as e:
            logger.warning(f"Qdrant not available for spec indexer: {e}")
        except Exception as e:
            logger.warning(f"Could not initialize spec indexer: {e}")
    
    # Initialize LLM compliance analyzer if needed
    if deps.llm_compliance_analyzer is None and api_key and api_base:
        try:
            from app.services.llm_compliance import LLMComplianceAnalyzer
            # LLMComplianceAnalyzer requires spec_indexer
            if deps.spec_indexer is not None:
                deps.llm_compliance_analyzer = LLMComplianceAnalyzer(
                    spec_indexer=deps.spec_indexer,
                    code_indexer=deps.indexer,
                    api_key=api_key,
                    api_base=api_base,
                    llm_model=os.getenv("LLM_MODEL", "gpt-4")
                )
                logger.info("LLM Compliance Analyzer initialized")
            else:
                logger.warning("Cannot initialize LLM analyzer: spec_indexer not available")
        except Exception as e:
            logger.warning(f"Could not initialize LLM analyzer: {e}")
    
    # Initialize GitHub client if needed
    if deps.github_client is None:
        github_token = os.getenv("GITHUB_TOKEN")
        if github_token:
            try:
                from app.services.github_client import GitHubClient
                deps.github_client = GitHubClient(github_token)
                logger.info("GitHub client initialized")
            except Exception as e:
                logger.warning(f"Could not initialize GitHub client: {e}")


async def _run_analysis_job(job: AnalysisJob, github_token: Optional[str]):
    """Background task to run analysis job"""
    from app.services.enhanced_compliance import run_dual_analysis
    
    try:
        job.status = JobStatus.RUNNING
        job.started_at = datetime.utcnow()
        job.message = "Initializing analysis..."
        job.progress = 5
        
        logger.info(f"Background job {job.job_id}: Starting {job.mode} analysis")
        
        # Define a progress callback
        def progress_callback(stage: str, progress: int):
            job.message = stage
            job.progress = progress
            logger.info(f"Background job {job.job_id}: {stage} ({progress}%)")
        
        # Update progress as we start
        progress_callback("Fetching PR information from GitHub...", 10)
        
        results = await run_dual_analysis(
            owner=job.owner,
            repo=job.repo,
            pr_number=job.pr_number,
            mode=job.mode,
            github_token=github_token,
            llm_analyzer=deps.llm_compliance_analyzer,
            indexer=deps.indexer,
            github_client=deps.github_client,
            spec_indexer=deps.spec_indexer,
            progress_callback=progress_callback
        )
        
        job.result = results
        job.status = JobStatus.COMPLETED
        job.progress = 100
        job.message = "Analysis complete"
        job.completed_at = datetime.utcnow()
        
        logger.info(f"Background job {job.job_id}: Completed successfully")
        
    except Exception as e:
        logger.error(f"Background job {job.job_id} failed: {e}")
        import traceback
        traceback.print_exc()
        job.status = JobStatus.FAILED
        job.error = str(e)
        job.message = f"Analysis failed: {str(e)}"
        job.completed_at = datetime.utcnow()


@router.post("/analyze", response_model=PRAnalysisResponse)
async def analyze_pr(request: PRAnalysisRequest):
    """
    Analyze a GitHub Pull Request for Ethereum protocol compliance.
    
    For quick mode: Returns results directly (synchronous).
    For deep/both mode: Use /analyze-async endpoint for better reliability.
    
    Modes:
    - quick: Fast diff-based analysis (~10-30 seconds)
    - deep: Comprehensive graph-based analysis (~2-5 minutes)
    - both: Run quick first, then deep
    
    Args:
        request: PR analysis request with owner, repo, PR number, and mode
        
    Returns:
        Analysis results with deviations and statistics
    """
    _init_components()
    
    # Use provided token or fall back to environment
    github_token = request.github_token or os.getenv("GITHUB_TOKEN")
    
    if not github_token:
        logger.warning("No GitHub token provided - some operations may fail")
    
    # Validate mode
    mode = request.mode.lower()
    if mode not in ['quick', 'deep', 'both']:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}. Use 'quick', 'deep', or 'both'")
    
    try:
        from app.services.enhanced_compliance import run_dual_analysis
        
        logger.info(f"Analyzing PR {request.owner}/{request.repo}#{request.pr_number} in mode: {mode}")
        
        results = await run_dual_analysis(
            owner=request.owner,
            repo=request.repo,
            pr_number=request.pr_number,
            mode=mode,
            github_token=github_token,
            llm_analyzer=deps.llm_compliance_analyzer,
            indexer=deps.indexer,
            github_client=deps.github_client,
            spec_indexer=deps.spec_indexer
        )
        
        # Generate graph ID for deep analysis
        graph_id = None
        if mode in ['deep', 'both'] and results.get('deep', {}).get('graph_persisted'):
            graph_id = f"{request.owner}_{request.repo}_{request.pr_number}"
        
        # Convert to response model
        response = PRAnalysisResponse(
            pr=results.get('pr', f"{request.owner}/{request.repo}#{request.pr_number}"),
            timestamp=results.get('timestamp', ''),
            combined_deviations=results.get('combined_deviations', []),
            total_critical=results.get('total_critical', 0),
            total_warning=results.get('total_warning', 0),
            compliance_passed=results.get('compliance_passed', True),
            commit_sha=results.get('commit_sha'),
            base_sha=results.get('base_sha'),
            graph_id=graph_id
        )
        
        # Add quick results if available
        if results.get('quick'):
            q = results['quick']
            response.quick = ModeResult(
                mode='quick',
                success=q.get('success', True),
                duration_seconds=q.get('duration_seconds', 0),
                deviations=q.get('deviations', []),
                files_analyzed=q.get('files_analyzed', 0),
                critical_count=q.get('critical_count', 0),
                warning_count=q.get('warning_count', 0),
                info_count=q.get('info_count', 0),
                error=q.get('error')
            )
        
        # Add deep results if available
        if results.get('deep'):
            d = results['deep']
            
            # Build graph stats if available
            graph_stats = None
            if d.get('graph_stats'):
                gs = d['graph_stats']
                graph_stats = GraphStatsResponse(
                    total_entities=gs.get('total_entities', 0),
                    total_relationships=gs.get('total_relationships', 0),
                    total_files=gs.get('total_files', 0),
                    languages=gs.get('languages', []),
                    entity_types=gs.get('entity_types', {}),
                    relationship_types=gs.get('relationship_types', {})
                )
            
            response.deep = ModeResult(
                mode='deep',
                success=d.get('success', False),
                duration_seconds=d.get('duration_seconds', 0),
                deviations=d.get('deviations', []),
                files_analyzed=d.get('files_analyzed', 0),
                entities_analyzed=d.get('entities_analyzed', 0),
                critical_count=d.get('critical_count', 0),
                warning_count=d.get('warning_count', 0),
                info_count=d.get('info_count', 0),
                error=d.get('error'),
                graph_stats=graph_stats,
                graph_persisted=d.get('graph_persisted', False)
            )
        
        return response
        
    except Exception as e:
        logger.error(f"PR analysis failed: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_status():
    """
    Get the status of the PR analysis system.
    
    Returns information about available components.
    """
    _init_components()
    
    return {
        "llm_analyzer_available": deps.llm_compliance_analyzer is not None,
        "github_client_available": deps.github_client is not None,
        "indexer_available": deps.indexer is not None,
        "spec_indexer_available": deps.spec_indexer is not None,
        "github_token_configured": bool(os.getenv("GITHUB_TOKEN")),
        "supported_modes": ["quick", "deep", "both"]
    }


# =============================================================================
# Async Analysis Endpoints (for deep/long-running analysis)
# =============================================================================

class AsyncAnalysisResponse(BaseModel):
    """Response for async analysis start"""
    job_id: str
    status: str
    message: str


class JobStatusResponse(BaseModel):
    """Response for job status check"""
    job_id: str
    status: str
    progress: int
    message: str
    owner: str
    repo: str
    pr_number: int
    mode: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@router.post("/analyze-async", response_model=AsyncAnalysisResponse)
async def analyze_pr_async(request: PRAnalysisRequest, background_tasks: BackgroundTasks):
    """
    Start an asynchronous PR analysis job.
    
    Use this endpoint for deep or both analysis modes to avoid timeout issues.
    Returns immediately with a job_id that can be used to poll for status.
    
    Args:
        request: PR analysis request with owner, repo, PR number, and mode
        
    Returns:
        Job ID and initial status
    """
    _init_components()
    
    # Use provided token or fall back to environment
    github_token = request.github_token or os.getenv("GITHUB_TOKEN")
    
    if not github_token:
        logger.warning("No GitHub token provided - some operations may fail")
    
    # Validate mode
    mode = request.mode.lower()
    if mode not in ['quick', 'deep', 'both']:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}. Use 'quick', 'deep', or 'both'")
    
    # Create job
    job_id = str(uuid.uuid4())
    job = AnalysisJob(
        job_id=job_id,
        owner=request.owner,
        repo=request.repo,
        pr_number=request.pr_number,
        mode=mode
    )
    _analysis_jobs[job_id] = job
    
    logger.info(f"Created analysis job {job_id} for {request.owner}/{request.repo}#{request.pr_number} in mode: {mode}")
    
    # Start background task
    background_tasks.add_task(_run_analysis_job, job, github_token)
    
    return AsyncAnalysisResponse(
        job_id=job_id,
        status=job.status.value,
        message=f"Analysis job started for {request.owner}/{request.repo}#{request.pr_number}"
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Get the status of an analysis job.
    
    Poll this endpoint to check if the analysis is complete.
    
    Args:
        job_id: The job ID returned from /analyze-async
        
    Returns:
        Current job status, progress, and results when complete
    """
    job = _analysis_jobs.get(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        progress=job.progress,
        message=job.message,
        owner=job.owner,
        repo=job.repo,
        pr_number=job.pr_number,
        mode=job.mode,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        result=job.result if job.status == JobStatus.COMPLETED else None,
        error=job.error
    )


@router.get("/jobs")
async def list_jobs():
    """
    List all analysis jobs.
    
    Returns:
        List of all jobs with their current status
    """
    jobs = []
    for job in _analysis_jobs.values():
        jobs.append({
            "job_id": job.job_id,
            "status": job.status.value,
            "progress": job.progress,
            "message": job.message,
            "pr": f"{job.owner}/{job.repo}#{job.pr_number}",
            "mode": job.mode,
            "created_at": job.created_at.isoformat()
        })
    
    # Sort by created_at descending
    jobs.sort(key=lambda x: x["created_at"], reverse=True)
    
    return {"jobs": jobs, "total": len(jobs)}


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str):
    """
    Delete a completed or failed job.
    
    Args:
        job_id: The job ID to delete
    """
    job = _analysis_jobs.get(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail=f"Job not found: {job_id}")
    
    if job.status == JobStatus.RUNNING:
        raise HTTPException(status_code=400, detail="Cannot delete a running job")
    
    del _analysis_jobs[job_id]
    
    return {"message": f"Job {job_id} deleted"}


# =============================================================================
# PR Graph Management Endpoints
# =============================================================================

@router.get("/graphs")
async def list_pr_graphs():
    """
    List all persisted PR graph analyses.
    
    Returns a list of PR analyses with their metadata and statistics.
    """
    from app.services.enhanced_compliance import EnhancedComplianceAnalyzer
    
    graphs = EnhancedComplianceAnalyzer.get_persisted_pr_graphs()
    return {
        "total": len(graphs),
        "graphs": graphs
    }


@router.get("/graphs/{pr_id}")
async def get_pr_graph(pr_id: str):
    """
    Get graph data for a specific PR analysis.
    
    Args:
        pr_id: PR identifier (format: owner_repo_prNumber)
        
    Returns:
        Graph data with nodes and edges
    """
    from app.services.enhanced_compliance import EnhancedComplianceAnalyzer
    
    graph_data = EnhancedComplianceAnalyzer.get_pr_graph_data(pr_id)
    
    if not graph_data:
        raise HTTPException(status_code=404, detail=f"PR graph not found: {pr_id}")
    
    return graph_data


@router.delete("/graphs/{pr_id}")
async def delete_pr_graph(pr_id: str):
    """
    Delete a persisted PR graph analysis.
    
    Args:
        pr_id: PR identifier to delete
    """
    from app.services.enhanced_compliance import EnhancedComplianceAnalyzer
    
    success = EnhancedComplianceAnalyzer.delete_pr_graph(pr_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"PR graph not found: {pr_id}")
    
    return {"message": f"PR graph {pr_id} deleted successfully"}


@router.post("/graphs/{pr_id}/load")
async def load_pr_graph_to_main(pr_id: str):
    """
    Load a PR graph into the main graph storage.
    
    This makes the PR's code graph available in the Statistics tab
    for visualization and querying.
    
    Args:
        pr_id: PR identifier to load
    """
    from app.services.enhanced_compliance import EnhancedComplianceAnalyzer
    
    success = EnhancedComplianceAnalyzer.load_pr_graph_to_main_storage(pr_id)
    
    if not success:
        raise HTTPException(status_code=404, detail=f"PR graph not found: {pr_id}")
    
    return {
        "message": f"PR graph {pr_id} loaded to main storage",
        "note": "Refresh the Statistics tab to see the updated graph"
    }
