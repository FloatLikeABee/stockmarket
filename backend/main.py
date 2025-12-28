from backend.api import StockAPI
import os
import sys


def main():
    # Create and run the API
    api = StockAPI()
    
    # Get host and port from environment or use defaults
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 9878))  # Changed from 8000 to 9878
    
    print(f"Starting Chinese Stock Market API on {host}:{port}")
    print("API endpoints:")
    print(f"  - http://{host}:{port} - API root")
    print(f"  - http://{host}:{port}/docs - API documentation")
    print(f"  - http://{host}:{port}/redoc - Alternative API documentation")
    
    api.run(host=host, port=port)


if __name__ == "__main__":
    main()