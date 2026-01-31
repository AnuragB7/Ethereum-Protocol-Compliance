"""
Code Parsers for Multiple Languages
Supports Python, Java, and COBOL code analysis
"""

import ast
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CodeEntity:
    """Represents a code entity (function, class, method)"""
    name: str
    type: str  # 'function', 'class', 'method', 'program'
    file_path: str
    line_start: int
    line_end: int
    language: str
    parameters: List[str] = field(default_factory=list)
    return_type: Optional[str] = None
    calls: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    body: str = ""
    parent: Optional[str] = None  # Parent class/module


@dataclass
class CodeRelationship:
    """Represents relationships between code entities"""
    source: str
    target: str
    relationship_type: str  # 'calls', 'inherits', 'imports', 'defines'
    file_path: str


class PythonParser:
    """Parse Python code and extract entities and relationships"""
    
    def __init__(self):
        self.entities: List[CodeEntity] = []
        self.relationships: List[CodeRelationship] = []
    
    def parse_file(self, file_path: str, content: str) -> tuple:
        """Parse Python file and extract entities and relationships"""
        try:
            tree = ast.parse(content)
            self.entities = []
            self.relationships = []
            self._visit_node(tree, file_path)
            return self.entities, self.relationships
        except Exception as e:
            print(f"Error parsing Python file {file_path}: {e}")
            return [], []
    
    def _visit_node(self, node: ast.AST, file_path: str, parent: Optional[str] = None):
        """Recursively visit AST nodes"""
        if isinstance(node, ast.FunctionDef):
            self._extract_function(node, file_path, parent)
        elif isinstance(node, ast.ClassDef):
            self._extract_class(node, file_path, parent)
        elif isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
            self._extract_import(node, file_path)
        
        # Visit child nodes
        for child in ast.iter_child_nodes(node):
            self._visit_node(child, file_path, parent)
    
    def _extract_function(self, node: ast.FunctionDef, file_path: str, parent: Optional[str]):
        """Extract function/method information"""
        params = [arg.arg for arg in node.args.args]
        docstring = ast.get_docstring(node)
        
        # Extract function calls
        calls = self._extract_calls(node)
        
        # Get return type annotation if present
        return_type = None
        if node.returns:
            return_type = ast.unparse(node.returns) if hasattr(ast, 'unparse') else str(node.returns)
        
        entity = CodeEntity(
            name=node.name,
            type='method' if parent else 'function',
            file_path=file_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            language='python',
            parameters=params,
            return_type=return_type,
            calls=calls,
            docstring=docstring,
            parent=parent
        )
        self.entities.append(entity)
        
        # Add call relationships
        for call in calls:
            self.relationships.append(CodeRelationship(
                source=node.name,
                target=call,
                relationship_type='calls',
                file_path=file_path
            ))
    
    def _extract_class(self, node: ast.ClassDef, file_path: str, parent: Optional[str]):
        """Extract class information"""
        docstring = ast.get_docstring(node)
        
        entity = CodeEntity(
            name=node.name,
            type='class',
            file_path=file_path,
            line_start=node.lineno,
            line_end=node.end_lineno or node.lineno,
            language='python',
            docstring=docstring,
            parent=parent
        )
        self.entities.append(entity)
        
        # Extract inheritance
        for base in node.bases:
            if isinstance(base, ast.Name):
                self.relationships.append(CodeRelationship(
                    source=node.name,
                    target=base.id,
                    relationship_type='inherits',
                    file_path=file_path
                ))
        
        # Visit methods
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                self._extract_function(item, file_path, parent=node.name)
    
    def _extract_import(self, node: ast.AST, file_path: str):
        """Extract import statements"""
        if isinstance(node, ast.Import):
            for alias in node.names:
                self.relationships.append(CodeRelationship(
                    source=file_path,
                    target=alias.name,
                    relationship_type='imports',
                    file_path=file_path
                ))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                for alias in node.names:
                    self.relationships.append(CodeRelationship(
                        source=file_path,
                        target=f"{node.module}.{alias.name}",
                        relationship_type='imports',
                        file_path=file_path
                    ))
    
    def _extract_calls(self, node: ast.FunctionDef) -> List[str]:
        """Extract function calls within a function"""
        calls = []
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                if isinstance(child.func, ast.Name):
                    calls.append(child.func.id)
                elif isinstance(child.func, ast.Attribute):
                    calls.append(child.func.attr)
        return list(set(calls))  # Remove duplicates


