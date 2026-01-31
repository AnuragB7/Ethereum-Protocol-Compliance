"""
Compliance Routes

Endpoints for Ethereum specification compliance checking.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional
from app.models.requests import ComplianceCheckRequest
from app.models.responses import ComplianceSummaryResponse, ComplianceResponse
from app.api import dependencies as deps

router = APIRouter(prefix="/api/compliance", tags=["Compliance"])


def _init_compliance_components():
    """Initialize compliance components if not already done."""
    if deps.compliance_analyzer is None:
        from app.services.compliance import EthereumSpecification, ComplianceAnalyzer
        from app.services.eip_fetcher import EIPFetcher
        
        deps.eth_specification = EthereumSpecification()
        deps.eip_fetcher = EIPFetcher()
        deps.compliance_analyzer = ComplianceAnalyzer(
            deps.eth_specification,
            indexer=deps.indexer  # Pass the indexer for codebase analysis
        )


@router.post("/check")
async def run_compliance_check(request: ComplianceCheckRequest = None):
    """
    Run compliance check on the indexed codebase.
    """
    _init_compliance_components()
    
    if not deps.entities:
        raise HTTPException(status_code=400, detail="No codebase indexed. Upload a codebase first.")
    
    try:
        # Run compliance analysis
        report = deps.compliance_analyzer.analyze_codebase(deps.entities)
        
        return {
            "status": "completed",
            "summary": {
                "compliance_score": report.compliance_score,
                "total_entities": report.total_entities,
                "total_rules_checked": report.total_rules_checked,
                "total_deviations": len(report.deviations),
                "critical_issues": report.critical_count,
                "warnings": report.warning_count,
                "compliance_passed": report.compliance_score >= 80.0
            },
            "deviations_count": len(report.deviations)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report")
async def get_compliance_report():
    """
    Get the full compliance report.
    """
    _init_compliance_components()
    
    if not deps.entities:
        return {"status": "no_codebase", "message": "No codebase indexed"}
    
    try:
        report = deps.compliance_analyzer.analyze_codebase(deps.entities)
        
        return {
            "status": "completed",
            "summary": {
                "compliance_score": report.compliance_score,
                "total_entities": report.total_entities,
                "total_rules_checked": report.total_rules_checked,
                "total_deviations": len(report.deviations),
                "critical_issues": report.critical_count,
                "warnings": report.warning_count,
                "compliance_passed": report.compliance_score >= 80.0
            },
            "deviations": [
                {
                    "rule_id": d.rule.id,
                    "rule_source": d.rule.source,
                    "severity": d.rule.severity,
                    "category": d.rule.category,
                    "description": d.rule.description,
                    "file_path": d.file_path,
                    "line_number": d.line_number,
                    "code_snippet": d.code_snippet,
                    "entity_name": d.entity_name,
                    "entity_type": d.entity_type,
                    "explanation": d.explanation,
                    "recommendation": d.recommendation,
                    "confidence": d.confidence
                }
                for d in report.deviations
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/deviations")
async def get_deviations(
    severity: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 100
):
    """
    Get compliance deviations with optional filtering.
    """
    _init_compliance_components()
    
    if not deps.entities:
        return {"deviations": [], "total": 0}
    
    try:
        report = deps.compliance_analyzer.analyze_codebase(deps.entities)
        
        deviations = report.deviations
        
        # Apply filters
        if severity:
            deviations = [d for d in deviations if d.rule.severity == severity]
        if category:
            deviations = [d for d in deviations if d.rule.category == category]
        
        return {
            "deviations": [
                {
                    "rule_id": d.rule.id,
                    "rule_source": d.rule.source,
                    "severity": d.rule.severity,
                    "category": d.rule.category,
                    "description": d.rule.description,
                    "file_path": d.file_path,
                    "line_number": d.line_number,
                    "explanation": d.explanation,
                    "recommendation": d.recommendation
                }
                for d in deviations[:limit]
            ],
            "total": len(deviations)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_compliance_summary():
    """
    Get compliance summary for the indexed codebase.
    """
    _init_compliance_components()
    
    if not deps.entities:
        return {
            "status": "no_codebase",
            "compliance_score": 0,
            "total_entities": 0,
            "total_rules_checked": 0,
            "total_deviations": 0,
            "critical_issues": 0,
            "warnings": 0,
            "compliance_passed": False,
            "most_common_issues": []
        }
    
    try:
        report = deps.compliance_analyzer.analyze_codebase(deps.entities)
        
        # Calculate most common issues
        issue_counts = {}
        for d in report.deviations:
            key = d.rule.id
            if key not in issue_counts:
                issue_counts[key] = {
                    "rule_id": d.rule.id,
                    "description": d.rule.description,
                    "severity": d.rule.severity,
                    "count": 0
                }
            issue_counts[key]["count"] += 1
        
        most_common = sorted(issue_counts.values(), key=lambda x: x["count"], reverse=True)[:5]
        
        return {
            "status": "completed",
            "compliance_score": report.compliance_score,
            "total_entities": report.total_entities,
            "total_rules_checked": report.total_rules_checked,
            "total_deviations": len(report.deviations),
            "critical_issues": report.critical_count,
            "warnings": report.warning_count,
            "compliance_passed": report.compliance_score >= 80.0,
            "most_common_issues": most_common
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
