#!/bin/bash

echo "🛑 Stopping existing server..."
lsof -ti:8000 | xargs kill -9 2>/dev/null
sleep 2

echo "🚀 Starting API server..."
cd /Users/A200309906/Downloads/Hybrid-Property-Graph-RAG-main
python3 api_server.py


