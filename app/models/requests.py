"""
Request Models

Pydantic models for API request validation.
"""

from typing import Optional, List
from pydantic import BaseModel, Field


class ConfigureRequest(BaseModel):
    """Request to configure the API with LLM settings."""
    api_key: str = Field(..., description="API key for the LLM service")
    api_base: str = Field(..., description="Base URL for the API")
    llm_model: str = Field(default="gpt-4", description="LLM model name")
    embed_model: str = Field(default="text-embedding-ada-002", description="Embedding model name")
    storage_dir: Optional[str] = Field(default="./graph_storage", description="Storage directory path")


class QueryRequest(BaseModel):
    """Request to query the codebase."""
    query: str = Field(..., description="Natural language query about the codebase")
    top_k: int = Field(default=5, description="Number of top results to return")


class AnalyzeRequest(BaseModel):
    """Request to analyze a specific function."""
    function_name: str = Field(..., description="Name of the function to analyze")


class TestGenerationRequest(BaseModel):
    """Request to generate tests for a function."""
    function_name: str = Field(..., description="Name of the function")
    num_tests: int = Field(default=5, description="Number of test cases to generate")


class ComplianceCheckRequest(BaseModel):
    """Request to run compliance check on the codebase."""
    spec_ids: Optional[List[str]] = Field(default=None, description="Specific specification IDs to check against")
    severity_filter: Optional[str] = Field(default=None, description="Filter by severity level")


class CommitAnalysisRequest(BaseModel):
    """Request to analyze a local git commit."""
    repo_path: str = Field(..., description="Path to the local git repository")
    commit_hash: str = Field(default="HEAD", description="Commit hash to analyze")


class RemoteCommitRequest(BaseModel):
    """Request to analyze a remote git commit."""
    repo_url: str = Field(..., description="URL of the remote repository")
    commit_hash: str = Field(..., description="Commit hash to analyze")
    branch: str = Field(default="main", description="Branch name")


class PRAnalysisRequest(BaseModel):
    """Request to analyze a pull request."""
    repo_url: str = Field(..., description="Repository URL (e.g., https://github.com/owner/repo)")
    pr_number: int = Field(..., description="Pull request number")


class CommitRangeRequest(BaseModel):
    """Request to analyze a range of commits."""
    repo_path: str = Field(..., description="Path to the local git repository")
    from_commit: str = Field(..., description="Starting commit hash")
    to_commit: str = Field(default="HEAD", description="Ending commit hash")


class SpecUploadRequest(BaseModel):
    """Request to upload a specification file."""
    name: str = Field(..., description="Name of the specification")
    content: str = Field(..., description="YAML/JSON content of the specification")
    format: str = Field(default="yaml", description="Format: yaml or json")


class CustomRuleRequest(BaseModel):
    """Request to add a custom compliance rule."""
    id: str = Field(..., description="Unique rule ID")
    source: str = Field(default="custom", description="Rule source")
    category: str = Field(default="general", description="Rule category")
    severity: str = Field(default="warning", description="Severity: critical, warning, info")
    description: str = Field(..., description="Rule description")
    patterns: List[str] = Field(default_factory=list, description="Regex patterns to match")
    must_contain: List[str] = Field(default_factory=list, description="Required content")
    must_not_contain: List[str] = Field(default_factory=list, description="Forbidden content")
    recommendation: str = Field(default="", description="Recommendation for fixing")
    languages: List[str] = Field(default_factory=lambda: ["solidity", "go", "javascript"], description="Applicable languages")


class EIPFetchRequest(BaseModel):
    """Request to fetch an EIP."""
    eip_number: int = Field(..., description="EIP number to fetch")
    add_rules: bool = Field(default=True, description="Whether to add rules from the EIP")


class WebhookConfigRequest(BaseModel):
    """Request to configure webhook settings."""
    secret: Optional[str] = Field(default=None, description="Webhook secret for verification")
    events: List[str] = Field(default_factory=lambda: ["push", "pull_request"], description="Events to listen for")
