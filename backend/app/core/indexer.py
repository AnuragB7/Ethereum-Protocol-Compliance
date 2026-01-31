"""
Code Graph Indexer - Extended version of hybrid_search_rag.py for code analysis
Ingests codebases and builds property graphs for analysis
"""

import os
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path

from llama_index.core import Document, Settings
from llama_index.llms.openai import OpenAI
# from llama_index.llms.openai_like import OpenAILike
from llama_index.llms.openai_like import OpenAILike

from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.core.indices.property_graph import (
    PropertyGraphIndex,
    LLMSynonymRetriever,
    VectorContextRetriever,
    PGRetriever,
)
from llama_index.core.query_engine import RetrieverQueryEngine

from app.core.parsers import CodebaseParser, CodeEntity, CodeRelationship

# Logging
logging.getLogger("llama_index").setLevel(logging.ERROR)


class CodeGraphIndexer:
    """
    Manages code ingestion and graph-based indexing for multi-language codebases
    """
    
    def __init__(self, api_key: str, api_base: str, llm_model: str = "gpt-4.1", 
                 embed_model: str = "text-embedding-ada-002", persist_dir: str = "./graph_storage"):
        """
        Initialize the Code Graph Indexer
        
        Args:
            api_key: API key for LLM service
            api_base: Base URL for API
            llm_model: Name of LLM model
            embed_model: Name of embedding model
            persist_dir: Directory to persist graph data
        """
        self.api_key = api_key
        self.api_base = api_base
        self.llm_model = llm_model
        self.embed_model = embed_model
        self.persist_dir = Path(persist_dir)
        
        # Create persist directory if it doesn't exist
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize parsers
        self.parser = CodebaseParser()
        
        # Initialize LlamaIndex settings
        self._setup_llm_settings()
        
        # Index storage
        self.index: Optional[PropertyGraphIndex] = None
        self.query_engine = None
        
        # Parsed code data
        self.entities: List[CodeEntity] = []
        self.relationships: List[CodeRelationship] = []
        self._data_loaded = False  # Flag to track if data was loaded from disk
        
        # Try to load existing index
        self._load_persisted_data()
    
    def _setup_llm_settings(self):
        """Configure LLM and embedding models"""
        print(f"🔗 Connecting to API at: {self.api_base}")
        
        # Use OpenAILike for custom model names (bypasses OpenAI model validation)
        Settings.llm = OpenAILike(
            model=self.llm_model,
            api_base=self.api_base,
            api_key=self.api_key,
            is_chat_model=True,      # Important: Enables chat-based interactions
            context_window=8192,     # Maximum tokens the model can process
            max_tokens=2048,         # Maximum tokens in generated response
            temperature=0,           # Low temperature = deterministic responses
        )
        
        Settings.embed_model = OpenAIEmbedding(
            model_name=self.embed_model,
            api_base=self.api_base,
            api_key=self.api_key
        )
    
    def ingest_codebase(self, codebase_path: str) -> Dict[str, Any]:
        """
        Parse and ingest entire codebase into the system
        
        Args:
            codebase_path: Path to root directory of codebase
            
        Returns:
            Dictionary with ingestion statistics
        """
        print(f"\n{'='*80}")
        print(f"INGESTING CODEBASE: {codebase_path}")
        print(f"{'='*80}\n")
        
        # Parse codebase
        print("📋 Parsing codebase...")
        parsed_data = self.parser.parse_codebase(codebase_path)
        
        self.entities = parsed_data['entities']
        self.relationships = parsed_data['relationships']
        
        print(f"\n✅ Parsing complete!")
        print(f"   Files processed: {parsed_data['total_files']}")
        print(f"   Entities extracted: {parsed_data['total_entities']}")
        print(f"   Relationships found: {parsed_data['total_relationships']}\n")
        
        # Convert to LlamaIndex documents
        documents = self._create_documents()
        
        # Build graph index
        print("🔨 Building Property Graph Index...")
        self.index = PropertyGraphIndex.from_documents(
            documents,
            show_progress=True,
            use_async=False
        )
        
        print("\n✨ Graph index built successfully!\n")
        
        # Build query engine
        self._build_query_engine()
        
        # Persist the data to disk
        self._persist_data()
        
        return parsed_data
    
    def _create_documents(self) -> List[Document]:
        """
        Convert parsed code entities into LlamaIndex documents
        """
        documents = []
        
        for entity in self.entities:
            # Create detailed text representation
            doc_text = self._entity_to_text(entity)
            
            # Create metadata
            metadata = {
                'entity_name': entity.name,
                'entity_type': entity.type,
                'language': entity.language,
                'file_path': entity.file_path,
                'line_start': entity.line_start,
                'line_end': entity.line_end,
                'parent': entity.parent or '',
                'parameters': ','.join(entity.parameters),
                'calls': ','.join(entity.calls),
            }
            
            doc = Document(
                text=doc_text,
                metadata=metadata,
            )
            documents.append(doc)
        
        print(f"📄 Created {len(documents)} documents from entities")
        return documents
    
    def _entity_to_text(self, entity: CodeEntity) -> str:
        """Convert code entity to text representation"""
        lines = []
        
        # Header
        lines.append(f"Entity: {entity.name}")
        lines.append(f"Type: {entity.type}")
        lines.append(f"Language: {entity.language}")
        lines.append(f"File: {entity.file_path}")
        lines.append(f"Lines: {entity.line_start}-{entity.line_end}")
        
        if entity.parent:
            lines.append(f"Parent: {entity.parent}")
        
        if entity.parameters:
            lines.append(f"Parameters: {', '.join(entity.parameters)}")
        
        if entity.return_type:
            lines.append(f"Returns: {entity.return_type}")
        
        if entity.docstring:
            lines.append(f"\nDocumentation:\n{entity.docstring}")
        
        if entity.calls:
            lines.append(f"\nCalls: {', '.join(entity.calls)}")
        
        # Add relationship context
        related = self._get_entity_relationships(entity.name)
        if related:
            lines.append(f"\nRelationships:")
            for rel in related:
                lines.append(f"  - {rel.relationship_type}: {rel.target}")
        
        return '\n'.join(lines)
    
    def _get_entity_relationships(self, entity_name: str) -> List[CodeRelationship]:
        """Get all relationships for an entity"""
        return [rel for rel in self.relationships if rel.source == entity_name]
    
    def _build_query_engine(self):
        """Build hybrid query engine with retrievers"""
        if not self.index:
            raise ValueError("Index not built. Call ingest_codebase first.")
        
        print("🔍 Building Hybrid Retrievers...")
        
        # Vector retriever
        vector_retriever = VectorContextRetriever(
            graph_store=self.index.property_graph_store,
            vector_store=self.index.vector_store,
            embed_model=Settings.embed_model,
            include_text=True,
            similarity_top_k=5,  # Increased for code analysis
        )
        
        # Synonym retriever
        synonym_retriever = LLMSynonymRetriever(
            graph_store=self.index.property_graph_store,
            llm=Settings.llm,
            include_text=True,
            max_keywords=5,
        )
        
        # Combine retrievers
        pg_retriever = PGRetriever(
            sub_retrievers=[vector_retriever, synonym_retriever]
        )
        
        # Create query engine
        self.query_engine = RetrieverQueryEngine.from_args(
            self.index.as_retriever(sub_retrievers=[pg_retriever]),
            llm=Settings.llm,
        )
        
        print("✅ Query engine ready!\n")
    
    def query(self, question: str) -> str:
        """
        Query the code graph
        
        Args:
            question: Natural language question about the code
            
        Returns:
            Answer string
        """
        # Ensure index is built if data was loaded from disk
        self._ensure_index_built()
        
        if not self.query_engine:
            raise ValueError("Query engine not initialized. Call ingest_codebase first.")
        
        try:
            result = self.query_engine.query(question)
            return str(result)
        except Exception as e:
            return f"Error: {e}"
    
    def get_entity_by_name(self, name: str) -> Optional[CodeEntity]:
        """Get entity by name"""
        for entity in self.entities:
            if entity.name == name:
                return entity
        return None
    
    def get_call_chain(self, function_name: str, depth: int = 3) -> List[List[str]]:
        """
        Get call chains starting from a function
        
        Args:
            function_name: Starting function name
            depth: Maximum depth to traverse
            
        Returns:
            List of call chains
        """
        chains = []
        visited = set()
        
        def dfs(current: str, chain: List[str], current_depth: int):
            if current_depth >= depth or current in visited:
                chains.append(chain.copy())
                return
            
            visited.add(current)
            
            # Find all calls from current function
            calls = [rel.target for rel in self.relationships 
                    if rel.source == current and rel.relationship_type == 'calls']
            
            if not calls:
                chains.append(chain.copy())
            else:
                for call in calls:
                    chain.append(call)
                    dfs(call, chain, current_depth + 1)
                    chain.pop()
            
            visited.remove(current)
        
        dfs(function_name, [function_name], 0)
        return chains
    
    def get_functional_summary(self, entity_name: Optional[str] = None) -> str:
        """
        Generate functional summary of code or specific entity
        
        Args:
            entity_name: Optional specific entity to analyze
            
        Returns:
            Functional summary text
        """
        if entity_name:
            entity = self.get_entity_by_name(entity_name)
            if not entity:
                return f"Entity '{entity_name}' not found"
            
            query = f"""
            Analyze the following code entity and provide a detailed functional understanding:
            
            Entity Name: {entity.name}
            Type: {entity.type}
            Language: {entity.language}
            
            Describe:
            1. What is the primary purpose and functionality?
            2. What are the inputs and outputs?
            3. What other components does it interact with?
            4. What is the business logic or algorithm?
            5. Any important patterns or concerns?
            """
        else:
            query = """
            Provide a high-level functional overview of this entire codebase:
            
            1. What is the main purpose of this system?
            2. What are the key components and their responsibilities?
            3. How do components interact with each other?
            4. What are the main data flows?
            5. What patterns or architectures are used?
            """
        
        return self.query(query)
    
    def export_graph_data(self, output_path: str):
        """
        Export graph data to JSON for visualization
        
        Args:
            output_path: Path to save JSON file
        """
        import json
        
        data = {
            'nodes': [
                {
                    'id': entity.name,
                    'label': entity.name,
                    'type': entity.type,
                    'language': entity.language,
                    'file': entity.file_path,
                    'parent': entity.parent
                }
                for entity in self.entities
            ],
            'edges': [
                {
                    'source': rel.source,
                    'target': rel.target,
                    'type': rel.relationship_type
                }
                for rel in self.relationships
            ]
        }
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"📊 Graph data exported to: {output_path}")
    
    def _persist_data(self):
        """Save entities and relationships to disk"""
        import json
        import pickle
        
        # Save entities and relationships as pickle for Python objects
        entities_path = self.persist_dir / "entities.pkl"
        relationships_path = self.persist_dir / "relationships.pkl"
        
        with open(entities_path, 'wb') as f:
            pickle.dump(self.entities, f)
        
        with open(relationships_path, 'wb') as f:
            pickle.dump(self.relationships, f)
        
        # Also save as JSON for human readability
        json_path = self.persist_dir / "graph_data.json"
        self.export_graph_data(str(json_path))
        
        # Save the LlamaIndex storage context (includes embeddings and index state)
        if self.index:
            storage_dir = self.persist_dir / "llamaindex_storage"
            storage_dir.mkdir(exist_ok=True)
            try:
                self.index.storage_context.persist(persist_dir=str(storage_dir))
                print(f"💾 Index storage persisted (includes embeddings)")
            except Exception as e:
                print(f"⚠️  Could not persist index storage: {e}")
        
        print(f"💾 Graph data persisted to: {self.persist_dir}")
    
    def _ensure_index_built(self):
        """Build index from loaded data if not already built"""
        if self.index is None and self._data_loaded and self.entities:
            # First, try to load from persisted storage (fast!)
            storage_dir = self.persist_dir / "llamaindex_storage"
            
            if storage_dir.exists():
                try:
                    print("⚡ Loading index from storage (fast, no embedding generation)...")
                    from llama_index.core import StorageContext, load_index_from_storage
                    
                    storage_context = StorageContext.from_defaults(persist_dir=str(storage_dir))
                    self.index = load_index_from_storage(storage_context)
                    self._build_query_engine()
                    print("✅ Index loaded from storage!")
                    return
                except Exception as e:
                    print(f"⚠️  Could not load from storage: {e}")
                    print("   Rebuilding from scratch...")
            
            # Fallback: rebuild from scratch (slow)
            print("🔨 Building index from loaded data (first-time setup)...")
            documents = self._create_documents()
            self.index = PropertyGraphIndex.from_documents(
                documents,
                show_progress=True,
                use_async=False
            )
            self._build_query_engine()
            print("✅ Index ready!")
    
    def _load_persisted_data(self):
        """Load entities and relationships from disk if available"""
        import pickle
        
        entities_path = self.persist_dir / "entities.pkl"
        relationships_path = self.persist_dir / "relationships.pkl"
        
        # Debug output
        print(f"🔍 Checking for persisted data:")
        print(f"   persist_dir: {self.persist_dir.resolve()}")
        print(f"   entities.pkl exists: {entities_path.exists()}")
        print(f"   relationships.pkl exists: {relationships_path.exists()}")
        
        if entities_path.exists() and relationships_path.exists():
            try:
                print(f"📂 Loading entities from: {entities_path.resolve()}")
                with open(entities_path, 'rb') as f:
                    self.entities = pickle.load(f)
                print(f"   ✓ Loaded {len(self.entities)} entities")
                
                print(f"📂 Loading relationships from: {relationships_path.resolve()}")
                with open(relationships_path, 'rb') as f:
                    self.relationships = pickle.load(f)
                print(f"   ✓ Loaded {len(self.relationships)} relationships")
                
                print(f"♻️  Loaded existing graph data from: {self.persist_dir}")
                print(f"   Entities: {len(self.entities)}, Relationships: {len(self.relationships)}")
                print(f"   Note: Index will be built on first query to save startup time")
                
                # Don't rebuild index on startup - just mark that we have data
                # The index will be built on-demand when first queried
                self._data_loaded = True
                    
            except Exception as e:
                import traceback
                print(f"⚠️  Could not load persisted data: {e}")
                traceback.print_exc()
                self.entities = []
                self.relationships = []
        else:
            print(f"ℹ️  No persisted data found at: {self.persist_dir}")


# Example usage
if __name__ == "__main__":
    # Configuration
    API_KEY = "YOUR_API_KEY"
    API_BASE = "YOUR_API_BASE"
    
    # Initialize indexer
    indexer = CodeGraphIndexer(
        api_key=API_KEY,
        api_base=API_BASE,
    )
    
    # Ingest codebase
    codebase_path = "./sample_codebase"
    indexer.ingest_codebase(codebase_path)
    
    # Query examples
    print("\n" + "="*80)
    print("EXAMPLE QUERIES")
    print("="*80 + "\n")
    
    queries = [
        "What are the main functions in this codebase?",
        "Show me the call hierarchy",
        "What does the main function do?",
    ]
    
    for q in queries:
        print(f"Q: {q}")
        answer = indexer.query(q)
        print(f"A: {answer}\n")