class JavaParser:
    """Parse Java code and extract entities and relationships"""
    
    def __init__(self):
        self.entities: List[CodeEntity] = []
        self.relationships: List[CodeRelationship] = []
    
    def parse_file(self, file_path: str, content: str) -> tuple:
        """Parse Java file using regex patterns"""
        self.entities = []
        self.relationships = []
        
        # Extract package
        package_match = re.search(r'package\s+([\w.]+);', content)
        package_name = package_match.group(1) if package_match else ''
        
        # Extract imports
        self._extract_imports(content, file_path)
        
        # Extract classes
        self._extract_classes(content, file_path, package_name)
        
        return self.entities, self.relationships
    
    def _extract_imports(self, content: str, file_path: str):
        """Extract import statements"""
        import_pattern = r'import\s+(static\s+)?([\w.]+);'
        for match in re.finditer(import_pattern, content):
            import_name = match.group(2)
            self.relationships.append(CodeRelationship(
                source=file_path,
                target=import_name,
                relationship_type='imports',
                file_path=file_path
            ))
    
    def _extract_classes(self, content: str, file_path: str, package_name: str):
        """Extract class definitions"""
        # Pattern for class declaration
        class_pattern = r'(public|private|protected)?\s*(abstract|final)?\s*class\s+(\w+)\s*(?:extends\s+(\w+))?\s*(?:implements\s+([\w,\s]+))?\s*\{'
        
        lines = content.split('\n')
        
        for match in re.finditer(class_pattern, content, re.MULTILINE):
            class_name = match.group(3)
            extends = match.group(4)
            
            # Find line numbers
            start_line = content[:match.start()].count('\n') + 1
            
            entity = CodeEntity(
                name=class_name,
                type='class',
                file_path=file_path,
                line_start=start_line,
                line_end=start_line + 1,  # Simplified
                language='java'
            )
            self.entities.append(entity)
            
            # Add inheritance relationship
            if extends:
                self.relationships.append(CodeRelationship(
                    source=class_name,
                    target=extends,
                    relationship_type='inherits',
                    file_path=file_path
                ))
            
            # Extract methods within class
            self._extract_methods(content, file_path, class_name, start_line)
    
    def _extract_methods(self, content: str, file_path: str, class_name: str, class_start: int):
        """Extract method definitions"""
        # Simplified method pattern
        method_pattern = r'(public|private|protected)?\s*(static)?\s*([\w<>\[\]]+)\s+(\w+)\s*\((.*?)\)\s*(?:throws\s+[\w,\s]+)?\s*\{'
        
        for match in re.finditer(method_pattern, content):
            return_type = match.group(3)
            method_name = match.group(4)
            params_str = match.group(5)
            
            # Parse parameters
            params = []
            if params_str.strip():
                for param in params_str.split(','):
                    param = param.strip()
                    if param:
                        parts = param.split()
                        if len(parts) >= 2:
                            params.append(parts[-1])
            
            start_line = content[:match.start()].count('\n') + 1
            
            # Extract method calls
            method_body = self._extract_method_body(content[match.end():])
            calls = self._extract_java_calls(method_body)
            
            entity = CodeEntity(
                name=method_name,
                type='method',
                file_path=file_path,
                line_start=start_line,
                line_end=start_line + 1,
                language='java',
                parameters=params,
                return_type=return_type,
                calls=calls,
                parent=class_name
            )
            self.entities.append(entity)
            
            # Add call relationships
            for call in calls:
                self.relationships.append(CodeRelationship(
                    source=method_name,
                    target=call,
                    relationship_type='calls',
                    file_path=file_path
                ))
    
    def _extract_method_body(self, text: str) -> str:
        """Extract method body (simplified)"""
        brace_count = 1
        body = []
        for char in text:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    break
            body.append(char)
        return ''.join(body)
    
    def _extract_java_calls(self, body: str) -> List[str]:
        """Extract method calls from Java code"""
        call_pattern = r'(\w+)\s*\('
        calls = [match.group(1) for match in re.finditer(call_pattern, body)]
        return list(set(calls))


