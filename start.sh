#!/bin/bash

# YouTube Downloader Pro - World Class Application Startup Script
echo "🚀 Starting YouTube Downloader Pro - World Class Application"
echo "================================================================"

# Check if Docker is available
if command -v docker &> /dev/null && command -v docker-compose &> /dev/null; then
    echo "🐳 Docker detected - Starting with Docker Compose (Recommended)"
    echo ""
    
    # Create necessary directories
    mkdir -p data downloads uploads logs
    
    # Generate secret key if not exists
    if [ ! -f .env ]; then
        echo "📝 Creating .env file..."
        cat > .env << EOF
SECRET_KEY=$(openssl rand -hex 32)
DEBUG=false
DATABASE_URL=sqlite+aiosqlite:///./data/downloads.db
REDIS_URL=redis://redis:6379/0
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000
EOF
    fi
    
    # Start all services
    echo "🚀 Starting all services..."
    docker-compose up -d
    
    echo ""
    echo "✅ Application started successfully!"
    echo ""
    echo "🌐 Access your application:"
    echo "   Main App:     http://localhost:8000"
    echo "   API Docs:     http://localhost:8000/api/docs"
    echo "   Flower UI:    http://localhost:5555"
    echo ""
    echo "📊 Monitor with:"
    echo "   docker-compose logs -f"
    echo "   docker-compose ps"
    
else
    echo "🐍 Starting in development mode..."
    
    # Check if virtual environment exists
    if [ ! -d "env" ]; then
        echo "📦 Creating virtual environment..."
        python3 -m venv env
    fi
    
    # Activate virtual environment
    source env/bin/activate
    
    # Install dependencies
    echo "📦 Installing dependencies..."
    pip install -r requirements.txt
    
    # Create directories
    mkdir -p downloads uploads temp logs data
    
    # Set environment variables
    export DEBUG=true
    export DATABASE_URL=sqlite+aiosqlite:///./data/downloads.db
    export SECRET_KEY=dev-secret-key
    
    echo ""
    echo "🚀 Starting FastAPI application..."
    echo "   You'll need to start Redis separately if you want full functionality"
    echo ""
    
    # Start the application
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
fi 