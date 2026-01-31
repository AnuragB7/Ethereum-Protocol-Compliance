"""
Specification Routes

Endpoints for managing Ethereum specifications and EIPs.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional
from app.models.requests import SpecUploadRequest, CustomRuleRequest, EIPFetchRequest
from app.api import dependencies as deps

router = APIRouter(prefix="/api/specs", tags=["Specifications"])


def _init_spec_components():
    """Initialize specification components if not already done."""
    if deps.eth_specification is None:
        from app.services.compliance import EthereumSpecification
        from app.services.eip_fetcher import EIPFetcher
        
        deps.eth_specification = EthereumSpecification()
        deps.eip_fetcher = EIPFetcher()


@router.get("/list")
async def list_specifications():
    """
    List all loaded specifications and their rule counts.
    """
    _init_spec_components()
    
    rules = deps.eth_specification.rules
    
    # Group by source
    rules_by_source = {}
    rules_by_severity = {"critical": 0, "warning": 0, "info": 0}
    rules_by_category = {}
    
    for rule in rules:
        # By source
        source = rule.source
        rules_by_source[source] = rules_by_source.get(source, 0) + 1
        
        # By severity
        severity = rule.severity
        if severity in rules_by_severity:
            rules_by_severity[severity] += 1
        
        # By category
        category = rule.category
        rules_by_category[category] = rules_by_category.get(category, 0) + 1
    
    return {
        "loaded_specs": list(rules_by_source.keys()),
        "total_rules": len(rules),
        "rules_by_source": rules_by_source,
        "rules_by_severity": rules_by_severity,
        "rules_by_category": rules_by_category
    }


@router.post("/upload")
async def upload_specification(request: SpecUploadRequest):
    """
    Upload a custom specification file (YAML/JSON).
    """
    _init_spec_components()
    
    try:
        if request.format.lower() == "yaml":
            import yaml
            spec_data = yaml.safe_load(request.content)
        else:
            import json
            spec_data = json.loads(request.content)
        
        # Add rules from spec
        rules_added = deps.eth_specification.load_from_dict(spec_data, source=request.name)
        
        return {
            "status": "success",
            "message": f"Specification '{request.name}' uploaded successfully",
            "rules_added": rules_added
        }
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse specification: {str(e)}")


@router.post("/add-rule")
async def add_custom_rule(request: CustomRuleRequest):
    """
    Add a custom compliance rule.
    """
    _init_spec_components()
    
    try:
        from app.services.compliance import ComplianceRule
        
        rule = ComplianceRule(
            id=request.id,
            source=request.source,
            category=request.category,
            severity=request.severity,
            description=request.description,
            patterns=request.patterns,
            must_contain=request.must_contain,
            must_not_contain=request.must_not_contain,
            recommendation=request.recommendation,
            languages=request.languages
        )
        
        deps.eth_specification.add_rule(rule)
        
        return {
            "status": "success",
            "message": f"Rule '{request.id}' added successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/eip/{eip_number}")
async def fetch_eip(eip_number: int, add_rules: bool = True):
    """
    Fetch an EIP and optionally add its rules.
    """
    _init_spec_components()
    
    try:
        eip = deps.eip_fetcher.fetch_eip(eip_number, force_refresh=False)
        
        rules_added = 0
        if add_rules:
            rules = deps.eip_fetcher.parse_eip_to_rules(eip)
            for rule in rules:
                deps.eth_specification.add_rule(rule)
            rules_added = len(rules)
        
        return {
            "number": eip.number,
            "title": eip.title,
            "status": eip.status,
            "type": eip.type,
            "category": eip.category,
            "abstract": eip.abstract[:500] if eip.abstract else "",
            "rules_added": rules_added
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch EIP-{eip_number}: {str(e)}")


@router.get("/eip/search")
async def search_eips(query: str):
    """
    Search for EIPs by keyword.
    """
    _init_spec_components()
    
    try:
        results = deps.eip_fetcher.search_eips(query)
        return {"results": results}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rules")
async def get_rules(
    source: Optional[str] = None,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 100
):
    """
    Get all compliance rules with optional filtering.
    """
    _init_spec_components()
    
    rules = deps.eth_specification.rules
    
    # Apply filters
    if source:
        rules = [r for r in rules if r.source == source]
    if severity:
        rules = [r for r in rules if r.severity == severity]
    if category:
        rules = [r for r in rules if r.category == category]
    
    return {
        "rules": [
            {
                "id": r.id,
                "source": r.source,
                "category": r.category,
                "severity": r.severity,
                "description": r.description,
                "patterns": r.patterns,
                "must_contain": r.must_contain,
                "must_not_contain": r.must_not_contain,
                "recommendation": r.recommendation,
                "languages": r.languages
            }
            for r in rules[:limit]
        ],
        "total": len(rules)
    }


@router.delete("/rules/{rule_id}")
async def delete_rule(rule_id: str):
    """
    Delete a compliance rule.
    """
    _init_spec_components()
    
    try:
        deps.eth_specification.remove_rule(rule_id)
        return {"status": "success", "message": f"Rule '{rule_id}' deleted"}
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Rule not found: {rule_id}")
