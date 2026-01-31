#!/usr/bin/env python3
"""
Ethereum Compliance Check CLI Tool
For CI/CD integration and command-line compliance checking

Usage:
    python -m cli.compliance_check --repo . --commit HEAD
    python -m cli.compliance_check --repo . --commit HEAD --fail-on-critical
    python -m cli.compliance_check --repo . --from-commit abc123 --to-commit HEAD
    python -m cli.compliance_check --codebase ./src --specs ./specs
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
                    "informationUri": "https://github.com/your-org/compliance-checker",
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


def main():
    """Main entry point"""
    parser = create_parser()
    args = parser.parse_args()
    
    # Validate arguments
    if not args.repo and not args.codebase:
        print("Error: Either --repo or --codebase must be specified")
        parser.print_help()
        sys.exit(1)
    
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
        # Run analysis
        if args.codebase:
            report = analyze_codebase(args.codebase, args.specs, eips, args)
        elif args.from_commit:
            report = analyze_git_range(args.repo, args.from_commit, args.to_commit, args.specs, eips, args)
        else:
            report = analyze_git_commit(args.repo, args.commit, args.specs, eips, args)
        
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