class CobolParser:
    """Parse COBOL code and extract entities and relationships"""
    
    def __init__(self):
        self.entities: List[CodeEntity] = []
        self.relationships: List[CodeRelationship] = []
    
    def parse_file(self, file_path: str, content: str) -> tuple:
        """Parse COBOL file"""
        self.entities = []
        self.relationships = []
        
        # Extract program name
        self._extract_program(content, file_path)
        
        # Extract paragraphs (similar to functions)
        self._extract_paragraphs(content, file_path)
        
        # Extract sections
        self._extract_sections(content, file_path)
        
        return self.entities, self.relationships
    
    def _extract_program(self, content: str, file_path: str):
        """Extract COBOL program name"""
        program_pattern = r'PROGRAM-ID\.\s+(\S+)'
        match = re.search(program_pattern, content, re.IGNORECASE)
        if match:
            program_name = match.group(1).rstrip('.')
            start_line = content[:match.start()].count('\n') + 1
            
            entity = CodeEntity(
                name=program_name,
                type='program',
                file_path=file_path,
                line_start=start_line,
                line_end=start_line,
                language='cobol'
            )
            self.entities.append(entity)
    
    def _extract_paragraphs(self, content: str, file_path: str):
        """Extract COBOL paragraphs"""
        # COBOL paragraph pattern (label at start of line)
        paragraph_pattern = r'^[\s]*([A-Z0-9][A-Z0-9\-]*)\s*\.\s*$'
        
        lines = content.split('\n')
        for i, line in enumerate(lines):
            match = re.match(paragraph_pattern, line)
            if match:
                para_name = match.group(1)
                
                # Skip division/section names
                if any(keyword in para_name for keyword in ['DIVISION', 'SECTION', 'DATA', 'PROCEDURE']):
                    continue
                
                # Extract PERFORM calls within paragraph
                para_content = self._get_paragraph_content(lines, i)
                calls = self._extract_cobol_calls(para_content)
                
                entity = CodeEntity(
                    name=para_name,
                    type='function',
                    file_path=file_path,
                    line_start=i + 1,
                    line_end=i + len(para_content),
                    language='cobol',
                    calls=calls,
                    body='\n'.join(para_content)
                )
                self.entities.append(entity)
                
                # Add call relationships
                for call in calls:
                    self.relationships.append(CodeRelationship(
                        source=para_name,
                        target=call,
                        relationship_type='calls',
                        file_path=file_path
                    ))
    
    def _extract_sections(self, content: str, file_path: str):
        """Extract COBOL sections"""
        section_pattern = r'^[\s]*([A-Z0-9][A-Z0-9\-]*)\s+SECTION\s*\.'
        
        for match in re.finditer(section_pattern, content, re.IGNORECASE | re.MULTILINE):
            section_name = match.group(1)
            start_line = content[:match.start()].count('\n') + 1
            
            entity = CodeEntity(
                name=section_name,
                type='function',
                file_path=file_path,
                line_start=start_line,
                line_end=start_line,
                language='cobol'
            )
            self.entities.append(entity)
    
    def _get_paragraph_content(self, lines: List[str], start_idx: int) -> List[str]:
        """Get paragraph content until next paragraph or section"""
        content = []
        for i in range(start_idx + 1, len(lines)):
            line = lines[i].strip()
            # Stop at next paragraph/section
            if re.match(r'^[A-Z0-9][A-Z0-9\-]*\s*\.?\s*$', line):
                break
            content.append(lines[i])
        return content
    
    def _extract_cobol_calls(self, content: List[str]) -> List[str]:
        """Extract PERFORM calls from COBOL code"""
        calls = []
        perform_pattern = r'PERFORM\s+([A-Z0-9][A-Z0-9\-]*)'
        
        for line in content:
            matches = re.finditer(perform_pattern, line, re.IGNORECASE)
            for match in matches:
                calls.append(match.group(1))
        
        return list(set(calls))


