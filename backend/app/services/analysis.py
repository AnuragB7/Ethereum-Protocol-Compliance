"""
Analysis Engine - Generates functional understanding and test cases
"""

from typing import List, Dict, Any, Optional
from app.core.indexer import CodeGraphIndexer


class FunctionalAnalyzer:
    """
    Analyzes code functionality and generates insights
    """
    
    def __init__(self, indexer: CodeGraphIndexer):
        self.indexer = indexer
    
    def analyze_function(self, function_name: str) -> Dict[str, Any]:
        """
        Deep analysis of a specific function
        
        Args:
            function_name: Name of function to analyze
            
        Returns:
            Analysis results dictionary
        """
        entity = self.indexer.get_entity_by_name(function_name)
        if not entity:
            return {'error': f'Function {function_name} not found'}
        
        # Get call chains
        call_chains = self.indexer.get_call_chain(function_name, depth=3)
        
        # Build detailed prompt for LLM analysis
        prompt = f"""
        Analyze this {entity.language} {entity.type} in detail:
        
        Name: {entity.name}
        File: {entity.file_path}
        Lines: {entity.line_start}-{entity.line_end}
        Parameters: {', '.join(entity.parameters) if entity.parameters else 'None'}
        Return Type: {entity.return_type or 'Not specified'}
        
        Function Calls Made: {', '.join(entity.calls) if entity.calls else 'None'}
        
        Call Chains (execution paths):
        {self._format_call_chains(call_chains)}
        
        Documentation: {entity.docstring or 'No documentation available'}
        
        Provide a comprehensive functional analysis:
        
        1. **Purpose**: What is the primary business/functional purpose?
        2. **Inputs**: What inputs does it accept and what are their purposes?
        3. **Processing Logic**: What operations/transformations does it perform?
        4. **Outputs**: What does it return/produce?
        5. **Side Effects**: Any state changes, I/O operations, external calls?
        6. **Dependencies**: What other components does it depend on?
        7. **Call Flow**: How does the execution flow through the call chains?
        8. **Business Logic**: What business rules or algorithms are implemented?
        """
        
        analysis = self.indexer.query(prompt)
        
        return {
            'function_name': function_name,
            'entity': entity,
            'call_chains': call_chains,
            'analysis': analysis
        }
    
    def analyze_module(self, file_path: str) -> Dict[str, Any]:
        """
        Analyze an entire module/file
        
        Args:
            file_path: Path to file
            
        Returns:
            Module analysis
        """
        # Get all entities in this file
        entities = [e for e in self.indexer.entities if e.file_path == file_path]
        
        if not entities:
            return {'error': f'No entities found in {file_path}'}
        
        entity_summary = '\n'.join([
            f"- {e.name} ({e.type}): {len(e.calls)} calls, {len(e.parameters)} params"
            for e in entities
        ])
        
        prompt = f"""
        Analyze this module/file comprehensively:
        
        File: {file_path}
        Language: {entities[0].language if entities else 'unknown'}
        
        Contains {len(entities)} entities:
        {entity_summary}
        
        Provide analysis covering:
        
        1. **Module Purpose**: What is this module's role in the system?
        2. **Key Components**: What are the main classes/functions?
        3. **Functionality**: What capabilities does it provide?
        4. **Dependencies**: What external modules/libraries does it use?
        5. **Architecture**: How is the code organized?
        6. **Interactions**: How does it interact with other modules?
        7. **Data Flow**: How does data flow through this module?
        """
        
        analysis = self.indexer.query(prompt)
        
        return {
            'file_path': file_path,
            'entity_count': len(entities),
            'entities': entities,
            'analysis': analysis
        }
    
    def analyze_codebase(self) -> Dict[str, Any]:
        """
        High-level codebase analysis
        
        Returns:
            Codebase analysis
        """
        # Group entities by type and language
        type_counts = {}
        language_counts = {}
        
        for entity in self.indexer.entities:
            type_counts[entity.type] = type_counts.get(entity.type, 0) + 1
            language_counts[entity.language] = language_counts.get(entity.language, 0) + 1
        
        # Get unique files
        files = list(set([e.file_path for e in self.indexer.entities]))
        
        summary = f"""
        Codebase Statistics:
        - Total Files: {len(files)}
        - Total Entities: {len(self.indexer.entities)}
        - Total Relationships: {len(self.indexer.relationships)}
        
        By Type:
        {self._format_dict(type_counts)}
        
        By Language:
        {self._format_dict(language_counts)}
        
        Files:
        {chr(10).join(f'- {f}' for f in files[:20])}
        {'...' if len(files) > 20 else ''}
        """
        
        prompt = f"""
        {summary}
        
        Provide a comprehensive codebase analysis:
        
        1. **System Overview**: What type of system is this?
        2. **Architecture**: What architectural patterns are evident?
        3. **Key Components**: What are the main subsystems/modules?
        4. **Technology Stack**: What languages and technologies are used?
        5. **Code Organization**: How is the codebase structured?
        6. **Integration Points**: How do different parts communicate?
        7. **Complexity Assessment**: What is the overall complexity level?
        8. **Potential Issues**: Any anti-patterns or concerns?
        """
        
        analysis = self.indexer.query(prompt)
        
        return {
            'statistics': {
                'files': len(files),
                'entities': len(self.indexer.entities),
                'relationships': len(self.indexer.relationships),
                'by_type': type_counts,
                'by_language': language_counts
            },
            'analysis': analysis
        }
    
    def _format_call_chains(self, chains: List[List[str]]) -> str:
        """Format call chains for display"""
        if not chains:
            return "No call chains found"
        
        formatted = []
        for i, chain in enumerate(chains[:10], 1):  # Limit to 10 chains
            formatted.append(f"Chain {i}: {' -> '.join(chain)}")
        
        if len(chains) > 10:
            formatted.append(f"... and {len(chains) - 10} more chains")
        
        return '\n'.join(formatted)
    
    def _format_dict(self, d: Dict) -> str:
        """Format dictionary for display"""
        return '\n'.join([f'- {k}: {v}' for k, v in d.items()])


