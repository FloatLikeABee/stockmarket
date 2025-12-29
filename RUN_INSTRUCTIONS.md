# Running the Chinese Stock Market Data Application

## Prerequisites

- Python 3.8+
- Node.js 14+
```

/Users/floatinbee/robo/stockmarket/RUN_INSTRUCTIONS.md
```markdown
<<<<<<< SEARCH
### 1. Install Redis

If you don't have Redis installed, run the install script:

```bash
# On macOS
./install_redis.sh

# Or on Linux
./install_redis.sh
```

### 2. Start the Application
### 1. Start the Application

## Quick Start

### 1. Install Redis

If you don't have Redis installed, run the install script:

```bash
# On macOS
./install_redis.sh

# Or on Linux
./install_redis.sh
```

### 2. Start the Application

You can start both the backend and frontend with a single command:

```bash
python start_app.py
```

This will:
1. Install backend dependencies
2. Check/start Redis
3. Start the FastAPI backend server on port 9878
4. Start the React frontend on port 4000

## Debug Mode

For debugging purposes, you have several options:

### Option 1: Python Debug Script

Run the application in debug mode with auto-reload:

```bash
python debug_app.py
```

This enables:
- Auto-reload for backend when code changes
- Debug mode for the backend
- Standard React development server with hot reloading

### Option 2: VS Code Debugger

If you're using VS Code, the project includes launch configurations in [.vscode/launch.json](file:///Users/floatinbee/robo/stockmarket/.vscode/launch.json):

1. Open the project in VS Code
2. Go to the Run and Debug view (Ctrl+Shift+D or Cmd+Shift+D)
3. Select one of the configurations:
   - "Debug Backend (Port 9878)" - Debug only the backend
   - "Debug Frontend (Port 4000)" - Debug only the frontend
   - "Debug Full Application" - Debug the full application start script

### Option 3: Shell Debug Script

Run the debug shell script:

```bash
./debug.sh
```

This will start both services in debug mode with auto-reload capabilities.

## Running Services Separately

### Backend Only

```bash
# Install dependencies
pip install -r requirements.txt

# Start the backend
python run_backend.py
```

The API will be available at `http://localhost:9878`

### Frontend Only

```bash
cd frontend
npm install
npm run start:4000
```

**Windows users**: If you get an error, use:
```bash
cd frontend
npm install
set PORT=4000 && npm start
```

Or simply use `npm start` (defaults to port 3000).

The frontend will be available at `http://localhost:4000` (or `http://localhost:3000` if using default)

## API Endpoints

Once the backend is running, you can access:

- `http://localhost:9878` - API root
- `http://localhost:9878/docs` - Interactive API documentation
- `http://localhost:9878/data/latest` - Get latest stock data
- `http://localhost:9878/stats` - Get database statistics

## Frontend Features

- Dark purple/green theme similar to Kraken
- Dashboard showing latest stock data
- Manual crawl triggering
- Data visualization
- Statistics overview

## Note about Redis

This application now uses redislite, which embeds Redis functionality directly in the Python application. This means:
- No need to install or run a separate Redis server
- All caching is handled internally by the application
- Cache data is stored in the data/cache.db file

## Troubleshooting

### Frontend Not Connecting to Backend

The frontend is configured to proxy API requests to `http://localhost:9878`. If you're running the backend on a different port, update the proxy in `frontend/package.json`.

### Rate Limiting

Crawling is limited to every 5 minutes per site to prevent abuse. You can check the rate limit status at:
`http://localhost:9878/rate_limit_status`