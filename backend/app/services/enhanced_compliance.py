"""
Enhanced Compliance Analyzer
Provides deep analysis by ingesting PR code into the property graph,
extracting entities, and running comprehensive LLM-based compliance checks.
"""

import os
import json
import logging
import tempfile
import shutil
import subprocess
import time
import asyncio
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class AnalysisMode(Enum):
    """Analysis mode selection"""
    QUICK = "quick"  # Lightweight: diff-based analysis
    DEEP = "deep"    # Enhanced: graph ingestion + entity analysis


@dataclass
class GraphStats:
    """Statistics about the analyzed code graph"""
    total_entities: int = 0
    total_relationships: int = 0
    total_files: int = 0
    languages: List[str] = field(default_factory=list)
    entity_types: Dict[str, int] = field(default_factory=dict)
    relationship_types: Dict[str, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_entities': self.total_entities,
            'total_relationships': self.total_relationships,
            'total_files': self.total_files,
            'languages': self.languages,
            'entity_types': self.entity_types,
            'relationship_types': self.relationship_types
        }


@dataclass
class AnalysisResult:
    """Result from compliance analysis"""
    mode: AnalysisMode
    success: bool
    duration_seconds: float
    deviations: List[Dict[str, Any]] = field(default_factory=list)
    entities_analyzed: int = 0
    files_analyzed: int = 0
    critical_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    error: Optional[str] = None
    commit_sha: Optional[str] = None
    base_sha: Optional[str] = None
    graph_stats: Optional[GraphStats] = None
    graph_persisted: bool = False
    # New fields for multi-commit PRs
    commits: List[Dict[str, str]] = field(default_factory=list)  # List of {sha, message, author}
    total_commits: int = 0
    analysis_note: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'mode': self.mode.value,
            'success': self.success,
            'duration_seconds': round(self.duration_seconds, 2),
            'deviations': self.deviations,
            'entities_analyzed': self.entities_analyzed,
            'files_analyzed': self.files_analyzed,
            'critical_count': self.critical_count,
            'warning_count': self.warning_count,
            'info_count': self.info_count,
            'error': self.error,
            'commit_sha': self.commit_sha,
            'base_sha': self.base_sha,
            'graph_stats': self.graph_stats.to_dict() if self.graph_stats else None,
            'graph_persisted': self.graph_persisted,
            'commits': self.commits,
            'total_commits': self.total_commits,
            'analysis_note': self.analysis_note
        }