class JavaScriptParser:
    """Parse JavaScript/TypeScript/React/Vue/Next.js code"""
    
    def __init__(self):
        self.entities: List[CodeEntity] = []
        self.relationships: List[CodeRelationship] = []
    
    def parse_file(self, file_path: str, content: str) -> tuple:
        """Parse JS/TS/JSX/TSX/Vue file"""
        try:
            self.entities = []
            self.relationships = []
            
            # Determine framework
            framework = self._detect_framework(content, file_path)
            language = self._detect_language(file_path)
            
            # Extract components, functions, hooks, etc.
            self._extract_functions(content, file_path, language, framework)
            self._extract_classes(content, file_path, language, framework)
            self._extract_react_components(content, file_path, language, framework)
            self._extract_vue_components(content, file_path, language, framework)
            self._extract_imports(content, file_path, language)
            
            return self.entities, self.relationships
        except Exception as e:
            print(f"Error parsing JS/TS file {file_path}: {e}")
            return [], []
    
    def _detect_framework(self, content: str, file_path: str) -> str:
        """Detect React, Vue, Next.js, or vanilla JS"""
        if 'vue' in file_path.lower() or '<template>' in content:
            return 'vue'
        elif 'pages/' in file_path or 'app/' in file_path:
            if 'next' in content.lower() or 'getServerSideProps' in content or 'getStaticProps' in content:
                return 'nextjs'
        
        if 'import React' in content or 'from \'react\'' in content or 'from "react"' in content:
            return 'react'
        elif 'useState' in content or 'useEffect' in content or 'React.' in content:
            return 'react'
        
        return 'javascript'
    
    def _detect_language(self, file_path: str) -> str:
        """Detect JavaScript or TypeScript"""
        if file_path.endswith(('.ts', '.tsx')):
            return 'typescript'
        elif file_path.endswith('.vue'):
            return 'vue'
        return 'javascript'
    
    def _extract_functions(self, content: str, file_path: str, language: str, framework: str):
        """Extract regular functions and arrow functions"""
        # Match function declarations
        func_pattern = r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)'
        for match in re.finditer(func_pattern, content):
            name = match.group(1)
            params = [p.strip().split(':')[0].strip() for p in match.group(2).split(',') if p.strip()]
            line_num = content[:match.start()].count('\n') + 1
            
            entity = CodeEntity(
                name=name,
                type='function',
                file_path=file_path,
                line_start=line_num,
                line_end=line_num,
                language=language,
                parameters=params,
                calls=self._extract_function_calls(content, match.start(), match.end()),
                parent=None
            )
            self.entities.append(entity)
        
        # Match arrow functions assigned to const/let/var
        arrow_pattern = r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?\(([^)]*)\)\s*=>'
        for match in re.finditer(arrow_pattern, content):
            name = match.group(1)
            params = [p.strip().split(':')[0].strip() for p in match.group(2).split(',') if p.strip()]
            line_num = content[:match.start()].count('\n') + 1
            
            entity = CodeEntity(
                name=name,
                type='function',
                file_path=file_path,
                line_start=line_num,
                line_end=line_num,
                language=language,
                parameters=params,
                calls=self._extract_function_calls(content, match.start(), match.end()),
                parent=None
            )
            self.entities.append(entity)
    
    def _extract_classes(self, content: str, file_path: str, language: str, framework: str):
        """Extract class declarations"""
        class_pattern = r'(?:export\s+)?(?:default\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?'
        for match in re.finditer(class_pattern, content):
            name = match.group(1)
            parent = match.group(2)
            line_num = content[:match.start()].count('\n') + 1
            
            entity = CodeEntity(
                name=name,
                type='class',
                file_path=file_path,
                line_start=line_num,
                line_end=line_num,
                language=language,
                parent=parent
            )
            self.entities.append(entity)
            
            if parent:
                rel = CodeRelationship(
                    source=name,
                    target=parent,
                    relationship_type='extends',
                    file_path=file_path
                )
                self.relationships.append(rel)
    
    def _extract_react_components(self, content: str, file_path: str, language: str, framework: str):
        """Extract React components (functional and class-based)"""
        if framework not in ['react', 'nextjs']:
            return
        
        # Functional components (named exports)
        func_comp_pattern = r'(?:export\s+)?(?:const|let|var|function)\s+([A-Z]\w+)\s*[=:]?\s*(?:\([^)]*\))?\s*(?:=>|{)'
        for match in re.finditer(func_comp_pattern, content):
            name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            
            # Check if it looks like a component (starts with capital letter and returns JSX)
            if name[0].isupper():
                # Extract hooks used
                hooks = self._extract_react_hooks(content, match.start(), min(match.end() + 500, len(content)))
                
                entity = CodeEntity(
                    name=name,
                    type='react_component',
                    file_path=file_path,
                    line_start=line_num,
                    line_end=line_num,
                    language=language,
                    calls=hooks,
                    parent='React'
                )
                self.entities.append(entity)
        
        # Next.js specific pages
        if framework == 'nextjs':
            # getServerSideProps
            if 'getServerSideProps' in content:
                line_num = content.find('getServerSideProps')
                if line_num != -1:
                    line_num = content[:line_num].count('\n') + 1
                    entity = CodeEntity(
                        name='getServerSideProps',
                        type='nextjs_function',
                        file_path=file_path,
                        line_start=line_num,
                        line_end=line_num,
                        language=language,
                        parent='Next.js'
                    )
                    self.entities.append(entity)
            
            # getStaticProps
            if 'getStaticProps' in content:
                line_num = content.find('getStaticProps')
                if line_num != -1:
                    line_num = content[:line_num].count('\n') + 1
                    entity = CodeEntity(
                        name='getStaticProps',
                        type='nextjs_function',
                        file_path=file_path,
                        line_start=line_num,
                        line_end=line_num,
                        language=language,
                        parent='Next.js'
                    )
                    self.entities.append(entity)
    
    def _extract_vue_components(self, content: str, file_path: str, language: str, framework: str):
        """Extract Vue.js components"""
        if framework != 'vue':
            return
        
        # Extract component name from file name
        component_name = Path(file_path).stem
        
        # Extract setup function (Composition API)
        if '<script setup' in content or 'setup()' in content:
            entity = CodeEntity(
                name=component_name,
                type='vue_component',
                file_path=file_path,
                line_start=1,
                line_end=content.count('\n'),
                language='vue',
                calls=self._extract_vue_composables(content),
                parent='Vue'
            )
            self.entities.append(entity)
        
        # Extract methods from Options API
        methods_pattern = r'methods:\s*{([^}]+)}'
        for match in re.finditer(methods_pattern, content, re.DOTALL):
            method_content = match.group(1)
            method_names = re.findall(r'(\w+)\s*\(', method_content)
            
            for method_name in method_names:
                entity = CodeEntity(
                    name=method_name,
                    type='vue_method',
                    file_path=file_path,
                    line_start=content[:match.start()].count('\n') + 1,
                    line_end=content[:match.start()].count('\n') + 1,
                    language='vue',
                    parent=component_name
                )
                self.entities.append(entity)
    
    def _extract_react_hooks(self, content: str, start: int, end: int) -> List[str]:
        """Extract React hooks usage"""
        hooks = []
        hook_pattern = r'(use[A-Z]\w+)\s*\('
        section = content[start:end]
        
        for match in re.finditer(hook_pattern, section):
            hooks.append(match.group(1))
        
        return list(set(hooks))
    
    def _extract_vue_composables(self, content: str) -> List[str]:
        """Extract Vue composables usage"""
        composables = []
        composable_pattern = r'(use[A-Z]\w+|ref|reactive|computed|watch|onMounted|onUnmounted)\s*\('
        
        for match in re.finditer(composable_pattern, content):
            composables.append(match.group(1))
        
        return list(set(composables))
    
    def _extract_imports(self, content: str, file_path: str, language: str):
        """Extract import statements"""
        # ES6 imports
        import_pattern = r'import\s+(?:{[^}]+}|[\w,\s]+)\s+from\s+[\'"]([^\'"]+)[\'"]'
        for match in re.finditer(import_pattern, content):
            imported_module = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            
            # Create relationship for imports
            rel = CodeRelationship(
                source='file',
                target=imported_module,
                relationship_type='imports',
                file_path=file_path
            )
            self.relationships.append(rel)
    
    def _extract_function_calls(self, content: str, start: int, end: int) -> List[str]:
        """Extract function calls within a function"""
        calls = []
        section = content[start:min(end + 200, len(content))]
        
        # Match function calls
        call_pattern = r'(\w+)\s*\('
        for match in re.finditer(call_pattern, section):
            calls.append(match.group(1))
        
        return list(set(calls))


