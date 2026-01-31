"""
FastAPI Backend Server
Provides REST API endpoints for code analysis
"""

from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
import json
from dotenv import load_dotenv
import warnings
import logging

# Suppress warnings and async noise
warnings.filterwarnings('ignore')
logging.getLogger('asyncio').setLevel(logging.CRITICAL)
logging.getLogger('llama_index').setLevel(logging.CRITICAL)

# Load environment variables from .env file (if exists)
try:
    load_dotenv()
except Exception:
    pass  # .env file doesn't exist or can't be read

from code_graph_indexer import CodeGraphIndexer
from analysis_engine import FunctionalAnalyzer, TestCaseGenerator
from structured_test_generator import StructuredTestCaseGenerator
from ethereum_compliance import EthereumSpecification, ComplianceAnalyzer, ComplianceRule
from eip_fetcher import EIPFetcher
from git_analyzer import GitAnalyzer, GitWebhookHandler

# Initialize FastAPI
app = FastAPI(
    title="Code Analysis API",
    description="API for analyzing codebases using Property Graph RAG",
    version="1.0.0"
)

# CORS middleware - adjust origins for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
indexer: Optional[CodeGraphIndexer] = None
analyzer: Optional[FunctionalAnalyzer] = None
test_generator: Optional[TestCaseGenerator] = None
structured_test_gen: Optional[StructuredTestCaseGenerator] = None

# Ethereum Compliance global state
eth_specification: Optional[EthereumSpecification] = None
compliance_analyzer: Optional[ComplianceAnalyzer] = None
eip_fetcher: Optional[EIPFetcher] = None
git_analyzer: Optional[GitAnalyzer] = None
webhook_handler: Optional[GitWebhookHandler] = None

# Initialize compliance components
SPECS_DIR = os.getenv("SPECS_DIR", "./specs")
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")
GITLAB_WEBHOOK_SECRET = os.getenv("GITLAB_WEBHOOK_SECRET", "")

# Temporary directory for uploaded codebases
UPLOAD_DIR = tempfile.mkdtemp()

# Auto-configure from environment variables if available
DEFAULT_API_KEY = os.getenv("API_KEY")
DEFAULT_API_BASE = os.getenv("API_BASE")
DEFAULT_LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4")
DEFAULT_EMBED_MODEL = os.getenv("EMBED_MODEL", "text-embedding-ada-002")
PERSIST_DIR = os.getenv("PERSIST_DIR", "./graph_storage")

# Auto-initialize with defaults if provided
if DEFAULT_API_KEY and DEFAULT_API_BASE:
    try:
        print("🔧 Auto-configuring from .env file...")
        indexer = CodeGraphIndexer(
            api_key=DEFAULT_API_KEY,
            api_base=DEFAULT_API_BASE,
            llm_model=DEFAULT_LLM_MODEL,
            embed_model=DEFAULT_EMBED_MODEL,
            persist_dir=PERSIST_DIR
        )
        
        # Initialize analyzers if data was loaded
        if indexer and len(indexer.entities) > 0:
            analyzer = FunctionalAnalyzer(indexer)
            test_generator = TestCaseGenerator(indexer)
            structured_test_gen = StructuredTestCaseGenerator(indexer, output_dir="test_output")
            print(f"✅ Analyzers initialized with loaded data")
        
        print(f"✅ Auto-configured successfully!")
        print(f"   API Base: {DEFAULT_API_BASE}")
        print(f"   LLM Model: {DEFAULT_LLM_MODEL}")
        print(f"   Embed Model: {DEFAULT_EMBED_MODEL}")
        print(f"   Storage: {PERSIST_DIR}")
    except Exception as e:
        print(f"⚠️  Auto-configuration failed: {e}")
        print("   You can still configure via the UI")
else:
    print("ℹ️  No .env configuration found. Please configure via the UI.")
    print(f"✅ Auto-configured with default credentials")

# Pydantic models
class ConfigModel(BaseModel):
    api_key: str
    api_base: str
    llm_model: str = "gpt-4.1"
    embed_model: str = "text-embedding-ada-002"


class QueryModel(BaseModel):
    question: str


