"""
GitHub API Client
Handles GitHub API interactions for posting PR comments and creating check runs.
"""

import json
import logging
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class GitHubComment:
    """Represents a GitHub PR comment"""
    id: int
    body: str
    user: str
    created_at: str
    updated_at: str


@dataclass
class CheckRunOutput:
    """Output for a GitHub check run"""
    title: str
    summary: str
    text: Optional[str] = None
    annotations: Optional[List[Dict[str, Any]]] = None


class GitHubClient:
    """
    GitHub API client for CI integration.
    
    Supports:
    - Posting PR comments with compliance results
    - Creating/updating check runs
    - Fetching PR information
    """
    
    def __init__(self, token: str, api_base: str = "https://api.github.com"):
        """
        Initialize GitHub client.
        
        Args:
            token: GitHub Personal Access Token or GitHub App token
            api_base: GitHub API base URL (for GitHub Enterprise support)
        """
        self.token = token
        self.api_base = api_base.rstrip('/')
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Make an authenticated request to GitHub API.
        
        Args:
            method: HTTP method (GET, POST, PATCH, DELETE)
            endpoint: API endpoint (e.g., /repos/owner/repo/issues/1/comments)
            data: Request body data
            headers: Additional headers
            
        Returns:
            Response JSON as dictionary
        """
        url = f"{self.api_base}{endpoint}"
        
        req_headers = {
            'Authorization': f'Bearer {self.token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'Ethereum-Compliance-Checker/1.0'
        }
        
        if headers:
            req_headers.update(headers)
        
        body = None
        if data:
            body = json.dumps(data).encode('utf-8')
            req_headers['Content-Type'] = 'application/json'
        
        request = urllib.request.Request(url, data=body, headers=req_headers, method=method)
        
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                response_data = response.read().decode('utf-8')
                if response_data:
                    return json.loads(response_data)
                return {}
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ''
            logger.error(f"GitHub API error: {e.code} - {error_body}")
            raise GitHubAPIError(e.code, error_body)
        except urllib.error.URLError as e:
            logger.error(f"GitHub API connection error: {e.reason}")
            raise GitHubAPIError(0, str(e.reason))
    
    # =========================================================================
    # PR Comments
    # =========================================================================
    
    def post_pr_comment(
        self, 
        owner: str, 
        repo: str, 
        pr_number: int, 
        body: str
    ) -> Dict[str, Any]:
        """
        Post a comment on a pull request.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            body: Comment body (markdown supported)
            
        Returns:
            Created comment data
        """
        endpoint = f"/repos/{owner}/{repo}/issues/{pr_number}/comments"
        return self._make_request('POST', endpoint, {'body': body})
    
    def update_pr_comment(
        self, 
        owner: str, 
        repo: str, 
        comment_id: int, 
        body: str
    ) -> Dict[str, Any]:
        """
        Update an existing PR comment.
        
        Args:
            owner: Repository owner
            repo: Repository name
            comment_id: Comment ID to update
            body: New comment body
            
        Returns:
            Updated comment data
        """
        endpoint = f"/repos/{owner}/{repo}/issues/comments/{comment_id}"
        return self._make_request('PATCH', endpoint, {'body': body})
    
    def find_bot_comment(
        self, 
        owner: str, 
        repo: str, 
        pr_number: int,
        marker: str = "<!-- ethereum-compliance-check -->"
    ) -> Optional[int]:
        """
        Find an existing bot comment by marker.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            marker: Hidden HTML marker to identify bot comments
            
        Returns:
            Comment ID if found, None otherwise
        """
        endpoint = f"/repos/{owner}/{repo}/issues/{pr_number}/comments"
        try:
            comments = self._make_request('GET', endpoint)
            for comment in comments:
                if marker in comment.get('body', ''):
                    return comment['id']
        except GitHubAPIError:
            pass
        return None
    
    def post_or_update_comment(
        self, 
        owner: str, 
        repo: str, 
        pr_number: int, 
        body: str,
        marker: str = "<!-- ethereum-compliance-check -->"
    ) -> Dict[str, Any]:
        """
        Post a new comment or update existing bot comment.
        
        This prevents multiple bot comments on the same PR.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            body: Comment body
            marker: Hidden HTML marker
            
        Returns:
            Comment data
        """
        # Add marker to body
        body_with_marker = f"{marker}\n{body}"
        
        # Try to find existing comment
        existing_id = self.find_bot_comment(owner, repo, pr_number, marker)
        
        if existing_id:
            logger.info(f"Updating existing comment {existing_id}")
            return self.update_pr_comment(owner, repo, existing_id, body_with_marker)
        else:
            logger.info(f"Creating new comment on PR #{pr_number}")
            return self.post_pr_comment(owner, repo, pr_number, body_with_marker)
    
    # =========================================================================
    # Check Runs (GitHub Checks API)
    # =========================================================================
    
    def create_check_run(
        self,
        owner: str,
        repo: str,
        head_sha: str,
        name: str = "Ethereum Compliance Check",
        status: str = "in_progress",
        conclusion: Optional[str] = None,
        output: Optional[CheckRunOutput] = None,
        details_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Create a check run for a commit.
        
        Args:
            owner: Repository owner
            repo: Repository name
            head_sha: Commit SHA to attach check to
            name: Check run name
            status: queued, in_progress, completed
            conclusion: success, failure, neutral, cancelled, skipped, timed_out, action_required
            output: Check run output details
            details_url: URL for more details
            
        Returns:
            Created check run data
        """
        endpoint = f"/repos/{owner}/{repo}/check-runs"
        
        data = {
            'name': name,
            'head_sha': head_sha,
            'status': status
        }
        
        if conclusion and status == 'completed':
            data['conclusion'] = conclusion
        
        if output:
            data['output'] = {
                'title': output.title,
                'summary': output.summary
            }
            if output.text:
                data['output']['text'] = output.text
            if output.annotations:
                data['output']['annotations'] = output.annotations
        
        if details_url:
            data['details_url'] = details_url
        
        return self._make_request('POST', endpoint, data)
    
    def update_check_run(
        self,
        owner: str,
        repo: str,
        check_run_id: int,
        status: Optional[str] = None,
        conclusion: Optional[str] = None,
        output: Optional[CheckRunOutput] = None
    ) -> Dict[str, Any]:
        """
        Update an existing check run.
        
        Args:
            owner: Repository owner
            repo: Repository name
            check_run_id: Check run ID to update
            status: New status
            conclusion: Conclusion (if completed)
            output: Updated output
            
        Returns:
            Updated check run data
        """
        endpoint = f"/repos/{owner}/{repo}/check-runs/{check_run_id}"
        
        data = {}
        
        if status:
            data['status'] = status
        
        if conclusion:
            data['conclusion'] = conclusion
        
        if output:
            data['output'] = {
                'title': output.title,
                'summary': output.summary
            }
            if output.text:
                data['output']['text'] = output.text
            if output.annotations:
                data['output']['annotations'] = output.annotations
        
        return self._make_request('PATCH', endpoint, data)
    
    # =========================================================================
    # PR Information
    # =========================================================================
    
    def get_pr(self, owner: str, repo: str, pr_number: int) -> Dict[str, Any]:
        """
        Get pull request information.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            
        Returns:
            PR data
        """
        endpoint = f"/repos/{owner}/{repo}/pulls/{pr_number}"
        return self._make_request('GET', endpoint)
    
    def get_pr_diff(self, owner: str, repo: str, pr_number: int) -> str:
        """
        Get pull request diff.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            
        Returns:
            Diff content as string
        """
        url = f"{self.api_base}/repos/{owner}/{repo}/pulls/{pr_number}"
        
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Accept': 'application/vnd.github.diff',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'Ethereum-Compliance-Checker/1.0'
        }
        
        request = urllib.request.Request(url, headers=headers)
        
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ''
            raise GitHubAPIError(e.code, error_body)
    
    def get_pr_files(self, owner: str, repo: str, pr_number: int) -> List[Dict[str, Any]]:
        """
        Get list of files changed in a PR.
        
        Args:
            owner: Repository owner
            repo: Repository name
            pr_number: Pull request number
            
        Returns:
            List of file change objects
        """
        endpoint = f"/repos/{owner}/{repo}/pulls/{pr_number}/files"
        return self._make_request('GET', endpoint)


