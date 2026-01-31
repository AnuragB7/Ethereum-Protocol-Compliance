"""
Enhanced Test Case Generator with Structured Output
Generates test cases in table format with XPath locators
"""

import json
import csv
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from code_graph_indexer import CodeGraphIndexer
from analysis_engine import FunctionalAnalyzer


class StructuredTestCaseGenerator:
    """
    Generates structured test cases with:
    - Table format (CSV/Excel-like)
    - XPath locators for UI elements
    - Cypress, TypeScript, and Selenium scripts
    """
    
    # Configuration: Maximum entities to send to LLM (prevents token overflow)
    MAX_ENTITIES_FOR_FALLBACK = 50
    
    def __init__(self, indexer: CodeGraphIndexer, output_dir: str = "test_output"):
        self.indexer = indexer
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    def generate_structured_test_cases(self, functionality: str, context: str = "") -> Dict[str, Any]:
        """
        Generate test cases in structured table format
        
        Args:
            functionality: Name of functionality to test
            context: Additional context about the feature
            
        Returns:
            Dictionary with test cases and file paths
        """
        # First, analyze the codebase to understand the functionality
        print(f"🔍 Analyzing codebase for: {functionality}")
        
        codebase_analysis_prompt = f"""
        Search the codebase for implementations related to '{functionality}'.
        
        Find and describe:
        1. All classes and files related to {functionality}
        2. Public methods/functions with their exact signatures
        3. File paths (e.g., "LoginController.java", "AuthenticationService.java")
        4. Method names (e.g., "login()", "authenticate()", "validateCredentials()")
        5. Line numbers where these methods are defined
        6. Input parameters each method accepts
        7. What each method returns
        8. Error handling and validation logic
        
        Focus on finding ACTUAL code in the indexed codebase.
        List the exact file names and function names you find.
        
        Format your response as:
        
        **Found Classes/Files:**
        - FileName.ext: Brief description
        
        **Found Methods/Functions:**
        - methodName() in FileName.ext (lines X-Y): What it does
        
        **Implementation Details:**
        - How the functionality works
        - Key validation rules
        - Error cases handled
        """
        
        # Get codebase-specific context using RAG
        # Strategy: Run RAG query in a separate thread to avoid asyncio conflicts
        try:
            import asyncio
            from concurrent.futures import ThreadPoolExecutor
            import traceback
            
            def _run_rag_query():
                """Run RAG query in isolated context"""
                try:
                    # Check if index is built
                    if self.indexer.index is None:
                        print("⚠️  Index not built yet, triggering build...")
                        self.indexer._ensure_index_built()
                    
                    # Perform RAG query
                    response = self.indexer.query(codebase_analysis_prompt)
                    return response
                except Exception as e:
                    print(f"❌ RAG query exception: {type(e).__name__}: {str(e)}")
                    traceback.print_exc()
                    return f"Error: {str(e)}"
            
            # Check if we're in an async context
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're in FastAPI's event loop, run in thread
                    print("🔄 Running RAG query in ThreadPoolExecutor to avoid asyncio conflicts...")
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(_run_rag_query)
                        codebase_context = future.result(timeout=30)  # 30 second timeout
                else:
                    # No running loop, safe to call directly
                    codebase_context = _run_rag_query()
            except RuntimeError:
                # No event loop, safe to call directly
                codebase_context = _run_rag_query()
            
            # Validate RAG response
            print(f"📊 RAG response length: {len(codebase_context)} chars")
            
            if "Error:" in codebase_context or "nest_asyncio" in codebase_context or len(codebase_context) < 200:
                print(f"⚠️  RAG query returned error or insufficient data")
                print(f"📄 RAG response preview: {codebase_context[:300]}...")
                raise Exception("RAG query failed or returned insufficient data")
            
            print(f"✅ RAG query successful!")
                
        except Exception as e:
            print(f"⚠️  RAG query error: {e}")
            # Fallback: Use entity data directly with smart filtering
            print(f"🔄 Using direct entity lookup instead (max {self.MAX_ENTITIES_FOR_FALLBACK} most relevant)...")
            codebase_context = self._get_entities_summary(functionality, max_entities=self.MAX_ENTITIES_FOR_FALLBACK)
        
        print(f"✅ Codebase analysis complete ({len(codebase_context)} chars)")
        print(f"📄 Analysis preview: {codebase_context[:500]}...")
        
        # Now generate test cases based on the actual codebase analysis
        prompt = f"""
        Based on this ACTUAL codebase analysis:
        
        {codebase_context}
        
        Generate comprehensive test cases for: {functionality}
        
        Additional context: {context}
        
        CRITICAL INSTRUCTIONS:
        1. You MUST use ONLY the actual file names, function names, and line numbers from the codebase analysis above
        2. DO NOT invent or make up any file paths, function names, or line numbers
        3. If the analysis shows "DatabaseManager.java", use exactly that - not "database/manager.py" or any other variation
        4. Extract the exact function names mentioned in the analysis (e.g., "connect()", "executeQuery()", "authenticate()")
        5. Use the actual line numbers if provided in the analysis, or use "N/A" if not available
        
        Create test cases in a STRUCTURED TABLE FORMAT with these columns:
        1. Test Case Name
        2. Step # (number)
        3. Action (what to do)
        4. UI Element (element to interact with)
        5. Expected Result (what should happen)
        6. Source Function - MUST be an actual function name from the codebase analysis above
        7. Source File - MUST be an actual file path from the codebase analysis above  
        8. Source Lines - Actual line numbers if available, otherwise "N/A"
        
        Generate test scenarios based on the ACTUAL implementation found in the codebase, covering:
        - Happy path (successful flow based on actual code)
        - Invalid inputs (based on actual validation rules)
        - Error handling (based on actual error cases in code)
        - Edge cases (based on actual boundary conditions)
        - Integration points (based on actual dependencies found)
        
        For EACH test case, provide multiple steps (typically 3-5 steps per scenario).
        
        Format as a CLEAR TABLE with columns separated by " | ".
        
        Example format (use YOUR actual codebase data, not this example):
        Test Case Name | Step # | Action | UI Element | Expected Result | Source Function | Source File | Source Lines
        Login - Successful Authentication | 1 | Navigate to the Login screen | Login Screen | Login screen is displayed | login() | LoginController.java | 45-67
        Login - Successful Authentication | 2 | Enter a valid username | Username Input | Entered text appears plainly | validateInput() | AuthenticationService.java | 23-30
        
        REMEMBER: Use ONLY actual data from the codebase analysis. Do NOT make up file names or function names!
        """
        
        # Query LLM directly with enriched context
        print(f"🤖 Generating test cases based on codebase analysis...")
        response = self._query_llm_directly(prompt)
        print(f"📝 Generated response: {len(response)} characters")
        
        # Parse the response into structured data
        test_cases = self._parse_test_table(response)
        
        # Generate XPath locators for UI elements
        xpath_data = self._generate_xpath_locators(test_cases)
        
        # Save to files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_filename = f"{functionality.replace(' ', '_')}_{timestamp}"
        
        # Save as CSV
        csv_path = self.output_dir / f"{base_filename}.csv"
        self._save_as_csv(test_cases, csv_path)
        
        # Save XPath file
        xpath_path = self.output_dir / f"{base_filename}_xpaths.json"
        self._save_xpath_file(xpath_data, xpath_path)
        
        # Generate automation scripts
        cypress_path = self.output_dir / f"{base_filename}_cypress.cy.ts"
        selenium_path = self.output_dir / f"{base_filename}_selenium.py"
        typescript_path = self.output_dir / f"{base_filename}_playwright.spec.ts"
        
        self._generate_cypress_script(test_cases, xpath_data, cypress_path, functionality)
        self._generate_selenium_script(test_cases, xpath_data, selenium_path, functionality)
        self._generate_playwright_script(test_cases, xpath_data, typescript_path, functionality)
        
        return {
            'functionality': functionality,
            'test_cases': test_cases,
            'xpath_data': xpath_data,
            'files': {
                'csv': str(csv_path),
                'xpath': str(xpath_path),
                'cypress': str(cypress_path),
                'selenium': str(selenium_path),
                'playwright': str(typescript_path)
            },
            'raw_response': response
        }
    
    def _get_entities_summary(self, functionality: str, max_entities: int = 50) -> str:
        """
        Get a summary of relevant entities from the indexer as fallback
        
        Uses intelligent keyword matching with relevance scoring to find
        the most relevant entities, capped at max_entities to prevent
        token overflow and rate limiting.
        
        Args:
            functionality: The functionality to search for
            max_entities: Maximum number of entities to include (default: 50)
        """
        relevant_entities = []
        
        # Search for relevant entities based on functionality keywords
        keywords = functionality.lower().split()
        
        # Score entities by relevance
        scored_entities = []
        for entity in self.indexer.entities:
            entity_text = f"{entity.name} {entity.file_path} {entity.docstring or ''}".lower()
            
            # Calculate relevance score
            score = 0
            for keyword in keywords:
                if keyword in entity.name.lower():
                    score += 10  # High score for name match
                elif keyword in entity.file_path.lower():
                    score += 5   # Medium score for file path match
                elif entity.docstring and keyword in entity.docstring.lower():
                    score += 3   # Lower score for docstring match
            
            if score > 0:
                scored_entities.append((score, entity))
        
        # Sort by relevance score (descending)
        scored_entities.sort(key=lambda x: x[0], reverse=True)
        relevant_entities = [entity for score, entity in scored_entities]
        
        if not relevant_entities:
            # If no keyword match, use most important entities (classes, methods)
            # Prioritize classes and public methods
            print(f"⚠️  No keyword matches found, using top {max_entities} entities")
            for entity in self.indexer.entities:
                if entity.type in ['class', 'method', 'function', 'component']:
                    relevant_entities.append(entity)
            
            if not relevant_entities:
                relevant_entities = self.indexer.entities[:max_entities]
        
        # Cap at max_entities to prevent token overflow
        total_found = len(relevant_entities)
        relevant_entities = relevant_entities[:max_entities]
        
        # Build summary
        summary = f"**Found {total_found} relevant entities, showing top {len(relevant_entities)} most relevant:**\n\n"
        
        for entity in relevant_entities:
            summary += f"**{entity.name}** ({entity.type})\n"
            summary += f"- File: {entity.file_path}\n"
            summary += f"- Lines: {entity.line_start}-{entity.line_end}\n"
            summary += f"- Language: {entity.language}\n"
            if entity.parameters:
                summary += f"- Parameters: {', '.join(entity.parameters)}\n"
            if entity.docstring:
                summary += f"- Description: {entity.docstring[:200]}\n"
            summary += "\n"
        
        if total_found > max_entities:
            summary += f"\n⚠️  Note: {total_found - max_entities} additional entities found but omitted to prevent token overflow.\n"
        
        return summary
    
    def _query_llm_directly(self, prompt: str) -> str:
        """Query the LLM directly without RAG context"""
        from llama_index.core.llms import ChatMessage
        
        # Get the LLM from indexer's settings
        llm = self.indexer.llm if hasattr(self.indexer, 'llm') else None
        
        if not llm:
            # Fallback: Use Settings.llm
            from llama_index.core import Settings
            llm = Settings.llm
        
        # Create a simple chat message
        messages = [
            ChatMessage(role="system", content="You are a test automation expert. Generate comprehensive test cases in structured table format."),
            ChatMessage(role="user", content=prompt)
        ]
        
        # Get response
        response = llm.chat(messages)
        return response.message.content
    
    def _parse_test_table(self, response: str) -> List[Dict[str, str]]:
        """Parse LLM response into structured test cases"""
        test_cases = []
        lines = response.strip().split('\n')
        
        print(f"DEBUG: Parsing {len(lines)} lines from LLM response")
        
        # Find table header
        header_found = False
        for i, line in enumerate(lines):
            if '|' in line and any(keyword in line.lower() for keyword in ['test case', 'step', 'action', 'element']):
                header_found = True
                print(f"DEBUG: Found header at line {i}: {line}")
                continue
            
            if header_found and '|' in line:
                # Split and clean up parts (remove empty strings from leading/trailing pipes)
                parts = [p.strip() for p in line.split('|') if p.strip()]
                
                # Skip separator lines
                if all(c in '-|: ' for c in line):
                    continue
                
                # Need at least 5 columns (original), but may have 8 (with source info)
                if len(parts) >= 5:
                    test_case = {
                        'test_case_name': parts[0],
                        'step_number': parts[1],
                        'action': parts[2],
                        'ui_element': parts[3],
                        'expected_result': parts[4],
                        'source_function': parts[5] if len(parts) > 5 else 'N/A',
                        'source_file': parts[6] if len(parts) > 6 else 'N/A',
                        'source_lines': parts[7] if len(parts) > 7 else 'N/A'
                    }
                    test_cases.append(test_case)
                    print(f"DEBUG: Added test case: {parts[0]} - Step {parts[1]}")
        
        # If no table found, try to extract from text
        if not test_cases:
            print("DEBUG: No table format found, trying text extraction...")
            test_cases = self._extract_from_text(response)
        
        print(f"DEBUG: Parsed {len(test_cases)} test cases")
        return test_cases
    
    def _extract_from_text(self, response: str) -> List[Dict[str, str]]:
        """Extract test cases from unstructured text"""
        # This is a fallback parser
        test_cases = []
        current_test = None
        step_num = 1
        
        lines = response.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Detect new test case
            if any(marker in line.lower() for marker in ['test case:', '##', 'scenario:']):
                current_test = line.replace('##', '').replace('Test Case:', '').strip()
                step_num = 1
            elif current_test and any(marker in line.lower() for marker in ['step', 'action', '-']):
                test_cases.append({
                    'test_case_name': current_test,
                    'step_number': str(step_num),
                    'action': line,
                    'ui_element': 'N/A',
                    'expected_result': 'N/A'
                })
                step_num += 1
        
        return test_cases
    
    def _generate_xpath_locators(self, test_cases: List[Dict[str, str]]) -> Dict[str, Dict[str, str]]:
        """Generate XPath locators for UI elements"""
        ui_elements = set()
        for tc in test_cases:
            element = tc.get('ui_element', '').strip()
            if element and element.lower() not in ['n/a', 'not applicable', '']:
                ui_elements.add(element)
        
        # Query LLM to generate XPath for each element
        xpath_data = {}
        
        if ui_elements:
            prompt = f"""
            For these UI elements, generate appropriate XPath, CSS selectors, and accessibility selectors:
            
            Elements:
            {chr(10).join([f"- {elem}" for elem in ui_elements])}
            
            For EACH element, provide:
            1. xpath - XPath selector
            2. css - CSS selector
            3. id - Possible ID attribute
            4. testid - data-testid attribute
            5. accessibility - aria-label or role
            
            Format as JSON:
            {{
                "Element Name": {{
                    "xpath": "//input[@type='text' and @name='username']",
                    "css": "input[name='username']",
                    "id": "username-input",
                    "testid": "username-field",
                    "accessibility": "input[aria-label='Username']"
                }}
            }}
            
            Be specific and realistic. Use common naming conventions.
            """
            
            print(f"🎯 Generating XPath for {len(ui_elements)} UI elements...")
            response = self._query_llm_directly(prompt)
            print(f"📝 XPath LLM Response length: {len(response)} characters")
            
            # Try to parse JSON from response
            try:
                # Extract JSON from response
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    json_str = response[json_start:json_end]
                    xpath_data = json.loads(json_str)
                    print(f"✅ Successfully parsed XPath for {len(xpath_data)} elements")
            except Exception as e:
                print(f"⚠️  Error parsing XPath JSON: {e}")
                print(f"📄 LLM Response preview: {response[:200]}...")
                # Fallback: generate basic XPath
                print(f"🔄 Using fallback XPath generation...")
                for elem in ui_elements:
                    elem_lower = elem.lower().replace(' ', '-')
                    xpath_data[elem] = {
                        'xpath': f"//*[@data-testid='{elem_lower}']",
                        'css': f"[data-testid='{elem_lower}']",
                        'id': elem_lower,
                        'testid': elem_lower,
                        'accessibility': f"[aria-label='{elem}']"
                    }
                print(f"✅ Generated fallback XPath for {len(xpath_data)} elements")
        
        return xpath_data
    
    def _save_as_csv(self, test_cases: List[Dict[str, str]], filepath: Path):
        """Save test cases as CSV"""
        if not test_cases:
            return
        
        # Use all fields including source traceability
        fieldnames = ['test_case_name', 'step_number', 'action', 'ui_element', 'expected_result', 
                     'source_function', 'source_file', 'source_lines']
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(test_cases)
        
        print(f"✅ Saved CSV: {filepath}")
    
    def _save_xpath_file(self, xpath_data: Dict[str, Dict[str, str]], filepath: Path):
        """Save XPath locators as JSON"""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(xpath_data, f, indent=2)
        
        print(f"✅ Saved XPath file: {filepath}")
    
    def _generate_cypress_script(self, test_cases: List[Dict[str, str]], xpath_data: Dict, filepath: Path, functionality: str):
        """Generate Cypress TypeScript test"""
        script = f"""// Cypress Test - {functionality}
// Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

import xpaths from './{filepath.stem.replace('_cypress', '_xpaths')}.json';

describe('{functionality}', () => {{
"""
        
        # Group test cases by test name
        grouped = {}
        for tc in test_cases:
            name = tc['test_case_name']
            if name not in grouped:
                grouped[name] = []
            grouped[name].append(tc)
        
        # Generate test for each group
        for test_name, steps in grouped.items():
            script += f"""
    it('{test_name}', () => {{
"""
            for step in steps:
                element = step['ui_element']
                action = step['action'].lower()
                
                # Convert action to Cypress command
                if 'navigate' in action or 'open' in action:
                    script += f"        cy.visit('/'); // {step['action']}\n"
                elif 'click' in action or 'tap' in action or 'press' in action:
                    if element in xpath_data:
                        script += f"        cy.get(xpaths['{element}'].css).click(); // {step['action']}\n"
                    else:
                        script += f"        cy.contains('{element}').click(); // {step['action']}\n"
                elif 'enter' in action or 'type' in action or 'input' in action:
                    if element in xpath_data:
                        script += f"        cy.get(xpaths['{element}'].css).type('test_data'); // {step['action']}\n"
                    else:
                        script += f"        cy.get('input').type('test_data'); // {step['action']}\n"
                elif 'verify' in action or 'check' in action:
                    script += f"        cy.contains('{element}').should('be.visible'); // {step['action']}\n"
                else:
                    script += f"        // {step['action']}\n"
                
                # Add assertion for expected result
                if step['expected_result'] and step['expected_result'].lower() not in ['n/a', 'not applicable']:
                    script += f"        // Expected: {step['expected_result']}\n"
            
            script += """    });
"""
        
        script += """});
"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(script)
        
        print(f"✅ Saved Cypress script: {filepath}")
    
    def _generate_selenium_script(self, test_cases: List[Dict[str, str]], xpath_data: Dict, filepath: Path, functionality: str):
        """Generate Python Selenium test"""
        script = f'''"""
