"""
Git Analyzer - Handles git integration for compliance checking
Supports webhooks, manual commit analysis, and CI/CD integration
"""

import os
import re
import json
import hmac
import hashlib
import tempfile
import subprocess
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from enum import Enum
import urllib.request
import urllib.error


class GitProvider(Enum):
    """Supported Git providers"""
    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"


@dataclass
class GitCommit:
    """Represents a git commit"""
    hash: str
    author: str
    author_email: str
    message: str
    timestamp: str
    files_changed: List[str] = field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'hash': self.hash,
            'author': self.author,
            'author_email': self.author_email,
            'message': self.message,
            'timestamp': self.timestamp,
            'files_changed': self.files_changed,
            'additions': self.additions,
            'deletions': self.deletions
        }


@dataclass
class PullRequest:
    """Represents a pull request"""
    number: int
    title: str
    description: str
    author: str
    source_branch: str
    target_branch: str
    state: str  # open, closed, merged
    commits: List[GitCommit] = field(default_factory=list)
    files_changed: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'number': self.number,
            'title': self.title,
            'description': self.description,
            'author': self.author,
            'source_branch': self.source_branch,
            'target_branch': self.target_branch,
            'state': self.state,
            'commits': [c.to_dict() for c in self.commits],
            'files_changed': self.files_changed
        }


@dataclass
class WebhookPayload:
    """Parsed webhook payload"""
    provider: GitProvider
    event_type: str  # push, pull_request, etc.
    repository: str
    branch: str
    commits: List[GitCommit] = field(default_factory=list)
    pull_request: Optional[PullRequest] = None
    raw_payload: Dict[str, Any] = field(default_factory=dict)