class GitHubAPIError(Exception):
    """Exception for GitHub API errors"""
    
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"GitHub API Error {status_code}: {message}")


# =============================================================================
# Comment Formatting
# =============================================================================

def format_compliance_comment(
    deviations: List[Dict[str, Any]],
    summary: Optional[Dict[str, Any]] = None,
    pr_title: Optional[str] = None,
    commit_sha: Optional[str] = None
) -> str:
    """
    Format compliance results as a GitHub markdown comment.
    
    Args:
        deviations: List of deviation dictionaries
        summary: Optional summary statistics
        pr_title: Optional PR title for context
        commit_sha: Optional commit SHA
        
    Returns:
        Formatted markdown string
    """
    lines = []
    
    # Header
    lines.append("## 🔍 Ethereum Protocol Compliance Check")
    lines.append("")
    
    if commit_sha:
        lines.append(f"**Commit:** `{commit_sha[:8]}`")
        lines.append("")
    
    # Count by severity
    critical_count = 0
    warning_count = 0
    info_count = 0
    
    for dev in deviations:
        severity = dev.get('severity', 'info').lower()
        if severity == 'critical':
            critical_count += 1
        elif severity == 'warning':
            warning_count += 1
        else:
            info_count += 1
    
    total = len(deviations)
    
    # Status badge
    if critical_count > 0:
        lines.append("### ❌ Compliance Check Failed")
        lines.append("")
        lines.append(f"Found **{critical_count} critical** issue(s) that must be addressed.")
    elif warning_count > 0:
        lines.append("### ⚠️ Compliance Check Passed with Warnings")
        lines.append("")
        lines.append(f"Found **{warning_count} warning(s)** that should be reviewed.")
    elif total == 0:
        lines.append("### ✅ Compliance Check Passed")
        lines.append("")
        lines.append("No compliance issues found. Great work!")
        return "\n".join(lines)
    else:
        lines.append("### ✅ Compliance Check Passed")
        lines.append("")
        lines.append(f"Found **{info_count} informational** item(s).")
    
    lines.append("")
    
    # Summary table
    lines.append("| Severity | Count |")
    lines.append("|----------|-------|")
    if critical_count > 0:
        lines.append(f"| 🔴 Critical | {critical_count} |")
    if warning_count > 0:
        lines.append(f"| 🟡 Warning | {warning_count} |")
    if info_count > 0:
        lines.append(f"| 🔵 Info | {info_count} |")
    lines.append("")
    
    # Deviations details
    if deviations:
        lines.append("### Details")
        lines.append("")
        
        # Group by severity
        critical_devs = [d for d in deviations if d.get('severity', '').lower() == 'critical']
        warning_devs = [d for d in deviations if d.get('severity', '').lower() == 'warning']
        info_devs = [d for d in deviations if d.get('severity', '').lower() not in ['critical', 'warning']]
        
        for severity_group, icon, devs in [
            ('Critical', '🔴', critical_devs),
            ('Warning', '🟡', warning_devs),
            ('Info', '🔵', info_devs)
        ]:
            if not devs:
                continue
            
            for i, dev in enumerate(devs, 1):
                # Get deviation details
                rule_name = dev.get('rule', {}).get('name', dev.get('rule_id', 'Unknown'))
                description = dev.get('description', dev.get('message', 'No description'))
                file_path = dev.get('file', dev.get('location', {}).get('file', ''))
                line_num = dev.get('line', dev.get('location', {}).get('line', ''))
                recommendation = dev.get('recommendation', dev.get('fix', ''))
                spec_ref = dev.get('spec_reference', dev.get('eip', ''))
                
                # Format location
                location = file_path
                if line_num:
                    location = f"{file_path}:{line_num}"
                
                # Create collapsible section
                summary_text = f"{icon} {severity_group}: {rule_name}"
                lines.append(f"<details>")
                lines.append(f"<summary><b>{summary_text}</b></summary>")
                lines.append("")
                
                if location:
                    lines.append(f"**📍 Location:** `{location}`")
                    lines.append("")
                
                lines.append(f"**📝 Description:** {description}")
                lines.append("")
                
                if spec_ref:
                    lines.append(f"**📚 Specification:** {spec_ref}")
                    lines.append("")
                
                if recommendation:
                    lines.append(f"**💡 Recommendation:** {recommendation}")
                    lines.append("")
                
                lines.append("</details>")
                lines.append("")
    
    # Footer
    lines.append("---")
    lines.append("*Generated by [Ethereum Protocol Compliance Checker](https://github.com/ethereum/execution-specs)*")
    
    return "\n".join(lines)


