"""
API Routes Module

Contains all route definitions organized by domain.
"""

from app.api.routes.health import router as health_router
from app.api.routes.config import router as config_router
from app.api.routes.codebase import router as codebase_router
from app.api.routes.analysis import router as analysis_router
from app.api.routes.compliance import router as compliance_router
from app.api.routes.specifications import router as specs_router
from app.api.routes.git import router as git_router
from app.api.routes.llm_compliance import router as llm_compliance_router
from app.api.routes.pr_analysis import router as pr_analysis_router

__all__ = [
    "health_router",
    "config_router", 
    "codebase_router",
    "analysis_router",
    "compliance_router",
    "specs_router",
    "git_router",
    "llm_compliance_router",
    "pr_analysis_router"
]