class GoParser:
    """Parse Go code and extract entities and relationships"""
    
    def __init__(self):
        self.entities: List[CodeEntity] = []
        self.relationships: List[CodeRelationship] = []
    
    def parse_file(self, file_path: str, content: str) -> tuple:
        """Parse Go file and extract entities and relationships"""
        try:
            self.entities = []
            self.relationships = []
            
            # Extract package name
            package_name = self._extract_package(content, file_path)
            
            # Extract imports
            self._extract_imports(content, file_path)
            
            # Extract structs (before methods so we can reference them)
            self._extract_structs(content, file_path, package_name)
            
            # Extract interfaces
            self._extract_interfaces(content, file_path, package_name)
            
            # Extract functions (standalone)
            self._extract_functions(content, file_path, package_name)
            
            # Extract methods (with receivers)
            self._extract_methods(content, file_path, package_name)
            
            # Extract goroutine launches
            self._extract_goroutines(content, file_path)
            
            # Extract channel operations
            self._extract_channels(content, file_path)
            
            # Extract Ethereum-specific patterns
            self._extract_ethereum_patterns(content, file_path, package_name)
            
            return self.entities, self.relationships
        except Exception as e:
            print(f"Error parsing Go file {file_path}: {e}")
            return [], []
    
    def _extract_package(self, content: str, file_path: str) -> str:
        """Extract Go package declaration"""
        package_pattern = r'^package\s+(\w+)'
        match = re.search(package_pattern, content, re.MULTILINE)
        if match:
            package_name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            
            entity = CodeEntity(
                name=package_name,
                type='package',
                file_path=file_path,
                line_start=line_num,
                line_end=line_num,
                language='go'
            )
            self.entities.append(entity)
            return package_name
        return ''
    
    def _extract_imports(self, content: str, file_path: str):
        """Extract Go import statements"""
        # Single import: import "package"
        single_import_pattern = r'import\s+"([^"]+)"'
        for match in re.finditer(single_import_pattern, content):
            import_path = match.group(1)
            self.relationships.append(CodeRelationship(
                source=file_path,
                target=import_path,
                relationship_type='imports',
                file_path=file_path
            ))
        
        # Grouped imports: import ( "pkg1" "pkg2" )
        grouped_import_pattern = r'import\s*\(\s*([\s\S]*?)\s*\)'
        for match in re.finditer(grouped_import_pattern, content):
            imports_block = match.group(1)
            # Parse each import line
            import_line_pattern = r'(?:(\w+)\s+)?"([^"]+)"'
            for imp_match in re.finditer(import_line_pattern, imports_block):
                alias = imp_match.group(1)  # Optional alias
                import_path = imp_match.group(2)
                self.relationships.append(CodeRelationship(
                    source=file_path,
                    target=import_path,
                    relationship_type='imports',
                    file_path=file_path
                ))
    
    def _extract_structs(self, content: str, file_path: str, package_name: str):
        """Extract Go struct definitions"""
        # Match: type StructName struct { ... }
        struct_pattern = r'type\s+(\w+)\s+struct\s*\{'
        
        for match in re.finditer(struct_pattern, content):
            struct_name = match.group(1)
            line_start = content[:match.start()].count('\n') + 1
            
            # Find the end of the struct (matching braces)
            struct_body = self._extract_body(content[match.end():])
            line_end = line_start + struct_body.count('\n')
            
            # Extract struct fields
            fields = self._extract_struct_fields(struct_body)
            
            # Check for embedded structs (composition/inheritance)
            embedded = self._extract_embedded_types(struct_body)
            
            entity = CodeEntity(
                name=struct_name,
                type='struct',
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                language='go',
                parameters=fields,
                body=struct_body,
                parent=package_name
            )
            self.entities.append(entity)
            
            # Add composition relationships for embedded types
            for embedded_type in embedded:
                self.relationships.append(CodeRelationship(
                    source=struct_name,
                    target=embedded_type,
                    relationship_type='embeds',
                    file_path=file_path
                ))
    
    def _extract_interfaces(self, content: str, file_path: str, package_name: str):
        """Extract Go interface definitions"""
        interface_pattern = r'type\s+(\w+)\s+interface\s*\{'
        
        for match in re.finditer(interface_pattern, content):
            interface_name = match.group(1)
            line_start = content[:match.start()].count('\n') + 1
            
            # Find the end of the interface
            interface_body = self._extract_body(content[match.end():])
            line_end = line_start + interface_body.count('\n')
            
            # Extract interface methods
            methods = self._extract_interface_methods(interface_body)
            
            entity = CodeEntity(
                name=interface_name,
                type='interface',
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                language='go',
                parameters=methods,
                body=interface_body,
                parent=package_name
            )
            self.entities.append(entity)
    
    def _extract_functions(self, content: str, file_path: str, package_name: str):
        """Extract standalone Go functions (not methods)"""
        # Match: func FunctionName[T any](params) returnType { or func FunctionName(params) (returnType1, returnType2) {
        func_pattern = r'func\s+(\w+)\s*(?:\[[^\]]*\])?\s*\(([^)]*)\)\s*(?:\(([^)]+)\)|(\w+(?:\s*\*?\w+)?))?\s*\{'
        
        for match in re.finditer(func_pattern, content):
            func_name = match.group(1)
            params_str = match.group(2)
            return_type = match.group(3) or match.group(4) or ''
            
            line_start = content[:match.start()].count('\n') + 1
            
            # Extract function body
            func_body = self._extract_body(content[match.end():])
            line_end = line_start + func_body.count('\n')
            
            # Parse parameters
            params = self._parse_go_params(params_str)
            
            # Extract function calls
            calls = self._extract_go_calls(func_body)
            
            # Extract docstring (comment above function)
            docstring = self._extract_go_doc(content, match.start())
            
            entity = CodeEntity(
                name=func_name,
                type='function',
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                language='go',
                parameters=params,
                return_type=return_type.strip() if return_type else None,
                calls=calls,
                docstring=docstring,
                body=func_body,
                parent=package_name
            )
            self.entities.append(entity)
            
            # Add call relationships
            for call in calls:
                self.relationships.append(CodeRelationship(
                    source=func_name,
                    target=call,
                    relationship_type='calls',
                    file_path=file_path
                ))
    
    def _extract_methods(self, content: str, file_path: str, package_name: str):
        """Extract Go methods (functions with receivers)"""
        # Match: func (receiver *Type) MethodName(params) returnType {
        method_pattern = r'func\s*\((\w+)\s+(\*?)(\w+)\)\s*(\w+)\s*(?:\[[^\]]*\])?\s*\(([^)]*)\)\s*(?:\(([^)]+)\)|(\w+(?:\s*\*?\w+)?))?\s*\{'
        
        for match in re.finditer(method_pattern, content):
            receiver_name = match.group(1)
            is_pointer = match.group(2) == '*'
            receiver_type = match.group(3)
            method_name = match.group(4)
            params_str = match.group(5)
            return_type = match.group(6) or match.group(7) or ''
            
            line_start = content[:match.start()].count('\n') + 1
            
            # Extract method body
            method_body = self._extract_body(content[match.end():])
            line_end = line_start + method_body.count('\n')
            
            # Parse parameters
            params = self._parse_go_params(params_str)
            
            # Extract function calls
            calls = self._extract_go_calls(method_body)
            
            # Extract docstring
            docstring = self._extract_go_doc(content, match.start())
            
            entity = CodeEntity(
                name=method_name,
                type='method',
                file_path=file_path,
                line_start=line_start,
                line_end=line_end,
                language='go',
                parameters=params,
                return_type=return_type.strip() if return_type else None,
                calls=calls,
                docstring=docstring,
                body=method_body,
                parent=receiver_type
            )
            self.entities.append(entity)
            
            # Add call relationships
            for call in calls:
                self.relationships.append(CodeRelationship(
                    source=f"{receiver_type}.{method_name}",
                    target=call,
                    relationship_type='calls',
                    file_path=file_path
                ))
            
            # Add defines relationship
            self.relationships.append(CodeRelationship(
                source=receiver_type,
                target=method_name,
                relationship_type='defines',
                file_path=file_path
            ))
    
    def _extract_goroutines(self, content: str, file_path: str):
        """Extract goroutine launches"""
        # Match: go functionName(...) or go func() { ... }()
        goroutine_pattern = r'\bgo\s+(\w+)\s*\('
        
        for match in re.finditer(goroutine_pattern, content):
            func_name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            
            entity = CodeEntity(
                name=f"goroutine_{func_name}",
                type='goroutine',
                file_path=file_path,
                line_start=line_num,
                line_end=line_num,
                language='go',
                calls=[func_name]
            )
            self.entities.append(entity)
            
            self.relationships.append(CodeRelationship(
                source=f"goroutine_{func_name}",
                target=func_name,
                relationship_type='spawns',
                file_path=file_path
            ))
    
    def _extract_channels(self, content: str, file_path: str):
        """Extract channel definitions and operations"""
        # Match channel creation: make(chan Type) or make(chan Type, buffer)
        channel_make_pattern = r'(\w+)\s*:?=\s*make\s*\(\s*chan\s+([^,)]+)(?:\s*,\s*(\d+))?\s*\)'
        
        for match in re.finditer(channel_make_pattern, content):
            channel_name = match.group(1)
            channel_type = match.group(2).strip()
            buffer_size = match.group(3)
            line_num = content[:match.start()].count('\n') + 1
            
            entity = CodeEntity(
                name=channel_name,
                type='channel',
                file_path=file_path,
                line_start=line_num,
                line_end=line_num,
                language='go',
                return_type=f"chan {channel_type}",
                parameters=[f"buffer:{buffer_size}"] if buffer_size else []
            )
            self.entities.append(entity)
    
    def _extract_ethereum_patterns(self, content: str, file_path: str, package_name: str):
        """Extract Ethereum-specific Go patterns (go-ethereum)"""
        # Check for common go-ethereum imports
        eth_imports = [
            'github.com/ethereum/go-ethereum',
            'ethclient',
            'accounts/abi',
            'common',
            'types',
            'crypto',
            'rpc'
        ]
        
        is_ethereum_file = any(imp in content for imp in eth_imports)
        if not is_ethereum_file:
            return
        
        # Extract ethclient connections
        ethclient_pattern = r'ethclient\.Dial\s*\(\s*["\']([^"\']+)["\']\s*\)'
        for match in re.finditer(ethclient_pattern, content):
            endpoint = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            
            entity = CodeEntity(
                name=f"eth_connection_{line_num}",
                type='eth_connection',
                file_path=file_path,
                line_start=line_num,
                line_end=line_num,
                language='go',
                parameters=[endpoint],
                parent=package_name
            )
            self.entities.append(entity)
        
        # Extract contract bindings
        contract_pattern = r'bind\.NewBound(\w+)\s*\('
        for match in re.finditer(contract_pattern, content):
            contract_type = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            
            entity = CodeEntity(
                name=f"contract_{contract_type}",
                type='eth_contract_binding',
                file_path=file_path,
                line_start=line_num,
                line_end=line_num,
                language='go',
                parent=package_name
            )
            self.entities.append(entity)
        
        # Extract transaction signing
        tx_sign_pattern = r'types\.SignTx\s*\('
        for match in re.finditer(tx_sign_pattern, content):
            line_num = content[:match.start()].count('\n') + 1
            
            entity = CodeEntity(
                name=f"tx_signing_{line_num}",
                type='eth_tx_signing',
                file_path=file_path,
                line_start=line_num,
                line_end=line_num,
                language='go',
                parent=package_name
            )
            self.entities.append(entity)
        
        # Extract RPC handlers
        rpc_handler_pattern = r'func\s*\(\w+\s+\*?\w+\)\s*(\w+)\s*\([^)]*\*?\s*rpc\.Context'
        for match in re.finditer(rpc_handler_pattern, content):
            handler_name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            
            entity = CodeEntity(
                name=handler_name,
                type='eth_rpc_handler',
                file_path=file_path,
                line_start=line_num,
                line_end=line_num,
                language='go',
                parent=package_name
            )
            self.entities.append(entity)
    
    def _extract_body(self, text: str) -> str:
        """Extract body content between matching braces"""
        brace_count = 1
        body = []
        for char in text:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    break
            body.append(char)
        return ''.join(body)
    
    def _extract_struct_fields(self, body: str) -> List[str]:
        """Extract struct field names"""
        fields = []
        field_pattern = r'^\s*(\w+)\s+\S+'
        for line in body.split('\n'):
            match = re.match(field_pattern, line.strip())
            if match:
                fields.append(match.group(1))
        return fields
    
    def _extract_embedded_types(self, body: str) -> List[str]:
        """Extract embedded types from struct body"""
        embedded = []
        # Embedded types are fields without names (just type)
        embedded_pattern = r'^\s*(\*?\w+)\s*$'
        for line in body.split('\n'):
            line = line.strip()
            if line and not '//' in line:
                match = re.match(embedded_pattern, line)
                if match:
                    embedded.append(match.group(1).lstrip('*'))
        return embedded
    
    def _extract_interface_methods(self, body: str) -> List[str]:
        """Extract interface method signatures"""
        methods = []
        method_pattern = r'(\w+)\s*\([^)]*\)'
        for match in re.finditer(method_pattern, body):
            methods.append(match.group(1))
        return methods
    
    def _parse_go_params(self, params_str: str) -> List[str]:
        """Parse Go function parameters"""
        if not params_str.strip():
            return []
        
        params = []
        # Split by comma, handling nested types
        depth = 0
        current = []
        for char in params_str:
            if char in '([{':
                depth += 1
            elif char in ')]}':
                depth -= 1
            elif char == ',' and depth == 0:
                param = ''.join(current).strip()
                if param:
                    # Extract parameter name (before type)
                    parts = param.split()
                    if parts:
                        params.append(parts[0])
                current = []
                continue
            current.append(char)
        
        # Last parameter
        param = ''.join(current).strip()
        if param:
            parts = param.split()
            if parts:
                params.append(parts[0])
        
        return params
    
    def _extract_go_calls(self, body: str) -> List[str]:
        """Extract function/method calls from Go code"""
        calls = []
        # Match function calls: functionName(...) or pkg.FunctionName(...)
        call_pattern = r'(?:(\w+)\.)?(\w+)\s*\('
        
        # Keywords to exclude
        keywords = {'if', 'for', 'switch', 'select', 'go', 'defer', 'return', 
                   'make', 'new', 'len', 'cap', 'append', 'copy', 'delete',
                   'close', 'panic', 'recover', 'print', 'println', 'func'}
        
        for match in re.finditer(call_pattern, body):
            pkg = match.group(1)
            func_name = match.group(2)
            
            if func_name.lower() not in keywords:
                if pkg:
                    calls.append(f"{pkg}.{func_name}")
                else:
                    calls.append(func_name)
        
        return list(set(calls))
    
    def _extract_go_doc(self, content: str, func_start: int) -> Optional[str]:
        """Extract Go documentation comment above function"""
        # Find the line before the function
        before = content[:func_start].rstrip()
        lines = before.split('\n')
        
        doc_lines = []
        for line in reversed(lines):
            stripped = line.strip()
            if stripped.startswith('//'):
                doc_lines.insert(0, stripped[2:].strip())
            elif stripped.startswith('/*') or stripped.endswith('*/'):
                # Block comment - simplified handling
                doc_lines.insert(0, stripped.strip('/* '))
            elif stripped == '':
                continue
            else:
                break
        
        return '\n'.join(doc_lines) if doc_lines else None


