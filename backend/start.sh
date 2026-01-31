#!/bin/bash
# ===========================================
# Code Analysis Platform - Startup Script
# ===========================================

echo "🚀 Starting Code Analysis Platform..."

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
    echo "✅ Loaded environment variables from .env"
else
    echo "⚠️  No .env file found. Create one from env.example"
fi

# Check Python version
python3 --version

# Start the server using main.py
echo ""
echo "🔧 Starting FastAPI server..."
echo "📚 API Docs: http://localhost:8000/docs"
echo "🏥 Health Check: http://localhost:8000/health"
echo ""

python3 main.py "$@"
