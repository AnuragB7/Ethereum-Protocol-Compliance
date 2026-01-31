"""
LLM-Powered Compliance Analyzer

Uses LLM to semantically compare code against Ethereum specifications
retrieved from the Qdrant hybrid search index.

Flow:
1. Get code entity from Property Graph
2. Query Spec Index (Qdrant Hybrid) for relevant specifications
3. Build prompt with code + specs
4. LLM analyzes for compliance
5. Parse and return structured deviations
"""

import re
import json
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from llama_index.core import Settings
from llama_index.core.schema import NodeWithScore
from llama_index.llms.openai_like import OpenAILike

logger = logging.getLogger(__name__)


@dataclass
class LLMDeviation:
    """A deviation found by LLM analysis."""
    rule_id: str                  # e.g., "SPEC-prague/vm/gas.py:calculate_intrinsic_gas"
    spec_reference: str           # Which spec was violated
    spec_fork: str               # Fork name (e.g., "prague")
    spec_file: str               # File path in specs
    severity: str                # "critical", "warning", "info"
    category: str                # "gas", "security", "interface", etc.
    description: str             # What the spec requires
    explanation: str             # Why the code doesn't comply
    recommendation: str          # How to fix
    code_location: str           # File and line in analyzed code
    entity_name: str             # Name of the code entity
    confidence: float            # 0.0 - 1.0
    eip_references: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "spec_reference": self.spec_reference,
            "spec_fork": self.spec_fork,
            "spec_file": self.spec_file,
            "severity": self.severity,
            "category": self.category,
            "description": self.description,
            "explanation": self.explanation,
            "recommendation": self.recommendation,
            "code_location": self.code_location,
            "entity_name": self.entity_name,
            "confidence": self.confidence,
            "eip_references": self.eip_references
        }


@dataclass
class LLMComplianceReport:
    """Full compliance report from LLM analysis."""
    timestamp: str
    total_entities_analyzed: int
    total_specs_checked: int
    total_deviations: int
    deviations: List[LLMDeviation] = field(default_factory=list)
    entities_analyzed: List[str] = field(default_factory=list)
    
    @property
    def critical_count(self) -> int:
        return len([d for d in self.deviations if d.severity == "critical"])
    
    @property
    def warning_count(self) -> int:
        return len([d for d in self.deviations if d.severity == "warning"])
    
    @property
    def info_count(self) -> int:
        return len([d for d in self.deviations if d.severity == "info"])
    
    @property
    def compliance_score(self) -> float:
        """Calculate compliance score (0-100)."""
        if self.total_entities_analyzed == 0:
            return 100.0
        
        # Weight by severity
        weights = {"critical": 10, "warning": 3, "info": 1}
        total_weight = sum(weights.get(d.severity, 1) for d in self.deviations)
        max_weight = self.total_entities_analyzed * weights["critical"]
        
        if max_weight == 0:
            return 100.0
        
        return max(0, round(100 - (total_weight / max_weight * 100), 2))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "total_entities_analyzed": self.total_entities_analyzed,
            "total_specs_checked": self.total_specs_checked,
            "total_deviations": self.total_deviations,
            "critical_count": self.critical_count,
            "warning_count": self.warning_count,
            "info_count": self.info_count,
            "compliance_score": self.compliance_score,
            "deviations": [d.to_dict() for d in self.deviations],
            "entities_analyzed": self.entities_analyzed
        }