class TestCaseGenerator:
    """
    Generates test cases and Selenium code for testing
    """
    
    def __init__(self, indexer: CodeGraphIndexer):
        self.indexer = indexer
    
    def generate_test_cases(self, function_name: str, count: int = 5) -> Dict[str, Any]:
        """
        Generate test cases for a function
        
        Args:
            function_name: Function to generate tests for
            count: Number of test cases to generate
            
        Returns:
            Test cases and descriptions
        """
        entity = self.indexer.get_entity_by_name(function_name)
        if not entity:
            return {'error': f'Function {function_name} not found'}
        
        # Analyze the function first
        analyzer = FunctionalAnalyzer(self.indexer)
        analysis = analyzer.analyze_function(function_name)
        
        prompt = f"""
        Based on this function analysis:
        
        Function: {entity.name}
        Type: {entity.type}
        Language: {entity.language}
        Parameters: {', '.join(entity.parameters) if entity.parameters else 'None'}
        Return Type: {entity.return_type or 'Not specified'}
        
        Functional Analysis:
        {analysis.get('analysis', 'No analysis available')}
        
        Generate the top {count} most important test cases covering:
        
        1. **Happy Path**: Normal successful execution
        2. **Edge Cases**: Boundary conditions, empty inputs, nulls
        3. **Error Cases**: Invalid inputs, exception scenarios
        4. **Integration**: Testing with called functions
        5. **Performance**: Large inputs, stress conditions
        
        For EACH test case, provide:
        
        - **Test Case Name**: Descriptive name
        - **Objective**: What is being tested
        - **Test Data**: Specific input values
        - **Expected Result**: What should happen
        - **Steps**: Execution steps
        - **Priority**: High/Medium/Low
        
        Format as a numbered list with clear sections.
        """
        
        test_cases = self.indexer.query(prompt)
        
        return {
            'function_name': function_name,
            'entity': entity,
            'test_cases': test_cases,
            'count': count
        }
    
    def generate_selenium_tests(self, function_name: str, base_url: str = "http://localhost:3000") -> str:
        """
        Generate Python Selenium test code
        
        Args:
            function_name: Function being tested
            base_url: Base URL of application
            
        Returns:
            Python Selenium test code
        """
        # Get test cases first
        test_data = self.generate_test_cases(function_name)
        
        if 'error' in test_data:
            return f"# Error: {test_data['error']}"
        
        entity = test_data['entity']
        
        prompt = f"""
        Generate complete, executable Python Selenium test code for:
        
        Function: {entity.name}
        Language: {entity.language}
        
        Test Cases:
        {test_data['test_cases']}
        
        Generate production-ready Selenium test code with:
        
        1. **Proper imports**: selenium, unittest/pytest, webdriver
        2. **Setup/Teardown**: Browser initialization and cleanup
        3. **Page Object Model**: If applicable
        4. **Test Methods**: One method per test case
        5. **Assertions**: Proper validation of results
        6. **Waits**: Explicit waits for elements
        7. **Error Handling**: Try-catch blocks
        8. **Screenshots**: On failure
        9. **Logging**: Detailed logging
        10. **Documentation**: Docstrings for each test
        
        Use pytest framework and follow best practices.
        Include comments explaining each section.
        Make the code executable and ready to run.
        
        Base URL: {base_url}
        
        ONLY return the Python code, no explanations outside code comments.
        """
        
        selenium_code = self.indexer.query(prompt)
        
        # Clean up the response to ensure it's just code
        # Remove markdown code blocks if present
        code = selenium_code.strip()
        if code.startswith('```python'):
            code = code[9:]
        if code.startswith('```'):
            code = code[3:]
        if code.endswith('```'):
            code = code[:-3]
        
        return code.strip()
    
    def generate_unit_tests(self, function_name: str) -> str:
        """
        Generate unit test code in the same language as the function
        
        Args:
            function_name: Function to test
            
        Returns:
            Unit test code
        """
        entity = self.indexer.get_entity_by_name(function_name)
        if not entity:
            return f"# Error: Function {function_name} not found"
        
        test_data = self.generate_test_cases(function_name)
        
        framework_map = {
            'python': 'pytest',
            'java': 'JUnit 5',
            'cobol': 'COBOL Unit Test Framework'
        }
        
        framework = framework_map.get(entity.language, 'appropriate test framework')
        
        prompt = f"""
        Generate complete unit test code for:
        
        Function: {entity.name}
        Language: {entity.language}
        Type: {entity.type}
        Parameters: {', '.join(entity.parameters) if entity.parameters else 'None'}
        
        Test Cases:
        {test_data['test_cases']}
        
        Generate production-ready unit test code using {framework}:
        
        1. **Proper imports**: Testing framework and dependencies
        2. **Test class/suite**: Organized test structure
        3. **Setup/Teardown**: Initialize test fixtures
        4. **Test methods**: One per test case
        5. **Mocking**: Mock external dependencies
        6. **Assertions**: Validate all expected outcomes
        7. **Coverage**: Cover all code paths
        8. **Documentation**: Clear comments and docstrings
        
        Follow {entity.language} best practices and conventions.
        Make the code executable and ready to run.
        
        ONLY return the {entity.language} code, no explanations outside code comments.
        """
        
        unit_test_code = self.indexer.query(prompt)
        
        # Clean up response
        code = unit_test_code.strip()
        if code.startswith('```'):
            # Remove code fence
            lines = code.split('\n')
            if lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            code = '\n'.join(lines)
        
        return code.strip()


# Example usage
if __name__ == "__main__":
    from app.core.indexer import CodeGraphIndexer
    
    # Initialize
    indexer = CodeGraphIndexer(
        api_key="YOUR_API_KEY",
        api_base="YOUR_API_BASE"
    )
    
    # Ingest codebase
    indexer.ingest_codebase("./sample_codebase")
    
    # Analyze
    analyzer = FunctionalAnalyzer(indexer)
    
    # Function analysis
    result = analyzer.analyze_function("main")
    print(result['analysis'])
    
    # Generate tests
    test_gen = TestCaseGenerator(indexer)
    tests = test_gen.generate_test_cases("main", count=5)
    print("\nTest Cases:")
    print(tests['test_cases'])
    
    # Generate Selenium code
    selenium_code = test_gen.generate_selenium_tests("main")
    print("\nSelenium Test Code:")
    print(selenium_code)