class EnhancedComplianceAnalyzer:
    """
    Enhanced compliance analyzer that provides both lightweight and deep analysis.
    
    Lightweight (Quick) Mode:
    - Fetches PR diff
    - Runs LLM analysis directly on diff
    - Fast (~10-30 seconds)
    
    Deep Mode:
    - Clones the PR branch
    - Ingests code into property graph
    - Extracts all entities
    - Runs comprehensive LLM analysis on each entity
    - Slower but more thorough (~2-5 minutes)
    - Optionally persists graph data for viewing in Statistics tab
    """
    
    # Default storage directory for PR analysis graphs
    # Use absolute path relative to this file's location (backend/app/services/)
    # This ensures consistent path regardless of where the server is started
    _BACKEND_DIR = Path(__file__).parent.parent.parent  # Goes from services/ -> app/ -> backend/
    PR_GRAPH_STORAGE_DIR = str(_BACKEND_DIR / "pr_graph_storage")
    
    def __init__(
        self,
        llm_analyzer=None,
        indexer=None,
        github_client=None,
        spec_indexer=None,
        persist_graphs: bool = True
    ):
        """
        Initialize the enhanced analyzer.
        
        Args:
            llm_analyzer: LLMComplianceAnalyzer for semantic analysis
            indexer: CodeGraphIndexer for property graph operations
            github_client: GitHubClient for API operations
            spec_indexer: SpecificationIndexer for Qdrant hybrid search
            persist_graphs: Whether to persist deep analysis graph data
        """
        self.llm_analyzer = llm_analyzer
        self.indexer = indexer
        self.github_client = github_client
        self.spec_indexer = spec_indexer
        self.temp_dirs: List[str] = []
        self.persist_graphs = persist_graphs
        
        # Ensure storage directory exists
        Path(self.PR_GRAPH_STORAGE_DIR).mkdir(parents=True, exist_ok=True)
        logger.info(f"PR graph storage directory: {self.PR_GRAPH_STORAGE_DIR}")
    
    async def analyze_pr(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        mode: AnalysisMode = AnalysisMode.QUICK,
        github_token: Optional[str] = None,
        persist_graph: bool = True
    ) -> AnalysisResult:
        """
        Analyze a pull request for Ethereum protocol compliance.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            mode: Analysis mode (QUICK or DEEP)
            github_token: GitHub token for API access
            persist_graph: Whether to persist graph data (deep mode only)
            
        Returns:
            AnalysisResult with deviations and statistics
        """
        start_time = time.time()
        
        try:
            if mode == AnalysisMode.QUICK:
                result = await self._quick_analysis(owner, repo, pr_number, github_token)
            else:
                result = await self._deep_analysis(
                    owner, repo, pr_number, github_token,
                    persist_graph=persist_graph and self.persist_graphs
                )
            
            result.duration_seconds = time.time() - start_time
            return result
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return AnalysisResult(
                mode=mode,
                success=False,
                duration_seconds=time.time() - start_time,
                error=str(e)
            )
    
    async def _quick_analysis(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        github_token: Optional[str]
    ) -> AnalysisResult:
        """
        Run lightweight diff-based analysis.
        
        This is fast and provides immediate feedback on the changes.
        """
        logger.info(f"Running QUICK analysis on {owner}/{repo}#{pr_number}")
        
        # Get PR info to extract commit SHA
        pr_info = await self._fetch_pr_info(owner, repo, pr_number, github_token)
        commit_sha = None
        base_sha = None
        if pr_info:
            head_info = pr_info.get('head') or {}
            base_info = pr_info.get('base') or {}
            commit_sha = head_info.get('sha')
            base_sha = base_info.get('sha')
        
        # Fetch all commits in the PR
        commits = await self._fetch_pr_commits(owner, repo, pr_number, github_token)
        total_commits = len(commits)
        logger.info(f"PR has {total_commits} commits")
        
        # Get the diff
        diff_content = await self._fetch_pr_diff(owner, repo, pr_number, github_token)
        
        if not diff_content:
            return AnalysisResult(
                mode=AnalysisMode.QUICK,
                success=False,
                duration_seconds=0,
                error="Failed to fetch PR diff",
                commit_sha=commit_sha,
                base_sha=base_sha
            )
        
        # Count files in diff and extract line number mappings
        files_count = diff_content.count('\ndiff --git')
        if files_count == 0:
            files_count = 1 if diff_content.strip() else 0
        
        # Parse diff to get file line mappings for better deviation reporting
        file_line_map = self._parse_diff_line_numbers(diff_content)
        
        # Run LLM analysis on diff
        deviations = []
        llm_error = None
        if self.llm_analyzer:
            try:
                report = self.llm_analyzer.analyze_diff(diff_content)
                if report and report.deviations:
                    deviations = [d.to_dict() for d in report.deviations]
                    # Enhance deviations with commit info and line numbers
                    for dev in deviations:
                        dev['commit_sha'] = commit_sha
                        # Try to extract line number from code_location if not already set
                        if not dev.get('line') and dev.get('code_location'):
                            loc = dev.get('code_location', '')
                            if ':' in loc:
                                parts = loc.split(':')
                                if len(parts) >= 2:
                                    dev['file'] = parts[0]
                                    try:
                                        # Handle ranges like "file.go:10-20"
                                        line_part = parts[1].split('-')[0]
                                        dev['line'] = int(line_part)
                                    except (ValueError, IndexError):
                                        pass
            except Exception as e:
                llm_error = str(e)
                logger.warning(f"LLM analysis skipped: {e}")
                # If specs not ingested, provide helpful message
                if "ingest_specs" in str(e).lower():
                    logger.info("Tip: Ingest Ethereum specs via LLM Compliance tab for full analysis")
        
        # Count by severity
        critical = sum(1 for d in deviations if d.get('severity', '').lower() == 'critical')
        warning = sum(1 for d in deviations if d.get('severity', '').lower() == 'warning')
        info = len(deviations) - critical - warning
        
        # Build analysis note about commits
        analysis_note = None
        if total_commits > 1:
            analysis_note = f"Analysis covers combined diff from all {total_commits} commits in this PR."
        elif total_commits == 1:
            analysis_note = "Analysis covers the single commit in this PR."
        
        result = AnalysisResult(
            mode=AnalysisMode.QUICK,
            success=True,
            duration_seconds=0,
            deviations=deviations,
            files_analyzed=files_count,
            critical_count=critical,
            warning_count=warning,
            info_count=info,
            commit_sha=commit_sha,
            base_sha=base_sha,
            commits=commits,
            total_commits=total_commits,
            analysis_note=analysis_note
        )
        
        # Add note if LLM analysis was skipped
        if llm_error and not deviations:
            result.error = f"LLM analysis skipped: {llm_error}. Ingest Ethereum specs for full compliance checking."
        
        return result
    
    def _parse_diff_line_numbers(self, diff_content: str) -> Dict[str, List[int]]:
        """
        Parse diff content to extract line number mappings for each file.
        
        Returns a dict of filename -> list of changed line numbers in the new file.
        """
        import re
        
        file_line_map = {}
        current_file = None
        current_line = 0
        
        for line in diff_content.split('\n'):
            # Match file header: +++ b/path/to/file.go
            if line.startswith('+++ b/'):
                current_file = line[6:]
                file_line_map[current_file] = []
            
            # Match hunk header: @@ -old_start,old_count +new_start,new_count @@
            elif line.startswith('@@'):
                match = re.search(r'\+(\d+)', line)
                if match:
                    current_line = int(match.group(1))
            
            # Track added lines
            elif line.startswith('+') and not line.startswith('+++'):
                if current_file:
                    file_line_map[current_file].append(current_line)
                current_line += 1
            
            # Track context and removed lines for line number tracking
            elif line.startswith('-') and not line.startswith('---'):
                pass  # Don't increment line number for removed lines
            elif not line.startswith('\\'):  # Skip "\ No newline at end of file"
                current_line += 1
        
        return file_line_map
    
    async def _deep_analysis(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        github_token: Optional[str],
        persist_graph: bool = True
    ) -> AnalysisResult:
        """
        Run enhanced graph-based analysis.
        
        This clones the PR branch, ingests into the property graph,
        and analyzes each entity comprehensively.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: PR number
            github_token: GitHub token for API access
            persist_graph: Whether to persist graph data for viewing in Statistics
        """
        logger.info(f"Running DEEP analysis on {owner}/{repo}#{pr_number}")
        
        temp_dir = None
        commit_sha = None
        base_sha = None
        graph_stats = None
        graph_persisted = False
        
        try:
            # Get PR info
            pr_info = await self._fetch_pr_info(owner, repo, pr_number, github_token)
            if not pr_info:
                return AnalysisResult(
                    mode=AnalysisMode.DEEP,
                    success=False,
                    duration_seconds=0,
                    error="Failed to fetch PR info"
                )
            
            head_info = pr_info.get('head') or {}
            base_info = pr_info.get('base') or {}
            head_repo = head_info.get('repo') or {}
            
            head_ref = head_info.get('ref', '')
            head_sha = head_info.get('sha', '')
            commit_sha = head_sha
            base_sha = base_info.get('sha', '')
            clone_url = head_repo.get('clone_url', '') if head_repo else ''
            
            if not clone_url:
                # Fallback to base repo clone URL for the main repo
                clone_url = f"https://github.com/{owner}/{repo}.git"
                logger.info(f"Using base repo clone URL: {clone_url}")
            
            # Clone the PR branch
            temp_dir = await self._clone_pr_branch(clone_url, head_ref, head_sha, github_token)
            
            if not temp_dir:
                return AnalysisResult(
                    mode=AnalysisMode.DEEP,
                    success=False,
                    duration_seconds=0,
                    error="Failed to clone PR branch",
                    commit_sha=commit_sha,
                    base_sha=base_sha
                )
            
            # Ingest into property graph
            entities, relationships = await self._ingest_to_graph(temp_dir)
            
            if not entities:
                return AnalysisResult(
                    mode=AnalysisMode.DEEP,
                    success=True,
                    duration_seconds=0,
                    deviations=[],
                    entities_analyzed=0,
                    files_analyzed=self._count_code_files(temp_dir),
                    commit_sha=commit_sha,
                    base_sha=base_sha
                )
            
            # Calculate graph statistics
            graph_stats = self._calculate_graph_stats(entities, relationships)
            
            # Persist graph data if requested
            if persist_graph:
                graph_persisted = self._persist_pr_graph(
                    owner, repo, pr_number, commit_sha,
                    entities, relationships, graph_stats
                )
            
            # Get changed files from PR
            changed_files = await self._get_pr_changed_files(owner, repo, pr_number, github_token)
            
            # Filter entities to only those in changed files
            relevant_entities = self._filter_entities_by_files(entities, changed_files)
            
            # Run LLM analysis on entities WITH graph context
            # Pass relationships and all entities for graph-aware batch analysis
            deviations = await self._analyze_entities(
                entities=relevant_entities,
                commit_sha=commit_sha,
                relationships=relationships,
                all_entities=entities
            )
            
            # Count by severity
            critical = sum(1 for d in deviations if d.get('severity', '').lower() == 'critical')
            warning = sum(1 for d in deviations if d.get('severity', '').lower() == 'warning')
            info = len(deviations) - critical - warning
            
            return AnalysisResult(
                mode=AnalysisMode.DEEP,
                success=True,
                duration_seconds=0,
                deviations=deviations,
                entities_analyzed=len(relevant_entities),
                files_analyzed=len(changed_files),
                critical_count=critical,
                warning_count=warning,
                info_count=info,
                commit_sha=commit_sha,
                base_sha=base_sha,
                graph_stats=graph_stats,
                graph_persisted=graph_persisted
            )
            
        finally:
            # Cleanup temp directory
            if temp_dir:
                self._cleanup_temp_dir(temp_dir)
    
    def _calculate_graph_stats(
        self,
        entities: List[Any],
        relationships: List[Any]
    ) -> GraphStats:
        """Calculate statistics about the code graph."""
        # Count entity types
        entity_types: Dict[str, int] = {}
        languages: set = set()
        files: set = set()
        
        for entity in entities:
            etype = getattr(entity, 'type', 'unknown')
            entity_types[etype] = entity_types.get(etype, 0) + 1
            
            lang = getattr(entity, 'language', None)
            if lang:
                languages.add(lang)
            
            fpath = getattr(entity, 'file_path', None)
            if fpath:
                files.add(fpath)
        
        # Count relationship types
        relationship_types: Dict[str, int] = {}
        for rel in relationships:
            rtype = getattr(rel, 'relationship_type', 'unknown')
            relationship_types[rtype] = relationship_types.get(rtype, 0) + 1
        
        return GraphStats(
            total_entities=len(entities),
            total_relationships=len(relationships),
            total_files=len(files),
            languages=sorted(list(languages)),
            entity_types=entity_types,
            relationship_types=relationship_types
        )
    
    def _persist_pr_graph(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        commit_sha: str,
        entities: List[Any],
        relationships: List[Any],
        graph_stats: GraphStats
    ) -> bool:
        """
        Persist PR graph data to storage for viewing in Statistics tab.
        
        Returns True if persistence succeeded.
        """
        try:
            import pickle
            
            # Create a unique directory for this PR analysis
            pr_id = f"{owner}_{repo}_{pr_number}"
            pr_dir = Path(self.PR_GRAPH_STORAGE_DIR) / pr_id
            pr_dir.mkdir(parents=True, exist_ok=True)
            
            # Save entities and relationships as pickle
            with open(pr_dir / "entities.pkl", 'wb') as f:
                pickle.dump(entities, f)
            
            with open(pr_dir / "relationships.pkl", 'wb') as f:
                pickle.dump(relationships, f)
            
            # Save graph data as JSON for human readability and visualization
            graph_data = {
                'nodes': [
                    {
                        'id': getattr(entity, 'name', f'entity_{i}'),
                        'label': getattr(entity, 'name', f'entity_{i}'),
                        'type': getattr(entity, 'type', 'unknown'),
                        'language': getattr(entity, 'language', 'unknown'),
                        'file': getattr(entity, 'file_path', ''),
                        'parent': getattr(entity, 'parent', None),
                        'line_start': getattr(entity, 'line_start', 0),
                        'line_end': getattr(entity, 'line_end', 0),
                    }
                    for i, entity in enumerate(entities)
                ],
                'edges': [
                    {
                        'source': getattr(rel, 'source', ''),
                        'target': getattr(rel, 'target', ''),
                        'type': getattr(rel, 'relationship_type', 'unknown')
                    }
                    for rel in relationships
                ]
            }
            
            with open(pr_dir / "graph_data.json", 'w') as f:
                json.dump(graph_data, f, indent=2)
            
            # Save metadata
            metadata = {
                'owner': owner,
                'repo': repo,
                'pr_number': pr_number,
                'commit_sha': commit_sha,
                'timestamp': datetime.utcnow().isoformat(),
                'stats': graph_stats.to_dict()
            }
            
            with open(pr_dir / "metadata.json", 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Graph data persisted to: {pr_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to persist PR graph: {e}")
            return False
    
    @classmethod
    def get_persisted_pr_graphs(cls) -> List[Dict[str, Any]]:
        """Get list of all persisted PR graph analyses."""
        pr_graphs = []
        storage_dir = Path(cls.PR_GRAPH_STORAGE_DIR)
        
        if not storage_dir.exists():
            return []
        
        for pr_dir in storage_dir.iterdir():
            if pr_dir.is_dir():
                metadata_file = pr_dir / "metadata.json"
                if metadata_file.exists():
                    try:
                        with open(metadata_file, 'r') as f:
                            metadata = json.load(f)
                        metadata['id'] = pr_dir.name
                        pr_graphs.append(metadata)
                    except Exception as e:
                        logger.warning(f"Failed to load metadata from {pr_dir}: {e}")
        
        # Sort by timestamp (newest first)
        pr_graphs.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return pr_graphs
    
    @classmethod
    def get_pr_graph_data(cls, pr_id: str) -> Optional[Dict[str, Any]]:
        """Get graph data for a specific PR analysis."""
        pr_dir = Path(cls.PR_GRAPH_STORAGE_DIR) / pr_id
        graph_file = pr_dir / "graph_data.json"
        
        if not graph_file.exists():
            return None
        
        try:
            with open(graph_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load graph data: {e}")
            return None
    
    @classmethod
    def delete_pr_graph(cls, pr_id: str) -> bool:
        """Delete a persisted PR graph analysis."""
        pr_dir = Path(cls.PR_GRAPH_STORAGE_DIR) / pr_id
        
        if not pr_dir.exists():
            return False
        
        try:
            shutil.rmtree(pr_dir)
            logger.info(f"Deleted PR graph: {pr_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete PR graph: {e}")
            return False
    
    @classmethod
    def load_pr_graph_to_main_storage(cls, pr_id: str, main_storage_dir: str = "./graph_storage") -> bool:
        """
        Load a PR graph into the main graph storage directory.
        This makes it available in the Statistics tab.
        """
        pr_dir = Path(cls.PR_GRAPH_STORAGE_DIR) / pr_id
        main_dir = Path(main_storage_dir)
        
        if not pr_dir.exists():
            return False
        
        try:
            # Copy files to main storage
            main_dir.mkdir(parents=True, exist_ok=True)
            
            for filename in ['entities.pkl', 'relationships.pkl', 'graph_data.json']:
                src = pr_dir / filename
                dst = main_dir / filename
                if src.exists():
                    shutil.copy2(src, dst)
            
            logger.info(f"Loaded PR graph {pr_id} to main storage: {main_dir}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load PR graph to main storage: {e}")
            return False
    
    async def _fetch_pr_diff(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        github_token: Optional[str]
    ) -> Optional[str]:
        """Fetch the diff content for a PR."""
        if self.github_client:
            try:
                return self.github_client.get_pr_diff(owner, repo, pr_number)
            except Exception as e:
                logger.warning(f"Failed to fetch diff via client: {e}")
        
        # Fallback to direct API call
        import urllib.request
        import urllib.error
        
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        headers = {
            'Accept': 'application/vnd.github.v3.diff',
            'User-Agent': 'Ethereum-Compliance-Checker'
        }
        if github_token:
            headers['Authorization'] = f'Bearer {github_token}'
        
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read().decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to fetch PR diff: {e}")
            return None
    
    async def _fetch_pr_info(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        github_token: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Fetch PR information."""
        if self.github_client:
            try:
                return self.github_client.get_pr(owner, repo, pr_number)
            except Exception as e:
                logger.warning(f"Failed to fetch PR info via client: {e}")
        
        # Fallback to direct API call
        import urllib.request
        
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        headers = {
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'Ethereum-Compliance-Checker'
        }
        if github_token:
            headers['Authorization'] = f'Bearer {github_token}'
        
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode('utf-8'))
        except Exception as e:
            logger.error(f"Failed to fetch PR info: {e}")
            return None
    
    async def _get_pr_changed_files(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        github_token: Optional[str]
    ) -> List[str]:
        """Get list of files changed in the PR."""
        if self.github_client:
            try:
                files = self.github_client.get_pr_files(owner, repo, pr_number)
                return [f['filename'] for f in files]
            except Exception as e:
                logger.warning(f"Failed to fetch PR files via client: {e}")
        
        # Fallback
        import urllib.request
        
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
        headers = {
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'Ethereum-Compliance-Checker'
        }
        if github_token:
            headers['Authorization'] = f'Bearer {github_token}'
        
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=30) as response:
                files = json.loads(response.read().decode('utf-8'))
                return [f['filename'] for f in files]
        except Exception as e:
            logger.error(f"Failed to fetch PR files: {e}")
            return []
    
    async def _fetch_pr_commits(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        github_token: Optional[str]
    ) -> List[Dict[str, str]]:
        """Fetch list of commits in the PR."""
        if self.github_client:
            try:
                commits = self.github_client.get_pr_commits(owner, repo, pr_number)
                return [
                    {
                        'sha': c.get('sha', '')[:7],
                        'full_sha': c.get('sha', ''),
                        'message': c.get('commit', {}).get('message', '').split('\n')[0][:80],
                        'author': c.get('commit', {}).get('author', {}).get('name', 'Unknown')
                    }
                    for c in commits
                ]
            except Exception as e:
                logger.warning(f"Failed to fetch PR commits via client: {e}")
        
        # Fallback to direct API call
        import urllib.request
        
        url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/commits"
        headers = {
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'Ethereum-Compliance-Checker'
        }
        if github_token:
            headers['Authorization'] = f'Bearer {github_token}'
        
        try:
            request = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(request, timeout=30) as response:
                commits = json.loads(response.read().decode('utf-8'))
                return [
                    {
                        'sha': c.get('sha', '')[:7],
                        'full_sha': c.get('sha', ''),
                        'message': c.get('commit', {}).get('message', '').split('\n')[0][:80],
                        'author': c.get('commit', {}).get('author', {}).get('name', 'Unknown')
                    }
                    for c in commits
                ]
        except Exception as e:
            logger.error(f"Failed to fetch PR commits: {e}")
            return []
    
    async def _clone_pr_branch(
        self,
        clone_url: str,
        branch: str,
        commit_sha: str,
        github_token: Optional[str]
    ) -> Optional[str]:
        """Clone the PR branch to a temporary directory."""
        temp_dir = tempfile.mkdtemp(prefix='compliance_deep_')
        self.temp_dirs.append(temp_dir)
        
        try:
            # Add token to URL if provided
            if github_token and clone_url.startswith('https://'):
                clone_url = clone_url.replace('https://', f'https://{github_token}@')
            
            # Clone with specific branch
            logger.info(f"Cloning {clone_url} branch {branch}")
            result = subprocess.run(
                ['git', 'clone', '--depth', '1', '--branch', branch, clone_url, temp_dir],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                # Try cloning default branch and checking out the commit
                logger.warning(f"Failed to clone branch {branch}, trying commit checkout")
                shutil.rmtree(temp_dir, ignore_errors=True)
                os.makedirs(temp_dir)
                
                subprocess.run(
                    ['git', 'clone', '--depth', '50', clone_url, temp_dir],
                    capture_output=True,
                    timeout=300
                )
                
                subprocess.run(
                    ['git', 'checkout', commit_sha],
                    cwd=temp_dir,
                    capture_output=True,
                    timeout=60
                )
            
            return temp_dir
            
        except Exception as e:
            logger.error(f"Failed to clone repository: {e}")
            self._cleanup_temp_dir(temp_dir)
            return None
    
    async def _ingest_to_graph(
        self,
        repo_path: str
    ) -> Tuple[List[Any], List[Any]]:
        """Ingest the repository code into the property graph.
        
        Always creates a temporary indexer to avoid affecting the main indexer state.
        """
        try:
            # Import the parser directly for lightweight parsing
            from app.core.parsers import CodebaseParser
            
            parser = CodebaseParser()
            parsed_data = parser.parse_codebase(repo_path)
            
            entities = parsed_data.get('entities', [])
            relationships = parsed_data.get('relationships', [])
            
            logger.info(f"Parsed {len(entities)} entities and {len(relationships)} relationships from {repo_path}")
            
            return entities, relationships
            
        except Exception as e:
            logger.error(f"Failed to parse codebase: {e}")
            return [], []
    
    def _filter_entities_by_files(
        self,
        entities: List[Any],
        changed_files: List[str]
    ) -> List[Any]:
        """Filter entities to only those in changed files."""
        if not changed_files:
            return entities
        
        # Normalize file paths
        changed_set = set()
        for f in changed_files:
            changed_set.add(f)
            changed_set.add(os.path.basename(f))
        
        filtered = []
        for entity in entities:
            entity_file = getattr(entity, 'file_path', '') or ''
            if not entity_file:
                continue
            
            # Check if entity's file matches any changed file
            if entity_file in changed_set or os.path.basename(entity_file) in changed_set:
                filtered.append(entity)
            else:
                # Check for partial match
                for cf in changed_files:
                    if entity_file.endswith(cf) or cf.endswith(entity_file):
                        filtered.append(entity)
                        break
        
        return filtered
    
    # Hybrid batch configuration
    BATCH_CONFIG = {
        'max_entities_per_batch': 10,       # Max entities in a single LLM call
        'max_chars_per_batch': 15000,       # Max characters of code in a single batch
        'max_parallel_batches': 3,          # Max batches to process in parallel
        'max_total_batches': 50,            # Max total batches to process
        'max_entities_total': 500,          # Max total entities to analyze
    }
    
    async def _analyze_entities(
        self,
        entities: List[Any],
        commit_sha: Optional[str] = None,
        relationships: List[Any] = None,
        all_entities: List[Any] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> List[Dict[str, Any]]:
        """Run LLM compliance analysis on entities using HYBRID BATCHING.
        
        This method implements a hybrid approach:
        1. Groups entities by file for better context
        2. Splits large groups into sub-batches (max entities & chars)
        3. Processes batches in parallel waves
        4. Each batch = ONE spec query + ONE LLM call
        
        This reduces API calls from O(n) to O(n/batch_size) and uses parallelism.
        
        Args:
            entities: Entities to analyze (filtered to changed files)
            commit_sha: Commit SHA for tracking
            relationships: Graph relationships for context (optional)
            all_entities: All entities for context lookup (optional)
            progress_callback: Optional callback for progress updates (percent, message)
        """
        if not self.llm_analyzer:
            logger.warning("No LLM analyzer available for entity analysis")
            return []
        
        use_graph_context = relationships is not None and all_entities is not None
        
        # Limit total entities
        entities_to_analyze = entities[:self.BATCH_CONFIG['max_entities_total']]
        total = len(entities_to_analyze)
        
        if total == 0:
            return []
        
        logger.info(f"Starting HYBRID BATCH analysis of {total} entities")
        if use_graph_context:
            logger.info("Using GRAPH CONTEXT for enhanced analysis")
        
        # Step 1: Group entities by file
        file_groups = self._group_entities_by_file(entities_to_analyze)
        logger.info(f"Grouped entities into {len(file_groups)} files")
        
        # Step 2: Create batches with size limits
        batches = self._create_batches(file_groups)
        total_batches = len(batches)
        logger.info(f"Created {total_batches} batches (max {self.BATCH_CONFIG['max_entities_per_batch']} entities/batch)")
        
        # Limit total batches
        batches = batches[:self.BATCH_CONFIG['max_total_batches']]
        if len(batches) < total_batches:
            logger.warning(f"Truncated to {len(batches)} batches (max {self.BATCH_CONFIG['max_total_batches']})")
        
        # Step 3: Process batches in parallel waves
        all_deviations = []
        max_parallel = self.BATCH_CONFIG['max_parallel_batches']
        processed = 0
        
        for wave_start in range(0, len(batches), max_parallel):
            wave_batches = batches[wave_start:wave_start + max_parallel]
            wave_num = (wave_start // max_parallel) + 1
            total_waves = (len(batches) + max_parallel - 1) // max_parallel
            
            logger.info(f"Processing wave {wave_num}/{total_waves} ({len(wave_batches)} batches in parallel)")
            
            if progress_callback:
                percent = int((wave_start / len(batches)) * 100)
                progress_callback(percent, f"Analyzing wave {wave_num}/{total_waves}...")
            
            # Process batches in this wave concurrently
            if use_graph_context:
                # Use batch analysis with graph context
                tasks = [
                    self._process_batch_async(
                        batch, relationships, all_entities, commit_sha
                    )
                    for batch in wave_batches
                ]
            else:
                # Fallback to individual analysis (shouldn't happen in deep mode)
                tasks = [
                    self._process_batch_async(
                        batch, None, None, commit_sha
                    )
                    for batch in wave_batches
                ]
            
            # Wait for all batches in this wave
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Batch {wave_start + i + 1} failed: {result}")
                elif result:
                    all_deviations.extend(result)
                processed += 1
            
            logger.info(f"Wave {wave_num} complete: {len(all_deviations)} total deviations so far")
        
        logger.info(f"HYBRID BATCH analysis complete: {total} entities in {len(batches)} batches, {len(all_deviations)} deviations found")
        return all_deviations
    
    def _group_entities_by_file(self, entities: List[Any]) -> Dict[str, List[Any]]:
        """Group entities by their source file."""
        groups = defaultdict(list)
        
        for entity in entities:
            file_path = getattr(entity, 'file_path', '') or 'unknown'
            groups[file_path].append(entity)
        
        return dict(groups)
    
    def _create_batches(self, file_groups: Dict[str, List[Any]]) -> List[List[Any]]:
        """Create batches from file groups, respecting size limits.
        
        Strategy:
        1. Keep entities from the same file together when possible
        2. Split large file groups into sub-batches
        3. Merge small file groups into single batches
        """
        batches = []
        max_entities = self.BATCH_CONFIG['max_entities_per_batch']
        max_chars = self.BATCH_CONFIG['max_chars_per_batch']
        
        current_batch = []
        current_chars = 0
        
        for file_path, entities in file_groups.items():
            # If this file's entities exceed limits, split it into sub-batches
            if len(entities) > max_entities:
                # Flush current batch first
                if current_batch:
                    batches.append(current_batch)
                    current_batch = []
                    current_chars = 0
                
                # Split large file into sub-batches
                for i in range(0, len(entities), max_entities):
                    sub_batch = entities[i:i + max_entities]
                    batches.append(sub_batch)
                continue
            
            # Calculate chars for this file's entities
            file_chars = sum(
                len(getattr(e, 'body', '') or '') 
                for e in entities
            )
            
            # Check if adding this file would exceed limits
            if (len(current_batch) + len(entities) > max_entities or 
                current_chars + file_chars > max_chars):
                # Flush current batch
                if current_batch:
                    batches.append(current_batch)
                current_batch = entities
                current_chars = file_chars
            else:
                # Add to current batch
                current_batch.extend(entities)
                current_chars += file_chars
        
        # Don't forget the last batch
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    async def _process_batch_async(
        self,
        batch: List[Any],
        relationships: Optional[List[Any]],
        all_entities: Optional[List[Any]],
        commit_sha: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Process a single batch asynchronously.
        
        Runs the LLM call in a thread pool to avoid blocking.
        """
        try:
            # Run synchronous LLM call in thread pool
            loop = asyncio.get_event_loop()
            
            if relationships is not None and all_entities is not None:
                # Use batch analysis method
                result = await loop.run_in_executor(
                    None,
                    lambda: self.llm_analyzer.analyze_entity_batch(
                        entities=batch,
                        relationships=relationships,
                        all_entities=all_entities
                    )
                )
            else:
                # Fallback: analyze entities individually (shouldn't happen)
                result = []
                for entity in batch:
                    entity_result = await loop.run_in_executor(
                        None,
                        lambda e=entity: self.llm_analyzer.analyze_entity(e)
                    )
                    if entity_result:
                        result.extend(entity_result if isinstance(entity_result, list) else [entity_result])
            
            # Process results
            all_deviations = []
            deviations_list = result if isinstance(result, list) else []
            
            for dev in deviations_list:
                # Handle both dict and object deviations
                if hasattr(dev, 'to_dict'):
                    dev_dict = dev.to_dict()
                elif isinstance(dev, dict):
                    dev_dict = dev
                else:
                    continue
                
                # Add commit SHA to each deviation
                dev_dict['commit_sha'] = commit_sha
                
                # Extract file and line from code_location if not already set
                if not dev_dict.get('file') and dev_dict.get('code_location'):
                    loc = dev_dict.get('code_location', '')
                    if ':' in loc:
                        parts = loc.split(':')
                        dev_dict['file'] = parts[0]
                        if len(parts) >= 2:
                            try:
                                line_part = parts[1].split('-')[0]
                                dev_dict['line'] = int(line_part)
                            except (ValueError, IndexError):
                                pass
                
                all_deviations.append(dev_dict)
            
            batch_names = [getattr(e, 'name', 'unknown') for e in batch[:3]]
            logger.info(f"Batch complete: {len(batch)} entities ({', '.join(batch_names)}...), {len(all_deviations)} deviations")
            
            return all_deviations
            
        except Exception as e:
            batch_names = [getattr(e, 'name', 'unknown') for e in batch[:3]]
            logger.error(f"Batch processing failed for entities ({', '.join(batch_names)}...): {e}")
            return []
    
    # Legacy method for backwards compatibility (single entity analysis)
    async def _analyze_entities_sequential(
        self,
        entities: List[Any],
        commit_sha: Optional[str] = None,
        relationships: List[Any] = None,
        all_entities: List[Any] = None
    ) -> List[Dict[str, Any]]:
        """Legacy sequential analysis method for fallback."""
        if not self.llm_analyzer:
            logger.warning("No LLM analyzer available for entity analysis")
            return []
        
        all_deviations = []
        use_graph_context = relationships is not None and all_entities is not None
        
        entities_to_analyze = entities[:500]
        total = len(entities_to_analyze)
        
        for i, entity in enumerate(entities_to_analyze):
            entity_name = getattr(entity, 'name', 'unknown')
            
            if i > 0 and i % 10 == 0:
                logger.info(f"Progress: {i}/{total} entities analyzed")
            
            try:
                if use_graph_context:
                    result = self.llm_analyzer.analyze_entity_with_graph_context(
                        entity=entity,
                        relationships=relationships,
                        all_entities=all_entities
                    )
                else:
                    result = self.llm_analyzer.analyze_entity(entity)
                
                deviations_list = result if isinstance(result, list) else []
                
                for dev in deviations_list:
                    if hasattr(dev, 'to_dict'):
                        dev_dict = dev.to_dict()
                    elif isinstance(dev, dict):
                        dev_dict = dev
                    else:
                        continue
                    
                    dev_dict['commit_sha'] = commit_sha
                    all_deviations.append(dev_dict)
                        
            except Exception as e:
                logger.warning(f"Failed to analyze entity {entity_name}: {e}")
        
        return all_deviations
    
    def _count_code_files(self, directory: str) -> int:
        """Count code files in a directory."""
        extensions = {'.py', '.go', '.sol', '.js', '.ts', '.jsx', '.tsx', '.java', '.rs'}
        count = 0
        
        for root, _, files in os.walk(directory):
            for f in files:
                if any(f.endswith(ext) for ext in extensions):
                    count += 1
        
        return count
    
    def _cleanup_temp_dir(self, temp_dir: str):
        """Clean up a temporary directory."""
        try:
            if temp_dir in self.temp_dirs:
                self.temp_dirs.remove(temp_dir)
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Failed to cleanup temp dir: {e}")
    
    def cleanup(self):
        """Clean up all temporary directories."""
        for temp_dir in list(self.temp_dirs):
            self._cleanup_temp_dir(temp_dir)


# =============================================================================
# Dual-Mode Analysis Runner
# =============================================================================

async def run_dual_analysis(
    owner: str,
    repo: str,
    pr_number: int,
    mode: str = "quick",
    github_token: Optional[str] = None,
    llm_analyzer=None,
    indexer=None,
    github_client=None,
    spec_indexer=None,
    progress_callback=None
) -> Dict[str, Any]:
    """
    Run compliance analysis in the specified mode.
    
    Args:
        owner: Repository owner
        repo: Repository name
        pr_number: Pull request number
        mode: Analysis mode - "quick", "deep", or "both"
        github_token: GitHub token
        llm_analyzer: LLM analyzer instance
        indexer: Code graph indexer instance
        github_client: GitHub client instance
        spec_indexer: Specification indexer instance
        progress_callback: Optional callback function(stage: str, progress: int)
        
    Returns:
        Combined results from the analysis
    """
    # Track overall analysis start time
    analysis_start_time = time.time()
    deep_start_time = None  # Will be set when deep analysis starts
    
    def report_progress(stage: str, progress: int):
        """Report progress via callback if provided"""
        if progress_callback:
            try:
                progress_callback(stage, progress)
            except Exception:
                pass
        logger.info(f"Analysis progress: {stage} ({progress}%)")
    
    analyzer = EnhancedComplianceAnalyzer(
        llm_analyzer=llm_analyzer,
        indexer=indexer,
        github_client=github_client,
        spec_indexer=spec_indexer
    )
    
    results = {
        'pr': f"{owner}/{repo}#{pr_number}",
        'timestamp': datetime.utcnow().isoformat(),
        'quick': None,
        'deep': None,
        'combined_deviations': [],
        'total_critical': 0,
        'total_warning': 0,
        'compliance_passed': True,
        'commit_sha': None,
        'base_sha': None
    }
    
    run_quick = mode in ['quick', 'both']
    run_deep = mode in ['deep', 'both']
    
    try:
        # Run quick analysis if requested
        if run_quick:
            report_progress("Running quick analysis...", 15)
            quick_result = await analyzer.analyze_pr(
                owner, repo, pr_number,
                mode=AnalysisMode.QUICK,
                github_token=github_token
            )
            results['quick'] = quick_result.to_dict()
            results['combined_deviations'].extend(quick_result.deviations)
            results['total_critical'] += quick_result.critical_count
            results['total_warning'] += quick_result.warning_count
            
            # Store commit info from quick analysis
            if quick_result.commit_sha:
                results['commit_sha'] = quick_result.commit_sha
            if quick_result.base_sha:
                results['base_sha'] = quick_result.base_sha
            
            report_progress("Quick analysis complete", 30 if run_deep else 90)
        
        # Run deep analysis if requested
        if run_deep:
            deep_start_time = time.time()  # Track deep analysis start
            report_progress("Starting deep analysis - fetching PR info...", 20 if not run_quick else 35)
            
            # Get PR info first
            pr_info = await analyzer._fetch_pr_info(owner, repo, pr_number, github_token)
            if not pr_info:
                raise ValueError(f"Could not fetch PR info for {owner}/{repo}#{pr_number}")
            
            report_progress("Cloning repository...", 30 if not run_quick else 40)
            
            # Extract commit info
            head_info = pr_info.get('head') or {}
            base_info = pr_info.get('base') or {}
            head_repo = head_info.get('repo') or {}
            
            clone_url = head_repo.get('clone_url', '') if head_repo else ''
            branch = head_info.get('ref', 'main')
            commit_sha = head_info.get('sha', '')
            
            if not clone_url:
                logger.warning("No clone URL available - using default repo URL")
                clone_url = f"https://github.com/{owner}/{repo}.git"
                branch = 'main'
            
            # Get list of changed files in the PR
            report_progress("Fetching changed files list...", 35 if not run_quick else 40)
            changed_files = await analyzer._get_pr_changed_files(owner, repo, pr_number, github_token)
            logger.info(f"PR has {len(changed_files)} changed files")
            
            report_progress("Cloning repository...", 40 if not run_quick else 45)
            
            # Clone and parse
            repo_path = await analyzer._clone_pr_branch(clone_url, branch, commit_sha, github_token)
            
            if repo_path:
                report_progress("Parsing code and extracting entities...", 50 if not run_quick else 55)
                entities, relationships = await analyzer._ingest_to_graph(repo_path)
                
                # Filter entities to only those in changed files
                if changed_files:
                    filtered_entities = [
                        e for e in entities 
                        if hasattr(e, 'file_path') and any(
                            cf in e.file_path or e.file_path.endswith(cf) 
                            for cf in changed_files
                        )
                    ]
                    logger.info(f"Filtered to {len(filtered_entities)} entities in changed files (from {len(entities)} total)")
                else:
                    # If we couldn't get changed files, limit to first 200 entities
                    filtered_entities = entities[:200]
                    logger.warning("Could not get changed files list, using first 200 entities")
                
                report_progress(f"Found {len(filtered_entities)} entities in changed files, analyzing...", 60 if not run_quick else 65)
                
                # Calculate graph stats (for full graph, not just filtered)
                graph_stats = analyzer._calculate_graph_stats(entities, relationships)
                
                report_progress("Running LLM compliance analysis with graph context...", 70 if not run_quick else 75)
                
                # Run LLM analysis on filtered entities WITH GRAPH CONTEXT
                # This passes relationships and all entities so the analyzer can understand
                # how the changed code interacts with the rest of the codebase
                deviations = await analyzer._analyze_entities(
                    entities=filtered_entities,
                    commit_sha=commit_sha,
                    relationships=relationships,  # Graph relationships for context
                    all_entities=entities  # All entities for lookup
                )
                
                report_progress("Persisting graph data...", 85 if not run_quick else 88)
                
                # Persist graph
                graph_persisted = analyzer._persist_pr_graph(
                    owner, repo, pr_number, commit_sha,
                    entities, relationships, graph_stats
                )
                
                # Build result with calculated duration
                deep_duration = time.time() - deep_start_time if deep_start_time else 0
                deep_result = AnalysisResult(
                    mode=AnalysisMode.DEEP,
                    success=True,
                    duration_seconds=deep_duration,
                    deviations=deviations,
                    entities_analyzed=len(entities),
                    files_analyzed=graph_stats.total_files,
                    critical_count=sum(1 for d in deviations if d.get('severity', '').lower() == 'critical'),
                    warning_count=sum(1 for d in deviations if d.get('severity', '').lower() == 'warning'),
                    commit_sha=commit_sha,
                    base_sha=base_info.get('sha'),
                    graph_stats=graph_stats,
                    graph_persisted=graph_persisted
                )
                
                # Cleanup temp directory
                analyzer._cleanup_temp_dir(repo_path)
            else:
                deep_duration = time.time() - deep_start_time if deep_start_time else 0
                deep_result = AnalysisResult(
                    mode=AnalysisMode.DEEP,
                    success=False,
                    duration_seconds=deep_duration,
                    deviations=[],
                    error="Failed to clone repository"
                )
            
            results['deep'] = deep_result.to_dict()
            
            # Update commit info if not already set
            if not results['commit_sha'] and deep_result.commit_sha:
                results['commit_sha'] = deep_result.commit_sha
            if not results['base_sha'] and deep_result.base_sha:
                results['base_sha'] = deep_result.base_sha
            
            # Merge deviations (deduplicate by description if both modes ran)
            if run_quick:
                existing_descriptions = {d.get('description', '') for d in results['combined_deviations']}
                for dev in deep_result.deviations:
                    if dev.get('description', '') not in existing_descriptions:
                        results['combined_deviations'].append(dev)
                        if dev.get('severity', '').lower() == 'critical':
                            results['total_critical'] += 1
                        elif dev.get('severity', '').lower() == 'warning':
                            results['total_warning'] += 1
            else:
                # Deep only - add all deviations
                results['combined_deviations'].extend(deep_result.deviations)
                results['total_critical'] += deep_result.critical_count
                results['total_warning'] += deep_result.warning_count
            
            report_progress("Deep analysis complete", 95)
        
        # Determine if compliance passed
        results['compliance_passed'] = results['total_critical'] == 0
        
        report_progress("Analysis complete!", 100)
        
    finally:
        analyzer.cleanup()
    
    return results