class LLMComplianceAnalyzer:
    """
    Analyzes code compliance against Ethereum specifications using LLM.
    
    Combines:
    - Code entities from PropertyGraphIndex
    - Specifications from Qdrant Hybrid Search
    - LLM reasoning for semantic comparison
    """
    
    # Compliance analysis prompt template
    COMPLIANCE_PROMPT = """You are an expert Ethereum protocol compliance auditor. Your task is to analyze code for compliance with Ethereum specifications.

## Code Being Analyzed
**Entity Name**: {entity_name}
**Type**: {entity_type}
**Language**: {language}
**File**: {file_path}
**Lines**: {line_start}-{line_end}

```{language}
{code_body}
```

## Relevant Ethereum Specifications

{specs_content}

## Task

Analyze the code above for compliance with the Ethereum specifications provided. For each potential deviation found:

1. **Identify the specific spec requirement** that may not be met
2. **Explain why** the code may not comply
3. **Assess the severity**:
   - CRITICAL: Security issue, incorrect protocol behavior, could cause consensus failure
   - WARNING: Suboptimal implementation, may cause issues in edge cases
   - INFO: Minor deviation, best practice suggestion
4. **Provide a recommendation** for how to fix the issue

If the code appears to comply with all relevant specifications, state "NO_DEVIATIONS_FOUND".

## Response Format

Respond with a JSON array of deviations (or empty array if none found):

```json
[
  {{
    "spec_reference": "Name or description of the spec requirement",
    "spec_fork": "Fork name (e.g., prague, cancun)",
    "spec_file": "Path to spec file",
    "severity": "critical|warning|info",
    "category": "gas|security|interface|state|transaction|block|vm|other",
    "description": "What the spec requires",
    "explanation": "Why the code doesn't comply",
    "recommendation": "How to fix it",
    "eip_references": ["EIP-1559", "EIP-4844"],
    "confidence": 0.85
  }}
]
```

Only include deviations you are confident about. Do not make up issues."""

    def __init__(
        self,
        spec_indexer,
        code_indexer=None,
        api_key: str = None,
        api_base: str = None,
        llm_model: str = "gpt-4"
    ):
        """
        Initialize the LLM Compliance Analyzer.
        
        Args:
            spec_indexer: SpecificationIndexer instance with Qdrant
            code_indexer: Optional CodeGraphIndexer for code entities
            api_key: API key for LLM
            api_base: API base URL
            llm_model: LLM model name
        """
        self.spec_indexer = spec_indexer
        self.code_indexer = code_indexer
        
        # Use provided credentials or fall back to Settings
        if api_key and api_base:
            self.llm = OpenAILike(
                model=llm_model,
                api_base=api_base,
                api_key=api_key,
                is_chat_model=True,
                context_window=8192,
                max_tokens=4096,
                temperature=0,
            )
        else:
            self.llm = Settings.llm
        
        self.llm_model = llm_model
    
    def analyze_entity(
        self,
        entity,
        spec_top_k: int = 5,
        alpha: float = 0.5
    ) -> List[LLMDeviation]:
        """
        Analyze a single code entity for compliance.
        
        Args:
            entity: Code entity from PropertyGraphIndex
            spec_top_k: Number of spec chunks to retrieve
            alpha: Hybrid search balance (0=keyword, 1=semantic)
            
        Returns:
            List of LLMDeviation objects
        """
        # Extract entity information
        entity_name = entity.name if hasattr(entity, 'name') else str(entity)
        entity_type = entity.type if hasattr(entity, 'type') else "unknown"
        language = entity.language if hasattr(entity, 'language') else "unknown"
        file_path = entity.file_path if hasattr(entity, 'file_path') else "unknown"
        line_start = entity.line_start if hasattr(entity, 'line_start') else 0
        line_end = entity.line_end if hasattr(entity, 'line_end') else 0
        code_body = entity.body if hasattr(entity, 'body') else ""
        
        if not code_body:
            logger.warning(f"No code body for entity: {entity_name}")
            return []
        
        # Query spec index for relevant specifications
        spec_nodes = self.spec_indexer.get_specs_for_code_entity(
            entity_name=entity_name,
            entity_type=entity_type,
            entity_code=code_body,
            language=language,
            top_k=spec_top_k
        )
        
        if not spec_nodes:
            logger.info(f"No relevant specs found for: {entity_name}")
            return []
        
        # Build specs content for prompt
        specs_content = self._format_specs_for_prompt(spec_nodes)
        
        # Build the prompt
        prompt = self.COMPLIANCE_PROMPT.format(
            entity_name=entity_name,
            entity_type=entity_type,
            language=language,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            code_body=code_body[:3000],  # Limit code length
            specs_content=specs_content
        )
        
        # Call LLM
        try:
            response = self.llm.complete(prompt)
            response_text = str(response)
            
            # Parse deviations from response
            deviations = self._parse_llm_response(
                response_text,
                entity_name=entity_name,
                code_location=f"{file_path}:{line_start}-{line_end}"
            )
            
            return deviations
            
        except Exception as e:
            logger.error(f"LLM analysis failed for {entity_name}: {e}")
            return []
    
    def _format_specs_for_prompt(self, spec_nodes: List[NodeWithScore]) -> str:
        """Format spec nodes for the LLM prompt."""
        parts = []
        
        for i, node in enumerate(spec_nodes, 1):
            metadata = node.node.metadata if hasattr(node.node, 'metadata') else {}
            fork = metadata.get('fork', 'unknown')
            file_path = metadata.get('file_path', 'unknown')
            chunk_type = metadata.get('chunk_type', 'spec')
            name = metadata.get('name', 'unnamed')
            eips = metadata.get('eip_references', '')
            
            content = node.node.text if hasattr(node.node, 'text') else str(node.node)
            
            # Truncate if too long
            if len(content) > 1500:
                content = content[:1500] + "\n... (truncated)"
            
            spec_header = f"### Spec {i}: [{fork}] {name}"
            if eips:
                spec_header += f" (Related: {eips})"
            spec_header += f"\n**File**: {file_path}\n**Type**: {chunk_type}\n**Relevance Score**: {node.score:.3f}"
            
            parts.append(f"{spec_header}\n\n```python\n{content}\n```")
        
        return "\n\n---\n\n".join(parts)
    
    def _parse_llm_response(
        self,
        response_text: str,
        entity_name: str,
        code_location: str
    ) -> List[LLMDeviation]:
        """Parse LLM response into structured deviations."""
        deviations = []
        
        # Check for no deviations
        if "NO_DEVIATIONS_FOUND" in response_text.upper():
            return []
        
        # Try to extract JSON from response
        json_match = re.search(r'\[[\s\S]*\]', response_text)
        if not json_match:
            logger.warning(f"No JSON array found in LLM response for {entity_name}")
            return []
        
        try:
            deviation_data = json.loads(json_match.group())
            
            for item in deviation_data:
                if not isinstance(item, dict):
                    continue
                
                # Generate rule ID
                spec_file = item.get("spec_file", "unknown")
                spec_ref = item.get("spec_reference", "unknown")
                rule_id = f"SPEC-{spec_file}:{spec_ref[:50]}"
                
                deviation = LLMDeviation(
                    rule_id=rule_id,
                    spec_reference=item.get("spec_reference", ""),
                    spec_fork=item.get("spec_fork", ""),
                    spec_file=spec_file,
                    severity=item.get("severity", "info").lower(),
                    category=item.get("category", "other"),
                    description=item.get("description", ""),
                    explanation=item.get("explanation", ""),
                    recommendation=item.get("recommendation", ""),
                    code_location=code_location,
                    entity_name=entity_name,
                    confidence=float(item.get("confidence", 0.7)),
                    eip_references=item.get("eip_references", [])
                )
                deviations.append(deviation)
                
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON from LLM response: {e}")
        except Exception as e:
            logger.warning(f"Error parsing deviation data: {e}")
        
        return deviations
    
    def analyze_codebase(
        self,
        entities: List = None,
        max_entities: int = 50,
        spec_top_k: int = 5
    ) -> LLMComplianceReport:
        """
        Analyze entire codebase for compliance.
        
        Args:
            entities: List of code entities (uses code_indexer if None)
            max_entities: Maximum entities to analyze (for cost control)
            spec_top_k: Number of specs to retrieve per entity
            
        Returns:
            LLMComplianceReport with all findings
        """
        # Get entities
        if entities is None:
            if self.code_indexer:
                entities = self.code_indexer.entities
            else:
                raise ValueError("No entities provided and no code_indexer configured")
        
        if not entities:
            return LLMComplianceReport(
                timestamp=datetime.now().isoformat(),
                total_entities_analyzed=0,
                total_specs_checked=0,
                total_deviations=0
            )
        
        # Limit entities for cost control
        entities_to_analyze = entities[:max_entities]
        
        logger.info(f"Analyzing {len(entities_to_analyze)} entities for compliance...")
        
        all_deviations = []
        entities_analyzed = []
        total_specs_checked = 0
        
        for i, entity in enumerate(entities_to_analyze):
            entity_name = entity.name if hasattr(entity, 'name') else f"entity_{i}"
            
            logger.info(f"  [{i+1}/{len(entities_to_analyze)}] Analyzing: {entity_name}")
            
            try:
                deviations = self.analyze_entity(entity, spec_top_k=spec_top_k)
                all_deviations.extend(deviations)
                entities_analyzed.append(entity_name)
                total_specs_checked += spec_top_k
                
            except Exception as e:
                logger.error(f"Failed to analyze {entity_name}: {e}")
        
        report = LLMComplianceReport(
            timestamp=datetime.now().isoformat(),
            total_entities_analyzed=len(entities_analyzed),
            total_specs_checked=total_specs_checked,
            total_deviations=len(all_deviations),
            deviations=all_deviations,
            entities_analyzed=entities_analyzed
        )
        
        logger.info(f"✅ Compliance analysis complete:")
        logger.info(f"   Entities: {report.total_entities_analyzed}")
        logger.info(f"   Deviations: {report.total_deviations}")
        logger.info(f"   Critical: {report.critical_count}")
        logger.info(f"   Score: {report.compliance_score}")
        
        return report
    
    def analyze_single_code(
        self,
        code: str,
        language: str,
        entity_name: str = "anonymous",
        spec_top_k: int = 5
    ) -> List[LLMDeviation]:
        """
        Analyze a single code snippet for compliance.
        
        Useful for analyzing PR diffs or individual files.
        
        Args:
            code: Code string to analyze
            language: Programming language
            entity_name: Name for the code entity
            spec_top_k: Number of specs to retrieve
            
        Returns:
            List of LLMDeviation objects
        """
        # Create a mock entity
        class MockEntity:
            pass
        
        entity = MockEntity()
        entity.name = entity_name
        entity.type = "code_snippet"
        entity.language = language
        entity.file_path = "<snippet>"
        entity.line_start = 1
        entity.line_end = code.count('\n') + 1
        entity.body = code
        
        return self.analyze_entity(entity, spec_top_k=spec_top_k)
    
    def analyze_diff(
        self,
        diff_content: str,
        base_language: str = "go"
    ) -> LLMComplianceReport:
        """
        Analyze a git diff for compliance issues.
        
        Args:
            diff_content: Git diff content
            base_language: Default language for analysis
            
        Returns:
            LLMComplianceReport with findings
        """
        # Parse diff to extract changed code
        all_deviations = []
        files_analyzed = []
        
        current_file = None
        current_additions = []
        
        for line in diff_content.split('\n'):
            if line.startswith('+++ b/'):
                # Process previous file
                if current_file and current_additions:
                    code = '\n'.join(current_additions)
                    lang = self._detect_language(current_file)
                    
                    deviations = self.analyze_single_code(
                        code=code,
                        language=lang,
                        entity_name=current_file
                    )
                    all_deviations.extend(deviations)
                    files_analyzed.append(current_file)
                
                current_file = line[6:]
                current_additions = []
            
            elif line.startswith('+') and not line.startswith('+++'):
                current_additions.append(line[1:])
        
        # Process last file
        if current_file and current_additions:
            code = '\n'.join(current_additions)
            lang = self._detect_language(current_file)
            
            deviations = self.analyze_single_code(
                code=code,
                language=lang,
                entity_name=current_file
            )
            all_deviations.extend(deviations)
            files_analyzed.append(current_file)
        
        return LLMComplianceReport(
            timestamp=datetime.now().isoformat(),
            total_entities_analyzed=len(files_analyzed),
            total_specs_checked=len(files_analyzed) * 5,
            total_deviations=len(all_deviations),
            deviations=all_deviations,
            entities_analyzed=files_analyzed
        )
    
    def _detect_language(self, file_path: str) -> str:
        """Detect language from file extension."""
        ext_map = {
            '.go': 'go',
            '.sol': 'solidity',
            '.js': 'javascript',
            '.ts': 'typescript',
            '.py': 'python',
            '.java': 'java',
            '.rs': 'rust'
        }
        
        for ext, lang in ext_map.items():
            if file_path.endswith(ext):
                return lang
        return 'go'
