"""
EIP Fetcher - Fetches and parses Ethereum Improvement Proposals
Downloads official EIPs from ethereum.org and converts them to compliance rules
"""

import re
import json
import hashlib
import ssl
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import urllib.request
import urllib.error


@dataclass
class EIPDocument:
    """Represents a parsed EIP document"""
    number: int
    title: str
    status: str
    type: str  # Standards Track, Meta, Informational
    category: Optional[str] = None  # Core, ERC, Networking, Interface
    created: Optional[str] = None
    requires: List[int] = field(default_factory=list)
    abstract: str = ""
    motivation: str = ""
    specification: str = ""
    rationale: str = ""
    security_considerations: str = ""
    raw_content: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'number': self.number,
            'title': self.title,
            'status': self.status,
            'type': self.type,
            'category': self.category,
            'created': self.created,
            'requires': self.requires,
            'abstract': self.abstract,
            'motivation': self.motivation,
            'specification': self.specification,
            'rationale': self.rationale,
            'security_considerations': self.security_considerations
        }


class EIPFetcher:
    """Fetches and parses Ethereum Improvement Proposals"""
    
    # Common EIP URLs
    GITHUB_RAW_BASE = "https://raw.githubusercontent.com/ethereum/EIPs/master/EIPS/eip-{}.md"
    GITHUB_ERCS_BASE = "https://raw.githubusercontent.com/ethereum/ERCs/master/ERCS/erc-{}.md"
    
    # Well-known token EIPs
    TOKEN_EIPS = {
        20: "ERC-20 Token Standard",
        721: "ERC-721 Non-Fungible Token",
        777: "ERC-777 Token Standard",
        1155: "ERC-1155 Multi Token Standard",
        2612: "ERC-2612 Permit Extension",
        4626: "ERC-4626 Tokenized Vault",
        165: "ERC-165 Interface Detection",
        173: "ERC-173 Contract Ownership",
        1820: "ERC-1820 Pseudo-introspection Registry",
        2981: "ERC-2981 NFT Royalty Standard",
    }
    
    # Core protocol EIPs
    CORE_EIPS = {
        1559: "Fee market change",
        4844: "Shard Blob Transactions",
        2930: "Access List Transaction",
        1014: "CREATE2 opcode",
        155: "Replay attack protection",
    }
    
    def __init__(self, cache_dir: str = "./.eip_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.cached_eips: Dict[int, EIPDocument] = {}
    
    def fetch_eip(self, eip_number: int, force_refresh: bool = False) -> EIPDocument:
        """
        Fetch an EIP by number
        
        Args:
            eip_number: EIP number to fetch
            force_refresh: If True, bypass cache
            
        Returns:
            Parsed EIPDocument
        """
        # Check memory cache first
        if not force_refresh and eip_number in self.cached_eips:
            cached = self.cached_eips[eip_number]
            # Only use cache if it has actual content
            if cached.title or cached.specification or cached.abstract:
                return cached
        
        # Check disk cache
        cache_file = self.cache_dir / f"eip-{eip_number}.json"
        if not force_refresh and cache_file.exists():
            try:
                data = json.loads(cache_file.read_text())
                eip = self._dict_to_eip(data)
                # Only use cache if it has actual content
                if eip.title or eip.specification or eip.abstract:
                    self.cached_eips[eip_number] = eip
                    return eip
                # Cache is empty/invalid, delete and fetch fresh
                cache_file.unlink()
            except Exception:
                pass  # Cache corrupted, fetch fresh
        
        # Fetch from network
        content = self._fetch_eip_content(eip_number)
        eip = self._parse_eip_markdown(eip_number, content)
        
        # Only cache if we got actual content
        if eip.title or eip.specification or eip.abstract:
            self.cached_eips[eip_number] = eip
            cache_file.write_text(json.dumps(eip.to_dict(), indent=2))
        
        return eip
    
    def _fetch_eip_content(self, eip_number: int) -> str:
        """Fetch EIP content from GitHub"""
        # Try ERCs repo first (for ERCs like ERC-20, ERC-721), then EIPs repo
        urls = [
            self.GITHUB_ERCS_BASE.format(eip_number),
            self.GITHUB_RAW_BASE.format(eip_number),
        ]
        
        # Create SSL context that doesn't verify certificates (for macOS SSL issues)
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        last_error = None
        for url in urls:
            try:
                req = urllib.request.Request(
                    url,
                    headers={'User-Agent': 'EIP-Fetcher/1.0'}
                )
                with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:
                    content = response.read().decode('utf-8')
                    # Verify we got actual content
                    if content and len(content) > 100:
                        return content
            except urllib.error.HTTPError as e:
                last_error = e
                continue
            except Exception as e:
                last_error = e
                continue
        
        raise Exception(f"Failed to fetch EIP-{eip_number}: {last_error}")
    
    def _parse_eip_markdown(self, eip_number: int, content: str) -> EIPDocument:
        """Parse EIP markdown content into EIPDocument"""
        eip = EIPDocument(
            number=eip_number,
            title="",
            status="",
            type="",
            raw_content=content
        )
        
        # Parse front matter (YAML-like header)
        front_matter_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if front_matter_match:
            front_matter = front_matter_match.group(1)
            
            # Extract fields
            title_match = re.search(r'title:\s*(.+)', front_matter)
            if title_match:
                eip.title = title_match.group(1).strip().strip('"\'')
            
            status_match = re.search(r'status:\s*(\w+)', front_matter)
            if status_match:
                eip.status = status_match.group(1)
            
            type_match = re.search(r'type:\s*(.+)', front_matter)
            if type_match:
                eip.type = type_match.group(1).strip()
            
            category_match = re.search(r'category:\s*(\w+)', front_matter)
            if category_match:
                eip.category = category_match.group(1)
            
            created_match = re.search(r'created:\s*(.+)', front_matter)
            if created_match:
                eip.created = created_match.group(1).strip()
            
            requires_match = re.search(r'requires:\s*(.+)', front_matter)
            if requires_match:
                requires_str = requires_match.group(1).strip()
                eip.requires = [int(x.strip()) for x in requires_str.split(',') if x.strip().isdigit()]
        
        # Parse sections
        eip.abstract = self._extract_section(content, ['Abstract', 'Simple Summary'])
        eip.motivation = self._extract_section(content, ['Motivation'])
        eip.specification = self._extract_section(content, ['Specification'])
        eip.rationale = self._extract_section(content, ['Rationale'])
        eip.security_considerations = self._extract_section(content, ['Security Considerations'])
        
        return eip
    
    def _extract_section(self, content: str, section_names: List[str]) -> str:
        """Extract a section from markdown content"""
        for name in section_names:
            # Match ## Section Name and capture everything until next ## heading or end
            pattern = rf'##\s*{name}\s*\n(.*?)(?=\n##|\Z)'
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                section_content = match.group(1).strip()
                # Limit the content to avoid overly large sections (first 5000 chars)
                if len(section_content) > 5000:
                    section_content = section_content[:5000] + "..."
                return section_content
        return ""
    
    def _dict_to_eip(self, data: Dict[str, Any]) -> EIPDocument:
        """Convert dictionary to EIPDocument"""
        return EIPDocument(
            number=data['number'],
            title=data['title'],
            status=data['status'],
            type=data['type'],
            category=data.get('category'),
            created=data.get('created'),
            requires=data.get('requires', []),
            abstract=data.get('abstract', ''),
            motivation=data.get('motivation', ''),
            specification=data.get('specification', ''),
            rationale=data.get('rationale', ''),
            security_considerations=data.get('security_considerations', '')
        )
    
    def parse_eip_to_rules(self, eip: EIPDocument) -> List['ComplianceRule']:
        """
        Convert an EIP document to compliance rules
        
        Args:
            eip: Parsed EIPDocument
            
        Returns:
            List of ComplianceRule objects
        """
        from ethereum_compliance import ComplianceRule
        
        rules = []
        
        # Extract rules based on EIP type
        if eip.category == 'ERC':
            rules.extend(self._extract_erc_rules(eip))
        else:
            rules.extend(self._extract_general_rules(eip))
        
        # Extract security rules
        if eip.security_considerations:
            rules.extend(self._extract_security_rules(eip))
        
        return rules
    
    def _extract_erc_rules(self, eip: EIPDocument) -> List['ComplianceRule']:
        """Extract compliance rules from ERC specification"""
        from ethereum_compliance import ComplianceRule
        
        rules = []
        spec = eip.specification
        
        # Extract interface methods from specification
        # Look for Solidity interface definitions
        interface_pattern = r'function\s+(\w+)\s*\(([^)]*)\)\s*(?:external|public)\s*(?:view|pure)?\s*(?:returns\s*\(([^)]+)\))?'
        
        for match in re.finditer(interface_pattern, spec):
            func_name = match.group(1)
            params = match.group(2)
            returns = match.group(3) or ''
            
            # Create rule for required function
            rule = ComplianceRule(
                id=f"EIP-{eip.number}-{func_name.upper()}",
                source=f"EIP-{eip.number}",
                category='interface',
                severity='critical',
                description=f"Contract must implement {func_name} function as per EIP-{eip.number}",
                patterns=[rf"func.*{func_name}", rf"function\s+{func_name}"],
                must_contain=[func_name],
                recommendation=f"Implement {func_name}({params}) returns ({returns})"
            )
            rules.append(rule)
        
        # Extract event requirements
        event_pattern = r'event\s+(\w+)\s*\(([^)]*)\)'
        for match in re.finditer(event_pattern, spec):
            event_name = match.group(1)
            params = match.group(2)
            
            # Determine which functions should emit this event
            emit_funcs = self._guess_emitting_functions(event_name)
            
            rule = ComplianceRule(
                id=f"EIP-{eip.number}-EVENT-{event_name.upper()}",
                source=f"EIP-{eip.number}",
                category='event',
                severity='critical',
                description=f"Must emit {event_name} event as per EIP-{eip.number}",
                patterns=[rf"func.*({emit_funcs})", rf"function\s+({emit_funcs})"],
                must_contain=[event_name, 'emit'],
                recommendation=f"Add event emission: emit {event_name}({params})"
            )
            rules.append(rule)
        
        # Extract MUST/SHALL requirements from specification text
        requirement_pattern = r'(?:MUST|SHALL)\s+(.+?)(?:\.|$)'
        for match in re.finditer(requirement_pattern, spec, re.IGNORECASE):
            requirement = match.group(1).strip()
            
            # Create a rule for significant requirements
            if len(requirement) > 20 and len(requirement) < 200:
                rule_id = hashlib.md5(requirement.encode()).hexdigest()[:8]
                rule = ComplianceRule(
                    id=f"EIP-{eip.number}-REQ-{rule_id}",
                    source=f"EIP-{eip.number}",
                    category='general',
                    severity='warning',
                    description=f"Requirement: {requirement}",
                    recommendation=f"Ensure implementation: {requirement}"
                )
                rules.append(rule)
        
        return rules
    
    def _extract_general_rules(self, eip: EIPDocument) -> List['ComplianceRule']:
        """Extract rules from non-ERC EIPs"""
        from ethereum_compliance import ComplianceRule
        
        rules = []
        
        # Extract key requirements
        for section in [eip.specification, eip.abstract]:
            requirement_pattern = r'(?:MUST|SHALL|REQUIRED)\s+(.+?)(?:\.|$)'
            for match in re.finditer(requirement_pattern, section, re.IGNORECASE):
                requirement = match.group(1).strip()
                
                if len(requirement) > 20:
                    rule_id = hashlib.md5(requirement.encode()).hexdigest()[:8]
                    rule = ComplianceRule(
                        id=f"EIP-{eip.number}-{rule_id}",
                        source=f"EIP-{eip.number}",
                        category='general',
                        severity='warning',
                        description=requirement[:200],
                        recommendation=f"Follow EIP-{eip.number} specification"
                    )
                    rules.append(rule)
        
        return rules
    
    def _extract_security_rules(self, eip: EIPDocument) -> List['ComplianceRule']:
        """Extract security-related rules from security considerations"""
        from ethereum_compliance import ComplianceRule
        
        rules = []
        sec = eip.security_considerations
        
        # Look for specific security concerns
        concern_patterns = [
            (r'reentrancy', 'reentrancy', 'critical'),
            (r'overflow|underflow', 'overflow', 'critical'),
            (r'front.?running', 'security', 'warning'),
            (r'access.?control|permission|authorization', 'access_control', 'critical'),
            (r'replay.?attack', 'security', 'critical'),
            (r'denial.?of.?service|dos', 'security', 'warning'),
        ]
        
        for pattern, category, severity in concern_patterns:
            if re.search(pattern, sec, re.IGNORECASE):
                # Extract the sentence containing the concern
                sentence_pattern = rf'[^.]*{pattern}[^.]*\.'
                match = re.search(sentence_pattern, sec, re.IGNORECASE)
                concern = match.group(0) if match else f"Security concern related to {pattern}"
                
                rule = ComplianceRule(
                    id=f"EIP-{eip.number}-SEC-{category.upper()}",
                    source=f"EIP-{eip.number}",
                    category=category,
                    severity=severity,
                    description=concern[:200],
                    recommendation=f"Address security consideration from EIP-{eip.number}"
                )
                rules.append(rule)
        
        return rules
    
    def _guess_emitting_functions(self, event_name: str) -> str:
        """Guess which functions should emit a given event"""
        event_func_map = {
            'Transfer': 'transfer|transferFrom|_transfer|mint|burn',
            'Approval': 'approve|_approve|increaseAllowance|decreaseAllowance',
            'ApprovalForAll': 'setApprovalForAll',
            'URI': 'setURI|_setURI',
            'TransferSingle': 'safeTransferFrom|mint|burn',
            'TransferBatch': 'safeBatchTransferFrom|mintBatch|burnBatch',
            'Deposit': 'deposit',
            'Withdraw': 'withdraw',
            'OwnershipTransferred': 'transferOwnership',
        }
        return event_func_map.get(event_name, event_name.lower())
    
    def get_all_token_eips(self) -> List[int]:
        """Get list of all well-known token EIP numbers"""
        return list(self.TOKEN_EIPS.keys())
    
    def get_all_core_eips(self) -> List[int]:
        """Get list of all well-known core protocol EIP numbers"""
        return list(self.CORE_EIPS.keys())
    
    def fetch_multiple_eips(self, eip_numbers: List[int]) -> Dict[int, EIPDocument]:
        """
        Fetch multiple EIPs
        
        Args:
            eip_numbers: List of EIP numbers to fetch
            
        Returns:
            Dictionary mapping EIP numbers to documents
        """
        results = {}
        for num in eip_numbers:
            try:
                results[num] = self.fetch_eip(num)
            except Exception as e:
                print(f"Failed to fetch EIP-{num}: {e}")
        return results
    
    def get_rules_for_eips(self, eip_numbers: List[int]) -> List['ComplianceRule']:
        """
        Get compliance rules for multiple EIPs
        
        Args:
            eip_numbers: List of EIP numbers
            
        Returns:
            List of all compliance rules
        """
        all_rules = []
        for num in eip_numbers:
            try:
                eip = self.fetch_eip(num)
                rules = self.parse_eip_to_rules(eip)
                all_rules.extend(rules)
            except Exception as e:
                print(f"Failed to get rules for EIP-{num}: {e}")
        return all_rules
    
    def search_eips(self, query: str) -> List[Dict[str, Any]]:
        """
        Search EIPs by keyword (searches cached EIPs)
        
        Args:
            query: Search query
            
        Returns:
            List of matching EIPs
        """
        results = []
        query_lower = query.lower()
        
        # Search in well-known EIPs first
        all_known = {**self.TOKEN_EIPS, **self.CORE_EIPS}
        for num, title in all_known.items():
            if query_lower in title.lower() or query_lower in str(num):
                results.append({
                    'number': num,
                    'title': title,
                    'cached': num in self.cached_eips
                })
        
        # Search in cached EIPs
        for num, eip in self.cached_eips.items():
            if num not in all_known:
                if (query_lower in eip.title.lower() or 
                    query_lower in eip.abstract.lower() or
                    query_lower in str(num)):
                    results.append({
                        'number': num,
                        'title': eip.title,
                        'cached': True
                    })
        
        return results
    
    def clear_cache(self):
        """Clear all cached EIPs"""
        self.cached_eips.clear()
        for cache_file in self.cache_dir.glob("eip-*.json"):
            cache_file.unlink()


# Pre-configured EIP rules for common standards
def get_erc20_rules() -> List['ComplianceRule']:
    """Get pre-configured ERC-20 compliance rules"""
    from ethereum_compliance import ComplianceRule
    
    return [
        ComplianceRule(
            id="ERC20-TOTAL-SUPPLY",
            source="EIP-20",
            category="interface",
            severity="critical",
            description="Must implement totalSupply() function",
            patterns=[r"contract.*ERC20", r"interface.*ERC20"],
            must_contain=["totalSupply"],
            recommendation="function totalSupply() public view returns (uint256)"
        ),
        ComplianceRule(
            id="ERC20-BALANCE-OF",
            source="EIP-20",
            category="interface",
            severity="critical",
            description="Must implement balanceOf(address) function",
            patterns=[r"contract.*ERC20", r"interface.*ERC20"],
            must_contain=["balanceOf"],
            recommendation="function balanceOf(address account) public view returns (uint256)"
        ),
        ComplianceRule(
            id="ERC20-TRANSFER",
            source="EIP-20",
            category="interface",
            severity="critical",
            description="Must implement transfer(address,uint256) function",
            patterns=[r"contract.*ERC20", r"interface.*ERC20"],
            must_contain=["transfer"],
            recommendation="function transfer(address to, uint256 amount) public returns (bool)"
        ),
        ComplianceRule(
            id="ERC20-ALLOWANCE",
            source="EIP-20",
            category="interface",
            severity="critical",
            description="Must implement allowance(address,address) function",
            patterns=[r"contract.*ERC20", r"interface.*ERC20"],
            must_contain=["allowance"],
            recommendation="function allowance(address owner, address spender) public view returns (uint256)"
        ),
        ComplianceRule(
            id="ERC20-APPROVE",
            source="EIP-20",
            category="interface",
            severity="critical",
            description="Must implement approve(address,uint256) function",
            patterns=[r"contract.*ERC20", r"interface.*ERC20"],
            must_contain=["approve"],
            recommendation="function approve(address spender, uint256 amount) public returns (bool)"
        ),
        ComplianceRule(
            id="ERC20-TRANSFER-FROM",
            source="EIP-20",
            category="interface",
            severity="critical",
            description="Must implement transferFrom(address,address,uint256) function",
            patterns=[r"contract.*ERC20", r"interface.*ERC20"],
            must_contain=["transferFrom"],
            recommendation="function transferFrom(address from, address to, uint256 amount) public returns (bool)"
        ),
    ]


def get_erc721_rules() -> List['ComplianceRule']:
    """Get pre-configured ERC-721 compliance rules"""
    from ethereum_compliance import ComplianceRule
    
    return [
        ComplianceRule(
            id="ERC721-BALANCE-OF",
            source="EIP-721",
            category="interface",
            severity="critical",
            description="Must implement balanceOf(address) function",
            patterns=[r"contract.*ERC721", r"interface.*ERC721"],
            must_contain=["balanceOf"],
            recommendation="function balanceOf(address owner) external view returns (uint256)"
        ),
        ComplianceRule(
            id="ERC721-OWNER-OF",
            source="EIP-721",
            category="interface",
            severity="critical",
            description="Must implement ownerOf(uint256) function",
            patterns=[r"contract.*ERC721", r"interface.*ERC721"],
            must_contain=["ownerOf"],
            recommendation="function ownerOf(uint256 tokenId) external view returns (address)"
        ),
        ComplianceRule(
            id="ERC721-SAFE-TRANSFER",
            source="EIP-721",
            category="interface",
            severity="critical",
            description="Must implement safeTransferFrom functions",
            patterns=[r"contract.*ERC721", r"interface.*ERC721"],
            must_contain=["safeTransferFrom"],
            recommendation="function safeTransferFrom(address from, address to, uint256 tokenId) external"
        ),
        ComplianceRule(
            id="ERC721-APPROVAL",
            source="EIP-721",
            category="interface",
            severity="critical",
            description="Must implement approve and getApproved functions",
            patterns=[r"contract.*ERC721", r"interface.*ERC721"],
            must_contain=["approve", "getApproved"],
            recommendation="Implement approve(address,uint256) and getApproved(uint256)"
        ),
        ComplianceRule(
            id="ERC721-OPERATOR-APPROVAL",
            source="EIP-721",
            category="interface",
            severity="critical",
            description="Must implement setApprovalForAll and isApprovedForAll",
            patterns=[r"contract.*ERC721", r"interface.*ERC721"],
            must_contain=["setApprovalForAll", "isApprovedForAll"],
            recommendation="Implement operator approval functions"
        ),
    ]
