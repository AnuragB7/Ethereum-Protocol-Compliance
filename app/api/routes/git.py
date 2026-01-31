"""
Git Routes

Endpoints for git repository analysis and webhooks.
"""

from fastapi import APIRouter, HTTPException, Request, Header
from typing import Optional
from app.models.requests import CommitAnalysisRequest, RemoteCommitRequest, PRAnalysisRequest, CommitRangeRequest
from app.api import dependencies as deps

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
    """
    _init_git_components()
    
    try:
        payload = await request.json()
        
        # Verify signature if secret is configured
        if deps.api_config and deps.api_config.get("github_webhook_secret"):
            body = await request.body()
            if not deps.webhook_handler.verify_github_signature(
                body, x_hub_signature_256,
                deps.api_config["github_webhook_secret"]
            ):
                raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Process the webhook
        event_type = x_github_event or "unknown"
        
        if event_type == "push":
            result = await deps.webhook_handler.handle_github_push(payload, deps.git_analyzer)
        elif event_type == "pull_request":
            result = await deps.webhook_handler.handle_github_pr(payload, deps.git_analyzer)
        else:
            return {"status": "ignored", "event": event_type}
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
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
        if deps.api_config and deps.api_config.get("gitlab_webhook_token"):
            if x_gitlab_token != deps.api_config["gitlab_webhook_token"]:
                raise HTTPException(status_code=401, detail="Invalid token")
        
        # Process the webhook
        event_type = x_gitlab_event or payload.get("object_kind", "unknown")
        
        if event_type == "push":
            result = await deps.webhook_handler.handle_gitlab_push(payload, deps.git_analyzer)
        elif event_type == "merge_request":
            result = await deps.webhook_handler.handle_gitlab_mr(payload, deps.git_analyzer)
        else:
            return {"status": "ignored", "event": event_type}
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