def format_check_run_output(
    deviations: List[Dict[str, Any]],
    files_analyzed: int = 0
) -> CheckRunOutput:
    """
    Format compliance results as a GitHub Check Run output.
    
    Args:
        deviations: List of deviation dictionaries
        files_analyzed: Number of files analyzed
        
    Returns:
        CheckRunOutput object
    """
    critical_count = sum(1 for d in deviations if d.get('severity', '').lower() == 'critical')
    warning_count = sum(1 for d in deviations if d.get('severity', '').lower() == 'warning')
    total = len(deviations)
    
    if critical_count > 0:
        title = f"❌ {critical_count} Critical Issues Found"
    elif warning_count > 0:
        title = f"⚠️ {warning_count} Warnings Found"
    elif total > 0:
        title = f"ℹ️ {total} Informational Items"
    else:
        title = "✅ No Compliance Issues"
    
    summary_lines = [
        f"Analyzed {files_analyzed} file(s) for Ethereum protocol compliance.",
        "",
        f"- Critical: {critical_count}",
        f"- Warnings: {warning_count}",
        f"- Info: {total - critical_count - warning_count}"
    ]
    
    # Create annotations for each deviation
    annotations = []
    for dev in deviations[:50]:  # GitHub limits to 50 annotations per request
        file_path = dev.get('file', dev.get('location', {}).get('file', ''))
        line_num = dev.get('line', dev.get('location', {}).get('line', 1))
        severity = dev.get('severity', 'notice').lower()
        message = dev.get('description', dev.get('message', 'Compliance issue'))
        
        if not file_path:
            continue
        
        annotation_level = 'failure' if severity == 'critical' else ('warning' if severity == 'warning' else 'notice')
        
        annotations.append({
            'path': file_path,
            'start_line': line_num or 1,
            'end_line': line_num or 1,
            'annotation_level': annotation_level,
            'message': message,
            'title': dev.get('rule', {}).get('name', 'Compliance Issue')
        })
    
    return CheckRunOutput(
        title=title,
        summary="\n".join(summary_lines),
        text=format_compliance_comment(deviations) if deviations else None,
        annotations=annotations if annotations else None
    )


