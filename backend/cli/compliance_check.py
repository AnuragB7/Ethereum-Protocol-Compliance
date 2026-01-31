#!/usr/bin/env python3
"""
Ethereum Compliance Check CLI Tool
For CI/CD integration and command-line compliance checking

Usage:
    python -m cli.compliance_check --repo . --commit HEAD
    python -m cli.compliance_check --repo . --commit HEAD --fail-on-critical
    python -m cli.compliance_check --repo . --from-commit abc123 --to-commit HEAD
    python -m cli.compliance_check --codebase ./src --specs ./specs
    
GitHub CI Integration:
    python -m cli.compliance_check --repo . --commit HEAD --post-comment --pr-number 123
"""

import argparse
import json
import sys
import os
from pathlib import Path
from typing import Optional, List
from datetime import datetime


def setup_path():
    """Add project root to path"""
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


setup_path()


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser"""
    parser = argparse.ArgumentParser(
        description='Ethereum Compliance Check CLI - Check code against Ethereum specifications',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Check current commit
  python -m cli.compliance_check --repo . --commit HEAD

  # Check with failure on critical issues
  python -m cli.compliance_check --repo . --commit HEAD --fail-on-critical

  # Check a range of commits
  python -m cli.compliance_check --repo . --from-commit abc123 --to-commit HEAD

  # Check a codebase directory
  python -m cli.compliance_check --codebase ./src

  # Output to JSON file
  python -m cli.compliance_check --repo . --commit HEAD --output report.json

  # Load custom specifications
  python -m cli.compliance_check --codebase ./src --specs ./my-specs

  # Check specific EIPs
  python -m cli.compliance_check --codebase ./src --eips 20,721,1155

  # Filter by severity
  python -m cli.compliance_check --codebase ./src --severity critical
        '''
    )
    
    # Input source (mutually exclusive)
    source_group = parser.add_argument_group('Input Source')
    source_group.add_argument(
        '--repo', '-r',
        type=str,
        help='Path to git repository'
    )
    source_group.add_argument(
        '--codebase', '-c',
        type=str,
        help='Path to codebase directory (non-git)'
    )
    
    # Git options
    git_group = parser.add_argument_group('Git Options')
    git_group.add_argument(
        '--commit',
        type=str,
        default='HEAD',
        help='Commit hash to analyze (default: HEAD)'
    )
    git_group.add_argument(
        '--from-commit',
        type=str,
        help='Starting commit for range analysis (exclusive)'
    )
    git_group.add_argument(
        '--to-commit',
        type=str,
        default='HEAD',
        help='Ending commit for range analysis (default: HEAD)'
    )
    
    # Specification options
    spec_group = parser.add_argument_group('Specification Options')
    spec_group.add_argument(
        '--specs', '-s',
        type=str,
        default='./specs',
        help='Path to specifications directory (default: ./specs)'
    )
    spec_group.add_argument(
        '--eips',
        type=str,
        help='Comma-separated list of EIP numbers to check (e.g., 20,721,1155)'
    )
    spec_group.add_argument(
        '--no-builtin-rules',
        action='store_true',
        help='Disable built-in compliance rules'
    )
    
    # Filter options
    filter_group = parser.add_argument_group('Filter Options')
    filter_group.add_argument(
        '--severity',
        type=str,
        choices=['critical', 'warning', 'info'],
        help='Only show deviations of specified severity'
    )
    filter_group.add_argument(
        '--category',
        type=str,
        help='Only show deviations of specified category'
    )
    filter_group.add_argument(
        '--file-pattern',
        type=str,
        help='Only check files matching pattern (e.g., "*.go")'
    )
    
    # Output options
    output_group = parser.add_argument_group('Output Options')
    output_group.add_argument(
        '--output', '-o',
        type=str,
        help='Output file path (JSON format)'
    )
    output_group.add_argument(
        '--format', '-f',
        type=str,
        choices=['text', 'json', 'sarif'],
        default='text',
        help='Output format (default: text)'
    )
    output_group.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose output'
    )
    output_group.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Quiet output (only show summary)'
    )
    
    # Behavior options
    behavior_group = parser.add_argument_group('Behavior Options')
    behavior_group.add_argument(
        '--fail-on-critical',
        action='store_true',
        help='Exit with non-zero status if critical issues found'
    )
    behavior_group.add_argument(
        '--fail-on-warning',
        action='store_true',
        help='Exit with non-zero status if warnings found'
    )
    behavior_group.add_argument(
        '--threshold',
        type=int,
        default=0,
        help='Fail if more than N deviations found'
    )
    
    # GitHub Integration options
    github_group = parser.add_argument_group('GitHub Integration')
    github_group.add_argument(
        '--post-comment',
        action='store_true',
        help='Post results as PR comment (requires GITHUB_TOKEN env var)'
    )
    github_group.add_argument(
        '--pr-number',
        type=int,
        help='PR number for comment posting'
    )
    github_group.add_argument(
        '--repo-owner',
        type=str,
        help='Repository owner (e.g., "ethereum")'
    )
    github_group.add_argument(
        '--repo-name',
        type=str,
        help='Repository name (e.g., "go-ethereum")'
    )
    github_group.add_argument(
        '--create-check-run',
        action='store_true',
        help='Create a GitHub check run (requires GITHUB_TOKEN with checks:write permission)'
    )
    github_group.add_argument(
        '--head-sha',
        type=str,
        help='Commit SHA for check run (auto-detected if --repo is used)'
    )
    
    # Analysis Mode options
    mode_group = parser.add_argument_group('Analysis Mode')
    mode_group.add_argument(
        '--mode',
        type=str,
        choices=['quick', 'deep', 'both'],
        default='quick',
        help='Analysis mode: quick (diff-based, fast), deep (graph-based, thorough), both (run both modes)'
    )
    
    return parser


def print_banner():
    """Print CLI banner"""
    print("""
