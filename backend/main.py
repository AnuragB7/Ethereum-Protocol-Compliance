#!/usr/bin/env python3
"""
Main Entry Point

Code Analysis Platform - Multi-language codebase analysis powered by Property Graph RAG
with Ethereum specification compliance checking.

Usage:
    python main.py                    # Start the server with default settings
    python main.py --host 0.0.0.0     # Specify host
    python main.py --port 8080        # Specify port
    python main.py --reload           # Enable auto-reload for development
"""

import argparse
import logging
import uvicorn
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging to suppress noisy HTTP request logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


def main():
    """Main entry point for the application."""
    parser = argparse.ArgumentParser(
        description="Code Analysis Platform API Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py                     Start with default settings
    python main.py --port 8080         Start on port 8080
    python main.py --reload            Start with auto-reload
    python main.py --workers 4         Start with 4 workers
        """
    )
    
    parser.add_argument(
        "--host",
        type=str,
        default="0.0.0.0",
        help="Host to bind the server to (default: 0.0.0.0)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the server to (default: 8000)"
    )
    
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )
    
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (default: 1)"
    )
    
    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Log level (default: info)"
    )
    
    args = parser.parse_args()
    
    # Print startup banner
    print("""
    ╔════════════════════════════════════════════════════════════════╗
    ║                                                                ║
    ║       Code Analysis Platform                                   ║
    ║       Multi-language codebase analysis                         ║
    ║       Powered by Property Graph RAG                            ║
    ║                                                                ║
    ╠════════════════════════════════════════════════════════════════╣
    ║                                                                ║
    ║       Features:                                                ║
    ║       • Python, Java, COBOL, JS/TS, Vue, Go parsing           ║
    ║       • Property Graph indexing with LlamaIndex               ║
    ║       • Hybrid retrieval (semantic + keyword)                 ║
    ║       • Ethereum specification compliance checking            ║
    ║       • EIP/ERC rule extraction and validation                ║
    ║       • Git integration for PR/commit analysis                ║
    ║                                                                ║
    ╚════════════════════════════════════════════════════════════════╝
    """)
    
    # Run the server
    uvicorn.run(
        "app.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        workers=args.workers if not args.reload else 1,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
