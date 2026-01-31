"""
Git Routes

Endpoints for git repository analysis and webhooks.
"""

import os
import logging
from fastapi import APIRouter, HTTPException, Request, Header
from typing import Optional
from app.models.requests import CommitAnalysisRequest, RemoteCommitRequest, PRAnalysisRequest, CommitRangeRequest
from app.api import dependencies as deps

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Git Analysis"])


def _init_git_components():
    """Initialize git components if not already done."""
    if deps.git_analyzer is None:
        from app.services.git_analyzer import GitAnalyzer, GitWebhookHandler
        from app.services.compliance import EthereumSpecification, ComplianceAnalyzer
        
        # Initialize compliance components if needed
        if deps.eth_specification is None:
            deps.eth_specification = EthereumSpecification()
        if deps.compliance_analyzer is None:
            deps.compliance_analyzer = ComplianceAnalyzer(deps.eth_specification)
        
        deps.git_analyzer = GitAnalyzer(deps.compliance_analyzer)
        deps.webhook_handler = GitWebhookHandler()
    
    # Initialize GitHub client if token is available
    if deps.github_client is None:
        github_token = os.getenv("GITHUB_TOKEN")
        if github_token:
            try:
                from app.services.github_client import GitHubClient
                deps.github_client = GitHubClient(github_token)
                logger.info("GitHub client initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize GitHub client: {e}")


@router.post("/compliance/analyze-commit")
async def analyze_commit(request: CommitAnalysisRequest):
    """
    Analyze a commit in a local git repository for compliance.
    """
    _init_git_components()
    
    try:
        result = deps.git_analyzer.analyze_local_commit(
            request.repo_path,
            request.commit_hash
        )
        
        return {
            "status": "completed",
            "commit": result.get("commit"),
            "deviations": result.get("deviations", []),
            "summary": result.get("summary")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compliance/analyze-remote-commit")
async def analyze_remote_commit(request: RemoteCommitRequest):
    """
    Analyze a commit from a remote git repository.
    """
    _init_git_components()
    
    try:
        result = deps.git_analyzer.analyze_remote_commit(
            request.repo_url,
            request.commit_hash,
            request.branch
        )
        
        return {
            "status": "completed",
            "commit": result.get("commit"),
            "deviations": result.get("deviations", []),
            "summary": result.get("summary")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compliance/analyze-pr")
async def analyze_pull_request(request: PRAnalysisRequest):
    """
    Analyze a pull request for compliance.
    """
    _init_git_components()
    
    try:
        # Parse owner/repo from URL
        import re
        match = re.match(r'https?://github\.com/([^/]+)/([^/]+)', request.repo_url)
        if not match:
            raise HTTPException(status_code=400, detail="Invalid GitHub URL format")
        
        owner = match.group(1)
        repo = match.group(2).rstrip('.git')
        
        result = deps.git_analyzer.analyze_pr_from_github(
            owner, repo, request.pr_number
        )
        
        return {
            "status": "completed",
            "pull_request": result.get("pull_request"),
            "deviations": result.get("deviations", []),
            "summary": result.get("summary")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compliance/analyze-commit-range")
async def analyze_commit_range(request: CommitRangeRequest):
    """
    Analyze a range of commits for compliance.
    """
    _init_git_components()
    
    try:
        result = deps.git_analyzer.analyze_commit_range(
            request.repo_path,
            request.from_commit,
            request.to_commit
        )
        
        return {
            "status": "completed",
            "commits_analyzed": result.get("commits_count", 0),
            "deviations": result.get("deviations", []),
            "summary": result.get("summary")
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None),
    x_github_event: Optional[str] = Header(None)
):
    """
    Handle GitHub webhook events.
    
    Supports push and pull_request events for automatic compliance checking.
    Posts compliance results as PR comments when GITHUB_TOKEN is configured.
    """
    _init_git_components()
    
    try:
        # Get raw body for signature verification
        body = await request.body()
        payload = await request.json()
        
        # Verify signature if secret is configured
        webhook_secret = os.getenv("GITHUB_WEBHOOK_SECRET")
        if webhook_secret:
            if not deps.webhook_handler.verify_github_signature(body, x_hub_signature_256, webhook_secret):
                raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Process the webhook
        event_type = x_github_event or "unknown"
        logger.info(f"Received GitHub webhook: {event_type}")
        
        if event_type == "push":
            result = await deps.webhook_handler.handle_github_push(
                payload,
                git_analyzer=deps.git_analyzer,
                llm_analyzer=deps.llm_compliance_analyzer,
                github_client=deps.github_client
            )
        elif event_type == "pull_request":
            result = await deps.webhook_handler.handle_github_pull_request(
                payload,
                git_analyzer=deps.git_analyzer,
                llm_analyzer=deps.llm_compliance_analyzer,
                github_client=deps.github_client,
                post_comment=True,
                indexer=deps.indexer,
                run_deep=False  # Controlled by PR labels
            )
        else:
            return {"status": "ignored", "event": event_type}
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook/gitlab")
async def gitlab_webhook(
    request: Request,
    x_gitlab_token: Optional[str] = Header(None),
    x_gitlab_event: Optional[str] = Header(None)
):
    """
    Handle GitLab webhook events.
    
    Supports push and merge_request events for automatic compliance checking.
    """
    _init_git_components()
    
    try:
        payload = await request.json()
        
        # Verify token if configured
        gitlab_token = os.getenv("GITLAB_WEBHOOK_TOKEN")
        if gitlab_token:
            if x_gitlab_token != gitlab_token:
                raise HTTPException(status_code=401, detail="Invalid token")
        
        # Process the webhook
        event_type = x_gitlab_event or payload.get("object_kind", "unknown")
        logger.info(f"Received GitLab webhook: {event_type}")
        
        if event_type == "push":
            result = await deps.webhook_handler.handle_gitlab_push(
                payload,
                git_analyzer=deps.git_analyzer,
                llm_analyzer=deps.llm_compliance_analyzer
            )
        elif event_type == "merge_request":
            result = await deps.webhook_handler.handle_gitlab_merge_request(
                payload,
                git_analyzer=deps.git_analyzer,
                llm_analyzer=deps.llm_compliance_analyzer
            )
        else:
            return {"status": "ignored", "event": event_type}
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"GitLab webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