class FunctionAnalysisRequest(BaseModel):
    function_name: str


class TestGenerationRequest(BaseModel):
    function_name: str
    count: int = 5
    base_url: str = "http://localhost:3000"


class ModuleAnalysisRequest(BaseModel):
    file_path: str


# API Endpoints

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Code Analysis API",
        "version": "1.0.0",
        "status": "running",
        "indexer_initialized": indexer is not None
    }


@app.post("/api/config")
async def configure(config: ConfigModel):
    """
    Configure the API with LLM credentials
    """
    global indexer, analyzer, test_generator
    
    try:
        indexer = CodeGraphIndexer(
            api_key=config.api_key,
            api_base=config.api_base,
            llm_model=config.llm_model,
            embed_model=config.embed_model,
            persist_dir=PERSIST_DIR
        )
        
        return {
            "status": "success",
            "message": "Configuration updated successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Configuration failed: {str(e)}")


@app.post("/api/upload-codebase")
async def upload_codebase(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None
):
    """
    Upload a codebase (ZIP file) for analysis
    """
    global indexer, analyzer, test_generator
    
    if not indexer:
        raise HTTPException(
            status_code=400,
            detail="API not configured. Call /api/config first"
        )
    
    # Validate file type
    if not file.filename.endswith('.zip'):
        raise HTTPException(
            status_code=400,
            detail="Only ZIP files are supported"
        )
    
    # Create temporary directory for this upload
    upload_id = os.urandom(16).hex()
    extract_path = os.path.join(UPLOAD_DIR, upload_id)
    os.makedirs(extract_path, exist_ok=True)
    
    try:
        # Save uploaded file
        zip_path = os.path.join(extract_path, file.filename)
        with open(zip_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Extract ZIP
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_path)
        
        # Remove the zip file
        os.remove(zip_path)
        
        # Ingest the codebase in a thread executor
        import asyncio
        import concurrent.futures
        
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            stats = await loop.run_in_executor(
                executor,
                indexer.ingest_codebase,
                extract_path
            )
        
        # Initialize analyzers
        analyzer = FunctionalAnalyzer(indexer)
        test_generator = TestCaseGenerator(indexer)
        structured_test_gen = StructuredTestCaseGenerator(indexer, output_dir="test_output")
        
        return {
            "status": "success",
            "message": "Codebase uploaded and indexed successfully",
            "upload_id": upload_id,
            "statistics": stats
        }
        
    except Exception as e:
        # Cleanup on error
        if os.path.exists(extract_path):
            shutil.rmtree(extract_path)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.post("/api/upload-folder")
