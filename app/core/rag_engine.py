"""
================================================================================
HYBRID SEARCH-BASED RAG (Retrieval Augmented Generation) SYSTEM
================================================================================

TUTORIAL: Understanding Graph-Based RAG with Hybrid Search

This script demonstrates an advanced RAG system that uses a Property Graph Index
combined with hybrid search capabilities. Unlike traditional vector-only RAG 
systems, this approach leverages both semantic similarity and knowledge graph 
relationships to retrieve more contextually relevant information.

KEY CONCEPTS EXPLAINED:

1. PROPERTY GRAPH INDEX:
   - Stores documents as nodes and relationships in a graph structure
   - Extracts entities and their connections from text
   - Enables traversal of knowledge relationships
   - Example: "Microsoft" (node) --[operates_in]--> "US" (node)

2. HYBRID SEARCH:
   - Combines multiple retrieval strategies for better accuracy
   - Vector Search: Finds semantically similar content via embeddings
   - Synonym Search: Uses LLM to expand query with related terms
   - Graph Traversal: Follows relationship paths in the knowledge graph

3. WHY USE HYBRID SEARCH?
   - Vector search alone might miss important context
   - Synonym expansion captures different phrasings of the same concept
   - Graph relationships provide structural knowledge
   - Combined approach = higher accuracy and recall

ARCHITECTURE FLOW:
User Query → Hybrid Retriever → [Vector Search + Synonym Expansion + Graph Traversal] 
→ Context Retrieval → LLM Answer Generation → Final Response

================================================================================
"""

import os
import logging
import nest_asyncio

# ============================================================================
# SECTION 1: CONFIGURATION
# ============================================================================
# This section sets up the connection to your LLM server and configures
# the models to use for text generation and embeddings.

# API Configuration - Replace with your own credentials
# NOTE: This example uses a custom OpenAI-compatible server
CUSTOM_API_KEY = "YOUR API KEY"
CUSTOM_API_BASE = "API BASE URL"

# Model Configuration
# LLM_MODEL: The language model for text generation and reasoning
# EMBED_MODEL: The model for converting text to vector embeddings
LLM_MODEL = "gpt-4.1"  # Custom model name (not standard OpenAI)
EMBED_MODEL = "text-embedding-ada-002"  # Standard embedding model

# Asyncio Fix - Required for running async operations in Jupyter/scripts
# This allows nested event loops, which some libraries require
nest_asyncio.apply()

# Logging Configuration - Reduce noise from llama_index internal logging
logging.getLogger("llama_index").setLevel(logging.ERROR)


# ============================================================================
# SECTION 2: GLOBAL SETTINGS SETUP
# ============================================================================
# LlamaIndex uses a global Settings object to configure LLMs and embeddings.
# We use OpenAILike instead of standard OpenAI to support custom model names.

from llama_index.core import Settings
from llama_index.llms.openai_like import OpenAILike  # For custom model names
from llama_index.embeddings.openai import OpenAIEmbedding

print(f"🔗 Connecting to custom server at: {CUSTOM_API_BASE}\n")

# Configure the Language Model (LLM)
# OpenAILike allows us to use non-standard model names with OpenAI-compatible APIs
Settings.llm = OpenAILike(
    model=LLM_MODEL,
    api_base=CUSTOM_API_BASE,
    api_key=CUSTOM_API_KEY,
    is_chat_model=True,      # Important: Enables chat-based interactions
    context_window=8192,     # Maximum tokens the model can process at once
    max_tokens=2048,         # Maximum tokens in the generated response
    temperature=0,           # Low temperature = more deterministic responses
)

# Configure the Embedding Model
# Embeddings convert text into dense vector representations for similarity search
Settings.embed_model = OpenAIEmbedding(
    model_name=EMBED_MODEL,
    api_base=CUSTOM_API_BASE,
    api_key=CUSTOM_API_KEY
)


# ============================================================================
# SECTION 3: IMPORT REQUIRED MODULES
# ============================================================================
# These modules provide the core functionality for building the RAG system

from llama_index.core import SimpleDirectoryReader
from llama_index.core.indices.property_graph import (
    PropertyGraphIndex,      # The main graph-based index
    LLMSynonymRetriever,    # Retriever that expands queries with synonyms
    VectorContextRetriever,  # Retriever using vector similarity search
    PGRetriever,            # Composite retriever combining multiple strategies
)
from llama_index.core.query_engine import RetrieverQueryEngine


# ============================================================================
# SECTION 4: LOAD DOCUMENTS AND BUILD INDEX
# ============================================================================
# This section loads your text documents and creates the Property Graph Index.
# The index automatically:
# 1. Chunks documents into smaller pieces
# 2. Extracts entities and relationships
# 3. Creates vector embeddings
# 4. Builds a queryable graph structure

