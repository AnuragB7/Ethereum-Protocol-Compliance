"""
Ethereum Specification Compliance Engine
Checks code against Ethereum specifications and reports deviations with recommendations
"""

import re
import json
import yaml
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum


class Severity(Enum):
    """Severity levels for compliance rules"""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class Category(Enum):
    """Categories for compliance rules"""
    TOKEN = "token"
    SECURITY = "security"
    GAS = "gas"
    INTERFACE = "interface"
    EVENT = "event"
    STORAGE = "storage"
    ACCESS_CONTROL = "access_control"
    REENTRANCY = "reentrancy"
    OVERFLOW = "overflow"
    GENERAL = "general"


@dataclass
class ComplianceRule:
    """Represents a single compliance rule from a specification"""
    id: str                                    # e.g., "EIP-20-TRANSFER"
    source: str                                # "EIP-20", "custom", etc.
    category: str                              # "token", "security", "gas", etc.
    severity: str                              # "critical", "warning", "info"
    description: str                           # Human-readable description
    patterns: List[str] = field(default_factory=list)    # Regex patterns to match
    must_contain: List[str] = field(default_factory=list)  # Required elements
    must_not_contain: List[str] = field(default_factory=list)  # Forbidden elements
    validator: Optional[str] = None            # Custom validator function name
    recommendation: str = ""                   # Fix suggestion
    languages: List[str] = field(default_factory=lambda: ["solidity", "go", "javascript", "typescript"])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'id': self.id,
            'source': self.source,
            'category': self.category,
            'severity': self.severity,
            'description': self.description,
            'patterns': self.patterns,
            'must_contain': self.must_contain,
            'must_not_contain': self.must_not_contain,
            'validator': self.validator,
            'recommendation': self.recommendation,
            'languages': self.languages
        }


@dataclass
class Deviation:
    """Represents a deviation from a compliance rule"""
    rule: ComplianceRule
    file_path: str
    line_number: int
    code_snippet: str
    entity_name: Optional[str] = None
    entity_type: Optional[str] = None
    explanation: str = ""                      # LLM-generated explanation
    recommendation: str = ""                   # LLM-generated fix
    confidence: float = 0.0                    # 0.0 - 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'rule_id': self.rule.id,
            'rule_source': self.rule.source,
            'severity': self.rule.severity,
            'category': self.rule.category,
            'description': self.rule.description,
            'file_path': self.file_path,
            'line_number': self.line_number,
            'code_snippet': self.code_snippet,
            'entity_name': self.entity_name,
            'entity_type': self.entity_type,
            'explanation': self.explanation,
            'recommendation': self.recommendation,
            'confidence': self.confidence
        }


@dataclass
class ComplianceReport:
    """Full compliance report for a codebase"""
    total_files: int = 0
    total_entities: int = 0
    total_rules_checked: int = 0
    deviations: List[Deviation] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def compliance_score(self) -> float:
        """Calculate overall compliance score (0-100)"""
        return self.summary.get('compliance_score', 100.0)
    
    @property
    def critical_count(self) -> int:
        """Count of critical severity deviations"""
        return len([d for d in self.deviations if d.rule.severity == 'critical'])
    
    @property
    def warning_count(self) -> int:
        """Count of warning severity deviations"""
        return len([d for d in self.deviations if d.rule.severity == 'warning'])
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'total_files': self.total_files,
            'total_entities': self.total_entities,
            'total_rules_checked': self.total_rules_checked,
            'total_deviations': len(self.deviations),
            'compliance_score': self.compliance_score,
            'critical_count': self.critical_count,
            'warning_count': self.warning_count,
            'deviations_by_severity': self._count_by_severity(),
            'deviations_by_category': self._count_by_category(),
            'deviations': [d.to_dict() for d in self.deviations],
            'summary': self.summary
        }
    
    def _count_by_severity(self) -> Dict[str, int]:
        """Count deviations by severity"""
        counts = {'critical': 0, 'warning': 0, 'info': 0}
        for d in self.deviations:
            if d.rule.severity in counts:
                counts[d.rule.severity] += 1
        return counts
    
    def _count_by_category(self) -> Dict[str, int]:
        """Count deviations by category"""
        counts = {}
        for d in self.deviations:
            cat = d.rule.category
            counts[cat] = counts.get(cat, 0) + 1
        return counts