class GitAnalyzer:
    """Analyzes git commits and diffs for compliance checking"""
    
    def __init__(self, compliance_analyzer=None):
        self.compliance_analyzer = compliance_analyzer
        self.temp_dirs: List[str] = []
    
    def set_compliance_analyzer(self, analyzer):
        """Set the compliance analyzer for checking"""
        self.compliance_analyzer = analyzer
    
    def analyze_local_commit(self, repo_path: str, commit_hash: str = "HEAD") -> Dict[str, Any]:
        """
        Analyze a commit in a local repository
        
        Args:
            repo_path: Path to the local git repository
            commit_hash: Commit hash to analyze (default: HEAD)
            
        Returns:
            Analysis results with compliance deviations
        """
        repo_path = Path(repo_path)
        if not (repo_path / ".git").exists():
            raise ValueError(f"Not a git repository: {repo_path}")
        
        # Get commit info
        commit = self._get_commit_info(repo_path, commit_hash)
        
        # Get the diff
        diff = self._get_commit_diff(repo_path, commit_hash)
        
        # Analyze for compliance
        deviations = []
        if self.compliance_analyzer:
            deviations = self.compliance_analyzer.analyze_diff(diff)
        
        return {
            'commit': commit.to_dict(),
            'diff_summary': self._summarize_diff(diff),
            'deviations': [d.to_dict() for d in deviations],
            'total_deviations': len(deviations),
            'critical_count': len([d for d in deviations if d.rule.severity == 'critical']),
            'warning_count': len([d for d in deviations if d.rule.severity == 'warning'])
        }
    
    def analyze_commit_range(self, repo_path: str, from_commit: str, to_commit: str = "HEAD") -> Dict[str, Any]:
        """
        Analyze a range of commits
        
        Args:
            repo_path: Path to the local git repository
            from_commit: Starting commit (exclusive)
            to_commit: Ending commit (inclusive, default: HEAD)
            
        Returns:
            Analysis results for all commits in range
        """
        repo_path = Path(repo_path)
        
        # Get diff between commits
        diff = self._run_git_command(
            repo_path,
            ['diff', f'{from_commit}..{to_commit}']
        )
        
        # Get list of commits in range
        log_output = self._run_git_command(
            repo_path,
            ['log', '--oneline', f'{from_commit}..{to_commit}']
        )
        
        commits = []
        for line in log_output.strip().split('\n'):
            if line:
                parts = line.split(' ', 1)
                if len(parts) >= 1:
                    commit_hash = parts[0]
                    commits.append(self._get_commit_info(repo_path, commit_hash))
        
        # Analyze for compliance
        deviations = []
        if self.compliance_analyzer:
            deviations = self.compliance_analyzer.analyze_diff(diff)
        
        return {
            'from_commit': from_commit,
            'to_commit': to_commit,
            'commits': [c.to_dict() for c in commits],
            'commit_count': len(commits),
            'diff_summary': self._summarize_diff(diff),
            'deviations': [d.to_dict() for d in deviations],
            'total_deviations': len(deviations)
        }
    
    def analyze_remote_commit(self, repo_url: str, commit_hash: str) -> Dict[str, Any]:
        """
        Analyze a commit from a remote repository
        
        Args:
            repo_url: URL of the git repository
            commit_hash: Commit hash to analyze
            
        Returns:
            Analysis results
        """
        # Clone to temp directory
        temp_dir = self._clone_repo(repo_url)
        
        try:
            return self.analyze_local_commit(temp_dir, commit_hash)
        finally:
            self._cleanup_temp_dir(temp_dir)
    
    def analyze_pr_from_github(self, owner: str, repo: str, pr_number: int, token: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze a GitHub pull request
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            token: Optional GitHub token for private repos
            
        Returns:
            Analysis results
        """
        # Fetch PR data
        pr_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        headers = {'Accept': 'application/vnd.github.v3+json'}
        if token:
            headers['Authorization'] = f'token {token}'
        
        req = urllib.request.Request(pr_url, headers=headers)
        with urllib.request.urlopen(req) as response:
            pr_data = json.loads(response.read().decode())
        
        # Parse PR info
        pr = PullRequest(
            number=pr_data['number'],
            title=pr_data['title'],
            description=pr_data.get('body', ''),
            author=pr_data['user']['login'],
            source_branch=pr_data['head']['ref'],
            target_branch=pr_data['base']['ref'],
            state=pr_data['state']
        )
        
        # Fetch PR diff
        diff_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
        headers['Accept'] = 'application/vnd.github.v3.diff'
        req = urllib.request.Request(diff_url, headers=headers)
        with urllib.request.urlopen(req) as response:
            diff = response.read().decode()
        
        # Fetch changed files
        files_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}/files"
        headers['Accept'] = 'application/vnd.github.v3+json'
        req = urllib.request.Request(files_url, headers=headers)
        with urllib.request.urlopen(req) as response:
            files_data = json.loads(response.read().decode())
        
        pr.files_changed = [f['filename'] for f in files_data]
        
        # Analyze for compliance
        deviations = []
        if self.compliance_analyzer:
            deviations = self.compliance_analyzer.analyze_diff(diff)
        
        return {
            'pull_request': pr.to_dict(),
            'diff_summary': self._summarize_diff(diff),
            'deviations': [d.to_dict() for d in deviations],
            'total_deviations': len(deviations),
            'critical_count': len([d for d in deviations if d.rule.severity == 'critical']),
            'warning_count': len([d for d in deviations if d.rule.severity == 'warning']),
            'compliance_passed': len([d for d in deviations if d.rule.severity == 'critical']) == 0
        }
    
    def _get_commit_info(self, repo_path: Path, commit_hash: str) -> GitCommit:
        """Get information about a specific commit"""
        format_str = '%H%n%an%n%ae%n%s%n%ci'
        output = self._run_git_command(
            repo_path,
            ['show', '-s', f'--format={format_str}', commit_hash]
        )
        
        lines = output.strip().split('\n')
        
        # Get files changed
        files_output = self._run_git_command(
            repo_path,
            ['show', '--name-only', '--format=', commit_hash]
        )
        files = [f for f in files_output.strip().split('\n') if f]
        
        # Get stats
        stats_output = self._run_git_command(
            repo_path,
            ['show', '--stat', '--format=', commit_hash]
        )
        additions = 0
        deletions = 0
        stats_match = re.search(r'(\d+) insertions?\(\+\)', stats_output)
        if stats_match:
            additions = int(stats_match.group(1))
        stats_match = re.search(r'(\d+) deletions?\(-\)', stats_output)
        if stats_match:
            deletions = int(stats_match.group(1))
        
        return GitCommit(
            hash=lines[0] if len(lines) > 0 else commit_hash,
            author=lines[1] if len(lines) > 1 else 'Unknown',
            author_email=lines[2] if len(lines) > 2 else '',
            message=lines[3] if len(lines) > 3 else '',
            timestamp=lines[4] if len(lines) > 4 else '',
            files_changed=files,
            additions=additions,
            deletions=deletions
        )
    
    def _get_commit_diff(self, repo_path: Path, commit_hash: str) -> str:
        """Get the diff for a specific commit"""
        return self._run_git_command(
            repo_path,
            ['show', '--format=', commit_hash]
        )
    
    def _run_git_command(self, repo_path: Path, args: List[str]) -> str:
        """Run a git command and return output"""
        result = subprocess.run(
            ['git'] + args,
            cwd=str(repo_path),
            capture_output=True,
            text=True
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Git command failed: {result.stderr}")
        
        return result.stdout
    
    def _clone_repo(self, repo_url: str, depth: int = 1) -> str:
        """Clone a repository to a temp directory"""
        temp_dir = tempfile.mkdtemp(prefix='git_analyzer_')
        self.temp_dirs.append(temp_dir)
        
        subprocess.run(
            ['git', 'clone', '--depth', str(depth), repo_url, temp_dir],
            capture_output=True,
            check=True
        )
        
        return temp_dir
    
    def _cleanup_temp_dir(self, temp_dir: str):
        """Clean up a temporary directory"""
        import shutil
        if temp_dir in self.temp_dirs:
            self.temp_dirs.remove(temp_dir)
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
    
    def _summarize_diff(self, diff: str) -> Dict[str, Any]:
        """Generate a summary of a diff"""
        files_changed = set()
        additions = 0
        deletions = 0
        
        for line in diff.split('\n'):
            if line.startswith('+++ b/'):
                files_changed.add(line[6:])
            elif line.startswith('+') and not line.startswith('+++'):
                additions += 1
            elif line.startswith('-') and not line.startswith('---'):
                deletions += 1
        
        return {
            'files_changed': list(files_changed),
            'files_count': len(files_changed),
            'additions': additions,
            'deletions': deletions
        }
    
    def cleanup(self):
        """Clean up all temporary directories"""
        for temp_dir in list(self.temp_dirs):
            self._cleanup_temp_dir(temp_dir)


class GitWebhookHandler:
    """Handles incoming Git webhooks from various providers"""
    
    def __init__(self, git_analyzer: GitAnalyzer, github_secret: str = None, gitlab_secret: str = None):
        self.git_analyzer = git_analyzer
        self.github_secret = github_secret
        self.gitlab_secret = gitlab_secret
    
    def verify_github_signature(self, payload: bytes, signature: str) -> bool:
        """Verify GitHub webhook signature"""
        if not self.github_secret:
            return True  # No secret configured, skip verification
        
        expected = 'sha256=' + hmac.new(
            self.github_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)
    
    def verify_gitlab_token(self, token: str) -> bool:
        """Verify GitLab webhook token"""
        if not self.gitlab_secret:
            return True  # No secret configured, skip verification
        
        return hmac.compare_digest(self.gitlab_secret, token)
    
    def parse_github_webhook(self, payload: Dict[str, Any], event_type: str) -> WebhookPayload:
        """Parse a GitHub webhook payload"""
        webhook = WebhookPayload(
            provider=GitProvider.GITHUB,
            event_type=event_type,
            repository=payload.get('repository', {}).get('full_name', ''),
            branch='',
            raw_payload=payload
        )
        
        if event_type == 'push':
            webhook.branch = payload.get('ref', '').replace('refs/heads/', '')
            
            for commit_data in payload.get('commits', []):
                commit = GitCommit(
                    hash=commit_data.get('id', ''),
                    author=commit_data.get('author', {}).get('name', ''),
                    author_email=commit_data.get('author', {}).get('email', ''),
                    message=commit_data.get('message', ''),
                    timestamp=commit_data.get('timestamp', ''),
                    files_changed=(
                        commit_data.get('added', []) + 
                        commit_data.get('modified', []) + 
                        commit_data.get('removed', [])
                    )
                )
                webhook.commits.append(commit)
        
        elif event_type == 'pull_request':
            pr_data = payload.get('pull_request', {})
            webhook.branch = pr_data.get('head', {}).get('ref', '')
            
            webhook.pull_request = PullRequest(
                number=pr_data.get('number', 0),
                title=pr_data.get('title', ''),
                description=pr_data.get('body', ''),
                author=pr_data.get('user', {}).get('login', ''),
                source_branch=pr_data.get('head', {}).get('ref', ''),
                target_branch=pr_data.get('base', {}).get('ref', ''),
                state=pr_data.get('state', '')
            )
        
        return webhook
    
    def parse_gitlab_webhook(self, payload: Dict[str, Any]) -> WebhookPayload:
        """Parse a GitLab webhook payload"""
        event_type = payload.get('object_kind', 'push')
        
        webhook = WebhookPayload(
            provider=GitProvider.GITLAB,
            event_type=event_type,
            repository=payload.get('project', {}).get('path_with_namespace', ''),
            branch='',
            raw_payload=payload
        )
        
        if event_type == 'push':
            webhook.branch = payload.get('ref', '').replace('refs/heads/', '')
            
            for commit_data in payload.get('commits', []):
                commit = GitCommit(
                    hash=commit_data.get('id', ''),
                    author=commit_data.get('author', {}).get('name', ''),
                    author_email=commit_data.get('author', {}).get('email', ''),
                    message=commit_data.get('message', ''),
                    timestamp=commit_data.get('timestamp', ''),
                    files_changed=(
                        commit_data.get('added', []) + 
                        commit_data.get('modified', []) + 
                        commit_data.get('removed', [])
                    )
                )
                webhook.commits.append(commit)
        
        elif event_type == 'merge_request':
            mr_data = payload.get('object_attributes', {})
            webhook.branch = mr_data.get('source_branch', '')
            
            webhook.pull_request = PullRequest(
                number=mr_data.get('iid', 0),
                title=mr_data.get('title', ''),
                description=mr_data.get('description', ''),
                author=payload.get('user', {}).get('username', ''),
                source_branch=mr_data.get('source_branch', ''),
                target_branch=mr_data.get('target_branch', ''),
                state=mr_data.get('state', '')
            )
        
        return webhook
    
    async def handle_github_push(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a GitHub push webhook
        
        Args:
            payload: GitHub webhook payload
            
        Returns:
            Compliance analysis results
        """
        webhook = self.parse_github_webhook(payload, 'push')
        
        # Get the compare URL to fetch the diff
        compare_url = payload.get('compare', '')
        
        results = {
            'provider': 'github',
            'event': 'push',
            'repository': webhook.repository,
            'branch': webhook.branch,
            'commits_analyzed': len(webhook.commits),
            'deviations': [],
            'compliance_passed': True
        }
        
        # If we have a local repo path, analyze locally
        # Otherwise, we'll analyze based on commit data
        
        # Analyze each commit's changes (from webhook data)
        all_deviations = []
        for commit in webhook.commits:
            # For each file changed, we might want to fetch and analyze
            # This is a simplified version - in production, you'd fetch actual file content
            for file_path in commit.files_changed:
                if self._is_analyzable_file(file_path):
                    # Note: In production, fetch actual diff content
                    pass
        
        results['deviations'] = [d.to_dict() for d in all_deviations]
        results['total_deviations'] = len(all_deviations)
        results['critical_count'] = len([d for d in all_deviations if d.rule.severity == 'critical'])
        results['compliance_passed'] = results['critical_count'] == 0
        
        return results
    
    async def handle_github_pull_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a GitHub pull request webhook
        
        Args:
            payload: GitHub webhook payload
            
        Returns:
            Compliance analysis results
        """
        webhook = self.parse_github_webhook(payload, 'pull_request')
        
        action = payload.get('action', '')
        
        results = {
            'provider': 'github',
            'event': 'pull_request',
            'action': action,
            'repository': webhook.repository,
            'pr_number': webhook.pull_request.number if webhook.pull_request else 0,
            'pr_title': webhook.pull_request.title if webhook.pull_request else '',
            'deviations': [],
            'compliance_passed': True
        }
        
        # Only analyze on opened, synchronize, or reopened
        if action in ['opened', 'synchronize', 'reopened']:
            if webhook.pull_request:
                # Parse repo owner and name
                parts = webhook.repository.split('/')
                if len(parts) == 2:
                    owner, repo = parts
                    try:
                        analysis = self.git_analyzer.analyze_pr_from_github(
                            owner, repo, webhook.pull_request.number
                        )
                        results.update(analysis)
                    except Exception as e:
                        results['error'] = str(e)
        
        return results
    
    async def handle_gitlab_push(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a GitLab push webhook"""
        webhook = self.parse_gitlab_webhook(payload)
        
        return {
            'provider': 'gitlab',
            'event': 'push',
            'repository': webhook.repository,
            'branch': webhook.branch,
            'commits_analyzed': len(webhook.commits),
            'deviations': [],
            'compliance_passed': True
        }
    
    async def handle_gitlab_merge_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a GitLab merge request webhook"""
        webhook = self.parse_gitlab_webhook(payload)
        
        return {
            'provider': 'gitlab',
            'event': 'merge_request',
            'repository': webhook.repository,
            'mr_number': webhook.pull_request.number if webhook.pull_request else 0,
            'mr_title': webhook.pull_request.title if webhook.pull_request else '',
            'deviations': [],
            'compliance_passed': True
        }
    
    def _is_analyzable_file(self, file_path: str) -> bool:
        """Check if a file should be analyzed for compliance"""
        analyzable_extensions = [
            '.go', '.sol', '.js', '.ts', '.jsx', '.tsx',
            '.py', '.java', '.rs'
        ]
        return any(file_path.endswith(ext) for ext in analyzable_extensions)


class ComplianceGitHook:
    """Git hook for local compliance checking"""
    
    HOOK_SCRIPT = '''#!/bin/sh
# Ethereum Compliance Check - Pre-commit Hook
# Generated by Code Analysis Platform

python3 -m cli.compliance_check --repo . --commit HEAD --fail-on-critical

exit_code=$?
if [ $exit_code -ne 0 ]; then
    echo ""
    echo "Compliance check failed! Please fix critical issues before committing."
    echo "Run 'python3 -m cli.compliance_check --repo . --commit HEAD' for details."
    echo ""
fi

exit $exit_code
'''
    
    @staticmethod
    def install_hook(repo_path: str, hook_type: str = "pre-commit") -> bool:
        """
        Install a git hook for compliance checking
        
        Args:
            repo_path: Path to the git repository
            hook_type: Type of hook (pre-commit, pre-push, etc.)
            
        Returns:
            True if installed successfully
        """
        hooks_dir = Path(repo_path) / ".git" / "hooks"
        
        if not hooks_dir.exists():
            raise ValueError(f"Not a git repository: {repo_path}")
        
        hook_path = hooks_dir / hook_type
        hook_path.write_text(ComplianceGitHook.HOOK_SCRIPT)
        hook_path.chmod(0o755)
        
        return True
    
    @staticmethod
    def uninstall_hook(repo_path: str, hook_type: str = "pre-commit") -> bool:
        """
        Uninstall a compliance git hook
        
        Args:
            repo_path: Path to the git repository
            hook_type: Type of hook to uninstall
            
        Returns:
            True if uninstalled successfully
        """
        hook_path = Path(repo_path) / ".git" / "hooks" / hook_type
        
        if hook_path.exists():
            content = hook_path.read_text()
            if "Ethereum Compliance Check" in content:
                hook_path.unlink()
                return True
        
        return False


# Utility function for CI/CD integration
def create_ci_config(provider: str = "github") -> str:
    """
    Generate CI/CD configuration for compliance checking
    
    Args:
        provider: CI provider (github, gitlab, etc.)
        
    Returns:
        Configuration file content
    """
    configs = {
        "github": '''# .github/workflows/compliance.yml
name: Ethereum Compliance Check

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  compliance:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
      with:
        fetch-depth: 0
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.10'
    
    - name: Install dependencies
      run: |
        pip install -r requirements.txt
    
    - name: Run Compliance Check
      run: |
        python -m cli.compliance_check --repo . --commit ${{ github.sha }} --output compliance-report.json
    
    - name: Upload Compliance Report
      uses: actions/upload-artifact@v3
      with:
        name: compliance-report
        path: compliance-report.json
    
    - name: Check for Critical Issues
      run: |
        python -m cli.compliance_check --repo . --commit ${{ github.sha }} --fail-on-critical
''',
        "gitlab": '''# .gitlab-ci.yml
stages:
  - compliance

compliance_check:
  stage: compliance
  image: python:3.10
  before_script:
    - pip install -r requirements.txt
  script:
    - python -m cli.compliance_check --repo . --commit $CI_COMMIT_SHA --output compliance-report.json
    - python -m cli.compliance_check --repo . --commit $CI_COMMIT_SHA --fail-on-critical
  artifacts:
    reports:
      compliance: compliance-report.json
    paths:
      - compliance-report.json
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
''',
    }
    
    return configs.get(provider, configs["github"])