╔══════════════════════════════════════════════════════════════╗
║            Ethereum Compliance Check                          ║
║            Code Analysis Platform                             ║
╚══════════════════════════════════════════════════════════════╝
    """)


def print_summary(report: dict, args):
    """Print compliance summary"""
    total = report.get('total_deviations', 0)
    critical = report.get('critical_count', 0) or len([d for d in report.get('deviations', []) if d.get('severity') == 'critical'])
    warnings = report.get('warning_count', 0) or len([d for d in report.get('deviations', []) if d.get('severity') == 'warning'])
    info = len([d for d in report.get('deviations', []) if d.get('severity') == 'info'])
    
    print("\n" + "=" * 60)
    print("COMPLIANCE SUMMARY")
    print("=" * 60)
    
    if 'compliance_score' in report.get('summary', {}):
        score = report['summary']['compliance_score']
        print(f"Compliance Score: {score:.1f}%")
    
    print(f"\nTotal Deviations: {total}")
    print(f"  • Critical: {critical}")
    print(f"  • Warnings: {warnings}")
    print(f"  • Info: {info}")
    
    if report.get('total_files'):
        print(f"\nFiles Analyzed: {report['total_files']}")
    if report.get('total_entities'):
        print(f"Entities Analyzed: {report['total_entities']}")
    if report.get('total_rules_checked'):
        print(f"Rules Checked: {report['total_rules_checked']}")
    
    # Pass/Fail status
    passed = critical == 0
    if args.fail_on_warning:
        passed = passed and warnings == 0
    if args.threshold > 0:
        passed = passed and total <= args.threshold
    
    print("\n" + "-" * 60)
    if passed:
        print("✅ COMPLIANCE CHECK PASSED")
    else:
        print("❌ COMPLIANCE CHECK FAILED")
    print("-" * 60 + "\n")
    
    return passed


def print_deviations(deviations: list, args):
    """Print deviation details"""
    if args.quiet:
        return
    
    if not deviations:
        print("\n✅ No compliance deviations found!")
        return
    
    # Group by severity
    critical = [d for d in deviations if d.get('severity') == 'critical']
    warnings = [d for d in deviations if d.get('severity') == 'warning']
    info = [d for d in deviations if d.get('severity') == 'info']
    
    # Print critical first
    if critical:
        print("\n🔴 CRITICAL ISSUES:")
        print("-" * 40)
        for d in critical:
            _print_deviation(d, args.verbose)
    
    if warnings:
        print("\n🟡 WARNINGS:")
        print("-" * 40)
        for d in warnings:
            _print_deviation(d, args.verbose)
    
    if info and args.verbose:
        print("\n🔵 INFO:")
        print("-" * 40)
        for d in info:
            _print_deviation(d, args.verbose)


def _print_deviation(d: dict, verbose: bool):
    """Print a single deviation"""
    print(f"\n  [{d.get('rule_id', 'UNKNOWN')}] {d.get('description', 'No description')}")
    print(f"  File: {d.get('file_path', 'Unknown')}:{d.get('line_number', 0)}")
    
    if d.get('entity_name'):
        print(f"  Entity: {d.get('entity_name')} ({d.get('entity_type', 'unknown')})")
    
    if d.get('explanation'):
        print(f"  Issue: {d.get('explanation')}")
    
    if d.get('recommendation') and verbose:
        print(f"  Fix: {d.get('recommendation')}")
    
    if d.get('confidence') and verbose:
        print(f"  Confidence: {d.get('confidence') * 100:.0f}%")


def output_json(report: dict, output_path: str):
    """Output report as JSON"""
    with open(output_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f"\n📄 Report saved to: {output_path}")


def output_sarif(report: dict, output_path: str):
    """Output report in SARIF format (for GitHub code scanning)"""
    sarif = {
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {
                "driver": {
                    "name": "Ethereum Compliance Checker",
                    "version": "1.0.0",
                    "informationUri": "https://github.com/ethereum/execution-specs",
                    "rules": []
                }
            },
            "results": []
        }]
    }
    
    # Add rules
    rules_seen = set()
    for d in report.get('deviations', []):
        rule_id = d.get('rule_id', 'UNKNOWN')
        if rule_id not in rules_seen:
            rules_seen.add(rule_id)
            sarif["runs"][0]["tool"]["driver"]["rules"].append({
                "id": rule_id,
                "name": rule_id,
                "shortDescription": {"text": d.get('description', '')},
                "defaultConfiguration": {
                    "level": "error" if d.get('severity') == 'critical' else "warning"
                }
            })
    
    # Add results
    for d in report.get('deviations', []):
        sarif["runs"][0]["results"].append({
            "ruleId": d.get('rule_id', 'UNKNOWN'),
            "level": "error" if d.get('severity') == 'critical' else "warning",
            "message": {"text": d.get('explanation', d.get('description', ''))},
            "locations": [{
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": d.get('file_path', 'unknown')
                    },
                    "region": {
                        "startLine": d.get('line_number', 1)
                    }
                }
            }]
        })
    
    with open(output_path, 'w') as f:
        json.dump(sarif, f, indent=2)
    print(f"\n📄 SARIF report saved to: {output_path}")


def post_github_comment(report: dict, args) -> bool:
    """
    Post compliance results as a GitHub PR comment.
    
    Returns True if successful, False otherwise.
    """
    github_token = os.environ.get('GITHUB_TOKEN')
    if not github_token:
        print("Warning: GITHUB_TOKEN not set, skipping PR comment")
        return False
    
    # Get repo info from args or environment
    owner = args.repo_owner or os.environ.get('GITHUB_REPOSITORY_OWNER')
    repo_name = args.repo_name or os.environ.get('GITHUB_REPOSITORY', '').split('/')[-1]
    pr_number = args.pr_number or os.environ.get('GITHUB_PR_NUMBER')
    
    # Try to get from GITHUB_REF for PR events
    if not pr_number:
        github_ref = os.environ.get('GITHUB_REF', '')
        if github_ref.startswith('refs/pull/'):
            try:
                pr_number = int(github_ref.split('/')[2])
            except (IndexError, ValueError):
                pass
    
    if not owner or not repo_name:
        # Try to parse from GITHUB_REPOSITORY
        full_repo = os.environ.get('GITHUB_REPOSITORY', '')
        if '/' in full_repo:
            owner, repo_name = full_repo.split('/', 1)
    
    if not all([owner, repo_name, pr_number]):
        print("Warning: Missing GitHub repository info (owner, repo, pr_number)")
        print(f"  Owner: {owner}, Repo: {repo_name}, PR: {pr_number}")
        return False
    
    try:
        from app.services.github_client import GitHubClient, format_compliance_comment
        
        client = GitHubClient(github_token)
        
        # Format deviations
        deviations = report.get('deviations', [])
        commit_sha = args.head_sha or report.get('commit', {}).get('hash', '')
        
        comment_body = format_compliance_comment(
            deviations=deviations,
            commit_sha=commit_sha
        )
        
        # Post or update comment
        result = client.post_or_update_comment(
            owner=owner,
            repo=repo_name,
            pr_number=int(pr_number),
            body=comment_body
        )
        
        print(f"\n✅ Posted compliance comment to PR #{pr_number}")
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to post PR comment: {e}")
        return False


def create_github_check_run(report: dict, args) -> bool:
    """
    Create a GitHub check run for the commit.
    
    Returns True if successful, False otherwise.
    """
    github_token = os.environ.get('GITHUB_TOKEN')
    if not github_token:
        print("Warning: GITHUB_TOKEN not set, skipping check run")
        return False
    
    # Get repo info
    owner = args.repo_owner or os.environ.get('GITHUB_REPOSITORY_OWNER')
    repo_name = args.repo_name
    
    if not repo_name:
        full_repo = os.environ.get('GITHUB_REPOSITORY', '')
        if '/' in full_repo:
            owner, repo_name = full_repo.split('/', 1)
    
    # Get commit SHA
    head_sha = args.head_sha or os.environ.get('GITHUB_SHA')
    
    if not head_sha and args.repo:
        # Try to get from git
        import subprocess
        try:
            result = subprocess.run(
                ['git', 'rev-parse', args.commit or 'HEAD'],
                cwd=args.repo,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                head_sha = result.stdout.strip()
        except Exception:
            pass
    
    if not all([owner, repo_name, head_sha]):
        print("Warning: Missing info for check run (owner, repo, head_sha)")
        return False
    
    try:
        from app.services.github_client import GitHubClient, format_check_run_output
        
        client = GitHubClient(github_token)
        deviations = report.get('deviations', [])
        
        # Determine conclusion
        critical_count = sum(1 for d in deviations if d.get('severity', '').lower() == 'critical')
        conclusion = 'failure' if critical_count > 0 else 'success'
        
        # Format output
        output = format_check_run_output(
            deviations=deviations,
            files_analyzed=report.get('total_files', 0)
        )
        
        # Create check run
        result = client.create_check_run(
            owner=owner,
            repo=repo_name,
            head_sha=head_sha,
            name="Ethereum Compliance Check",
            status="completed",
            conclusion=conclusion,
            output=output
        )
        
        print(f"\n✅ Created check run (conclusion: {conclusion})")
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to create check run: {e}")
        return False


def analyze_codebase(codebase_path: str, specs_dir: str, eips: Optional[List[int]], args) -> dict:
    """Analyze a codebase directory"""
    from ethereum_compliance import EthereumSpecification, ComplianceAnalyzer
    from eip_fetcher import EIPFetcher
    from code_parsers import CodebaseParser
    
    if args.verbose:
        print(f"Analyzing codebase: {codebase_path}")
        print(f"Specifications directory: {specs_dir}")
    
    # Initialize specification
    spec = EthereumSpecification(specs_dir=specs_dir)
    
    # Load EIPs if specified
    if eips:
        if args.verbose:
            print(f"Loading EIPs: {eips}")
        fetcher = EIPFetcher()
        for eip_num in eips:
            try:
                eip = fetcher.fetch_eip(eip_num)
                rules = fetcher.parse_eip_to_rules(eip)
                for rule in rules:
                    spec.add_rule(rule)
            except Exception as e:
                print(f"Warning: Failed to load EIP-{eip_num}: {e}")
    
    # Parse codebase
    if args.verbose:
        print("Parsing codebase...")
    
    parser = CodebaseParser()
    parsed = parser.parse_codebase(codebase_path)
    
    # Create a mock indexer-like object
    class MockIndexer:
        def __init__(self, parsed_data):
            self.entities = parsed_data['entities']
            self.relationships = parsed_data['relationships']
        
        def get_entity_by_name(self, name):
            for e in self.entities:
                if e.name == name:
                    return e
            return None
    
    mock_indexer = MockIndexer(parsed)
    
    # Analyze
    if args.verbose:
        print("Running compliance analysis...")
    
    analyzer = ComplianceAnalyzer(spec, mock_indexer)
    report = analyzer.analyze_codebase()
    
    return report.to_dict()


def analyze_git_commit(repo_path: str, commit_hash: str, specs_dir: str, eips: Optional[List[int]], args) -> dict:
    """Analyze a git commit"""
    from ethereum_compliance import EthereumSpecification, ComplianceAnalyzer
    from git_analyzer import GitAnalyzer
    from eip_fetcher import EIPFetcher
    
    if args.verbose:
        print(f"Analyzing repository: {repo_path}")
        print(f"Commit: {commit_hash}")
    
    # Initialize specification
    spec = EthereumSpecification(specs_dir=specs_dir)
    
    # Load EIPs if specified
    if eips:
        fetcher = EIPFetcher()
        for eip_num in eips:
            try:
                eip = fetcher.fetch_eip(eip_num)
                rules = fetcher.parse_eip_to_rules(eip)
                for rule in rules:
                    spec.add_rule(rule)
            except Exception as e:
                print(f"Warning: Failed to load EIP-{eip_num}: {e}")
    
    # Create compliance analyzer
    compliance = ComplianceAnalyzer(spec)
    
    # Create git analyzer
    git_analyzer = GitAnalyzer(compliance)
    
    # Analyze commit
    result = git_analyzer.analyze_local_commit(repo_path, commit_hash)
    
    return result


def analyze_git_range(repo_path: str, from_commit: str, to_commit: str, specs_dir: str, eips: Optional[List[int]], args) -> dict:
    """Analyze a range of git commits"""
    from ethereum_compliance import EthereumSpecification, ComplianceAnalyzer
    from git_analyzer import GitAnalyzer
    from eip_fetcher import EIPFetcher
    
    if args.verbose:
        print(f"Analyzing repository: {repo_path}")
        print(f"Commit range: {from_commit}..{to_commit}")
    
    # Initialize specification
    spec = EthereumSpecification(specs_dir=specs_dir)
    
    # Load EIPs if specified
    if eips:
        fetcher = EIPFetcher()
        for eip_num in eips:
            try:
                eip = fetcher.fetch_eip(eip_num)
                rules = fetcher.parse_eip_to_rules(eip)
                for rule in rules:
                    spec.add_rule(rule)
            except Exception as e:
                print(f"Warning: Failed to load EIP-{eip_num}: {e}")
    
    # Create compliance analyzer
    compliance = ComplianceAnalyzer(spec)
    
    # Create git analyzer
    git_analyzer = GitAnalyzer(compliance)
    
    # Analyze range
    result = git_analyzer.analyze_commit_range(repo_path, from_commit, to_commit)
    
    return result


def run_mode_analysis(args, eips) -> dict:
    """
    Run analysis based on the selected mode.
    
    Modes:
    - quick: Fast diff-based analysis
    - deep: Comprehensive graph-based analysis
    - both: Run quick first, then deep
    """
    import asyncio
    import time
    
    mode = getattr(args, 'mode', 'quick')
    
    if not args.quiet:
        print(f"\n📋 Analysis Mode: {mode.upper()}")
        if mode == 'quick':
            print("   ⚡ Fast diff-based analysis")
        elif mode == 'deep':
            print("   🔬 Comprehensive graph-based analysis")
        else:
            print("   ⚡ Quick analysis + 🔬 Deep analysis")
        print("")
    
    # For PR-based analysis with GitHub integration
    if args.pr_number and args.repo_owner and args.repo_name:
        return asyncio.run(_run_pr_analysis(args, mode))
    
    # For local repository analysis
    if args.codebase:
        return analyze_codebase(args.codebase, args.specs, eips, args)
    elif args.from_commit:
        return analyze_git_range(args.repo, args.from_commit, args.to_commit, args.specs, eips, args)
    else:
        # Use enhanced analyzer for mode support
        if mode in ['deep', 'both']:
            return asyncio.run(_run_local_enhanced_analysis(args, mode, eips))
        else:
            return analyze_git_commit(args.repo, args.commit, args.specs, eips, args)


async def _run_pr_analysis(args, mode: str) -> dict:
    """Run PR-based analysis using the enhanced analyzer."""
    from app.services.enhanced_compliance import run_dual_analysis, AnalysisMode
    
    github_token = os.environ.get('GITHUB_TOKEN')
    run_deep = mode in ['deep', 'both']
    
    if args.verbose:
        print(f"Analyzing PR #{args.pr_number} on {args.repo_owner}/{args.repo_name}")
    
    try:
        # Try to use LLM analyzer if available
        llm_analyzer = None
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("API_KEY")
        api_base = os.environ.get("OPENAI_API_BASE") or os.environ.get("API_BASE")
        
        if api_key and api_base:
            try:
                from app.services.spec_indexer import SpecificationIndexer
                from app.services.llm_compliance import LLMComplianceAnalyzer
                spec_indexer = SpecificationIndexer(api_key=api_key, api_base=api_base)
                llm_analyzer = LLMComplianceAnalyzer(spec_indexer=spec_indexer, api_key=api_key, api_base=api_base)
            except Exception as e:
                if args.verbose:
                    print(f"Note: LLM analyzer not available: {e}")
        
        results = await run_dual_analysis(
            owner=args.repo_owner,
            repo=args.repo_name,
            pr_number=args.pr_number,
            run_deep=run_deep,
            github_token=github_token,
            llm_analyzer=llm_analyzer
        )
        
        # Convert to standard report format
        report = {
            'mode': mode,
            'pr_number': args.pr_number,
            'deviations': results.get('combined_deviations', []),
            'total_deviations': len(results.get('combined_deviations', [])),
            'critical_count': results.get('total_critical', 0),
            'warning_count': results.get('total_warning', 0),
            'compliance_passed': results.get('compliance_passed', True),
            'quick_analysis': results.get('quick'),
            'deep_analysis': results.get('deep')
        }
        
        return report
        
    except Exception as e:
        if args.verbose:
            import traceback
            traceback.print_exc()
        return {
            'mode': mode,
            'error': str(e),
            'deviations': [],
            'total_deviations': 0
        }


async def _run_local_enhanced_analysis(args, mode: str, eips) -> dict:
    """Run enhanced analysis on a local repository."""
    import time
    from pathlib import Path
    
    start_time = time.time()
    repo_path = args.repo
    
    if args.verbose:
        print(f"Running {mode} analysis on local repository: {repo_path}")
    
    # For deep analysis, we need to ingest into graph
    try:
        from app.services.code_graph_indexer import CodeGraphIndexer
        from app.services.llm_compliance import LLMComplianceAnalyzer
        
        # Initialize components
        indexer = CodeGraphIndexer()
        
        if args.verbose:
            print("Indexing codebase into property graph...")
        
        # Index the codebase
        indexer.index_codebase(repo_path)
        entities = indexer.entities
        
        if args.verbose:
            print(f"Found {len(entities)} entities")
        
        # Run LLM analysis on entities
        deviations = []
        llm_analyzer = None
        api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("API_KEY")
        api_base = os.environ.get("OPENAI_API_BASE") or os.environ.get("API_BASE")
        
        if api_key and api_base:
            try:
                from app.services.spec_indexer import SpecificationIndexer
                from app.services.llm_compliance import LLMComplianceAnalyzer
                spec_indexer = SpecificationIndexer(api_key=api_key, api_base=api_base)
                llm_analyzer = LLMComplianceAnalyzer(spec_indexer=spec_indexer, code_indexer=indexer, api_key=api_key, api_base=api_base)
                
                for entity in entities[:50]:  # Limit for performance
                    try:
                        result = llm_analyzer.analyze_entity(entity)
                        if result and result.deviations:
                            deviations.extend([d.to_dict() for d in result.deviations])
                    except Exception as e:
                        if args.verbose:
                            print(f"Warning: Failed to analyze entity: {e}")
            except Exception as e:
                if args.verbose:
                    print(f"Note: LLM analyzer not available: {e}")
        
        duration = time.time() - start_time
        
        # Count by severity
        critical = sum(1 for d in deviations if d.get('severity', '').lower() == 'critical')
        warning = sum(1 for d in deviations if d.get('severity', '').lower() == 'warning')
        
        return {
            'mode': mode,
            'duration_seconds': duration,
            'deviations': deviations,
            'total_deviations': len(deviations),
            'critical_count': critical,
            'warning_count': warning,
            'entities_analyzed': len(entities),
            'total_entities': len(entities),
            'compliance_passed': critical == 0
        }
        
    except Exception as e:
        if args.verbose:
            import traceback
            traceback.print_exc()
        
        # Fallback to basic analysis
        return analyze_git_commit(repo_path, args.commit, args.specs, eips, args)


def main():
    """Main entry point"""
    parser = create_parser()
    args = parser.parse_args()
    
    # Validate arguments
    if not args.repo and not args.codebase:
        print("Error: Either --repo or --codebase must be specified")
        parser.print_help()
        sys.exit(1)
    
    # Validate GitHub options
    if args.post_comment and not args.pr_number and not os.environ.get('GITHUB_REF', '').startswith('refs/pull/'):
        print("Warning: --post-comment specified but no --pr-number provided and not in PR context")
    
    if not args.quiet:
        print_banner()
    
    # Parse EIPs
    eips = None
    if args.eips:
        try:
            eips = [int(x.strip()) for x in args.eips.split(',')]
        except ValueError:
            print("Error: Invalid EIP numbers. Use comma-separated integers (e.g., 20,721)")
            sys.exit(1)
    
    try:
        # Run analysis based on mode
        report = run_mode_analysis(args, eips)
        
        # Apply filters
        if args.severity:
            report['deviations'] = [d for d in report.get('deviations', []) if d.get('severity') == args.severity]
        if args.category:
            report['deviations'] = [d for d in report.get('deviations', []) if d.get('category') == args.category]
        
        # Update counts after filtering
        report['total_deviations'] = len(report.get('deviations', []))
        
        # Output results
        if args.format == 'json' or args.output:
            output_path = args.output or 'compliance-report.json'
            if args.format == 'sarif':
                output_sarif(report, output_path.replace('.json', '.sarif.json'))
            else:
                output_json(report, output_path)
        
        if args.format == 'text' or not args.output:
            print_deviations(report.get('deviations', []), args)
            passed = print_summary(report, args)
        else:
            passed = len([d for d in report.get('deviations', []) if d.get('severity') == 'critical']) == 0
            if args.fail_on_warning:
                passed = passed and len([d for d in report.get('deviations', []) if d.get('severity') == 'warning']) == 0
        
        # GitHub Integration: Post PR comment
        if args.post_comment:
            post_github_comment(report, args)
        
        # GitHub Integration: Create check run
        if args.create_check_run:
            create_github_check_run(report, args)
        
        # Exit with appropriate status
        if args.fail_on_critical or args.fail_on_warning or args.threshold > 0:
            if not passed:
                sys.exit(1)
        
        sys.exit(0)
    
    except KeyboardInterrupt:
        print("\nInterrupted")
        sys.exit(130)
    except Exception as e:
        print(f"\nError: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
