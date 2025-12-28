#!/usr/bin/env python3
"""
Startup script for the Chinese Stock Market Data API
"""
import subprocess
import sys
import os
from pathlib import Path
import importlib.util


def install_dependencies():
    """Install required dependencies from requirements.txt"""
    print("Installing dependencies...")
    result = subprocess.run([
        sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        print("Error installing dependencies:")
        print(result.stderr)
        return False
    print("Dependencies installed successfully!")
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


def run_api():
    """Run the main API application"""
    print("Starting the Chinese Stock Market API...")
    
    # Add the project root directory to Python path
    project_dir = Path(__file__).parent
    sys.path.insert(0, str(project_dir))
    
    try:
        # Import and run the main function from the backend
        from backend.main import main
        main()
    except ImportError as e:
        print(f"Import error: {e}")
        import traceback
        traceback.print_exc()
    except KeyboardInterrupt:
        print("\nShutting down the API server...")
    except Exception as e:
        print(f"Error running the API: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main startup function"""
    print("Initializing Chinese Stock Market Data Crawler and API")
    
    # Change to the project directory
    project_dir = Path(__file__).parent
    os.chdir(project_dir)
    
    # Install dependencies
    if not install_dependencies():
        return
    
    # Run the API
    run_api()


if __name__ == "__main__":
    main()