Selenium Test - {functionality}
Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
"""

import json
import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys


class Test{functionality.replace(" ", "").replace("-", "")}:
    """Test suite for {functionality}"""
    
    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """Setup and teardown for each test"""
        self.driver = webdriver.Chrome()
        self.driver.implicitly_wait(10)
        self.wait = WebDriverWait(self.driver, 10)
        
        # Load XPath locators
        with open('{filepath.parent}/{filepath.stem.replace("_selenium", "_xpaths")}.json', 'r') as f:
            self.xpaths = json.load(f)
        
        yield
        
        self.driver.quit()
    
    def find_element(self, element_name):
        """Find element using multiple strategies"""
        if element_name in self.xpaths:
            locators = self.xpaths[element_name]
            try:
                # Try data-testid first
                return self.driver.find_element(By.CSS_SELECTOR, f"[data-testid='{{locators['testid']}}']")
            except:
                try:
                    # Try CSS selector
                    return self.driver.find_element(By.CSS_SELECTOR, locators['css'])
                except:
                    # Try XPath
                    return self.driver.find_element(By.XPATH, locators['xpath'])
        else:
            # Fallback: search by text
            return self.driver.find_element(By.XPATH, f"//*[contains(text(), '{{element_name}}')]")
    
'''
        
        # Group test cases by test name
        grouped = {}
        for tc in test_cases:
            name = tc['test_case_name']
            if name not in grouped:
                grouped[name] = []
            grouped[name].append(tc)
        
        # Generate test for each group
        for test_name, steps in grouped.items():
            method_name = test_name.lower().replace(' ', '_').replace('-', '_')
            script += f'''    def test_{method_name}(self):
        """Test: {test_name}"""
'''
            for i, step in enumerate(steps, 1):
                element = step['ui_element']
                action = step['action'].lower()
                
                script += f"        # Step {i}: {step['action']}\n"
                
                # Convert action to Selenium command
                if 'navigate' in action or 'open' in action:
                    script += f"        self.driver.get('http://localhost:3000')\n"
                elif 'click' in action or 'tap' in action or 'press' in action:
                    script += f"        element = self.find_element('{element}')\n"
                    script += f"        element.click()\n"
                elif 'enter' in action or 'type' in action or 'input' in action:
                    script += f"        element = self.find_element('{element}')\n"
                    script += f"        element.send_keys('test_data')\n"
                elif 'verify' in action or 'check' in action:
                    script += f"        element = self.find_element('{element}')\n"
                    script += f"        assert element.is_displayed()\n"
                
                # Add comment for expected result
                if step['expected_result'] and step['expected_result'].lower() not in ['n/a', 'not applicable']:
                    script += f"        # Expected: {step['expected_result']}\n"
                
                script += "\n"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(script)
        
        print(f"✅ Saved Selenium script: {filepath}")
    
    def _generate_playwright_script(self, test_cases: List[Dict[str, str]], xpath_data: Dict, filepath: Path, functionality: str):
        """Generate Playwright TypeScript test"""
        script = f"""// Playwright Test - {functionality}
// Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

import {{ test, expect }} from '@playwright/test';
import xpaths from './{filepath.stem.replace('_playwright', '_xpaths')}.json';

test.describe('{functionality}', () => {{
"""
        
        # Group test cases by test name
        grouped = {}
        for tc in test_cases:
            name = tc['test_case_name']
            if name not in grouped:
                grouped[name] = []
            grouped[name].append(tc)
        
        # Generate test for each group
        for test_name, steps in grouped.items():
            script += f"""
    test('{test_name}', async ({{ page }}) => {{
"""
            for step in steps:
                element = step['ui_element']
                action = step['action'].lower()
                
                # Convert action to Playwright command
                if 'navigate' in action or 'open' in action:
                    script += f"        await page.goto('/'); // {step['action']}\n"
                elif 'click' in action or 'tap' in action or 'press' in action:
                    if element in xpath_data:
                        script += f"        await page.locator(xpaths['{element}'].css).click(); // {step['action']}\n"
                    else:
                        script += f"        await page.getByText('{element}').click(); // {step['action']}\n"
                elif 'enter' in action or 'type' in action or 'input' in action:
                    if element in xpath_data:
                        script += f"        await page.locator(xpaths['{element}'].css).fill('test_data'); // {step['action']}\n"
                    else:
                        script += f"        await page.locator('input').fill('test_data'); // {step['action']}\n"
                elif 'verify' in action or 'check' in action:
                    script += f"        await expect(page.getByText('{element}')).toBeVisible(); // {step['action']}\n"
                else:
                    script += f"        // {step['action']}\n"
                
                # Add comment for expected result
                if step['expected_result'] and step['expected_result'].lower() not in ['n/a', 'not applicable']:
                    script += f"        // Expected: {step['expected_result']}\n"
            
            script += """    });
"""
        
        script += """});
"""
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(script)
        
        print(f"✅ Saved Playwright script: {filepath}")


# Convenience function for backward compatibility
def generate_structured_tests(indexer: CodeGraphIndexer, functionality: str, output_dir: str = "test_output") -> Dict[str, Any]:
    """Generate structured test cases with XPath and automation scripts"""
    generator = StructuredTestCaseGenerator(indexer, output_dir)
    return generator.generate_structured_test_cases(functionality)

