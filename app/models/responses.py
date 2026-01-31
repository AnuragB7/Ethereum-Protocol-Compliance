"""
Response Models

Pydantic models for API responses.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Service status")
    indexer_ready: bool = Field(..., description="Whether the indexer is ready")
    entities_count: int = Field(default=0, description="Number of indexed entities")
    relationships_count: int = Field(default=0, description="Number of indexed relationships")


class ConfigureResponse(BaseModel):
    """Configuration response."""
    status: str = Field(..., description="Configuration status")
    message: str = Field(..., description="Status message")


class QueryResponse(BaseModel):
    """Query response."""
    query: str = Field(..., description="Original query")
    answer: str = Field(..., description="Generated answer")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="Source documents")


class EntityResponse(BaseModel):
    """Code entity response."""
    name: str
    type: str
    file_path: str
    line_start: int
    line_end: int
    language: str
    parameters: List[str] = Field(default_factory=list)
    return_type: Optional[str] = None
    docstring: Optional[str] = None
    parent: Optional[str] = None


class AnalysisResponse(BaseModel):
    """Function analysis response."""
    function_name: str = Field(..., description="Analyzed function name")
    entity: EntityResponse = Field(..., description="Entity details")
    analysis: str = Field(..., description="Analysis result")
    call_chain: List[str] = Field(default_factory=list, description="Call chain")


class TestCaseResponse(BaseModel):
    """Test generation response."""
    function_name: str = Field(..., description="Function name")
    test_cases: str = Field(..., description="Generated test cases")
    num_tests: int = Field(..., description="Number of test cases")


class DeviationResponse(BaseModel):
    """Compliance deviation response."""
    rule_id: str
    rule_source: str
    severity: str
    category: str
    description: str
    file_path: str
    line_number: int
    code_snippet: Optional[str] = None
    entity_name: Optional[str] = None
    entity_type: Optional[str] = None
    explanation: str
    recommendation: str
    confidence: float


class ComplianceSummaryResponse(BaseModel):
    """Compliance summary response."""
    status: str
    compliance_score: float
    total_entities: int
    total_rules_checked: int
    total_deviations: int
    critical_issues: int
    warnings: int
    compliance_passed: bool
    most_common_issues: List[Dict[str, Any]] = Field(default_factory=list)


class ComplianceResponse(BaseModel):
    """Full compliance report response."""
    summary: ComplianceSummaryResponse
    deviations: List[DeviationResponse]
    timestamp: str


class StatisticsResponse(BaseModel):
    """Codebase statistics response."""
    total_files: int = Field(..., description="Total number of files")
    total_entities: int = Field(..., description="Total number of code entities")
    total_relationships: int = Field(..., description="Total number of relationships")
    languages: Dict[str, int] = Field(default_factory=dict, description="Count by language")
    entity_types: Dict[str, int] = Field(default_factory=dict, description="Count by entity type")
    relationship_types: Dict[str, int] = Field(default_factory=dict, description="Count by relationship type")


class UploadResponse(BaseModel):
    """Codebase upload response."""
    status: str = Field(..., description="Upload status")
    message: str = Field(..., description="Status message")
    files_processed: int = Field(default=0, description="Number of files processed")
    entities_extracted: int = Field(default=0, description="Number of entities extracted")
    relationships_found: int = Field(default=0, description="Number of relationships found")


class SpecificationSummaryResponse(BaseModel):
    """Specification summary response."""
    loaded_specs: List[str]
    total_rules: int
    rules_by_source: Dict[str, int]
    rules_by_severity: Dict[str, int]
    rules_by_category: Dict[str, int]


class RuleResponse(BaseModel):
    """Compliance rule response."""
    id: str
    source: str
    category: str
    severity: str
    description: str
    patterns: List[str]
    must_contain: List[str]
    must_not_contain: List[str]
    recommendation: str
    languages: List[str]


class GitCommitResponse(BaseModel):
    """Git commit response."""
    hash: str
    author: str
    author_email: str
    message: str
    timestamp: str
    files_changed: List[str]
    additions: int
    deletions: int


class GitAnalysisResponse(BaseModel):
    """Git analysis response."""
    status: str
    commit: Optional[GitCommitResponse] = None
    deviations: List[DeviationResponse] = Field(default_factory=list)
    summary: Optional[ComplianceSummaryResponse] = None
    error: Optional[str] = None


class EIPResponse(BaseModel):
    """EIP document response."""
    number: int
    title: str
    status: str
    type: str
    category: Optional[str] = None
    abstract: str
    rules_added: int = 0