def format_dual_mode_comment(
    quick_result: Optional[Dict[str, Any]] = None,
    deep_result: Optional[Dict[str, Any]] = None,
    commit_sha: Optional[str] = None,
    pr_title: Optional[str] = None
) -> str:
    """
    Format dual-mode compliance results as a GitHub markdown comment.
    
    Shows results from both quick (diff-based) and deep (graph-based) analysis.
    
    Args:
        quick_result: Results from quick/lightweight analysis
        deep_result: Results from deep/enhanced analysis (optional)
        commit_sha: Commit SHA
        pr_title: PR title
        
    Returns:
        Formatted markdown string
    """
    lines = []
    
    # Header
    lines.append("## 🔍 Ethereum Protocol Compliance Check")
    lines.append("")
    
    if commit_sha:
        lines.append(f"**Commit:** `{commit_sha[:8]}`")
    
    # Determine mode
    mode_str = "Quick Analysis"
    if deep_result and deep_result.get('success'):
        mode_str = "Quick + Deep Analysis"
    
    lines.append(f"**Mode:** {mode_str}")
    lines.append("")
    
    # Combine deviations
    all_deviations = []
    if quick_result:
        all_deviations.extend(quick_result.get('deviations', []))
    if deep_result:
        # Add deep deviations that aren't duplicates
        existing = {d.get('description', '') for d in all_deviations}
        for d in deep_result.get('deviations', []):
            if d.get('description', '') not in existing:
                all_deviations.append(d)
    
    # Count by severity
    critical_count = sum(1 for d in all_deviations if d.get('severity', '').lower() == 'critical')
    warning_count = sum(1 for d in all_deviations if d.get('severity', '').lower() == 'warning')
    info_count = len(all_deviations) - critical_count - warning_count
    
    # Status badge
    if critical_count > 0:
        lines.append("### ❌ Compliance Check Failed")
        lines.append("")
        lines.append(f"Found **{critical_count} critical** issue(s) that must be addressed.")
    elif warning_count > 0:
        lines.append("### ⚠️ Compliance Check Passed with Warnings")
        lines.append("")
        lines.append(f"Found **{warning_count} warning(s)** that should be reviewed.")
    elif len(all_deviations) == 0:
        lines.append("### ✅ Compliance Check Passed")
        lines.append("")
        lines.append("No compliance issues found. Great work!")
    else:
        lines.append("### ✅ Compliance Check Passed")
        lines.append("")
        lines.append(f"Found **{info_count} informational** item(s).")
    
    lines.append("")
    
    # Analysis summary table
    lines.append("### Analysis Summary")
    lines.append("")
    lines.append("| Analysis | Duration | Files | Entities | Issues |")
    lines.append("|----------|----------|-------|----------|--------|")
    
    if quick_result:
        q_duration = quick_result.get('duration_seconds', 0)
        q_files = quick_result.get('files_analyzed', 0)
        q_issues = len(quick_result.get('deviations', []))
        lines.append(f"| ⚡ Quick (diff-based) | {q_duration:.1f}s | {q_files} | - | {q_issues} |")
    
    if deep_result and deep_result.get('success'):
        d_duration = deep_result.get('duration_seconds', 0)
        d_files = deep_result.get('files_analyzed', 0)
        d_entities = deep_result.get('entities_analyzed', 0)
        d_issues = len(deep_result.get('deviations', []))
        lines.append(f"| 🔬 Deep (graph-based) | {d_duration:.1f}s | {d_files} | {d_entities} | {d_issues} |")
    elif deep_result and not deep_result.get('success'):
        error = deep_result.get('error', 'Unknown error')[:50]
        lines.append(f"| 🔬 Deep (graph-based) | - | - | - | ❌ {error} |")
    
    lines.append("")
    
    # Severity summary
    if all_deviations:
        lines.append("### Issues by Severity")
        lines.append("")
        lines.append("| Severity | Count |")
        lines.append("|----------|-------|")
        if critical_count > 0:
            lines.append(f"| 🔴 Critical | {critical_count} |")
        if warning_count > 0:
            lines.append(f"| 🟡 Warning | {warning_count} |")
        if info_count > 0:
            lines.append(f"| 🔵 Info | {info_count} |")
        lines.append("")
    
    # Deviation details
    if all_deviations:
        lines.append("### Issue Details")
        lines.append("")
        
        # Group by severity
        critical_devs = [d for d in all_deviations if d.get('severity', '').lower() == 'critical']
        warning_devs = [d for d in all_deviations if d.get('severity', '').lower() == 'warning']
        info_devs = [d for d in all_deviations if d.get('severity', '').lower() not in ['critical', 'warning']]
        
        for severity_group, icon, devs in [
            ('Critical', '🔴', critical_devs),
            ('Warning', '🟡', warning_devs),
            ('Info', '🔵', info_devs)
        ]:
            if not devs:
                continue
            
            for dev in devs[:10]:  # Limit to 10 per severity
                rule_name = dev.get('rule', {}).get('name', dev.get('rule_id', 'Unknown'))
                description = dev.get('description', dev.get('message', 'No description'))
                file_path = dev.get('file', dev.get('location', {}).get('file', ''))
                line_num = dev.get('line', dev.get('location', {}).get('line', ''))
                recommendation = dev.get('recommendation', dev.get('fix', ''))
                spec_ref = dev.get('spec_reference', dev.get('eip', ''))
                source = dev.get('source', 'quick' if dev in (quick_result or {}).get('deviations', []) else 'deep')
                
                location = file_path
                if line_num:
                    location = f"{file_path}:{line_num}"
                
                source_badge = "⚡" if source == 'quick' else "🔬"
                
                lines.append(f"<details>")
                lines.append(f"<summary><b>{icon} {severity_group}: {rule_name}</b> {source_badge}</summary>")
                lines.append("")
                
                if location:
                    lines.append(f"**📍 Location:** `{location}`")
                    lines.append("")
                
                lines.append(f"**📝 Description:** {description}")
                lines.append("")
                
                if spec_ref:
                    lines.append(f"**📚 Specification:** {spec_ref}")
                    lines.append("")
                
                if recommendation:
                    lines.append(f"**💡 Recommendation:** {recommendation}")
                    lines.append("")
                
                lines.append("</details>")
                lines.append("")
    
    # Deep analysis tip
    if not deep_result:
        lines.append("---")
        lines.append("")
        lines.append("> 💡 **Tip:** Add the `compliance-deep-check` label to run comprehensive graph-based analysis.")
        lines.append("")
    
    # Footer
    lines.append("---")
    lines.append("*Generated by [Ethereum Protocol Compliance Checker](https://github.com/ethereum/execution-specs)*")
    
    return "\n".join(lines)