class EthereumSpecification:
    """Manages Ethereum specifications and rules"""
    
    def __init__(self, specs_dir: str = "./specs"):
        self.specs_dir = Path(specs_dir)
        self.rules: List[ComplianceRule] = []
        self.loaded_specs: List[str] = []
        
        # Load built-in rules
        self._load_builtin_rules()
        
        # Load specs from directory if exists
        if self.specs_dir.exists():
            self.load_all_specs()
    
    def _load_builtin_rules(self):
        """Load built-in compliance rules for common EIPs"""
        builtin_rules = [
            # EIP-20 (ERC-20) Rules
            ComplianceRule(
                id="EIP-20-TRANSFER-EVENT",
                source="EIP-20",
                category="event",
                severity="critical",
                description="transfer function must emit Transfer event",
                patterns=[r"func.*[Tt]ransfer.*\{", r"function\s+transfer\s*\("],
                must_contain=["Transfer", "emit"],
                recommendation="Add Transfer event emission after balance update: emit Transfer(from, to, amount)"
            ),
            ComplianceRule(
                id="EIP-20-APPROVE-EVENT",
                source="EIP-20",
                category="event",
                severity="critical",
                description="approve function must emit Approval event",
                patterns=[r"func.*[Aa]pprove.*\{", r"function\s+approve\s*\("],
                must_contain=["Approval", "emit"],
                recommendation="Add Approval event emission: emit Approval(owner, spender, amount)"
            ),
            ComplianceRule(
                id="EIP-20-BALANCE-CHECK",
                source="EIP-20",
                category="security",
                severity="critical",
                description="transfer must check sender has sufficient balance",
                patterns=[r"func.*[Tt]ransfer.*\{", r"function\s+transfer\s*\("],
                must_contain=["balance", "require", ">="],
                recommendation="Add balance check: require(balanceOf[sender] >= amount, 'Insufficient balance')"
            ),
            ComplianceRule(
                id="EIP-20-ZERO-ADDRESS",
                source="EIP-20",
                category="security",
                severity="warning",
                description="Should check for zero address in transfer",
                patterns=[r"func.*[Tt]ransfer.*\{", r"function\s+transfer\s*\("],
                must_contain=["address(0)", "0x0", "zero"],
                recommendation="Add zero address check: require(to != address(0), 'Transfer to zero address')"
            ),
            
            # EIP-721 (NFT) Rules
            ComplianceRule(
                id="EIP-721-SAFE-TRANSFER",
                source="EIP-721",
                category="security",
                severity="critical",
                description="safeTransferFrom must check onERC721Received",
                patterns=[r"func.*[Ss]afe[Tt]ransfer.*\{", r"function\s+safeTransferFrom\s*\("],
                must_contain=["onERC721Received", "IERC721Receiver"],
                recommendation="Implement receiver check: require(IERC721Receiver(to).onERC721Received(...) == selector)"
            ),
            ComplianceRule(
                id="EIP-721-OWNER-CHECK",
                source="EIP-721",
                category="security",
                severity="critical",
                description="transferFrom must verify caller is owner or approved",
                patterns=[r"func.*[Tt]ransfer[Ff]rom.*\{", r"function\s+transferFrom\s*\("],
                must_contain=["owner", "approved", "operator"],
                recommendation="Add authorization check: require(isApprovedOrOwner(msg.sender, tokenId))"
            ),
            
            # EIP-1155 (Multi-Token) Rules
            ComplianceRule(
                id="EIP-1155-BATCH-BALANCE",
                source="EIP-1155",
                category="interface",
                severity="warning",
                description="Should implement balanceOfBatch for gas efficiency",
                patterns=[r"interface.*1155", r"ERC1155"],
                must_contain=["balanceOfBatch"],
                recommendation="Implement balanceOfBatch(address[] accounts, uint256[] ids) for batch queries"
            ),
            
            # Security Rules
            ComplianceRule(
                id="SEC-REENTRANCY",
                source="security-best-practices",
                category="reentrancy",
                severity="critical",
                description="External calls should follow checks-effects-interactions pattern",
                patterns=[r"\.call\{", r"\.transfer\(", r"\.send\(", r"external.*call"],
                must_not_contain=["state change after external call"],
                recommendation="Follow CEI pattern: perform all state changes before external calls"
            ),
            ComplianceRule(
                id="SEC-OVERFLOW",
                source="security-best-practices",
                category="overflow",
                severity="warning",
                description="Arithmetic operations should be protected against overflow",
                patterns=[r"\+\s*\d+", r"\*\s*\d+", r"-\s*\d+"],
                must_contain=["SafeMath", "unchecked", "Solidity 0.8"],
                recommendation="Use SafeMath library or Solidity 0.8+ built-in overflow checks"
            ),
            ComplianceRule(
                id="SEC-ACCESS-CONTROL",
                source="security-best-practices",
                category="access_control",
                severity="critical",
                description="Sensitive functions must have access control",
                patterns=[r"func.*(mint|burn|pause|upgrade|admin).*\{", r"function\s+(mint|burn|pause|upgrade)"],
                must_contain=["onlyOwner", "onlyRole", "require", "modifier", "auth"],
                recommendation="Add access control modifier: onlyOwner, onlyRole(ADMIN_ROLE), or custom auth check"
            ),
            
            # Gas Optimization Rules
            ComplianceRule(
                id="GAS-STORAGE-CACHE",
                source="gas-optimization",
                category="gas",
                severity="info",
                description="Storage variables accessed multiple times should be cached",
                patterns=[r"storage\[", r"mapping.*\[.*\].*\["],
                recommendation="Cache storage reads in memory: uint256 cached = storageVar; use cached in loop"
            ),
            ComplianceRule(
                id="GAS-LOOP-LENGTH",
                source="gas-optimization",
                category="gas",
                severity="info",
                description="Array length should be cached outside loops",
                patterns=[r"for.*\.length", r"for.*len\("],
                recommendation="Cache array length: uint256 len = array.length; for(uint i; i < len;)"
            ),
            
            # Go-Ethereum Specific Rules
            ComplianceRule(
                id="GETH-ERROR-HANDLING",
                source="go-ethereum",
                category="security",
                severity="critical",
                description="Ethereum RPC calls must have proper error handling",
                patterns=[r"ethclient\.", r"client\.(Call|Send|Transact)"],
                must_contain=["err", "error", "if err"],
                languages=["go"],
                recommendation="Always check and handle errors from RPC calls: if err != nil { return err }"
            ),
            ComplianceRule(
                id="GETH-NONCE-MANAGEMENT",
                source="go-ethereum",
                category="security",
                severity="warning",
                description="Transaction nonce should be properly managed",
                patterns=[r"PendingNonceAt", r"types\.NewTransaction"],
                must_contain=["PendingNonceAt", "nonce"],
                languages=["go"],
                recommendation="Use PendingNonceAt for accurate nonce: nonce, err := client.PendingNonceAt(ctx, from)"
            ),
            ComplianceRule(
                id="GETH-GAS-ESTIMATION",
                source="go-ethereum",
                category="gas",
                severity="warning",
                description="Transaction gas should be estimated before sending",
                patterns=[r"SendTransaction", r"types\.NewTransaction"],
                must_contain=["EstimateGas", "gasLimit"],
                languages=["go"],
                recommendation="Estimate gas before transaction: gasLimit, err := client.EstimateGas(ctx, msg)"
            ),
            ComplianceRule(
                id="GETH-CONTEXT-TIMEOUT",
                source="go-ethereum",
                category="security",
                severity="warning",
                description="RPC calls should have context with timeout",
                patterns=[r"ethclient\.", r"\.CallContract", r"\.SendTransaction"],
                must_contain=["context.WithTimeout", "ctx"],
                languages=["go"],
                recommendation="Add timeout to context: ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)"
            ),
            
            # EIP-2612 (Permit) Rules
            ComplianceRule(
                id="EIP-2612-DEADLINE",
                source="EIP-2612",
                category="security",
                severity="critical",
                description="Permit must check deadline has not passed",
                patterns=[r"func.*[Pp]ermit.*\{", r"function\s+permit\s*\("],
                must_contain=["deadline", "block.timestamp", "require"],
                recommendation="Add deadline check: require(block.timestamp <= deadline, 'Permit expired')"
            ),
            ComplianceRule(
                id="EIP-2612-NONCE",
                source="EIP-2612",
                category="security",
                severity="critical",
                description="Permit must increment nonce to prevent replay",
                patterns=[r"func.*[Pp]ermit.*\{", r"function\s+permit\s*\("],
                must_contain=["nonces", "++", "increment"],
                recommendation="Increment nonce after use: _nonces[owner]++"
            ),
            
            # EIP-4626 (Tokenized Vault) Rules
            ComplianceRule(
                id="EIP-4626-PREVIEW",
                source="EIP-4626",
                category="interface",
                severity="warning",
                description="Vault should implement preview functions",
                patterns=[r"interface.*4626", r"ERC4626"],
                must_contain=["previewDeposit", "previewMint", "previewWithdraw", "previewRedeem"],
                recommendation="Implement all preview functions for accurate share/asset calculations"
            ),
            ComplianceRule(
                id="EIP-4626-ROUNDING",
                source="EIP-4626",
                category="security",
                severity="warning",
                description="Vault conversions must round in favor of the vault",
                patterns=[r"convertToShares", r"convertToAssets"],
                must_contain=["round", "ceil", "floor"],
                recommendation="Round down for deposits/mints (shares), round up for withdrawals/redeems (assets)"
            ),
            
            # EIP-165 (Interface Detection) Rules
            ComplianceRule(
                id="EIP-165-SUPPORT",
                source="EIP-165",
                category="interface",
                severity="info",
                description="Contract should implement supportsInterface",
                patterns=[r"interface", r"contract.*ERC"],
                must_contain=["supportsInterface", "interfaceId"],
                recommendation="Implement EIP-165: function supportsInterface(bytes4 interfaceId) returns (bool)"
            ),
        ]
        
        self.rules.extend(builtin_rules)
        self.loaded_specs.append("builtin")
    
    def load_spec_file(self, file_path: str) -> int:
        """Load specification from a YAML or JSON file"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Specification file not found: {file_path}")
        
        content = path.read_text()
        
        if path.suffix in ['.yaml', '.yml']:
            data = yaml.safe_load(content)
        elif path.suffix == '.json':
            data = json.loads(content)
        else:
            raise ValueError(f"Unsupported file format: {path.suffix}")
        
        rules_loaded = 0
        spec_info = data.get('specification', {})
        spec_id = spec_info.get('id', path.stem)
        
        for rule_data in data.get('rules', []):
            rule = ComplianceRule(
                id=rule_data.get('id', f"{spec_id}-{rules_loaded}"),
                source=spec_id,
                category=rule_data.get('category', 'general'),
                severity=rule_data.get('severity', 'info'),
                description=rule_data.get('description', ''),
                patterns=rule_data.get('patterns', []),
                must_contain=rule_data.get('must_contain', []),
                must_not_contain=rule_data.get('must_not_contain', []),
                validator=rule_data.get('validator'),
                recommendation=rule_data.get('recommendation', ''),
                languages=rule_data.get('languages', ['solidity', 'go', 'javascript', 'typescript'])
            )
            self.rules.append(rule)
            rules_loaded += 1
        
        self.loaded_specs.append(spec_id)
        return rules_loaded
    
    def load_all_specs(self) -> int:
        """Load all specification files from specs directory"""
        total_loaded = 0
        for ext in ['*.yaml', '*.yml', '*.json']:
            for file_path in self.specs_dir.glob(ext):
                try:
                    loaded = self.load_spec_file(str(file_path))
                    total_loaded += loaded
                    print(f"Loaded {loaded} rules from {file_path.name}")
                except Exception as e:
                    print(f"Error loading {file_path}: {e}")
        return total_loaded
    
    def add_rule(self, rule: ComplianceRule):
        """Add a single rule"""
        self.rules.append(rule)
    
    def get_rules_by_source(self, source: str) -> List[ComplianceRule]:
        """Get all rules from a specific source (e.g., 'EIP-20')"""
        return [r for r in self.rules if r.source == source]
    
    def get_rules_by_category(self, category: str) -> List[ComplianceRule]:
        """Get all rules for a specific category"""
        return [r for r in self.rules if r.category == category]
    
    def get_rules_by_severity(self, severity: str) -> List[ComplianceRule]:
        """Get all rules with specific severity"""
        return [r for r in self.rules if r.severity == severity]
    
    def get_rules_for_language(self, language: str) -> List[ComplianceRule]:
        """Get rules applicable to a specific language"""
        return [r for r in self.rules if language.lower() in [l.lower() for l in r.languages]]
    
    def to_dict(self) -> Dict[str, Any]:
        """Export specifications as dictionary"""
        return {
            'loaded_specs': self.loaded_specs,
            'total_rules': len(self.rules),
            'rules': [r.to_dict() for r in self.rules]
        }


class ComplianceAnalyzer:
    """Analyzes code for compliance with Ethereum specifications"""
    
    def __init__(self, specification: EthereumSpecification, indexer=None):
        self.specification = specification
        self.indexer = indexer
        self.custom_validators: Dict[str, Callable] = {}
        
        # Register built-in validators
        self._register_builtin_validators()
    
    def _register_builtin_validators(self):
        """Register built-in custom validators"""
        self.custom_validators['check_reentrancy'] = self._validate_reentrancy
        self.custom_validators['check_overflow'] = self._validate_overflow
        self.custom_validators['check_access_control'] = self._validate_access_control
    
    def _validate_reentrancy(self, code: str, entity_name: str) -> Optional[str]:
        """Check for potential reentrancy vulnerabilities"""
        # Check if there are state changes after external calls
        external_call_patterns = [r'\.call\{', r'\.transfer\(', r'\.send\(']
        state_change_patterns = [r'=\s*\w+', r'\+\+', r'--', r'\+=', r'-=']
        
        for call_pattern in external_call_patterns:
            call_match = re.search(call_pattern, code)
            if call_match:
                after_call = code[call_match.end():]
                for state_pattern in state_change_patterns:
                    if re.search(state_pattern, after_call):
                        return "Potential reentrancy: state change detected after external call"
        return None
    
    def _validate_overflow(self, code: str, entity_name: str) -> Optional[str]:
        """Check for potential overflow vulnerabilities"""
        # Check for arithmetic without SafeMath in older Solidity
        if 'pragma solidity' in code:
            version_match = re.search(r'pragma solidity\s*\^?([\d.]+)', code)
            if version_match:
                version = version_match.group(1)
                if version < '0.8.0' and 'SafeMath' not in code:
                    if re.search(r'[\+\-\*]', code):
                        return "Potential overflow: arithmetic without SafeMath in Solidity < 0.8.0"
        return None
    
    def _validate_access_control(self, code: str, entity_name: str) -> Optional[str]:
        """Check for missing access control on sensitive functions"""
        sensitive_funcs = ['mint', 'burn', 'pause', 'unpause', 'upgrade', 'setOwner', 'withdraw']
        
        for func in sensitive_funcs:
            if func.lower() in entity_name.lower():
                access_patterns = ['onlyOwner', 'onlyRole', 'require.*msg.sender', 'auth', 'modifier']
                if not any(re.search(p, code, re.IGNORECASE) for p in access_patterns):
                    return f"Missing access control on sensitive function: {entity_name}"
        return None
    
    def analyze_entity(self, entity, rules: Optional[List[ComplianceRule]] = None) -> List[Deviation]:
        """
        Analyze a single code entity for compliance
        
        Args:
            entity: CodeEntity to analyze
            rules: Optional list of rules to check (defaults to all rules)
            
        Returns:
            List of deviations found
        """
        deviations = []
        
        if rules is None:
            rules = self.specification.get_rules_for_language(entity.language)
        
        code = entity.body if entity.body else ""
        
        for rule in rules:
            # Skip if language doesn't match
            if entity.language.lower() not in [l.lower() for l in rule.languages]:
                continue
            
            # Check pattern match
            pattern_matched = False
            for pattern in rule.patterns:
                if re.search(pattern, entity.name, re.IGNORECASE) or re.search(pattern, code, re.IGNORECASE):
                    pattern_matched = True
                    break
            
            if not pattern_matched and rule.patterns:
                continue
            
            # Check must_contain
            missing_required = []
            for required in rule.must_contain:
                if required.lower() not in code.lower() and required.lower() not in entity.name.lower():
                    missing_required.append(required)
            
            # Check must_not_contain
            found_forbidden = []
            for forbidden in rule.must_not_contain:
                if forbidden.lower() in code.lower():
                    found_forbidden.append(forbidden)
            
            # Run custom validator if specified
            validator_result = None
            if rule.validator and rule.validator in self.custom_validators:
                validator_result = self.custom_validators[rule.validator](code, entity.name)
            
            # Create deviation if any check failed
            if missing_required or found_forbidden or validator_result:
                explanation_parts = []
                if missing_required:
                    explanation_parts.append(f"Missing required elements: {', '.join(missing_required)}")
                if found_forbidden:
                    explanation_parts.append(f"Contains forbidden elements: {', '.join(found_forbidden)}")
                if validator_result:
                    explanation_parts.append(validator_result)
                
                deviation = Deviation(
                    rule=rule,
                    file_path=entity.file_path,
                    line_number=entity.line_start,
                    code_snippet=code[:500] if code else entity.name,
                    entity_name=entity.name,
                    entity_type=entity.type,
                    explanation="; ".join(explanation_parts),
                    recommendation=rule.recommendation,
                    confidence=0.8 if pattern_matched else 0.6
                )
                deviations.append(deviation)
        
        return deviations
    
    def analyze_codebase(self, entities=None) -> ComplianceReport:
        """
        Analyze entire indexed codebase for compliance
        
        Args:
            entities: Optional list of entities to analyze. If not provided,
                     uses entities from self.indexer
        
        Returns:
            ComplianceReport with all deviations
        """
        # Use provided entities or fall back to indexer
        if entities is None:
            if not self.indexer:
                raise ValueError("No indexer configured and no entities provided.")
            entities = self.indexer.entities
        
        if not entities:
            # Return empty report if no entities
            return ComplianceReport(
                total_files=0,
                total_entities=0,
                total_rules_checked=len(self.specification.rules),
                summary={'compliance_score': 100.0}
            )
        
        report = ComplianceReport()
        report.total_rules_checked = len(self.specification.rules)
        
        # Get unique files
        files = set()
        for entity in entities:
            if hasattr(entity, 'file_path'):
                files.add(entity.file_path)
        report.total_files = len(files)
        report.total_entities = len(entities)
        
        # Analyze each entity
        for entity in entities:
            deviations = self.analyze_entity(entity)
            report.deviations.extend(deviations)
        
        # Generate summary
        report.summary = {
            'compliance_score': self._calculate_compliance_score(report),
            'critical_issues': len([d for d in report.deviations if d.rule.severity == 'critical']),
            'warnings': len([d for d in report.deviations if d.rule.severity == 'warning']),
            'info': len([d for d in report.deviations if d.rule.severity == 'info']),
            'most_common_issues': self._get_most_common_issues(report.deviations),
            'files_with_issues': len(set(d.file_path for d in report.deviations))
        }
        
        return report
    
    def analyze_code_string(self, code: str, language: str, entity_name: str = "anonymous") -> List[Deviation]:
        """
        Analyze a code string directly (for git diff analysis)
        
        Args:
            code: Code string to analyze
            language: Programming language
            entity_name: Name to use for the entity
            
        Returns:
            List of deviations
        """
        from code_parsers import CodeEntity
        
        # Create a temporary entity
        entity = CodeEntity(
            name=entity_name,
            type='function',
            file_path='<string>',
            line_start=1,
            line_end=code.count('\n') + 1,
            language=language,
            body=code
        )
        
        return self.analyze_entity(entity)
    
    def analyze_diff(self, diff_content: str, base_language: str = "go") -> List[Deviation]:
        """
        Analyze a git diff for compliance issues
        
        Args:
            diff_content: Git diff content
            base_language: Default language for analysis
            
        Returns:
            List of deviations in the changed code
        """
        deviations = []
        
        # Parse diff to extract changed files and code
        current_file = None
        current_additions = []
        line_number = 0
        
        for line in diff_content.split('\n'):
            # New file in diff
            if line.startswith('+++ b/'):
                # Analyze previous file's additions if any
                if current_file and current_additions:
                    code = '\n'.join(current_additions)
                    lang = self._detect_language_from_file(current_file)
                    file_deviations = self.analyze_code_string(code, lang, current_file)
                    for d in file_deviations:
                        d.file_path = current_file
                    deviations.extend(file_deviations)
                
                current_file = line[6:]  # Remove '+++ b/'
                current_additions = []
                line_number = 0
            
            # Line number marker
            elif line.startswith('@@'):
                match = re.search(r'\+(\d+)', line)
                if match:
                    line_number = int(match.group(1))
            
            # Added line
            elif line.startswith('+') and not line.startswith('+++'):
                current_additions.append(line[1:])
                line_number += 1
            
            # Context line (for both old and new)
            elif not line.startswith('-'):
                line_number += 1
        
        # Analyze last file
        if current_file and current_additions:
            code = '\n'.join(current_additions)
            lang = self._detect_language_from_file(current_file)
            file_deviations = self.analyze_code_string(code, lang, current_file)
            for d in file_deviations:
                d.file_path = current_file
            deviations.extend(file_deviations)
        
        return deviations
    
    def _detect_language_from_file(self, file_path: str) -> str:
        """Detect programming language from file extension"""
        ext_map = {
            '.go': 'go',
            '.sol': 'solidity',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.jsx': 'javascript',
            '.tsx': 'typescript',
            '.py': 'python',
            '.java': 'java',
            '.rs': 'rust'
        }
        
        for ext, lang in ext_map.items():
            if file_path.endswith(ext):
                return lang
        return 'go'  # Default
    
    def _calculate_compliance_score(self, report: ComplianceReport) -> float:
        """Calculate overall compliance score (0-100)"""
        if report.total_entities == 0:
            return 100.0
        
        # Weight deviations by severity
        weights = {'critical': 10, 'warning': 3, 'info': 1}
        total_weight = sum(weights.get(d.rule.severity, 1) for d in report.deviations)
        
        # Max possible weight (assume 1 critical per entity as baseline)
        max_weight = report.total_entities * weights['critical']
        
        if max_weight == 0:
            return 100.0
        
        score = max(0, 100 - (total_weight / max_weight * 100))
        return round(score, 2)
    
    def _get_most_common_issues(self, deviations: List[Deviation], top_n: int = 5) -> List[Dict[str, Any]]:
        """Get the most common compliance issues"""
        issue_counts = {}
        for d in deviations:
            key = d.rule.id
            if key not in issue_counts:
                issue_counts[key] = {
                    'rule_id': d.rule.id,
                    'description': d.rule.description,
                    'severity': d.rule.severity,
                    'count': 0
                }
            issue_counts[key]['count'] += 1
        
        sorted_issues = sorted(issue_counts.values(), key=lambda x: x['count'], reverse=True)
        return sorted_issues[:top_n]
    
    def analyze_with_llm(self, entity, rule: ComplianceRule) -> Optional[Deviation]:
        """
        Use LLM for deeper compliance analysis
        
        Args:
            entity: CodeEntity to analyze
            rule: ComplianceRule to check
            
        Returns:
            Deviation if found, None otherwise
        """
        if not self.indexer or not hasattr(self.indexer, 'query'):
            return None
        
        prompt = f"""
        Analyze this {entity.language} code for compliance with {rule.source}:
        
        Rule ID: {rule.id}
        Rule Description: {rule.description}
        Severity: {rule.severity}
        
        Code Entity: {entity.name} ({entity.type})
        File: {entity.file_path}
        
        Code:
        ```
        {entity.body[:2000] if entity.body else 'No body available'}
        ```
        
        Determine:
        1. Is there a deviation from the specification? (YES/NO)
        2. If YES, what is the specific issue?
        3. How should it be fixed?
        4. Confidence level (0-100%)
        
        Respond in this exact format:
        DEVIATION: YES/NO
        ISSUE: <description of the issue or "N/A">
        FIX: <recommended fix or "N/A">
        CONFIDENCE: <number 0-100>
        """
        
        try:
            response = self.indexer.query(prompt)
            
            # Parse response
            is_deviation = 'DEVIATION: YES' in response.upper()
            
            if is_deviation:
                issue_match = re.search(r'ISSUE:\s*(.+?)(?=FIX:|$)', response, re.DOTALL | re.IGNORECASE)
                fix_match = re.search(r'FIX:\s*(.+?)(?=CONFIDENCE:|$)', response, re.DOTALL | re.IGNORECASE)
                conf_match = re.search(r'CONFIDENCE:\s*(\d+)', response, re.IGNORECASE)
                
                return Deviation(
                    rule=rule,
                    file_path=entity.file_path,
                    line_number=entity.line_start,
                    code_snippet=entity.body[:500] if entity.body else entity.name,
                    entity_name=entity.name,
                    entity_type=entity.type,
                    explanation=issue_match.group(1).strip() if issue_match else rule.description,
                    recommendation=fix_match.group(1).strip() if fix_match else rule.recommendation,
                    confidence=float(conf_match.group(1)) / 100 if conf_match else 0.7
                )
        except Exception as e:
            print(f"LLM analysis failed: {e}")
        
        return None


# Utility functions
def create_compliance_report_json(report: ComplianceReport) -> str:
    """Convert compliance report to JSON string"""
    return json.dumps(report.to_dict(), indent=2)


def load_specification_from_eip(eip_number: int, eip_fetcher) -> List[ComplianceRule]:
    """Load compliance rules from an EIP document"""
    eip_doc = eip_fetcher.fetch_eip(eip_number)
    return eip_fetcher.parse_eip_to_rules(eip_doc)
