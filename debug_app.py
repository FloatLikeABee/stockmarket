#!/usr/bin/env python3
"""
Debug startup script for the Chinese Stock Market Data application
This script runs both backend and frontend in debug mode
"""
import subprocess
import sys
import os
import time
import threading
from pathlib import Path


def install_dependencies():
    """Install required dependencies from requirements.txt"""
    print("Installing backend dependencies...")
    result = subprocess.run([
        sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        print("Error installing backend dependencies:")
        print(result.stderr)
        return False
    print("Backend dependencies installed successfully!")
    return True


def check_node_available():
    """Check if Node.js is available in the system"""
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Node.js is available: {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    
    print("❌ Node.js is not available. Please install Node.js before running the frontend.")
    print("You can download it from: https://nodejs.org/")
    return False


def run_backend_debug():
    """Run the backend API server in debug mode"""
    print("Starting backend API server in debug mode...")
    
    # Add the project root directory to Python path
    project_dir = Path(__file__).parent
    sys.path.insert(0, str(project_dir))
    
    try:
        import uvicorn
        from backend.api import api
        
        # Run with debug/reload options
        uvicorn.run(
            api, 
            host="0.0.0.0", 
            port=9878, 
            reload=True,  # Enable auto-reload on code changes
            debug=True    # Enable debug mode
        )
    except KeyboardInterrupt:
        print("\nBackend server stopped")
    except Exception as e:
        print(f"Error running the backend: {e}")
        import traceback
        traceback.print_exc()


def run_frontend_debug():
    """Run the React frontend in debug mode"""
    print("Starting frontend in debug mode...")
    
    # Check if Node.js is available
    if not check_node_available():
        print("Skipping frontend startup due to missing Node.js")
        return False
    
    frontend_path = Path(__file__).parent / "frontend"
    
    # Check if node_modules exists, if not install dependencies
    node_modules_path = frontend_path / "node_modules"
    if not node_modules_path.exists():
        print("Installing frontend dependencies...")
        result = subprocess.run([
            "npm", "install"
        ], cwd=frontend_path, capture_output=True, text=True)
        
        if result.returncode != 0:
            print("Error installing frontend dependencies:")
            print(result.stderr)
            return False
    
    # Set the PORT environment variable and start the development server
    env = os.environ.copy()
    env['PORT'] = '4000'
    
    result = subprocess.run([
        "npm", "start"
    ], cwd=frontend_path, env=env)
    
    return result.returncode == 0


def run_backend_in_thread():
    """Run the backend in a separate thread for debug mode"""
    def run_backend():
        run_backend_debug()
    
    backend_thread = threading.Thread(target=run_backend, daemon=True)
    backend_thread.start()
    return backend_thread


def main():
    """Main debug startup function"""
    print("🐛 Starting Chinese Stock Market Data Application in Debug Mode")
    print("=" * 65)
    
    # Change to the project directory
    project_dir = Path(__file__).parent
    os.chdir(project_dir)
    
    # Install backend dependencies
    if not install_dependencies():
        print("❌ Failed to install backend dependencies")
        return
    
    # Run both backend and frontend
    print("\nStarting services in debug mode...")
    print("Backend API will be available at: http://localhost:9878")
    print("Frontend will be available at: http://localhost:4000")
    print("Auto-reload enabled for both services")
    print("\nPress Ctrl+C to stop all services\n")
    
    # Start backend in a thread
    backend_thread = run_backend_in_thread()
    
    # Small delay to let backend start
    time.sleep(2)
    
    # Start frontend
    try:
        run_frontend_debug()
    except KeyboardInterrupt:
        print("\nStopping application...")
        return


if __name__ == "__main__":
    main()