def load_and_index_documents(data_dir="./data"):
    """
    Load documents from a directory and build a Property Graph Index.
    
    WHAT HAPPENS DURING INDEXING:
    1. Documents are split into smaller chunks (nodes)
    2. LLM extracts entities and relationships from each chunk
    3. Vector embeddings are created for semantic search
    4. Graph structure is built connecting related entities
    
    Args:
        data_dir: Path to directory containing .txt files
        
    Returns:
        PropertyGraphIndex object ready for querying
    """
    print("📚 Loading documents...")
    
    # Check if data directory exists, create if not
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        print(f"⚠️  Created {data_dir} folder. Please put your .txt files there and re-run.")
        return None
    
    # Load all documents from the directory
    # SimpleDirectoryReader automatically handles various text formats
    documents = SimpleDirectoryReader(data_dir).load_data()
    print(f"✅ Loaded {len(documents)} document(s)\n")
    
    # Build the Property Graph Index
    print("🔨 Building Property Graph Index...")
    print("   This process will:")
    print("   1. Parse and chunk documents")
    print("   2. Extract entities and relationships")
    print("   3. Generate vector embeddings")
    print("   4. Build the graph structure\n")
    
    index = PropertyGraphIndex.from_documents(
        documents,
        show_progress=True,   # Display progress bars
        use_async=False       # Use synchronous processing (simpler for debugging)
    )
    
    print("\n✨ PropertyGraphIndex built successfully!\n")
    return index


# ============================================================================
# SECTION 5: BUILD HYBRID RETRIEVERS
# ============================================================================
# Hybrid search combines multiple retrieval strategies for better results.
# Each retriever uses a different approach to find relevant information.

def build_hybrid_retrievers(index):
    """
    Create a hybrid retriever combining vector and synonym-based search.
    
    RETRIEVER STRATEGIES EXPLAINED:
    
    1. VectorContextRetriever:
       - Uses cosine similarity between query and document embeddings
       - Finds semantically similar content
       - Example: "automobile" matches "car" even if exact word isn't present
    
    2. LLMSynonymRetriever:
       - Uses LLM to generate synonyms and related terms
       - Expands query to capture different phrasings
       - Example: Query "CEO" → expands to ["CEO", "chief executive", "president"]
    
    3. PGRetriever:
       - Combines results from all sub-retrievers
       - Merges and ranks retrieved contexts
       - Provides diverse, comprehensive results
    
    Args:
        index: PropertyGraphIndex object
        
    Returns:
        PGRetriever configured with multiple retrieval strategies
    """
    print("🔍 Building Hybrid Retrievers...")
    
    # RETRIEVER 1: Vector-based semantic search
    # This finds documents with similar meaning to the query
    vector_retriever = VectorContextRetriever(
        graph_store=index.property_graph_store,  # The graph structure
        vector_store=index.vector_store,          # The vector embeddings
        embed_model=Settings.embed_model,         # Embedding model to use
        include_text=True,                        # Include full text in results
        similarity_top_k=3,                       # Return top 3 most similar chunks
    )
    print("   ✓ Vector retriever configured (top_k=3)")
    
    # RETRIEVER 2: LLM-based synonym expansion
    # This uses the LLM to understand alternative phrasings
    synonym_retriever = LLMSynonymRetriever(
        graph_store=index.property_graph_store,  # The graph structure
        llm=Settings.llm,                        # LLM for generating synonyms
        include_text=True,                       # Include full text in results
        max_keywords=5,                          # Generate up to 5 synonym terms
    )
    print("   ✓ Synonym retriever configured (max_keywords=5)")
    
    # RETRIEVER 3: Compose into unified hybrid retriever
    # Combines results from both strategies
    pg_retriever = PGRetriever(
        sub_retrievers=[vector_retriever, synonym_retriever]
    )
    print("   ✓ Hybrid retriever created\n")
    
    return pg_retriever


# ============================================================================
# SECTION 6: BUILD QUERY ENGINE
# ============================================================================
# The query engine coordinates retrieval and response generation.

def build_query_engine(index, pg_retriever):
    """
    Create a query engine that uses the hybrid retriever.
    
    HOW THE QUERY ENGINE WORKS:
    1. Takes user's natural language question
    2. Passes it to the hybrid retriever
    3. Retriever returns relevant context from documents
    4. LLM synthesizes the context into a coherent answer
    5. Returns the final response to the user
    
    Args:
        index: PropertyGraphIndex object
        pg_retriever: Configured hybrid retriever
        
    Returns:
        RetrieverQueryEngine ready to answer questions
    """
    print("⚙️  Building Query Engine...")
    
    query_engine = RetrieverQueryEngine.from_args(
        index.as_retriever(sub_retrievers=[pg_retriever]),
        llm=Settings.llm,  # Use globally configured LLM
    )
    
    print("   ✓ Query engine ready\n")
    return query_engine


