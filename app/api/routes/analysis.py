"""
Analysis Routes

Endpoints for code analysis, queries, and test generation.
"""

from fastapi import APIRouter, HTTPException
from app.models.requests import QueryRequest, AnalyzeRequest, TestGenerationRequest
from app.models.responses import QueryResponse, AnalysisResponse, TestCaseResponse
from app.api import dependencies as deps

router = APIRouter(prefix="/api", tags=["Analysis"])


@router.post("/query", response_model=QueryResponse)
async def query_codebase(request: QueryRequest):
    """
    Query the codebase using natural language.
    
    Uses hybrid retrieval (semantic + keyword) to find relevant code
    and generates a comprehensive answer using the LLM.
    """
    if not deps.indexer:
        raise HTTPException(status_code=400, detail="API not configured. Call /api/configure first.")
    
    try:
        result = deps.indexer.query(request.query)
        
        # The indexer.query() returns a string, not a dict
        # Handle both cases for compatibility
        if isinstance(result, dict):
            answer = result.get("answer", "")
            sources = result.get("sources", [])
        else:
            # Result is a string (the answer itself)
            answer = str(result)
            sources = []
        
        return QueryResponse(
            query=request.query,
            answer=answer,
            sources=sources
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze")
async def analyze_function(request: AnalyzeRequest):
    """
    Analyze a specific function in detail.
    
    Provides functional analysis including purpose, parameters,
    return values, and usage patterns.
    """
    if not deps.analysis_engine:
        raise HTTPException(status_code=400, detail="API not configured. Call /api/configure first.")
    
    try:
        # Find the entity
        entity = None
        for e in deps.entities or []:
            if e.name == request.function_name:
                entity = e
                break
        
        if not entity:
            raise HTTPException(status_code=404, detail=f"Function '{request.function_name}' not found")
        
        # Perform analysis
        analysis = deps.analysis_engine.analyze_function(request.function_name)
        
        return {
            "function_name": request.function_name,
            "entity": {
                "name": entity.name,
                "type": entity.type,
                "file_path": entity.file_path,
                "line_start": entity.line_start,
                "line_end": entity.line_end,
                "language": entity.language,
                "parameters": entity.parameters if hasattr(entity, 'parameters') else [],
                "return_type": entity.return_type if hasattr(entity, 'return_type') else None,
                "docstring": entity.docstring if hasattr(entity, 'docstring') else None,
                "parent": entity.parent if hasattr(entity, 'parent') else None
            },
            "analysis": analysis
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate-tests")
async def generate_tests(request: TestGenerationRequest):
    """
    Generate test cases for a function.
    """
    if not deps.analysis_engine:
        raise HTTPException(status_code=400, detail="API not configured. Call /api/configure first.")
    
    try:
        tests = deps.analysis_engine.generate_test_cases(
            request.function_name, 
            num_tests=request.num_tests
        )
        
        return TestCaseResponse(
            function_name=request.function_name,
            test_cases=tests,
            num_tests=request.num_tests
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/generate-selenium/{function_name}")
async def generate_selenium_tests(function_name: str):
    """
    Generate Selenium test code for a function.
    """
    if not deps.analysis_engine:
        raise HTTPException(status_code=400, detail="API not configured. Call /api/configure first.")
    
    try:
        selenium_code = deps.analysis_engine.generate_selenium_tests(function_name)
        
        return {
            "function_name": function_name,
            "selenium_code": selenium_code
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/generate-unit-tests/{function_name}")
async def generate_unit_tests(function_name: str):
    """
    Generate unit test code for a function.
    """
    if not deps.analysis_engine:
        raise HTTPException(status_code=400, detail="API not configured. Call /api/configure first.")
    
    try:
        unit_test_code = deps.analysis_engine.generate_unit_tests(function_name)
        
        return {
            "function_name": function_name,
            "unit_test_code": unit_test_code
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/call-chain/{function_name}")
async def get_call_chain(function_name: str, depth: int = 3):
    """
    Get the call chain for a function.
    
    Shows what functions this function calls and what calls it.
    """
    if not deps.indexer:
        raise HTTPException(status_code=400, detail="API not configured. Call /api/configure first.")
    
    try:
        chains = deps.indexer.get_call_chains(function_name, max_depth=depth)
        
        return {
            "function_name": function_name,
            "chains": chains,
            "chain_count": len(chains)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_entities(q: str, limit: int = 20):
    """
    Search for entities by name.
    """
    if not deps.entities:
        return {"results": [], "total": 0}
    
    query_lower = q.lower()
    results = []
    
    for e in deps.entities:
        if query_lower in e.name.lower():
            results.append({
                "name": e.name,
                "type": e.type if hasattr(e, 'type') else None,
                "file_path": e.file_path if hasattr(e, 'file_path') else None,
                "language": e.language if hasattr(e, 'language') else None
            })
            
            if len(results) >= limit:
                break
    
    return {"results": results, "total": len(results)}
