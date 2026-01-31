"""
Specification Parser for ethereum/execution-specs

Parses Python specification files from the execution-specs repository
and extracts structured chunks for indexing.

The execution-specs repository structure:
    src/ethereum/forks/
        ├── frontier/
        ├── homestead/
        ├── ...
        ├── cancun/
        │   ├── __init__.py
        │   ├── blocks.py
        │   ├── fork.py
        │   ├── state.py
        │   ├── transactions.py
        │   └── vm/
        │       ├── gas.py
        │       ├── instructions/
        │       └── ...
        └── prague/
            └── ...
"""

import ast
import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class SpecChunk:
    """Represents a chunk of specification content"""
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata fields
    fork_name: str = ""           # e.g., "prague", "cancun"
    file_path: str = ""           # e.g., "src/ethereum/forks/prague/vm/gas.py"
    chunk_type: str = ""          # "function", "class", "module", "docstring"
    name: str = ""                # Function/class name
    eip_references: List[str] = field(default_factory=list)  # ["EIP-1559", "EIP-4844"]
    line_start: int = 0
    line_end: int = 0


class SpecificationParser:
    """
    Parses Ethereum execution specifications from Python files.
    
    Extracts functions, classes, docstrings, and comments,
    identifying EIP references and organizing by fork.
    """
    
    # Known Ethereum forks in chronological order
    KNOWN_FORKS = [
        "frontier", "homestead", "tangerine_whistle", "spurious_dragon",
        "byzantium", "constantinople", "petersburg", "istanbul",
        "muir_glacier", "berlin", "london", "arrow_glacier",
        "gray_glacier", "paris", "shanghai", "cancun", "prague", 
        "osaka", "amsterdam"
    ]
    
    # Recent forks to prioritize (amsterdam is current, osaka is next)
    RECENT_FORKS = ["amsterdam", "osaka", "prague", "cancun", "shanghai"]
    
    def __init__(self, specs_dir: str):
        """
        Initialize the parser.
        
        Args:
            specs_dir: Path to the execution-specs repository root
        """
        self.specs_dir = Path(specs_dir)
        self.forks_dir = self.specs_dir / "src" / "ethereum" / "forks"
        
        if not self.forks_dir.exists():
            # Try alternative path (might be cloned differently)
            alt_path = self.specs_dir / "src" / "ethereum"
            if alt_path.exists():
                self.forks_dir = alt_path / "forks"
            else:
                logger.warning(f"Forks directory not found at expected path: {self.forks_dir}")
    
    def get_available_forks(self) -> List[str]:
        """Get list of available fork directories."""
        if not self.forks_dir.exists():
            return []
        
        forks = []
        for item in self.forks_dir.iterdir():
            if item.is_dir() and not item.name.startswith(('_', '.')):
                forks.append(item.name)
        
        # Sort by known fork order
        def fork_order(name):
            try:
                return self.KNOWN_FORKS.index(name)
            except ValueError:
                return 999
        
        return sorted(forks, key=fork_order)
    
    def parse_all_forks(
        self, 
        forks: Optional[List[str]] = None,
        include_docs: bool = True
    ) -> List[SpecChunk]:
        """
        Parse specifications from all or selected forks.
        
        Args:
            forks: List of fork names to parse. If None, parses recent forks.
            include_docs: Whether to include documentation files
            
        Returns:
            List of SpecChunk objects
        """
        available_forks = self.get_available_forks()
        
        if not available_forks:
            logger.warning("No forks found to parse")
            return []
        
        # Default to recent forks if not specified
        if forks is None:
            forks = [f for f in self.RECENT_FORKS if f in available_forks]
            if not forks:
                forks = available_forks[-3:]  # Last 3 forks
        
        logger.info(f"Parsing forks: {', '.join(forks)}")
        
        all_chunks = []
        
        for fork_name in forks:
            if fork_name not in available_forks:
                logger.warning(f"Fork not found: {fork_name}")
                continue
            
            fork_chunks = self.parse_fork(fork_name)
            all_chunks.extend(fork_chunks)
            logger.info(f"  {fork_name}: {len(fork_chunks)} chunks")
        
        # Optionally include docs
        if include_docs:
            docs_chunks = self._parse_docs()
            all_chunks.extend(docs_chunks)
            if docs_chunks:
                logger.info(f"  docs: {len(docs_chunks)} chunks")
        
        return all_chunks
    
    def parse_fork(self, fork_name: str) -> List[SpecChunk]:
        """
        Parse all Python files in a fork directory.
        
        Args:
            fork_name: Name of the fork (e.g., "prague")
            
        Returns:
            List of SpecChunk objects
        """
        fork_dir = self.forks_dir / fork_name
        
        if not fork_dir.exists():
            logger.warning(f"Fork directory not found: {fork_dir}")
            return []
        
        chunks = []
        
        # Find all Python files
        for py_file in fork_dir.rglob("*.py"):
            if py_file.name.startswith('_') and py_file.name != "__init__.py":
                continue
            
            try:
                file_chunks = self.parse_python_file(py_file, fork_name)
                chunks.extend(file_chunks)
            except Exception as e:
                logger.warning(f"Failed to parse {py_file}: {e}")
        
        return chunks
    
    def parse_python_file(self, file_path: Path, fork_name: str) -> List[SpecChunk]:
        """
        Parse a Python file and extract specification chunks.
        
        Args:
            file_path: Path to the Python file
            fork_name: Name of the fork
            
        Returns:
            List of SpecChunk objects
        """
        try:
            content = file_path.read_text(encoding='utf-8')
        except Exception as e:
            logger.warning(f"Failed to read {file_path}: {e}")
            return []
        
        chunks = []
        relative_path = str(file_path.relative_to(self.specs_dir))
        
        # Parse module-level docstring
        module_doc = self._extract_module_docstring(content)
        if module_doc:
            eip_refs = self._extract_eip_references(module_doc)
            chunks.append(SpecChunk(
                content=module_doc,
                fork_name=fork_name,
                file_path=relative_path,
                chunk_type="module",
                name=file_path.stem,
                eip_references=eip_refs,
                line_start=1,
                line_end=module_doc.count('\n') + 1
            ))
        
        # Parse AST for functions and classes
        try:
            tree = ast.parse(content)
            chunks.extend(self._extract_from_ast(tree, content, fork_name, relative_path))
        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_path}: {e}")
            # Fall back to regex-based extraction
            chunks.extend(self._extract_with_regex(content, fork_name, relative_path))
        
        return chunks
    
    def _extract_from_ast(
        self, 
        tree: ast.AST, 
        content: str,
        fork_name: str,
        file_path: str
    ) -> List[SpecChunk]:
        """Extract chunks from AST nodes."""
        chunks = []
        lines = content.split('\n')
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                chunk = self._extract_function(node, lines, fork_name, file_path)
                if chunk:
                    chunks.append(chunk)
            
            elif isinstance(node, ast.ClassDef):
                chunk = self._extract_class(node, lines, fork_name, file_path)
                if chunk:
                    chunks.append(chunk)
        
        return chunks
    
    def _extract_function(
        self, 
        node: ast.FunctionDef, 
        lines: List[str],
        fork_name: str,
        file_path: str
    ) -> Optional[SpecChunk]:
        """Extract a function definition as a chunk."""
        # Skip private functions (but include dunder methods)
        if node.name.startswith('_') and not node.name.startswith('__'):
            return None
        
        # Get function source
        start_line = node.lineno - 1
        end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line + 20
        
        func_lines = lines[start_line:end_line]
        func_content = '\n'.join(func_lines)
        
        # Get docstring
        docstring = ast.get_docstring(node) or ""
        
        # Extract EIP references from docstring and function body
        eip_refs = self._extract_eip_references(func_content)
        
        # Build chunk content
        content_parts = []
        
        # Add function signature
        signature = self._get_function_signature(node)
        content_parts.append(f"def {signature}")
        
        # Add docstring
        if docstring:
            content_parts.append(f'"""{docstring}"""')
        
        # Add function body (truncated if too long)
        body_content = func_content
        if len(body_content) > 2000:
            body_content = body_content[:2000] + "\n# ... (truncated)"
        content_parts.append(body_content)
        
        return SpecChunk(
            content='\n'.join(content_parts),
            fork_name=fork_name,
            file_path=file_path,
            chunk_type="function",
            name=node.name,
            eip_references=eip_refs,
            line_start=node.lineno,
            line_end=end_line
        )
    
    def _extract_class(
        self, 
        node: ast.ClassDef, 
        lines: List[str],
        fork_name: str,
        file_path: str
    ) -> Optional[SpecChunk]:
        """Extract a class definition as a chunk."""
        # Get class source
        start_line = node.lineno - 1
        end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line + 50
        
        class_lines = lines[start_line:end_line]
        class_content = '\n'.join(class_lines)
        
        # Get docstring
        docstring = ast.get_docstring(node) or ""
        
        # Extract EIP references
        eip_refs = self._extract_eip_references(class_content)
        
        # Build chunk content
        content_parts = []
        
        # Add class definition with bases
        bases = [self._get_node_name(base) for base in node.bases]
        bases_str = f"({', '.join(bases)})" if bases else ""
        content_parts.append(f"class {node.name}{bases_str}:")
        
        # Add docstring
        if docstring:
            content_parts.append(f'    """{docstring}"""')
        
        # Add class body (truncated if too long)
        if len(class_content) > 3000:
            class_content = class_content[:3000] + "\n    # ... (truncated)"
        content_parts.append(class_content)
        
        return SpecChunk(
            content='\n'.join(content_parts),
            fork_name=fork_name,
            file_path=file_path,
            chunk_type="class",
            name=node.name,
            eip_references=eip_refs,
            line_start=node.lineno,
            line_end=end_line
        )
    
    def _get_function_signature(self, node: ast.FunctionDef) -> str:
        """Get function signature as string."""
        args = []
        
        # Regular arguments
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                arg_str += f": {self._get_node_name(arg.annotation)}"
            args.append(arg_str)
        
        # Build signature
        sig = f"{node.name}({', '.join(args)})"
        
        # Add return type
        if node.returns:
            sig += f" -> {self._get_node_name(node.returns)}"
        
        return sig
    
    def _get_node_name(self, node: ast.AST) -> str:
        """Get name from an AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_node_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Subscript):
            return f"{self._get_node_name(node.value)}[...]"
        elif isinstance(node, ast.Constant):
            return repr(node.value)
        else:
            return "..."
    
    def _extract_module_docstring(self, content: str) -> str:
        """Extract module-level docstring."""
        # Match triple-quoted string at the beginning (after comments/blank lines)
        pattern = r'^(?:\s*#.*\n)*\s*("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\')'
        match = re.match(pattern, content)
        if match:
            docstring = match.group(1)
            # Remove quotes
            return docstring[3:-3].strip()
        return ""
    
    def _extract_eip_references(self, text: str) -> List[str]:
        """Extract EIP/ERC references from text."""
        # Match patterns like EIP-1559, EIP 1559, EIP1559, ERC-20, etc.
        patterns = [
            r'EIP[- ]?(\d+)',
            r'ERC[- ]?(\d+)',
        ]
        
        refs = set()
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for num in matches:
                if pattern.startswith('ERC'):
                    refs.add(f"ERC-{num}")
                else:
                    refs.add(f"EIP-{num}")
        
        return sorted(list(refs))
    
    def _extract_with_regex(
        self, 
        content: str, 
        fork_name: str, 
        file_path: str
    ) -> List[SpecChunk]:
        """Fallback extraction using regex (for files with syntax errors)."""
        chunks = []
        
        # Extract function definitions
        func_pattern = r'def\s+(\w+)\s*\([^)]*\)[^:]*:\s*("""[\s\S]*?""")?'
        for match in re.finditer(func_pattern, content):
            name = match.group(1)
            docstring = match.group(2) or ""
            
            # Get surrounding context
            start = max(0, match.start() - 50)
            end = min(len(content), match.end() + 500)
            context = content[start:end]
            
            eip_refs = self._extract_eip_references(context)
            
            chunks.append(SpecChunk(
                content=context,
                fork_name=fork_name,
                file_path=file_path,
                chunk_type="function",
                name=name,
                eip_references=eip_refs,
                line_start=content[:match.start()].count('\n') + 1,
                line_end=content[:match.end()].count('\n') + 1
            ))
        
        return chunks
    
    def _parse_docs(self) -> List[SpecChunk]:
        """Parse documentation files."""
        chunks = []
        docs_dir = self.specs_dir / "docs"
        
        if not docs_dir.exists():
            return chunks
        
        for doc_file in docs_dir.rglob("*.md"):
            try:
                content = doc_file.read_text(encoding='utf-8')
                
                # Split into sections
                sections = self._split_markdown(content)
                
                for section in sections:
                    if len(section['content']) < 50:
                        continue
                    
                    eip_refs = self._extract_eip_references(section['content'])
                    
                    chunks.append(SpecChunk(
                        content=section['content'],
                        fork_name="docs",
                        file_path=str(doc_file.relative_to(self.specs_dir)),
                        chunk_type="documentation",
                        name=section['title'],
                        eip_references=eip_refs,
                        line_start=section.get('line_start', 0),
                        line_end=section.get('line_end', 0)
                    ))
            except Exception as e:
                logger.warning(f"Failed to parse doc {doc_file}: {e}")
        
        return chunks
    
    def _split_markdown(self, content: str) -> List[Dict[str, Any]]:
        """Split markdown into sections by headers."""
        sections = []
        current_section = {'title': 'Introduction', 'content': '', 'line_start': 1}
        
        lines = content.split('\n')
        for i, line in enumerate(lines):
            # Check for header
            header_match = re.match(r'^(#{1,3})\s+(.+)$', line)
            if header_match:
                # Save current section
                if current_section['content'].strip():
                    current_section['line_end'] = i
                    sections.append(current_section)
                
                # Start new section
                current_section = {
                    'title': header_match.group(2),
                    'content': '',
                    'line_start': i + 1
                }
            else:
                current_section['content'] += line + '\n'
        
        # Save last section
        if current_section['content'].strip():
            current_section['line_end'] = len(lines)
            sections.append(current_section)
        
        return sections