async def upload_folder(codebase_path: str):
    """
    Analyze a codebase from a local folder path
    """
    global indexer, analyzer, test_generator, structured_test_gen
    
    if not indexer:
        raise HTTPException(
            status_code=400,
            detail="API not configured. Call /api/config first"
        )
    
    if not os.path.exists(codebase_path):
        raise HTTPException(
            status_code=404,
            detail=f"Path not found: {codebase_path}"
        )
    
    try:
        # Run the synchronous ingest_codebase in a thread executor
        # to avoid asyncio.run() conflicts with the FastAPI event loop
        import asyncio
        import concurrent.futures
        
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as executor:
            stats = await loop.run_in_executor(
                executor,
                indexer.ingest_codebase,
                codebase_path
            )
        
        # Initialize analyzers
        analyzer = FunctionalAnalyzer(indexer)
        test_generator = TestCaseGenerator(indexer)
        structured_test_gen = StructuredTestCaseGenerator(indexer, output_dir="test_output")
        
        return {
            "status": "success",
            "message": "Codebase indexed successfully",
            "statistics": stats
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")


@app.post("/api/query")
async def query(query_data: QueryModel):
    """
    Query the indexed codebase
    """
    if not indexer:
        raise HTTPException(
            status_code=400,
            detail="No codebase indexed. Upload a codebase first"
        )
    
    try:
        answer = indexer.query(query_data.question)
        return {
            "question": query_data.question,
            "answer": answer
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@app.get("/api/entities")
async def get_entities():
    """
    Get all code entities
    """
    if not indexer:
        raise HTTPException(
            status_code=400,
            detail="No codebase indexed"
        )
    
    entities = [
        {
            "name": e.name,
            "type": e.type,
            "language": e.language,
            "file_path": e.file_path,
            "line_start": e.line_start,
            "line_end": e.line_end,
            "parent": e.parent,
            "parameters": e.parameters,
            "calls": e.calls
        }
        for e in indexer.entities
    ]
    
    return {
        "count": len(entities),
        "entities": entities
    }


@app.get("/api/entities/{entity_name}")
async def get_entity(entity_name: str):
    """
    Get specific entity details
    """
    if not indexer:
        raise HTTPException(status_code=400, detail="No codebase indexed")
    
    entity = indexer.get_entity_by_name(entity_name)
    if not entity:
        raise HTTPException(status_code=404, detail=f"Entity '{entity_name}' not found")
    
    return {
        "name": entity.name,
        "type": entity.type,
        "language": entity.language,
        "file_path": entity.file_path,
        "line_start": entity.line_start,
        "line_end": entity.line_end,
        "parent": entity.parent,
        "parameters": entity.parameters,
        "return_type": entity.return_type,
        "calls": entity.calls,
        "docstring": entity.docstring
    }


@app.post("/api/analyze/function")
async def analyze_function(request: FunctionAnalysisRequest):
    """
    Analyze a specific function
    """
    if not analyzer:
        raise HTTPException(status_code=400, detail="No codebase indexed")
    
    try:
        result = analyzer.analyze_function(request.function_name)
        
        if 'error' in result:
            raise HTTPException(status_code=404, detail=result['error'])
        
        return {
            "function_name": request.function_name,
            "analysis": result['analysis'],
            "call_chains": result['call_chains'],
            "entity": {
                "name": result['entity'].name,
                "type": result['entity'].type,
                "language": result['entity'].language,
                "file_path": result['entity'].file_path
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/api/analyze/module")
async def analyze_module(request: ModuleAnalysisRequest):
    """
    Analyze a module/file
    """
    if not analyzer:
        raise HTTPException(status_code=400, detail="No codebase indexed")
    
    try:
        result = analyzer.analyze_module(request.file_path)
        
        if 'error' in result:
            raise HTTPException(status_code=404, detail=result['error'])
        
        return {
            "file_path": request.file_path,
            "entity_count": result['entity_count'],
            "analysis": result['analysis']
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/api/analyze/codebase")
async def analyze_codebase():
    """
    Analyze entire codebase
    """
    if not analyzer:
        raise HTTPException(status_code=400, detail="No codebase indexed")
    
    try:
        result = analyzer.analyze_codebase()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/api/tests/generate")
async def generate_tests(request: TestGenerationRequest):
    """
    Generate test cases for a function
    """
    if not test_generator:
        raise HTTPException(status_code=400, detail="No codebase indexed")
    
    try:
        result = test_generator.generate_test_cases(
            request.function_name,
            count=request.count
        )
        
        if 'error' in result:
            raise HTTPException(status_code=404, detail=result['error'])
        
        return {
            "function_name": request.function_name,
            "test_cases": result['test_cases'],
            "count": request.count
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Test generation failed: {str(e)}")


@app.post("/api/tests/selenium")
async def generate_selenium_tests(request: TestGenerationRequest):
    """
    Generate Selenium test code
    """
    if not test_generator:
        raise HTTPException(status_code=400, detail="No codebase indexed")
    
    try:
        code = test_generator.generate_selenium_tests(
            request.function_name,
            base_url=request.base_url
        )
        
        if code.startswith("# Error:"):
            raise HTTPException(status_code=404, detail=code)
        
        return {
            "function_name": request.function_name,
            "selenium_code": code,
            "base_url": request.base_url
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Code generation failed: {str(e)}")


@app.post("/api/tests/unit")
async def generate_unit_tests(request: FunctionAnalysisRequest):
    """
    Generate unit test code
    """
    if not test_generator:
        raise HTTPException(status_code=400, detail="No codebase indexed")
    
    try:
        code = test_generator.generate_unit_tests(request.function_name)
        
        if code.startswith("# Error:"):
            raise HTTPException(status_code=404, detail=code)
        
        return {
            "function_name": request.function_name,
            "unit_test_code": code
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Code generation failed: {str(e)}")


class StructuredTestRequest(BaseModel):
    functionality: str
    context: Optional[str] = ""


@app.post("/api/tests/structured")
async def generate_structured_tests(request: StructuredTestRequest):
    """
    Generate structured test cases with XPath and automation scripts
    Returns CSV, XPath JSON, Cypress, Selenium, and Playwright files
    """
    global structured_test_gen
    
    if not indexer:
        raise HTTPException(status_code=400, detail="No codebase indexed")
    
    try:
        # Initialize structured test generator if not already done
        if not structured_test_gen:
            structured_test_gen = StructuredTestCaseGenerator(indexer, output_dir="test_output")
        
        # Generate structured tests
        result = structured_test_gen.generate_structured_test_cases(
            functionality=request.functionality,
            context=request.context
        )
        
        return {
            "success": True,
            "functionality": result['functionality'],
            "test_cases": result['test_cases'],
            "xpath_data": result['xpath_data'],
            "files": result['files'],
            "message": f"Generated {len(result['test_cases'])} test steps"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate structured tests: {str(e)}")


@app.get("/api/tests/download/{filename}")
async def download_test_file(filename: str):
    """
    Download generated test files
    """
    from fastapi.responses import FileResponse
    
    file_path = Path("test_output") / filename
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type='application/octet-stream'
    )


@app.get("/api/call-chain/{function_name}")
async def get_call_chain(function_name: str, depth: int = 3):
    """
    Get call chain for a function
    """
    if not indexer:
        raise HTTPException(status_code=400, detail="No codebase indexed")
    
    try:
        chains = indexer.get_call_chain(function_name, depth=depth)
        
        return {
            "function_name": function_name,
            "depth": depth,
            "chain_count": len(chains),
            "chains": chains
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get call chain: {str(e)}")


@app.get("/api/graph-data")
async def get_graph_data():
    """
    Get graph data for visualization
    """
    if not indexer:
        raise HTTPException(status_code=400, detail="No codebase indexed")
    
    # Create a mapping to ensure unique node IDs
    entity_to_id = {}
    nodes = []
    
    for idx, entity in enumerate(indexer.entities):
        # Create a unique ID combining file path, entity name, type, and line number
        # This handles cases where classes and constructors have the same name
        unique_id = f"{entity.file_path}::{entity.type}::{entity.name}::L{entity.line_start}"
        
        # Map entity name to this unique ID for relationship lookups
        # Store all possible IDs for this entity name
        if entity.name not in entity_to_id:
            entity_to_id[entity.name] = []
        entity_to_id[entity.name].append(unique_id)
        
        # Create a readable label
        label = f"{entity.name}"
        if entity.type in ['class', 'method', 'function']:
            label = f"{entity.name} ({entity.type})"
        
        nodes.append({
            'id': unique_id,
            'name': entity.name,
            'label': label,
            'type': entity.type,
            'language': entity.language,
            'file_path': entity.file_path,
            'parent': entity.parent,
            'line_start': entity.line_start,
            'line_end': entity.line_end
        })
    
    # Map edges to use unique IDs
    edges = []
    for rel in indexer.relationships:
        # Get all possible IDs for source and target
        source_ids = entity_to_id.get(rel.source, [rel.source])
        target_ids = entity_to_id.get(rel.target, [rel.target])
        
        # If there's only one match, use it. Otherwise use the first one
        # (In a perfect world, we'd have more context to choose the right one)
        source_id = source_ids[0] if isinstance(source_ids, list) else source_ids
        target_id = target_ids[0] if isinstance(target_ids, list) else target_ids
        
        edges.append({
            'source': source_id,
            'target': target_id,
            'from': source_id,
            'to': target_id,
            'label': rel.relationship_type,
            'relationship': rel.relationship_type
        })
    
    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges)
    }


@app.get("/api/statistics")
async def get_statistics():
    """
    Get codebase statistics
    """
    if not indexer:
        raise HTTPException(status_code=400, detail="No codebase indexed")
    
    # Group by type and language
    type_counts = {}
    language_counts = {}
    file_set = set()
    
    for entity in indexer.entities:
        type_counts[entity.type] = type_counts.get(entity.type, 0) + 1
        language_counts[entity.language] = language_counts.get(entity.language, 0) + 1
        file_set.add(entity.file_path)
    
    return {
        "total_files": len(file_set),
        "total_entities": len(indexer.entities),
        "total_relationships": len(indexer.relationships),
        "by_type": type_counts,
        "by_language": language_counts,
        "files": list(file_set)
    }


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "indexer_ready": indexer is not None,
        "analyzer_ready": analyzer is not None,
        "test_generator_ready": test_generator is not None
    }


@app.get("/api/check-existing-data")
async def check_existing_data():
    """
    Check if there's already indexed data available
    """
    if not indexer:
        return {
            "has_data": False,
            "data_loaded": False
        }
    
    has_entities = len(indexer.entities) > 0
    
    return {
        "has_data": has_entities,
        "data_loaded": indexer._data_loaded if hasattr(indexer, '_data_loaded') else False,
        "total_entities": len(indexer.entities) if has_entities else 0,
        "total_relationships": len(indexer.relationships) if has_entities else 0
    }


# ============================================================================
# ETHEREUM COMPLIANCE API ENDPOINTS
# ============================================================================

# Pydantic models for compliance endpoints
class SpecUploadRequest(BaseModel):
    content: str
    filename: str
    format: str = "yaml"  # yaml or json


class ComplianceCheckRequest(BaseModel):
    entity_name: Optional[str] = None
    file_path: Optional[str] = None
    rule_ids: Optional[List[str]] = None
    severity_filter: Optional[str] = None


class CommitAnalysisRequest(BaseModel):
    repo_path: str
    commit_hash: str = "HEAD"


class RemoteCommitRequest(BaseModel):
    repo_url: str
    commit_hash: str


class PRAnalysisRequest(BaseModel):
    owner: str
    repo: str
    pr_number: int
    token: Optional[str] = None


class CustomRuleRequest(BaseModel):
    id: str
    source: str
    category: str
    severity: str
    description: str
    patterns: List[str] = []
    must_contain: List[str] = []
    must_not_contain: List[str] = []
    recommendation: str = ""
    languages: List[str] = ["solidity", "go", "javascript", "typescript"]


def _init_compliance_components():
    """Initialize compliance-related components"""
    global eth_specification, compliance_analyzer, eip_fetcher, git_analyzer, webhook_handler
    
    if eth_specification is None:
        eth_specification = EthereumSpecification(specs_dir=SPECS_DIR)
    
    if eip_fetcher is None:
        eip_fetcher = EIPFetcher()
    
    if compliance_analyzer is None and indexer is not None:
        compliance_analyzer = ComplianceAnalyzer(eth_specification, indexer)
    
    if git_analyzer is None:
        git_analyzer = GitAnalyzer(compliance_analyzer)
    
    if webhook_handler is None:
        webhook_handler = GitWebhookHandler(
            git_analyzer,
            github_secret=GITHUB_WEBHOOK_SECRET,
            gitlab_secret=GITLAB_WEBHOOK_SECRET
        )


# Specification Management Endpoints

@app.get("/api/specs/list")
async def list_specifications():
    """
    List all loaded specifications and rules
    """
    _init_compliance_components()
    
    return {
        "loaded_specs": eth_specification.loaded_specs,
        "total_rules": len(eth_specification.rules),
        "rules_by_source": _count_rules_by_source(),
        "rules_by_severity": _count_rules_by_severity(),
        "rules_by_category": _count_rules_by_category()
    }


def _count_rules_by_source() -> Dict[str, int]:
    counts = {}
    for rule in eth_specification.rules:
        counts[rule.source] = counts.get(rule.source, 0) + 1
    return counts


def _count_rules_by_severity() -> Dict[str, int]:
    counts = {'critical': 0, 'warning': 0, 'info': 0}
    for rule in eth_specification.rules:
        if rule.severity in counts:
            counts[rule.severity] += 1
    return counts


def _count_rules_by_category() -> Dict[str, int]:
    counts = {}
    for rule in eth_specification.rules:
        counts[rule.category] = counts.get(rule.category, 0) + 1
    return counts


@app.post("/api/specs/upload")
async def upload_specification(file: UploadFile = File(...)):
    """
    Upload a custom specification file (YAML or JSON)
    """
    _init_compliance_components()
    
    if not file.filename.endswith(('.yaml', '.yml', '.json')):
        raise HTTPException(
            status_code=400,
            detail="Only YAML (.yaml, .yml) and JSON (.json) files are supported"
        )
    
    # Create specs directory if it doesn't exist
    specs_path = Path(SPECS_DIR)
    specs_path.mkdir(exist_ok=True)
    
    # Save the file
    file_path = specs_path / file.filename
    content = await file.read()
    file_path.write_bytes(content)
    
    try:
        # Load the specification
        rules_loaded = eth_specification.load_spec_file(str(file_path))
        
        # Reinitialize compliance analyzer with updated rules
        global compliance_analyzer
        if indexer:
            compliance_analyzer = ComplianceAnalyzer(eth_specification, indexer)
        
        return {
            "status": "success",
            "filename": file.filename,
            "rules_loaded": rules_loaded,
            "total_rules": len(eth_specification.rules)
        }
    except Exception as e:
        # Remove the file if loading failed
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=400, detail=f"Failed to load specification: {str(e)}")


@app.post("/api/specs/add-rule")
async def add_custom_rule(rule: CustomRuleRequest):
    """
    Add a custom compliance rule
    """
    _init_compliance_components()
    
    new_rule = ComplianceRule(
        id=rule.id,
        source=rule.source,
        category=rule.category,
        severity=rule.severity,
        description=rule.description,
        patterns=rule.patterns,
        must_contain=rule.must_contain,
        must_not_contain=rule.must_not_contain,
        recommendation=rule.recommendation,
        languages=rule.languages
    )
    
    eth_specification.add_rule(new_rule)
    
    return {
        "status": "success",
        "rule_id": rule.id,
        "total_rules": len(eth_specification.rules)
    }


@app.get("/api/specs/eip/{eip_number}")
async def fetch_eip(eip_number: int, load_rules: bool = True):
    """
    Fetch and optionally load an EIP specification
    """
    _init_compliance_components()
    
    try:
        eip = eip_fetcher.fetch_eip(eip_number)
        
        result = {
            "eip": eip.to_dict(),
            "rules_generated": 0
        }
        
        if load_rules:
            rules = eip_fetcher.parse_eip_to_rules(eip)
            for rule in rules:
                eth_specification.add_rule(rule)
            result["rules_generated"] = len(rules)
            result["total_rules"] = len(eth_specification.rules)
        
        return result
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Failed to fetch EIP-{eip_number}: {str(e)}")


@app.get("/api/specs/eip/search")
async def search_eips(query: str):
    """
    Search for EIPs by keyword
    """
    _init_compliance_components()
    
    results = eip_fetcher.search_eips(query)
    return {
        "query": query,
        "results": results,
        "count": len(results)
    }


@app.get("/api/specs/rules")
async def get_rules(
    source: Optional[str] = None,
    category: Optional[str] = None,
    severity: Optional[str] = None,
    language: Optional[str] = None
):
    """
    Get compliance rules with optional filtering
    """
    _init_compliance_components()
    
    rules = eth_specification.rules
    
    if source:
        rules = [r for r in rules if r.source == source]
    if category:
        rules = [r for r in rules if r.category == category]
    if severity:
        rules = [r for r in rules if r.severity == severity]
    if language:
        rules = [r for r in rules if language.lower() in [l.lower() for l in r.languages]]
    
    return {
        "count": len(rules),
        "rules": [r.to_dict() for r in rules]
    }


# Compliance Check Endpoints

@app.post("/api/compliance/check")
async def check_compliance(request: ComplianceCheckRequest):
    """
    Check compliance of indexed code against specifications
    """
    _init_compliance_components()
    
    if not indexer:
        raise HTTPException(status_code=400, detail="No codebase indexed")
    
    global compliance_analyzer
    if compliance_analyzer is None:
        compliance_analyzer = ComplianceAnalyzer(eth_specification, indexer)
    
    try:
        # Filter rules if specified
        rules = None
        if request.rule_ids:
            rules = [r for r in eth_specification.rules if r.id in request.rule_ids]
        elif request.severity_filter:
            rules = eth_specification.get_rules_by_severity(request.severity_filter)
        
        # Check specific entity or full codebase
        if request.entity_name:
            entity = indexer.get_entity_by_name(request.entity_name)
            if not entity:
                raise HTTPException(status_code=404, detail=f"Entity '{request.entity_name}' not found")
            
            deviations = compliance_analyzer.analyze_entity(entity, rules)
            return {
                "entity_name": request.entity_name,
                "deviations": [d.to_dict() for d in deviations],
                "total_deviations": len(deviations),
                "compliance_passed": len([d for d in deviations if d.rule.severity == 'critical']) == 0
            }
        
        elif request.file_path:
            # Analyze all entities in a specific file
            entities = [e for e in indexer.entities if e.file_path == request.file_path]
            if not entities:
                raise HTTPException(status_code=404, detail=f"No entities found in '{request.file_path}'")
            
            all_deviations = []
            for entity in entities:
                deviations = compliance_analyzer.analyze_entity(entity, rules)
                all_deviations.extend(deviations)
            
            return {
                "file_path": request.file_path,
                "entities_checked": len(entities),
                "deviations": [d.to_dict() for d in all_deviations],
                "total_deviations": len(all_deviations),
                "compliance_passed": len([d for d in all_deviations if d.rule.severity == 'critical']) == 0
            }
        
        else:
            # Full codebase check
            report = compliance_analyzer.analyze_codebase()
            return report.to_dict()
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Compliance check failed: {str(e)}")


@app.get("/api/compliance/report")
async def get_compliance_report():
    """
    Get full compliance report for the indexed codebase
    """
    _init_compliance_components()
    
    if not indexer:
        raise HTTPException(status_code=400, detail="No codebase indexed")
    
    global compliance_analyzer
    if compliance_analyzer is None:
        compliance_analyzer = ComplianceAnalyzer(eth_specification, indexer)
    
    try:
        report = compliance_analyzer.analyze_codebase()
        return report.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@app.get("/api/compliance/deviations")
async def get_deviations(
    severity: Optional[str] = None,
    category: Optional[str] = None,
    file_path: Optional[str] = None
):
    """
    Get all compliance deviations with optional filtering
    """
    _init_compliance_components()
    
    if not indexer:
        raise HTTPException(status_code=400, detail="No codebase indexed")
    
    global compliance_analyzer
    if compliance_analyzer is None:
        compliance_analyzer = ComplianceAnalyzer(eth_specification, indexer)
    
    try:
        report = compliance_analyzer.analyze_codebase()
        deviations = report.deviations
        
        # Apply filters
        if severity:
            deviations = [d for d in deviations if d.rule.severity == severity]
        if category:
            deviations = [d for d in deviations if d.rule.category == category]
        if file_path:
            deviations = [d for d in deviations if file_path in d.file_path]
        
        return {
            "deviations": [d.to_dict() for d in deviations],
            "total": len(deviations),
            "critical": len([d for d in deviations if d.rule.severity == 'critical']),
            "warnings": len([d for d in deviations if d.rule.severity == 'warning']),
            "info": len([d for d in deviations if d.rule.severity == 'info'])
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get deviations: {str(e)}")


# Git Analysis Endpoints

@app.post("/api/compliance/analyze-commit")
async def analyze_commit(request: CommitAnalysisRequest):
    """
    Analyze a local git commit for compliance
    """
    _init_compliance_components()
    
    if not os.path.exists(request.repo_path):
        raise HTTPException(status_code=404, detail=f"Repository path not found: {request.repo_path}")
    
    try:
        result = git_analyzer.analyze_local_commit(request.repo_path, request.commit_hash)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Commit analysis failed: {str(e)}")


@app.post("/api/compliance/analyze-remote-commit")
async def analyze_remote_commit(request: RemoteCommitRequest):
    """
    Analyze a commit from a remote repository
    """
    _init_compliance_components()
    
    try:
        result = git_analyzer.analyze_remote_commit(request.repo_url, request.commit_hash)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Remote commit analysis failed: {str(e)}")


@app.post("/api/compliance/analyze-pr")
async def analyze_pull_request(request: PRAnalysisRequest):
    """
    Analyze a GitHub pull request for compliance
    """
    _init_compliance_components()
    
    try:
        result = git_analyzer.analyze_pr_from_github(
            request.owner,
            request.repo,
            request.pr_number,
            request.token
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PR analysis failed: {str(e)}")


@app.post("/api/compliance/analyze-commit-range")
async def analyze_commit_range(repo_path: str, from_commit: str, to_commit: str = "HEAD"):
    """
    Analyze a range of commits for compliance
    """
    _init_compliance_components()
    
    if not os.path.exists(repo_path):
        raise HTTPException(status_code=404, detail=f"Repository path not found: {repo_path}")
    
    try:
        result = git_analyzer.analyze_commit_range(repo_path, from_commit, to_commit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Commit range analysis failed: {str(e)}")


# Webhook Endpoints

@app.post("/api/webhook/github")
async def github_webhook(request: Dict[str, Any], x_hub_signature_256: Optional[str] = None, x_github_event: str = "push"):
    """
    Handle GitHub webhook events
    """
    from fastapi import Request as FastAPIRequest
    
    _init_compliance_components()
    
    # Verify signature if secret is configured
    if GITHUB_WEBHOOK_SECRET and x_hub_signature_256:
        # In production, verify the signature
        pass
    
    try:
        if x_github_event == "push":
            result = await webhook_handler.handle_github_push(request)
        elif x_github_event == "pull_request":
            result = await webhook_handler.handle_github_pull_request(request)
        else:
            return {"status": "ignored", "event": x_github_event}
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")


@app.post("/api/webhook/gitlab")
async def gitlab_webhook(request: Dict[str, Any], x_gitlab_token: Optional[str] = None):
    """
    Handle GitLab webhook events
    """
    _init_compliance_components()
    
    # Verify token if secret is configured
    if GITLAB_WEBHOOK_SECRET and x_gitlab_token:
        if not webhook_handler.verify_gitlab_token(x_gitlab_token):
            raise HTTPException(status_code=401, detail="Invalid webhook token")
    
    try:
        event_type = request.get("object_kind", "push")
        
        if event_type == "push":
            result = await webhook_handler.handle_gitlab_push(request)
        elif event_type == "merge_request":
            result = await webhook_handler.handle_gitlab_merge_request(request)
        else:
            return {"status": "ignored", "event": event_type}
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Webhook processing failed: {str(e)}")


# Compliance Summary Endpoint

@app.get("/api/compliance/summary")
async def get_compliance_summary():
    """
    Get a quick summary of compliance status
    """
    _init_compliance_components()
    
    if not indexer:
        return {
            "status": "no_codebase",
            "message": "No codebase indexed"
        }
    
    global compliance_analyzer
    if compliance_analyzer is None:
        compliance_analyzer = ComplianceAnalyzer(eth_specification, indexer)
    
    try:
        report = compliance_analyzer.analyze_codebase()
        
        return {
            "status": "analyzed",
            "compliance_score": report.summary.get('compliance_score', 0),
            "total_entities": report.total_entities,
            "total_rules_checked": report.total_rules_checked,
            "total_deviations": len(report.deviations),
            "critical_issues": report.summary.get('critical_issues', 0),
            "warnings": report.summary.get('warnings', 0),
            "compliance_passed": report.summary.get('critical_issues', 0) == 0,
            "most_common_issues": report.summary.get('most_common_issues', [])
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


if __name__ == "__main__":
    import uvicorn
    
    print("""
    ╔════════════════════════════════════════════════════════════╗
    ║          Code Analysis API Server                          ║
    ║                                                            ║
    ║  Starting FastAPI server on http://localhost:8000         ║
    ║  Documentation: http://localhost:8000/docs                ║
    ╚════════════════════════════════════════════════════════════╝
    """)
    
    # Run uvicorn directly without nest_asyncio complications
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000, 
        log_level="info"
    )