class CodebaseParser:
    """Main parser that handles multiple languages"""
    
    def __init__(self):
        self.python_parser = PythonParser()
        self.java_parser = JavaParser()
        self.cobol_parser = CobolParser()
        self.js_parser = JavaScriptParser()
        self.go_parser = GoParser()
    
    def parse_codebase(self, root_path: str) -> Dict[str, Any]:
        """
        Parse entire codebase and extract all entities and relationships
        
        Args:
            root_path: Root directory of codebase
            
        Returns:
            Dictionary with entities and relationships
        """
        all_entities = []
        all_relationships = []
        
        root = Path(root_path)
        
        # File extensions to parse
        extensions = {
            '.py': self.python_parser,
            '.java': self.java_parser,
            '.cob': self.cobol_parser,
            '.cbl': self.cobol_parser,
            '.js': self.js_parser,
            '.jsx': self.js_parser,
            '.ts': self.js_parser,
            '.tsx': self.js_parser,
            '.vue': self.js_parser,
            '.go': self.go_parser,
        }
        
        for ext, parser in extensions.items():
            files = list(root.rglob(f'*{ext}'))
            print(f"Found {len(files)} {ext} files")
            
            for file_path in files:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    
                    entities, relationships = parser.parse_file(str(file_path), content)
                    all_entities.extend(entities)
                    all_relationships.extend(relationships)
                    
                    print(f"Parsed: {file_path.name} - {len(entities)} entities, {len(relationships)} relationships")
                except Exception as e:
                    print(f"Error parsing {file_path}: {e}")
        
        return {
            'entities': all_entities,
            'relationships': all_relationships,
            'total_files': sum(len(list(root.rglob(f'*{ext}'))) for ext in extensions.keys()),
            'total_entities': len(all_entities),
            'total_relationships': len(all_relationships)
        }

