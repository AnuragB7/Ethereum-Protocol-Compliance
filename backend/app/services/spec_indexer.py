"""
Specification Indexer with Qdrant Hybrid Search

Ingests Ethereum specifications from ethereum/execution-specs and provides
hybrid (semantic + keyword) search for compliance checking.

Architecture:
- Uses Qdrant for vector storage with hybrid search (dense + sparse vectors)
- Dense vectors: OpenAI embeddings for semantic search
- Sparse vectors: BM25 for keyword matching (EIP numbers, function names)
- Supports cloning specs from GitHub or loading from local path
"""

import os
import json
import shutil
import subprocess
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from llama_index.core import Document, Settings, VectorStoreIndex, StorageContext
from llama_index.core.schema import NodeWithScore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai_like import OpenAILike

# Qdrant imports
try:
    from llama_index.vector_stores.qdrant import QdrantVectorStore
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False
    QdrantVectorStore = None
    QdrantClient = None
    logger.warning("Qdrant not available. Install with: pip install llama-index-vector-stores-qdrant qdrant-client fastembed")

logging.basicConfig(level=logging.INFO)
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


@dataclass 
class SpecIngestionResult:
    """Result of specification ingestion"""
    total_files: int = 0
    total_chunks: int = 0
    forks_ingested: List[str] = field(default_factory=list)
    eips_found: List[str] = field(default_factory=list)


