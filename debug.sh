#!/bin/bash

echo "🐛 Starting Chinese Stock Market Data Application in Debug Mode"
echo "================================================================"

# Check if Node.js is available
if ! command -v node &> /dev/null; then
    echo "Node.js is not installed or not in PATH."
    echo "Please install Node.js from https://nodejs.org/ and try again."
    exit 1
fi

echo "Node.js version: $(node --version)"

# Check if npm is available
if ! command -v npm &> /dev/null; then
    echo "npm is not installed or not in PATH."
    echo "Please install Node.js (which includes npm) from https://nodejs.org/ and try again."
    exit 1
fi

# Change to project directory
cd "$(dirname "$0")"

echo "Starting backend server on port 9878..."
python -c "import sys; sys.path.insert(0, '.'); import uvicorn; from backend.api import api; uvicorn.run(api, host='0.0.0.0', port=9878, reload=True, debug=True)" &

# Wait a bit for the backend to start
sleep 3

# Start frontend
echo "Starting frontend server on port 4000..."
cd frontend

# Install dependencies if node_modules doesn't exist or react-scripts is missing
if [ ! -d "node_modules" ] || [ ! -f "node_modules/.bin/react-scripts" ]; then
    echo "Installing or fixing frontend dependencies..."
    ../fix_frontend_deps.sh
    if [ $? -ne 0 ]; then
        echo "Failed to install frontend dependencies. Exiting."
        exit 1
    fi
fi

PORT=4000 npm start &

# Wait for processes to start
sleep 3

echo ""
echo "Application is now running in debug mode:"
echo "Backend: http://localhost:9878"
echo "Frontend: http://localhost:4000"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

# Wait for user to press Ctrl+C
wait