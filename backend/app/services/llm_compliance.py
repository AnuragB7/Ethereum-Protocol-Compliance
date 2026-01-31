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
    
    # Compliance analysis prompt template (basic - no graph context)
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

    # Diff-based compliance analysis prompt (for quick mode)
    DIFF_COMPLIANCE_PROMPT = """You are an expert Ethereum protocol compliance auditor. Your task is to analyze code changes (diff) for compliance with Ethereum specifications.

## Code Changes Being Reviewed

**File**: {file_path}
**Language**: {language}

### Changes (Diff)
Lines starting with '+' are additions, '-' are deletions, and ' ' (space) are context.

```diff
{diff_content}
```

## Relevant Ethereum Specifications

{specs_content}

## Task

Analyze the code changes above for compliance with Ethereum specifications. Focus on:

1. **What was changed** - Are the modifications correct per Ethereum specs?
2. **What was added** - Do new implementations follow spec requirements?
3. **What was removed** - Could removing this code break spec compliance?
4. **Edge cases** - Do the changes handle all required scenarios?

For each potential deviation found:

1. **Identify the specific spec requirement** that may not be met
2. **Explain why** the change introduces or misses compliance
3. **Point to the specific lines** that are problematic (use + or - prefix)
4. **Assess the severity**:
   - CRITICAL: Security issue, incorrect protocol behavior, could cause consensus failure
   - WARNING: Suboptimal implementation, may cause issues in edge cases
   - INFO: Minor deviation, best practice suggestion
5. **Provide a recommendation** for how to fix the issue

If the changes appear to comply with all relevant specifications, state "NO_DEVIATIONS_FOUND".

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
    "explanation": "Why the change doesn't comply (reference specific + or - lines)",
    "recommendation": "How to fix it",
    "problematic_lines": "Quote the specific lines from the diff",
    "eip_references": ["EIP-1559", "EIP-4844"],
    "confidence": 0.85
  }}
]
```

Only include deviations you are confident about. Focus on the actual changes, not pre-existing code."""

    # Graph-aware compliance analysis prompt template
    GRAPH_COMPLIANCE_PROMPT = """You are an expert Ethereum protocol compliance auditor. Your task is to analyze code for compliance with Ethereum specifications, considering its relationships with other code in the codebase.

## Code Being Analyzed
**Entity Name**: {entity_name}
**Type**: {entity_type}
**Language**: {language}
**File**: {file_path}
**Lines**: {line_start}-{line_end}

```{language}
{code_body}
```

## Code Relationships (from Property Graph)

{graph_context}

## Relevant Ethereum Specifications

{specs_content}

## Task

Analyze the code above for compliance with the Ethereum specifications provided. **Pay special attention to**:

1. **How this code interacts with other components** (callers, callees, dependencies)
2. **Whether the relationships follow Ethereum protocol patterns** correctly
3. **Whether the code properly handles data from/to related components**
4. **Whether changes to this code could break callers or callees**

For each potential deviation found:

1. **Identify the specific spec requirement** that may not be met
2. **Explain why** the code may not comply (consider the graph relationships)
3. **Assess the severity**:
   - CRITICAL: Security issue, incorrect protocol behavior, could cause consensus failure
   - WARNING: Suboptimal implementation, may cause issues in edge cases
   - INFO: Minor deviation, best practice suggestion
4. **Assess the impact** on related code (callers/callees)
5. **Provide a recommendation** for how to fix the issue

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
    "explanation": "Why the code doesn't comply (include relationship analysis)",
    "recommendation": "How to fix it",
    "impact": "How this affects related code (callers/callees)",
    "affected_components": ["list", "of", "affected", "components"],
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
    
    def analyze_entity_with_graph_context(
        self,
        entity,
        relationships: List[Any],
        all_entities: List[Any],
        spec_top_k: int = 5,
        alpha: float = 0.5
    ) -> List[LLMDeviation]:
        """
        Analyze a code entity WITH graph relationship context.
        
        This method uses the property graph to understand:
        - What functions/methods this entity calls
        - What calls this entity
        - Imports and dependencies
        - Class inheritance/implementation relationships
        
        Args:
            entity: Code entity from PropertyGraphIndex
            relationships: List of all relationships from the graph
            all_entities: List of all entities for context lookup
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
        
        # Build graph context
        graph_context = self._build_graph_context(entity_name, relationships, all_entities)
        
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
        
        # Build the graph-aware prompt
        prompt = self.GRAPH_COMPLIANCE_PROMPT.format(
            entity_name=entity_name,
            entity_type=entity_type,
            language=language,
            file_path=file_path,
            line_start=line_start,
            line_end=line_end,
            code_body=code_body[:3000],  # Limit code length
            graph_context=graph_context,
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
            logger.error(f"LLM graph-aware analysis failed for {entity_name}: {e}")
            return []
    
    # Batch analysis prompt template for analyzing multiple entities at once
    BATCH_GRAPH_COMPLIANCE_PROMPT = """You are an expert Ethereum protocol compliance auditor. Your task is to analyze a BATCH of code entities for compliance with Ethereum specifications, considering their relationships with other code.

## Entities Being Analyzed (Total: {entity_count})

{entities_content}

## Combined Graph Context (Relationships)

{combined_graph_context}

## Relevant Ethereum Specifications

{specs_content}

## Task

Analyze ALL the entities above for compliance with the Ethereum specifications provided. For EACH entity, consider:

1. **How the entity interacts with other components** (callers, callees, dependencies)
2. **Whether the relationships follow Ethereum protocol patterns** correctly
3. **Whether the entity properly handles data from/to related components**
4. **Whether changes to the entity could break callers or callees**

For each potential deviation found:

1. **Identify which entity** has the issue (use the exact entity name)
2. **Identify the specific spec requirement** that may not be met
3. **Explain why** the code may not comply (consider the graph relationships)
4. **Assess the severity**:
   - CRITICAL: Security issue, incorrect protocol behavior, could cause consensus failure
   - WARNING: Suboptimal implementation, may cause issues in edge cases
   - INFO: Minor deviation, best practice suggestion
5. **Provide a recommendation** for how to fix the issue

If an entity appears to comply with all relevant specifications, you can skip it (don't include it in the response).

## Response Format

Respond with a JSON array of deviations across ALL entities (or empty array if none found):

```json
[
  {{
    "entity_name": "Name of the entity with the issue",
    "file_path": "Path to the file",
    "line_range": "start-end",
    "spec_reference": "Name or description of the spec requirement",
    "spec_fork": "Fork name (e.g., prague, cancun)",
    "spec_file": "Path to spec file",
    "severity": "critical|warning|info",
    "category": "gas|security|interface|state|transaction|block|vm|other",
    "description": "What the spec requires",
    "explanation": "Why the code doesn't comply (include relationship analysis)",
    "recommendation": "How to fix it",
    "impact": "How this affects related code (callers/callees)",
    "affected_components": ["list", "of", "affected", "components"],
    "eip_references": ["EIP-1559", "EIP-4844"],
    "confidence": 0.85
  }}
]
```

Only include deviations you are confident about. Do not make up issues. It's better to report fewer high-confidence issues than many low-confidence ones."""

    def analyze_entity_batch(
        self,
        entities: List[Any],
        relationships: List[Any],
        all_entities: List[Any],
        spec_top_k: int = 5,
        alpha: float = 0.5
    ) -> List[LLMDeviation]:
        """
        Analyze a BATCH of code entities together WITH graph relationship context.
        
        This method:
        1. Combines multiple entities into a single prompt
        2. Performs ONE spec query for the combined code
        3. Performs ONE LLM call for all entities
        4. Parses deviations for each entity from the response
        
        This significantly reduces API calls compared to per-entity analysis.
        
        Args:
            entities: List of code entities to analyze together
            relationships: List of all relationships from the graph
            all_entities: List of all entities for context lookup
            spec_top_k: Number of spec chunks to retrieve
            alpha: Hybrid search balance (0=keyword, 1=semantic)
            
        Returns:
            List of LLMDeviation objects for all entities in the batch
        """
        if not entities:
            return []
        
        # Build combined entities content
        entities_content_parts = []
        entity_names = []
        combined_code = ""
        
        for i, entity in enumerate(entities, 1):
            entity_name = entity.name if hasattr(entity, 'name') else str(entity)
            entity_type = entity.type if hasattr(entity, 'type') else "unknown"
            language = entity.language if hasattr(entity, 'language') else "unknown"
            file_path = entity.file_path if hasattr(entity, 'file_path') else "unknown"
            line_start = entity.line_start if hasattr(entity, 'line_start') else 0
            line_end = entity.line_end if hasattr(entity, 'line_end') else 0
            code_body = entity.body if hasattr(entity, 'body') else ""
            
            if not code_body:
                continue
            
            entity_names.append(entity_name)
            combined_code += f" {code_body[:500]}"  # Sample for spec query
            
            # Format entity for prompt (truncate code to manage token count)
            code_preview = code_body[:1500] if len(code_body) > 1500 else code_body
            entity_section = f"""### Entity {i}: {entity_name}
**Type**: {entity_type} | **Language**: {language}
**File**: {file_path} | **Lines**: {line_start}-{line_end}

```{language}
{code_preview}
```
"""
            entities_content_parts.append(entity_section)
        
        if not entities_content_parts:
            return []
        
        entities_content = "\n---\n\n".join(entities_content_parts)
        
        # Build combined graph context (summarized for all entities)
        combined_graph_context = self._build_batch_graph_context(entity_names, relationships, all_entities)
        
        # Query spec index using combined code (one query for the batch)
        spec_nodes = self.spec_indexer.get_specs_for_code_entity(
            entity_name=", ".join(entity_names[:5]),  # Use first few names for query
            entity_type="batch",
            entity_code=combined_code[:3000],  # Sample of combined code
            language="mixed",
            top_k=spec_top_k
        )
        
        if not spec_nodes:
            logger.info(f"No relevant specs found for batch of {len(entities)} entities")
            return []
        
        # Build specs content for prompt
        specs_content = self._format_specs_for_prompt(spec_nodes)
        
        # Build the batch prompt
        prompt = self.BATCH_GRAPH_COMPLIANCE_PROMPT.format(
            entity_count=len(entities_content_parts),
            entities_content=entities_content,
            combined_graph_context=combined_graph_context,
            specs_content=specs_content
        )
        
        # Call LLM (one call for the entire batch)
        try:
            response = self.llm.complete(prompt)
            response_text = str(response)
            
            # Parse deviations from response (handles multiple entities)
            deviations = self._parse_batch_llm_response(
                response_text,
                entities
            )
            
            logger.info(f"Batch analysis found {len(deviations)} deviations in {len(entities)} entities")
            return deviations
            
        except Exception as e:
            logger.error(f"LLM batch analysis failed: {e}")
            return []
    
    def _build_batch_graph_context(
        self,
        entity_names: List[str],
        relationships: List[Any],
        all_entities: List[Any]
    ) -> str:
        """
        Build a summarized graph context for multiple entities.
        
        Instead of full context per entity, provides a summarized view
        to stay within token limits.
        """
        # Create entity lookup dict
        entity_dict = {}
        for e in all_entities:
            name = e.name if hasattr(e, 'name') else str(e)
            entity_dict[name] = e
        
        # Build relationship index for quick lookup
        outgoing_by_entity = {}
        incoming_by_entity = {}
        
        for rel in relationships:
            source = rel.source if hasattr(rel, 'source') else rel.get('source', '') if isinstance(rel, dict) else ''
            target = rel.target if hasattr(rel, 'target') else rel.get('target', '') if isinstance(rel, dict) else ''
            rel_type = rel.type if hasattr(rel, 'type') else rel.get('type', 'UNKNOWN') if isinstance(rel, dict) else 'UNKNOWN'
            
            if source in entity_names:
                if source not in outgoing_by_entity:
                    outgoing_by_entity[source] = []
                outgoing_by_entity[source].append({'target': target, 'type': rel_type})
            
            if target in entity_names:
                if target not in incoming_by_entity:
                    incoming_by_entity[target] = []
                incoming_by_entity[target].append({'source': source, 'type': rel_type})
        
        # Build summarized context
        context_parts = []
        
        for entity_name in entity_names:
            entity_context = []
            
            # Outgoing relationships
            outgoing = outgoing_by_entity.get(entity_name, [])
            if outgoing:
                calls = [r['target'] for r in outgoing if r['type'] in ('CALLS', 'INVOKES')][:5]
                if calls:
                    entity_context.append(f"calls: {', '.join(calls)}")
            
            # Incoming relationships
            incoming = incoming_by_entity.get(entity_name, [])
            if incoming:
                callers = [r['source'] for r in incoming if r['type'] in ('CALLS', 'INVOKES')][:5]
                if callers:
                    entity_context.append(f"called by: {', '.join(callers)}")
            
            if entity_context:
                context_parts.append(f"**{entity_name}**: {' | '.join(entity_context)}")
        
        if not context_parts:
            return "No significant relationships found for these entities."
        
        # Add summary stats
        total_entities = len(entity_names)
        entities_with_rels = len([n for n in entity_names if n in outgoing_by_entity or n in incoming_by_entity])
        
        summary = f"\n**Summary**: {entities_with_rels}/{total_entities} entities have graph relationships"
        
        return '\n'.join(context_parts[:20]) + summary  # Limit to 20 entities for context
    
    def _parse_batch_llm_response(
        self,
        response_text: str,
        entities: List[Any]
    ) -> List[LLMDeviation]:
        """Parse LLM response from batch analysis into structured deviations."""
        deviations = []
        
        # Check for no deviations
        if "NO_DEVIATIONS_FOUND" in response_text.upper():
            return []
        
        # Build entity lookup for code_location
        entity_lookup = {}
        for e in entities:
            name = e.name if hasattr(e, 'name') else str(e)
            file_path = e.file_path if hasattr(e, 'file_path') else "unknown"
            line_start = e.line_start if hasattr(e, 'line_start') else 0
            line_end = e.line_end if hasattr(e, 'line_end') else 0
            entity_lookup[name] = f"{file_path}:{line_start}-{line_end}"
        
        # Try to extract JSON from response
        json_match = re.search(r'\[[\s\S]*\]', response_text)
        if not json_match:
            logger.warning("No JSON array found in batch LLM response")
            return []
        
        try:
            deviation_data = json.loads(json_match.group())
            
            for item in deviation_data:
                if not isinstance(item, dict):
                    continue
                
                # Extract entity name from response
                entity_name = item.get("entity_name", "unknown")
                
                # Get code location from our lookup, or use what LLM provided
                code_location = entity_lookup.get(
                    entity_name, 
                    f"{item.get('file_path', 'unknown')}:{item.get('line_range', '0-0')}"
                )
                
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
            logger.warning(f"Failed to parse JSON from batch LLM response: {e}")
        except Exception as e:
            logger.warning(f"Error parsing batch deviation data: {e}")
        
        return deviations
    
    def _build_graph_context(
        self, 
        entity_name: str, 
        relationships: List[Any],
        all_entities: List[Any]
    ) -> str:
        """
        Build a human-readable context string from graph relationships.
        
        Args:
            entity_name: Name of the entity being analyzed
            relationships: All relationships from the graph
            all_entities: All entities for context lookup
            
        Returns:
            Formatted string describing the entity's relationships
        """
        # Create entity lookup dict for quick access
        entity_dict = {}
        for e in all_entities:
            name = e.name if hasattr(e, 'name') else str(e)
            entity_dict[name] = e
        
        # Find relationships involving this entity
        outgoing = []  # This entity -> other
        incoming = []  # Other -> this entity
        
        for rel in relationships:
            # Get relationship attributes
            source = rel.source if hasattr(rel, 'source') else rel.get('source', '') if isinstance(rel, dict) else ''
            target = rel.target if hasattr(rel, 'target') else rel.get('target', '') if isinstance(rel, dict) else ''
            rel_type = rel.type if hasattr(rel, 'type') else rel.get('type', 'UNKNOWN') if isinstance(rel, dict) else 'UNKNOWN'
            
            if source == entity_name:
                outgoing.append({'target': target, 'type': rel_type})
            elif target == entity_name:
                incoming.append({'source': source, 'type': rel_type})
        
        # Build context string
        context_parts = []
        
        # Outgoing relationships (what this entity uses/calls)
        if outgoing:
            calls = [r['target'] for r in outgoing if r['type'] in ('CALLS', 'INVOKES')]
            imports = [r['target'] for r in outgoing if r['type'] in ('IMPORTS', 'USES')]
            inherits = [r['target'] for r in outgoing if r['type'] in ('EXTENDS', 'IMPLEMENTS', 'INHERITS')]
            contains = [r['target'] for r in outgoing if r['type'] in ('CONTAINS', 'DEFINES')]
            
            if calls:
                context_parts.append(f"**Functions/Methods Called by {entity_name}**: {', '.join(calls[:15])}")
                # Add signatures of called functions if available
                called_sigs = []
                for call in calls[:5]:
                    if call in entity_dict:
                        called_entity = entity_dict[call]
                        sig = getattr(called_entity, 'signature', None) or getattr(called_entity, 'body', '')[:100]
                        if sig:
                            called_sigs.append(f"  - {call}: {sig.split(chr(10))[0]}")
                if called_sigs:
                    context_parts.append("**Called Function Signatures**:\n" + '\n'.join(called_sigs))
            
            if imports:
                context_parts.append(f"**Dependencies/Imports**: {', '.join(imports[:10])}")
            
            if inherits:
                context_parts.append(f"**Extends/Implements**: {', '.join(inherits[:5])}")
            
            if contains:
                context_parts.append(f"**Contains/Defines**: {', '.join(contains[:10])}")
        
        # Incoming relationships (what uses/calls this entity)
        if incoming:
            callers = [r['source'] for r in incoming if r['type'] in ('CALLS', 'INVOKES')]
            importers = [r['source'] for r in incoming if r['type'] in ('IMPORTS', 'USES')]
            children = [r['source'] for r in incoming if r['type'] in ('EXTENDS', 'IMPLEMENTS', 'INHERITS')]
            
            if callers:
                context_parts.append(f"**Called By (Callers)**: {', '.join(callers[:15])}")
                context_parts.append(f"  *Impact*: Changes to {entity_name} could affect {len(callers)} callers")
            
            if importers:
                context_parts.append(f"**Imported/Used By**: {', '.join(importers[:10])}")
            
            if children:
                context_parts.append(f"**Extended/Implemented By**: {', '.join(children[:5])}")
        
        # Summary statistics
        total_outgoing = len(outgoing)
        total_incoming = len(incoming)
        
        if total_outgoing > 0 or total_incoming > 0:
            context_parts.append(f"\n**Relationship Summary**: {total_outgoing} outgoing, {total_incoming} incoming relationships")
            
            # Identify high-impact entities
            if total_incoming > 5:
                context_parts.append(f"  *Note*: This is a **high-impact entity** with {total_incoming} dependents - changes require careful review")
        
        if not context_parts:
            return "No relationships found for this entity in the code graph."
        
        return '\n\n'.join(context_parts)
    
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
        base_language: str = "go",
        max_files_per_batch: int = 10,
        max_batches: int = 5
    ) -> LLMComplianceReport:
        """
        Analyze a git diff for compliance issues.
        
        Uses smart batching to reduce API calls:
        - Groups files into batches (max_files_per_batch)
        - One spec query per batch
        - One LLM call per batch
        - Skips test files and non-code files
        
        Args:
            diff_content: Git diff content
            base_language: Default language for analysis
            max_files_per_batch: Max files to analyze in one LLM call
            max_batches: Max number of batches (controls cost)
            
        Returns:
            LLMComplianceReport with findings
        """
        # Parse diff into per-file chunks
        file_diffs = self._parse_diff_into_files(diff_content)
        
        # Filter to code files only, skip tests and generated files
        code_extensions = ['.go', '.sol', '.js', '.ts', '.py', '.java', '.rs', '.jsx', '.tsx']
        skip_patterns = ['_test.go', '_test.py', '_test.js', '_test.ts', 'test_', 
                        '.pb.go', '_generated', '_mock', 'vendor/', 'node_modules/']
        
        filtered_files = {}
        for file_path, file_diff in file_diffs.items():
            # Must be a code file
            if not any(file_path.endswith(ext) for ext in code_extensions):
                continue
            # Skip test and generated files
            if any(pattern in file_path for pattern in skip_patterns):
                continue
            filtered_files[file_path] = file_diff
        
        logger.info(f"Analyzing diff: {len(file_diffs)} total files, {len(filtered_files)} code files (after filtering)")
        
        if not filtered_files:
            return LLMComplianceReport(
                timestamp=datetime.now().isoformat(),
                total_entities_analyzed=0,
                total_specs_checked=0,
                total_deviations=0
            )
        
        # Sort files by size (smaller first) and create batches
        sorted_files = sorted(filtered_files.items(), key=lambda x: len(x[1]))
        
        # Create batches
        batches = []
        current_batch = []
        current_size = 0
        max_batch_chars = 15000  # ~4K tokens per batch
        
        for file_path, file_diff in sorted_files:
            file_size = len(file_diff)
            
            # If adding this file exceeds batch size, start new batch
            if current_batch and (len(current_batch) >= max_files_per_batch or 
                                   current_size + file_size > max_batch_chars):
                batches.append(current_batch)
                current_batch = []
                current_size = 0
                
                # Stop if we have enough batches
                if len(batches) >= max_batches:
                    logger.warning(f"Limiting analysis to {max_batches} batches ({sum(len(b) for b in batches)} files)")
                    break
            
            current_batch.append((file_path, file_diff))
            current_size += file_size
        
        # Don't forget the last batch
        if current_batch and len(batches) < max_batches:
            batches.append(current_batch)
        
        logger.info(f"Created {len(batches)} batches for analysis")
        
        all_deviations = []
        files_analyzed = []
        
        # Process each batch
        for batch_idx, batch in enumerate(batches):
            logger.info(f"Processing batch {batch_idx + 1}/{len(batches)} ({len(batch)} files)")
            
            # Combine diffs for this batch
            batch_diff_content = self._format_batch_diff(batch)
            batch_files = [f[0] for f in batch]
            
            # Extract code for spec query (combined from all files in batch)
            combined_code = '\n'.join(
                line[1:] for fp, fd in batch 
                for line in fd.split('\n')
                if line.startswith('+') and not line.startswith('+++')
            )[:3000]
            
            # One spec query per batch
            spec_nodes = self.spec_indexer.get_specs_for_code_entity(
                entity_name=f"batch_{batch_idx}",
                entity_type="diff_batch",
                entity_code=combined_code,
                language=base_language,
                top_k=7  # Slightly more specs for batch
            )
            
            if not spec_nodes:
                logger.info(f"  No relevant specs found for batch {batch_idx + 1}")
                continue
            
            specs_content = self._format_specs_for_prompt(spec_nodes)
            
            # Build batched prompt
            prompt = self._build_batch_diff_prompt(batch, specs_content)
            
            # One LLM call per batch
            try:
                response = self.llm.complete(prompt)
                response_text = str(response)
                
                # Parse deviations
                deviations = self._parse_llm_response(
                    response_text,
                    entity_name=f"batch_{batch_idx}",
                    code_location="multiple_files"
                )
                
                if deviations:
                    logger.info(f"  Found {len(deviations)} deviations in batch {batch_idx + 1}")
                    all_deviations.extend(deviations)
                
                files_analyzed.extend(batch_files)
                
            except Exception as e:
                logger.error(f"LLM analysis failed for batch {batch_idx + 1}: {e}")
        
        logger.info(f"Quick analysis complete: {len(files_analyzed)} files, {len(all_deviations)} deviations")
        
        return LLMComplianceReport(
            timestamp=datetime.now().isoformat(),
            total_entities_analyzed=len(files_analyzed),
            total_specs_checked=len(batches) * 7,
            total_deviations=len(all_deviations),
            deviations=all_deviations,
            entities_analyzed=files_analyzed
        )
    
    def _format_batch_diff(self, batch: List[tuple]) -> str:
        """Format multiple file diffs into a combined string."""
        parts = []
        for file_path, file_diff in batch:
            # Truncate individual file diffs if too long
            truncated_diff = file_diff[:2000] if len(file_diff) > 2000 else file_diff
            parts.append(f"### File: {file_path}\n```diff\n{truncated_diff}\n```")
        return '\n\n'.join(parts)
    
    def _build_batch_diff_prompt(self, batch: List[tuple], specs_content: str) -> str:
        """Build a prompt for analyzing multiple files at once."""
        files_list = ', '.join(f[0] for f in batch)
        batch_diff = self._format_batch_diff(batch)
        
        prompt = f"""You are an expert Ethereum protocol compliance auditor. Analyze the following code changes for compliance with Ethereum specifications.

## Files Being Reviewed
{files_list}

## Code Changes

{batch_diff}

## Relevant Ethereum Specifications

{specs_content}

## Task

Analyze ALL the code changes above for compliance issues. For each file with issues:

1. Identify the specific spec requirement that may not be met
2. Reference the specific file and lines (use + or - prefix)
3. Assess severity: CRITICAL (security/consensus), WARNING (edge cases), INFO (best practice)
4. Provide a recommendation

If all changes comply with specifications, respond with "NO_DEVIATIONS_FOUND".

## Response Format

Respond with a JSON array:

```json
[
  {{
    "spec_reference": "Spec requirement description",
    "spec_fork": "Fork name",
    "spec_file": "Spec file path",
    "severity": "critical|warning|info",
    "category": "gas|security|interface|state|transaction|block|vm|other",
    "description": "What the spec requires",
    "explanation": "Why the code doesn't comply",
    "recommendation": "How to fix",
    "file": "path/to/affected/file.go",
    "eip_references": ["EIP-XXXX"],
    "confidence": 0.85
  }}
]
```

Only report issues you're confident about."""
        
        return prompt
    
    def _parse_diff_into_files(self, diff_content: str) -> Dict[str, str]:
        """
        Parse a unified diff into per-file chunks.
        
        Returns a dict of file_path -> diff_content (including context lines).
        """
        file_diffs = {}
        current_file = None
        current_diff_lines = []
        
        for line in diff_content.split('\n'):
            if line.startswith('diff --git'):
                # Save previous file
                if current_file and current_diff_lines:
                    file_diffs[current_file] = '\n'.join(current_diff_lines)
                
                current_diff_lines = [line]
                current_file = None
            
            elif line.startswith('+++ b/'):
                current_file = line[6:]
                current_diff_lines.append(line)
            
            elif current_file is not None:
                current_diff_lines.append(line)
        
        # Save last file
        if current_file and current_diff_lines:
            file_diffs[current_file] = '\n'.join(current_diff_lines)
        
        return file_diffs
    
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