class SpecificationIndexer:
    """
    Indexes Ethereum specifications using Qdrant Hybrid Search.
    
    Provides both semantic (dense vector) and keyword (sparse vector) search
    for finding relevant specifications during compliance checking.
    """
    
    # Default repository URL
    EXECUTION_SPECS_REPO = "https://github.com/ethereum/execution-specs.git"
    
    def __init__(
        self,
        api_key: str,
        api_base: str,
        embed_model: str = "text-embedding-ada-002",
        llm_model: str = "gpt-4",
        specs_dir: str = "./execution-specs",
        storage_dir: str = "./spec_storage",
        collection_name: str = "ethereum_specs"
    ):
        """
        Initialize the Specification Indexer.
        
        Args:
            api_key: API key for embedding model
            api_base: API base URL
            embed_model: Embedding model name
            llm_model: LLM model name (for query expansion)
            specs_dir: Directory to clone/store execution-specs
            storage_dir: Directory for Qdrant persistent storage
            collection_name: Qdrant collection name
        """
        if not QDRANT_AVAILABLE:
            raise ImportError("Qdrant is not available. Install required packages.")
        
        self.api_key = api_key
        self.api_base = api_base
        self.embed_model = embed_model
        self.llm_model = llm_model
        self.specs_dir = Path(specs_dir)
        self.storage_dir = Path(storage_dir)
        self.collection_name = collection_name
        
        # Create storage directory
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure LlamaIndex settings
        self._setup_settings()
        
        # Initialize Qdrant client with persistent storage
        self.qdrant_client = QdrantClient(
            path=str(self.storage_dir / "qdrant_db")
        )
        
        # Create hybrid vector store
        self.vector_store = QdrantVectorStore(
            collection_name=self.collection_name,
            client=self.qdrant_client,
            enable_hybrid=True,                    # Enable hybrid search!
            fastembed_sparse_model="Qdrant/bm25",  # BM25 for sparse vectors
            batch_size=20,
        )
        
        # Index (will be created on ingest or loaded from storage)
        self.index: Optional[VectorStoreIndex] = None
        self.chunks: List[SpecChunk] = []
        self.ingestion_result: Optional[SpecIngestionResult] = None
        
        # Try to load existing index
        self._try_load_existing()
    
    def _setup_settings(self):
        """Configure LlamaIndex settings for embeddings and LLM."""
        logger.info(f"Setting up embeddings with model: {self.embed_model}")
        
        Settings.embed_model = OpenAIEmbedding(
            model_name=self.embed_model,
            api_base=self.api_base,
            api_key=self.api_key
        )
        
        Settings.llm = OpenAILike(
            model=self.llm_model,
            api_base=self.api_base,
            api_key=self.api_key,
            is_chat_model=True,
            context_window=8192,
            max_tokens=2048,
            temperature=0,
        )
        
        Settings.chunk_size = 1024
        Settings.chunk_overlap = 128
    
    def _try_load_existing(self):
        """Try to load existing index from storage."""
        metadata_file = self.storage_dir / "spec_metadata.json"
        
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                
                # Check if Qdrant collection exists
                collections = self.qdrant_client.get_collections()
                collection_names = [c.name for c in collections.collections]
                
                if self.collection_name in collection_names:
                    # Recreate index from existing vector store
                    self.index = VectorStoreIndex.from_vector_store(
                        vector_store=self.vector_store
                    )
                    
                    self.ingestion_result = SpecIngestionResult(
                        total_files=metadata.get("total_files", 0),
                        total_chunks=metadata.get("total_chunks", 0),
                        forks_ingested=metadata.get("forks_ingested", []),
                        eips_found=metadata.get("eips_found", [])
                    )
                    
                    logger.info(f"✅ Loaded existing spec index: {self.ingestion_result.total_chunks} chunks")
                    return True
            except Exception as e:
                logger.warning(f"Failed to load existing index: {e}")
        
        return False
    
    def clone_specs(self, branch: str = "forks/amsterdam", force: bool = False) -> bool:
        """
        Clone ethereum/execution-specs from GitHub.
        
        Args:
            branch: Git branch to clone (default: forks/amsterdam - the current default branch)
            force: If True, delete existing directory and re-clone
            
        Returns:
            True if successful
        """
        if self.specs_dir.exists():
            if force:
                logger.info(f"Removing existing specs directory: {self.specs_dir}")
                shutil.rmtree(self.specs_dir)
            else:
                logger.info(f"Specs directory already exists: {self.specs_dir}")
                # Pull latest changes
                try:
                    subprocess.run(
                        ["git", "pull"],
                        cwd=self.specs_dir,
                        check=True,
                        capture_output=True
                    )
                    logger.info("Pulled latest changes")
                    return True
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Git pull failed: {e}")
                    return True  # Directory exists, continue anyway
        
        # Clone the repository
        logger.info(f"Cloning {self.EXECUTION_SPECS_REPO} to {self.specs_dir}")
        try:
            subprocess.run(
                ["git", "clone", "--depth", "1", "--branch", branch, 
                 self.EXECUTION_SPECS_REPO, str(self.specs_dir)],
                check=True,
                capture_output=True
            )
            logger.info("✅ Successfully cloned execution-specs")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clone repository: {e.stderr.decode()}")
            return False
    
    def ingest_specs(
        self, 
        forks: Optional[List[str]] = None,
        include_docs: bool = True
    ) -> SpecIngestionResult:
        """
        Parse and ingest specifications into Qdrant.
        
        Args:
            forks: List of fork names to ingest (e.g., ["prague", "cancun"]).
                   If None, ingests all forks.
            include_docs: Whether to include documentation files
            
        Returns:
            SpecIngestionResult with statistics
        """
        if not self.specs_dir.exists():
            raise FileNotFoundError(
                f"Specs directory not found: {self.specs_dir}. "
                "Call clone_specs() first or provide a valid path."
            )
        
        # Parse specifications
        from app.services.spec_parser import SpecificationParser
        parser = SpecificationParser(str(self.specs_dir))
        
        self.chunks = parser.parse_all_forks(forks=forks, include_docs=include_docs)
        
        if not self.chunks:
            logger.warning("No specification chunks found!")
            return SpecIngestionResult()
        
        # Convert to LlamaIndex documents
        documents = self._chunks_to_documents(self.chunks)
        
        logger.info(f"Creating Qdrant hybrid index with {len(documents)} documents...")
        
        # Create storage context with Qdrant vector store
        storage_context = StorageContext.from_defaults(
            vector_store=self.vector_store
        )
        
        # Build the index (this will create both dense and sparse vectors)
        self.index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            show_progress=True,
        )
        
        # Collect statistics
        forks_found = list(set(c.fork_name for c in self.chunks if c.fork_name))
        eips_found = list(set(
            eip for c in self.chunks 
            for eip in c.eip_references
        ))
        
        self.ingestion_result = SpecIngestionResult(
            total_files=len(set(c.file_path for c in self.chunks)),
            total_chunks=len(self.chunks),
            forks_ingested=forks_found,
            eips_found=sorted(eips_found)
        )
        
        # Save metadata
        self._save_metadata()
        
        logger.info(f"✅ Ingested {self.ingestion_result.total_chunks} spec chunks")
        logger.info(f"   Forks: {', '.join(forks_found)}")
        logger.info(f"   EIPs found: {len(eips_found)}")
        
        return self.ingestion_result
    
    def _chunks_to_documents(self, chunks: List[SpecChunk]) -> List[Document]:
        """Convert SpecChunks to LlamaIndex Documents."""
        documents = []
        
        for chunk in chunks:
            # Build rich metadata for filtering and context
            metadata = {
                "fork": chunk.fork_name,
                "file_path": chunk.file_path,
                "chunk_type": chunk.chunk_type,
                "name": chunk.name,
                "eip_references": ",".join(chunk.eip_references),
                "line_start": chunk.line_start,
                "line_end": chunk.line_end,
            }
            
            # Add EIP references to content for better keyword matching
            eip_text = ""
            if chunk.eip_references:
                eip_text = f"\nRelated EIPs: {', '.join(chunk.eip_references)}"
            
            # Create document with enhanced content
            doc = Document(
                text=f"[{chunk.fork_name}] {chunk.name}\n{chunk.content}{eip_text}",
                metadata=metadata,
                excluded_embed_metadata_keys=["line_start", "line_end"],
                excluded_llm_metadata_keys=["line_start", "line_end"],
            )
            documents.append(doc)
        
        return documents
    
    def _save_metadata(self):
        """Save ingestion metadata to file."""
        if self.ingestion_result:
            metadata = {
                "total_files": self.ingestion_result.total_files,
                "total_chunks": self.ingestion_result.total_chunks,
                "forks_ingested": self.ingestion_result.forks_ingested,
                "eips_found": self.ingestion_result.eips_found,
            }
            
            metadata_file = self.storage_dir / "spec_metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
    
    def query(
        self, 
        query_text: str, 
        top_k: int = 5,
        alpha: float = 0.5,
        filter_fork: Optional[str] = None,
        filter_eip: Optional[str] = None
    ) -> List[NodeWithScore]:
        """
        Query specifications using hybrid search.
        
        Args:
            query_text: Natural language query or keywords
            top_k: Number of results to return
            alpha: Balance between dense (semantic) and sparse (keyword) search.
                   0.0 = pure keyword, 1.0 = pure semantic, 0.5 = balanced
            filter_fork: Optional fork filter (e.g., "prague")
            filter_eip: Optional EIP filter (e.g., "EIP-1559")
            
        Returns:
            List of NodeWithScore containing relevant spec chunks
        """
        if not self.index:
            raise ValueError("Index not initialized. Call ingest_specs() first.")
        
        # Build metadata filters if specified
        # Note: Qdrant filters would be added here for fork/EIP filtering
        
        # Create query engine with hybrid search
        query_engine = self.index.as_query_engine(
            similarity_top_k=top_k,
            sparse_top_k=top_k * 2,  # Get more from each method for better fusion
            vector_store_query_mode="hybrid",
            alpha=alpha,
        )
        
        # Execute query
        response = query_engine.query(query_text)
        
        return response.source_nodes
    
    def search_by_eip(self, eip_number: str, top_k: int = 10) -> List[NodeWithScore]:
        """
        Search for specifications related to a specific EIP.
        
        Uses keyword-heavy search (low alpha) to find exact EIP references.
        
        Args:
            eip_number: EIP number (e.g., "EIP-1559" or "1559")
            top_k: Number of results
            
        Returns:
            List of relevant spec chunks
        """
        # Normalize EIP reference
        if not eip_number.upper().startswith("EIP"):
            eip_number = f"EIP-{eip_number}"
        
        # Use keyword-heavy search for exact matching
        return self.query(eip_number, top_k=top_k, alpha=0.3)
    
    def search_by_concept(self, concept: str, top_k: int = 5) -> List[NodeWithScore]:
        """
        Search for specifications by conceptual description.
        
        Uses semantic-heavy search (high alpha) for conceptual matching.
        
        Args:
            concept: Conceptual description (e.g., "transaction validation")
            top_k: Number of results
            
        Returns:
            List of relevant spec chunks
        """
        return self.query(concept, top_k=top_k, alpha=0.7)
    
    def get_specs_for_code_entity(
        self, 
        entity_name: str,
        entity_type: str,
        entity_code: str,
        language: str,
        top_k: int = 5
    ) -> List[NodeWithScore]:
        """
        Find relevant specifications for a code entity.
        
        Combines entity metadata with code analysis to find the most
        relevant specifications for compliance checking.
        
        Args:
            entity_name: Name of the code entity (function/class)
            entity_type: Type of entity (function, class, etc.)
            entity_code: The actual code content
            language: Programming language
            top_k: Number of results
            
        Returns:
            List of relevant spec chunks
        """
        # Build a comprehensive query from the entity
        # Extract key terms from entity name and code
        query_parts = [entity_name]
        
        # Add common Ethereum-related keywords found in code
        ethereum_keywords = [
            "transaction", "block", "gas", "nonce", "signature",
            "address", "balance", "transfer", "call", "create",
            "storage", "state", "receipt", "log", "event",
            "EIP", "ERC", "validate", "verify", "check"
        ]
        
        for keyword in ethereum_keywords:
            if keyword.lower() in entity_code.lower():
                query_parts.append(keyword)
        
        # Extract EIP references from code comments
        import re
        eip_matches = re.findall(r'EIP[- ]?(\d+)', entity_code, re.IGNORECASE)
        for eip_num in eip_matches:
            query_parts.append(f"EIP-{eip_num}")
        
        query = " ".join(query_parts[:10])  # Limit query length
        
        logger.debug(f"Spec query for {entity_name}: {query}")
        
        return self.query(query, top_k=top_k, alpha=0.5)
    
    def reset(self):
        """Reset/clear all specification data."""
        logger.info("Resetting specification index...")
        
        # Delete Qdrant collection
        try:
            self.qdrant_client.delete_collection(self.collection_name)
            logger.info(f"Deleted collection: {self.collection_name}")
        except Exception as e:
            logger.warning(f"Failed to delete collection: {e}")
        
        # Clear metadata
        metadata_file = self.storage_dir / "spec_metadata.json"
        if metadata_file.exists():
            metadata_file.unlink()
        
        # Clear in-memory data
        self.index = None
        self.chunks = []
        self.ingestion_result = None
        
        # Reinitialize vector store
        self.vector_store = QdrantVectorStore(
            collection_name=self.collection_name,
            client=self.qdrant_client,
            enable_hybrid=True,
            fastembed_sparse_model="Qdrant/bm25",
            batch_size=20,
        )
        
        logger.info("✅ Specification index reset complete")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the indexed specifications."""
        if not self.ingestion_result:
            return {
                "indexed": False,
                "total_chunks": 0,
                "forks": [],
                "eips": []
            }
        
        return {
            "indexed": True,
            "total_files": self.ingestion_result.total_files,
            "total_chunks": self.ingestion_result.total_chunks,
            "forks": self.ingestion_result.forks_ingested,
            "eips": self.ingestion_result.eips_found,
            "storage_path": str(self.storage_dir),
        }