# ============================================================================
# SECTION 7: QUERY EXECUTION FUNCTION
# ============================================================================
# Helper function to execute queries and handle errors gracefully

def execute_query(query_engine, question):
    """
    Execute a query and return the result.
    
    Args:
        query_engine: Configured RetrieverQueryEngine
        question: Natural language question string
        
    Returns:
        String response from the LLM
    """
    print(f"\n💬 Query: {question}")
    print("-" * 80)
    
    try:
        result = query_engine.query(question)
        response = str(result)
        print(f"🤖 Answer:\n{response}\n")
        return response
    except Exception as e:
        error_msg = f"❌ Query failed: {e}"
        print(error_msg)
        return error_msg


# ============================================================================
# SECTION 8: MAIN EXECUTION
# ============================================================================
# This is where everything comes together

def main():
    """
    Main function that orchestrates the entire RAG pipeline.
    
    EXECUTION FLOW:
    1. Load documents from ./data directory
    2. Build Property Graph Index (with embeddings and relationships)
    3. Configure hybrid retrievers (vector + synonym)
    4. Create query engine
    5. Execute sample queries
    """
    print("=" * 80)
    print("HYBRID SEARCH-BASED RAG SYSTEM")
    print("=" * 80)
    print()
    
    # Step 1: Load and index documents
    index = load_and_index_documents("./data")
    
    if index is None:
        print("⚠️  No index created. Add documents to ./data and try again.")
        return
    
    # Step 2: Build hybrid retrievers
    pg_retriever = build_hybrid_retrievers(index)
    
    # Step 3: Build query engine
    query_engine = build_query_engine(index, pg_retriever)
    
    # Step 4: Execute sample queries
    print("=" * 80)
    print("SAMPLE QUERIES")
    print("=" * 80)
    
    # Example queries - replace these with your own questions
    queries = [
        "What is the customer name and in which country this customer present and its in which industry?",
        "What are the customer requirements?",
        "What all are required softwares, tools, platforms and other technical things in this project?",
        "What all are key dates and timelines in this project?",
    ]
    
    for query in queries:
        execute_query(query_engine, query)
    
    print("=" * 80)
    print("✅ EXECUTION COMPLETE")
    print("=" * 80)
    
    # Return the query engine for interactive use
    return query_engine


# ============================================================================
# SECTION 9: SCRIPT ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    # Run the main function when script is executed directly
    query_engine = main()
    
    # Optional: Interactive query loop
    # Uncomment the code below to enable interactive querying
    """
    print("\n" + "="*80)
    print("INTERACTIVE MODE - Enter your queries (type 'exit' to quit)")
    print("="*80 + "\n")
    
    while True:
        user_query = input("Your question: ").strip()
        
        if user_query.lower() in ['exit', 'quit', 'q']:
            print("👋 Goodbye!")
            break
            
        if not user_query:
            continue
            
        execute_query(query_engine, user_query)
    """


# ============================================================================
# ADDITIONAL NOTES FOR DEVELOPERS
# ============================================================================
"""
CUSTOMIZATION OPTIONS:

1. Adjust Retrieval Parameters:
   - similarity_top_k: Increase to get more context (default: 3)
   - max_keywords: Change number of synonym expansions (default: 5)

2. Model Settings:
   - temperature: 0 = deterministic, 1 = creative responses
   - max_tokens: Control response length
   - context_window: Must match your LLM's capacity

3. Adding More Retrievers:
   You can add additional retrievers to the PGRetriever:
   - TextToCypherRetriever: For graph database queries
   - CustomRetriever: Implement your own retrieval logic

4. Performance Optimization:
   - Set use_async=True for faster indexing (requires proper async setup)
   - Use batching for large document collections
   - Consider caching index to disk to avoid rebuilding

5. Data Requirements:
   - Place .txt files in ./data directory
   - Supported formats: .txt, .pdf, .docx (with appropriate readers)
   - For best results, use clean, well-structured documents

TROUBLESHOOTING:

Q: "Model not found" error?
A: Ensure your CUSTOM_API_BASE and LLM_MODEL are correct for your server.

Q: Slow indexing?
A: Large documents take time. Use show_progress=True to monitor progress.

Q: Poor answer quality?
A: Try adjusting similarity_top_k and max_keywords to retrieve more context.

Q: Out of memory?
A: Process documents in smaller batches or reduce context_window size.

FURTHER READING:
- LlamaIndex Documentation: https://docs.llamaindex.ai
- Property Graphs: https://en.wikipedia.org/wiki/Graph_database
- Vector Embeddings: https://platform.openai.com/docs/guides/embeddings
- RAG Architecture: https://arxiv.org/abs/2005.11401
"""
