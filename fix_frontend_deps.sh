#!/bin/bash

echo "🔧 Fixing frontend dependencies..."
echo "=================================="

# Change to the project directory
cd "$(dirname "$0")"

# Navigate to frontend directory
cd frontend

# Remove node_modules and package-lock.json to reinstall everything fresh
echo "Removing node_modules and package-lock.json..."
rm -rf node_modules
rm -f package-lock.json

# Clear npm cache
echo "Clearing npm cache..."
npm cache clean --force

# Install dependencies
echo "Installing dependencies..."
npm install

# Check if react-scripts is installed in node_modules/.bin
if [ -f "node_modules/.bin/react-scripts" ]; then
    echo "✅ react-scripts is available at node_modules/.bin/react-scripts"
else
    echo "❌ react-scripts is not available, trying to install explicitly..."
    
    # Try to install react-scripts specifically
    npm install --save-dev react-scripts
    
    # Check again
    if [ -f "node_modules/.bin/react-scripts" ]; then
        echo "✅ react-scripts is now available"
    else
        echo "❌ react-scripts still not available, trying global install..."
        npm install -g react-scripts
        
        # Final check
        if command -v react-scripts &> /dev/null; then
            echo "✅ react-scripts is now available globally"
        else
            echo "❌ react-scripts is still not available"
            exit 1
        fi
    fi
fi

# Verify installation by checking package.json dependencies
echo "Verifying react-scripts in package.json..."
if grep -q "react-scripts" package.json; then
    echo "✅ react-scripts found in package.json"
else
    echo "❌ react-scripts not found in package.json, adding it..."
    npm install --save-dev react-scripts
fi

echo "✅ Dependencies fixed successfully!"
echo ""
echo "You can now run the frontend with:"
echo "cd frontend && PORT=4000 npm start"