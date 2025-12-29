# Chinese Stock Market Data Crawler & API

A professional stock market data crawler for Chinese financial websites with a React frontend and FastAPI backend.

## Features

- **Multi-site crawling**: Supports 同花顺, 通达信, 东方财富, 雪球, 财联社
- **Rate limiting**: Prevents abuse with 5-10 minute minimum intervals
- **Automatic crawling**: Runs every 20 minutes
- **Data indexing**: Uses TinyDB for persistent storage and redislite for embedded caching
- **RESTful API**: For controlling crawls and accessing data
- **Modern UI**: React frontend with Material UI in dark purple/green theme
- **Responsive design**: Works on desktop and mobile

## Architecture

```
backend/                 # FastAPI backend
├── crawler.py          # Stock data crawler
├── database.py         # TinyDB + redislite integration
├── api.py              # API endpoints
└── main.py             # Application entry point

frontend/               # React frontend
├── src/
│   ├── App.js          # Main application component
│   ├── index.js        # Entry point
│   └── index.css       # Styling
└── package.json        # Dependencies

data/                   # Crawled data storage
├── general/            # General category data
├── scheduled/          # Scheduled crawl data
└── index.json          # TinyDB index
└── cache.db            # Embedded Redis cache
```

## Setup

### Backend

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Run the backend:
```bash
python run_backend.py
```

The API will be available at `http://localhost:9878`

### Frontend

1. Install Node.js dependencies:
```bash
cd frontend
npm install
```

2. Run the development server:
```bash
cd frontend
npm start
```

Or to specify port 4000 explicitly:
```bash
cd frontend
npm run start:4000
```

**Windows users**: If you get an error with `PORT=4000`, use:
```bash
cd frontend
set PORT=4000 && npm start
```

Or simply use `npm start` (defaults to port 3000) or `npm run start:4000` after installing dependencies.

The frontend will be available at `http://localhost:4000` (or `http://localhost:3000` if using default)

## API Endpoints

- `GET /` - API root
- `POST /crawl` - Trigger crawling (request body: `{ sites: ["tonghuashun", ...] }` or null for all)
- `GET /data/latest?limit=10` - Get latest crawled records
- `GET /data/sites` - Get all unique sites in DB
- `GET /data/site/{site_name}` - Get data from specific site
- `GET /stats` - Get database statistics
- `GET /rate_limit_status` - Get rate limit status for crawlers
- `GET /docs` - Interactive API documentation

## Data Storage

- Crawled data is stored in JSON files in the `data/` directory
- Files are organized by category and timestamp
- TinyDB maintains an index of all files in `data/index.json`
- redislite provides embedded caching in `data/cache.db`

## Rate Limiting

To prevent abuse, crawlers are limited to running every 5 minutes per site. The API tracks the last crawl time for each site and will return an error if the minimum interval hasn't passed.

## Frontend Features

- Dark theme with purple and green colors (like Kraken)
- Real-time data visualization
- Manual crawl triggering
- Statistics dashboard
- Responsive layout for all devices
- Data explorer for browsing crawled records

## Security Note

This project includes a placeholder API key. In a production environment, you should:

1. Use environment variables for sensitive data
2. Implement proper authentication
3. Add rate limiting at the network level
4. Validate and sanitize all inputs