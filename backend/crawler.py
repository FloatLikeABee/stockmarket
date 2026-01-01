import asyncio
import requests
import json
import re
from datetime import datetime
import os
import time
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import fake_useragent
from pathlib import Path
from openai import OpenAI
from .akshare_fetcher import AKShareFetcher
from .json_repair import repair_json, extract_partial_json


class ChineseStockCrawler:
    def __init__(self, data_dir: str = "data", qwen_api_key: str = "sk-206d748313fb42dab3910dc3407f441b"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': fake_useragent.UserAgent().random
        })
        
        # Qwen API configuration using OpenAI compatible mode
        self.qwen_api_key = qwen_api_key
        self.qwen_api_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
        # Initialize OpenAI client for Qwen with error handling
        self.openai_client = None
        try:
            # Try to initialize OpenAI client
            # Note: If there's a version conflict with httpx, we'll catch it and continue without AI processing
            import httpx
            # Create a custom httpx client without proxies to avoid the compatibility issue
            http_client = httpx.Client(
                timeout=httpx.Timeout(60.0, connect=10.0),
                follow_redirects=True
            )
            self.openai_client = OpenAI(
                api_key=self.qwen_api_key,
                base_url=self.qwen_api_url,
                http_client=http_client
            )
            print("[Crawler] OpenAI client initialized successfully")
        except (TypeError, AttributeError) as e:
            # This is likely the httpx proxies issue or version incompatibility
            print(f"[Crawler] Warning: OpenAI client initialization failed due to version conflict: {e}")
            print("[Crawler] Attempting fallback initialization without custom http_client...")
            try:
                # Fallback: try without custom http_client
                self.openai_client = OpenAI(
                    api_key=self.qwen_api_key,
                    base_url=self.qwen_api_url
                )
                print("[Crawler] OpenAI client initialized with fallback method")
            except Exception as e2:
                print(f"[Crawler] Error: Could not initialize OpenAI client even with fallback: {e2}")
                print("[Crawler] Continuing without AI processing. Web scraping and AKShare will still work.")
                self.openai_client = None
        except Exception as e:
            print(f"[Crawler] Warning: Could not initialize OpenAI client: {e}")
            print("[Crawler] Continuing without AI processing. Web scraping and AKShare will still work.")
            self.openai_client = None
        
        # Initialize AKShare fetcher for deep data collection
        try:
            self.akshare_fetcher = AKShareFetcher()
            print("[Crawler] AKShare fetcher initialized successfully")
        except Exception as e:
            print(f"[Crawler] Warning: Could not initialize AKShare fetcher: {e}")
            self.akshare_fetcher = None
        
        # Only using AKShare now - no web scraping sites
        self.sites = {}
        
        # Rate limiting
        self.last_crawl_times = {}
        self.min_crawl_interval = 300  # 5 minutes in seconds

    def can_crawl(self, site_name: str, bypass_rate_limit: bool = False) -> bool:
        """Check if we can crawl the site based on rate limiting"""
        if bypass_rate_limit:
            return True  # Manual crawls bypass rate limiting
        current_time = time.time()
        last_crawl = self.last_crawl_times.get(site_name, 0)
        
        if current_time - last_crawl >= self.min_crawl_interval:
            return True
        return False

    def update_crawl_time(self, site_name: str):
        """Update the last crawl time for a site"""
        self.last_crawl_times[site_name] = time.time()
    
    def _extract_data_from_text(self, text: str, raw_preview: str) -> Optional[Dict]:
        """Extract structured data from text when JSON parsing fails"""
        try:
            extracted = {
                "stocks": [],
                "indices": [],
                "market_overview": "",
                "top_gainers": [],
                "top_losers": [],
                "trading_summary": ""
            }
            
            # Try to extract indices from raw preview (we saw indices in the error message)
            # Pattern: 指数名称 数值 (百分比)
            index_pattern = r'([^\s]+(?:指数|成指|加权))[:\s]+(\d+\.?\d*)[\s(]+([+-]?\d+\.?\d*%)'
            matches = re.findall(index_pattern, raw_preview)
            for match in matches:
                if len(match) >= 2:
                    extracted["indices"].append({
                        "name": match[0],
                        "value": match[1],
                        "change_percent": match[2] if len(match) > 2 else ""
                    })
            
            # Extract market overview from text
            if "市场" in text or "行情" in text:
                # Try to find a summary sentence
                sentences = text.split('。')
                for sentence in sentences[:3]:  # First 3 sentences
                    if len(sentence) > 20 and ("市场" in sentence or "指数" in sentence or "行情" in sentence):
                        extracted["market_overview"] = sentence.strip() + "。"
                        break
            
            # Only return if we extracted something useful
            if extracted["indices"] or extracted["market_overview"]:
                return extracted
            
            return None
        except Exception as e:
            print(f"[Crawler] Error in _extract_data_from_text: {str(e)}")
            return None

    def _follow_link(self, base_url: str, link_href: str) -> Optional[BeautifulSoup]:
        """Follow a link and return its soup, handling relative URLs and various link formats"""
        try:
            from urllib.parse import urljoin, urlparse
            
            # Skip JavaScript links and anchors
            if not link_href or link_href.startswith('javascript:') or link_href.startswith('#'):
                return None
            
            # Build absolute URL
            absolute_url = urljoin(base_url, link_href)
            
            # Only follow links from the same domain (more lenient - allow subdomains)
            base_parsed = urlparse(base_url)
            link_parsed = urlparse(absolute_url)
            
            base_domain = base_parsed.netloc.replace('www.', '')
            link_domain = link_parsed.netloc.replace('www.', '')
            
            # Allow same domain and subdomains
            if base_domain not in link_domain and link_domain not in base_domain:
                return None
            
            # Skip common non-content URLs
            skip_patterns = ['mailto:', 'tel:', '.pdf', '.zip', '.exe', '.jpg', '.png', '.gif', '.css', '.js']
            if any(pattern in absolute_url.lower() for pattern in skip_patterns):
                return None
            
            # Follow the link with timeout
            response = self.session.get(absolute_url, timeout=15, allow_redirects=True)
            response.raise_for_status()
            
            # Check if it's HTML content
            content_type = response.headers.get('content-type', '').lower()
            if 'html' not in content_type and 'text' not in content_type:
                return None
            
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            # Silently skip errors to avoid spam
            return None
    
    def _detect_pagination(self, soup: BeautifulSoup) -> List[str]:
        """Detect pagination links in the page"""
        pagination_links = []
        
        try:
            # Look for common pagination patterns
            # Pattern 1: Links with "page", "p", "next", numbers
            pagination_keywords = ['page', 'p=', 'pagenum', 'next', '上一页', '下一页', '第', '页']
            
            for link in soup.find_all('a', href=True):
                href = link.get('href', '').lower()
                text = link.get_text(strip=True).lower()
                
                # Check if it looks like a pagination link
                if any(keyword in href or keyword in text for keyword in pagination_keywords):
                    # Check if it contains numbers (page numbers)
                    if any(char.isdigit() for char in href) or any(char.isdigit() for char in text):
                        pagination_links.append(link.get('href'))
            
            # Pattern 2: Look for pagination containers
            pagination_containers = soup.find_all(['div', 'ul', 'nav'], class_=re.compile(r'page|pagination', re.I))
            for container in pagination_containers:
                for link in container.find_all('a', href=True):
                    href = link.get('href')
                    if href and href not in pagination_links:
                        pagination_links.append(href)
        
        except Exception as e:
            print(f"[Crawler] Error detecting pagination: {e}")
        
        return pagination_links[:10]  # Limit to 10 pagination links
    
    def _extract_table_with_pagination(self, soup: BeautifulSoup, base_url: str, table: BeautifulSoup) -> List[List[str]]:
        """Extract table data and follow pagination if present"""
        all_rows = []
        
        # Extract current page table data
        for tr in table.find_all('tr'):
            cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
            if cells:
                all_rows.append(cells)
        
        # Check for pagination near this table
        # Look for pagination elements within 2 levels of the table
        parent = table.parent
        if parent:
            pagination_links = self._detect_pagination(parent)
            
            # Follow up to 3 pagination pages
            for pag_link in pagination_links[:3]:
                pag_soup = self._follow_link(base_url, pag_link)
                if pag_soup:
                    # Find the same table structure in the paginated page
                    pag_tables = pag_soup.find_all('table')
                    if pag_tables:
                        for pag_tr in pag_tables[0].find_all('tr'):
                            cells = [td.get_text(strip=True) for td in pag_tr.find_all(['td', 'th'])]
                            if cells and cells not in all_rows:  # Avoid duplicates
                                all_rows.append(cells)
        
        return all_rows
    
    def deep_extract_data(self, soup: BeautifulSoup, site_name: str, base_url: str = None) -> Dict:
        """Deep extract structured data from HTML - Enhanced for deeper extraction with link following"""
        extracted_data = {
            "tables": [],
            "lists": [],
            "links": [],
            "text_blocks": [],
            "numbers": [],
            "headings": [],
            "stock_codes": [],
            "prices": [],
            "percentages": [],
            "followed_links_data": []
        }
        
        try:
            # Extract tables (often contain stock data) - WITH PAGINATION SUPPORT
            tables = soup.find_all('table')
            for table in tables[:20]:  # Increased to 20 tables
                if base_url:
                    # Try to get paginated data
                    rows = self._extract_table_with_pagination(soup, base_url, table)
                else:
                    # Fallback to simple extraction
                    rows = []
                    for tr in table.find_all('tr')[:100]:  # Increased to 100 rows
                        cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                        if cells:
                            rows.append(cells)
                
                if rows:
                    extracted_data["tables"].append(rows)
            
            # Extract lists (often contain stock symbols or news) - INCREASED LIMITS
            lists = soup.find_all(['ul', 'ol'])
            for lst in lists[:20]:  # Increased from 10 to 20 lists
                items = [li.get_text(strip=True) for li in lst.find_all('li')[:30]]  # Increased from 20 to 30
                if items:
                    extracted_data["lists"].append(items)
            
            # Extract links (may lead to more data) - FOLLOW USEFUL LINKS AND BUTTONS
            links = soup.find_all('a', href=True)
            useful_link_keywords = ['股票', '指数', '行情', '数据', '列表', '排行', 'stock', 'index', 'quote', 'market', '实时', '最新', '热门', '涨跌']
            
            # Also find buttons that might have links or onclick handlers
            buttons = soup.find_all(['button', 'div', 'span'], {
                'onclick': True,
                'data-url': True,
                'data-href': True,
                'class': re.compile(r'btn|button|link|more|next|page', re.I)
            })
            
            # Extract URLs from buttons (skip login/register buttons)
            button_links = []
            # Keywords to skip (login/register in English and Chinese)
            skip_keywords = [
                'login', 'register', 'signin', 'signup', 'sign-in', 'sign-up',
                '登录', '注册', '登陆', '登入', '登錄', '註冊', '註册',
                'account', 'user', '会员', '會員', '用户', '用戶'
            ]
            
            for button in buttons[:50]:  # Limit to 50 buttons
                # Get button text and attributes
                button_text = button.get_text(strip=True).lower()
                button_class = button.get('class', [])
                button_id = button.get('id', '').lower()
                button_href = button.get('href', '').lower()
                
                # Skip if it's a login/register button
                should_skip = False
                
                # Check button text
                if any(keyword in button_text for keyword in skip_keywords):
                    should_skip = True
                
                # Check button class
                if isinstance(button_class, list):
                    class_str = ' '.join(button_class).lower()
                else:
                    class_str = str(button_class).lower()
                if any(keyword in class_str for keyword in skip_keywords):
                    should_skip = True
                
                # Check button ID
                if any(keyword in button_id for keyword in skip_keywords):
                    should_skip = True
                
                # Check href if present
                if button_href and any(keyword in button_href for keyword in skip_keywords):
                    should_skip = True
                
                if should_skip:
                    continue  # Skip this button
                
                # Check onclick for URLs
                onclick = button.get('onclick', '')
                if onclick:
                    # Skip if onclick contains login/register
                    if any(keyword in onclick.lower() for keyword in skip_keywords):
                        continue
                    
                    # Extract URL from onclick (common patterns)
                    url_match = re.search(r'(?:href|url|link)\s*[=:]\s*["\']([^"\']+)["\']', onclick)
                    if url_match:
                        extracted_url = url_match.group(1).lower()
                        # Skip if extracted URL contains login/register
                        if not any(keyword in extracted_url for keyword in skip_keywords):
                            button_links.append(url_match.group(1))
                
                # Check data attributes
                data_url = button.get('data-url') or button.get('data-href')
                if data_url:
                    # Skip if data URL contains login/register
                    if not any(keyword in data_url.lower() for keyword in skip_keywords):
                        button_links.append(data_url)
            
            # Combine regular links and button links
            all_links_to_follow = []
            
            # Keywords to skip for links (login/register)
            skip_link_keywords = [
                'login', 'register', 'signin', 'signup', 'sign-in', 'sign-up',
                '登录', '注册', '登陆', '登入', '登錄', '註冊', '註册',
                'account', 'user', '会员', '會員', '用户', '用戶'
            ]
            
            for link in links[:300]:  # Increased to 300 links
                text = link.get_text(strip=True)
                href = link.get('href', '')
                
                # Skip login/register links
                if href:
                    href_lower = href.lower()
                    text_lower = text.lower() if text else ''
                    
                    # Check if link is login/register related
                    if any(keyword in href_lower or keyword in text_lower for keyword in skip_link_keywords):
                        continue  # Skip this link
                
                if text and len(text) < 200:
                    extracted_data["links"].append({"text": text, "href": href})
                    if href:
                        all_links_to_follow.append((href, text))
            
            # Add button links
            for button_url in button_links:
                all_links_to_follow.append((button_url, "Button Link"))
            
            # Follow useful links to get more data (DEEPER CRAWLING)
            followed_count = 0
            max_follow_links = 30  # Follow up to 30 links per page for deeper crawling
            
            for href, text in all_links_to_follow:
                if followed_count >= max_follow_links:
                    break
                
                # More lenient check - follow if it might contain data
                should_follow = False
                if base_url:
                    # Check keywords
                    if any(keyword in text.lower() or keyword in href.lower() for keyword in useful_link_keywords):
                        should_follow = True
                    # Also follow if URL contains data-related patterns
                    elif any(pattern in href.lower() for pattern in ['/data/', '/list/', '/rank/', '/table/', '/detail/', '/info/']):
                        should_follow = True
                    # Follow if text suggests it's a data link
                    elif any(word in text.lower() for word in ['查看', '更多', '详情', '列表', '数据', '排行']):
                        should_follow = True
                
                if should_follow:
                    link_soup = self._follow_link(base_url, href)
                    if link_soup:
                        followed_count += 1
                        # Extract data from followed link
                        link_data = {
                            "url": href,
                            "title": text,
                            "tables": [],
                            "text": link_soup.get_text(strip=True)[:3000]  # Increased to 3000 chars
                        }
                        
                        # Extract tables from linked page (MORE COMPREHENSIVE)
                        link_tables = link_soup.find_all('table')[:15]  # Increased to 15 tables
                        for link_table in link_tables:
                            link_rows = []
                            for tr in link_table.find_all('tr')[:100]:  # Increased to 100 rows
                                cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                                if cells:
                                    link_rows.append(cells)
                            if link_rows:
                                link_data["tables"].append(link_rows)
                        
                        # Also extract lists from linked page
                        link_lists = link_soup.find_all(['ul', 'ol'])[:15]
                        link_list_items = []
                        for lst in link_lists:
                            items = [li.get_text(strip=True) for li in lst.find_all('li')[:30]]
                            if items:
                                link_list_items.extend(items)
                        if link_list_items:
                            link_data["lists"] = link_list_items
                        
                        # Extract stock codes from linked page
                        link_text = link_soup.get_text()
                        stock_code_pattern = r'\b([0-3][0-9]{5}|6[0-9]{5})\b'
                        stock_codes = re.findall(stock_code_pattern, link_text)
                        if stock_codes:
                            link_data["stock_codes"] = list(set(stock_codes[:50]))
                        
                        if link_data["tables"] or link_data["text"] or link_data.get("lists") or link_data.get("stock_codes"):
                            extracted_data["followed_links_data"].append(link_data)
            
            # Extract text blocks with numbers (likely stock prices) - INCREASED LIMITS
            text_elements = soup.find_all(['div', 'span', 'p', 'td', 'th'])
            for elem in text_elements[:300]:  # Increased from 100 to 300 elements
                text = elem.get_text(strip=True)
                # Look for patterns that might be stock data
                if text and (any(char.isdigit() for char in text) or '%' in text or '涨' in text or '跌' in text):
                    if 5 < len(text) < 200:
                        extracted_data["text_blocks"].append(text)
            
            # Extract headings (often contain market summaries) - INCREASED LIMITS
            headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            for heading in headings[:30]:  # Increased from 20 to 30
                text = heading.get_text(strip=True)
                if text:
                    extracted_data["headings"].append(text)
            
            # Extract stock codes (6-digit codes for Chinese stocks)
            all_text = soup.get_text()
            # Pattern for Chinese stock codes: 6 digits (000001-999999)
            stock_code_pattern = r'\b([0-3][0-9]{5}|6[0-9]{5})\b'
            stock_codes = re.findall(stock_code_pattern, all_text)
            extracted_data["stock_codes"] = list(set(stock_codes[:100]))  # Unique codes, limit to 100
            
            # Extract prices - Enhanced pattern matching
            price_pattern = r'\d+\.\d{2,4}'
            prices = re.findall(price_pattern, all_text)
            extracted_data["prices"] = list(set(prices[:100]))  # Increased from 50 to 100
            
            # Extract percentage changes
            percent_pattern = r'[+-]?\d+\.?\d*%'
            percentages = re.findall(percent_pattern, all_text)
            extracted_data["percentages"] = list(set(percentages[:100]))
            
            # Extract numbers that might be prices
            extracted_data["numbers"] = list(set(prices[:100]))  # Increased limit
            
        except Exception as e:
            print(f"[Crawler] Error in deep extraction for {site_name}: {str(e)}")
        
        return extracted_data
    
    def process_with_ai(self, raw_data: str, site_name: str, structured_data: Optional[Dict] = None) -> Dict:
        """Process raw data with Qwen AI API to organize it"""
        # Check if OpenAI client is available
        if not self.openai_client:
            return {
                "site": site_name,
                "timestamp": datetime.now().isoformat(),
                "raw_data_preview": raw_data[:500] if raw_data else "",
                "ai_processed_data": None,
                "error": "OpenAI client not initialized"
            }
        
        try:
            # Validate input - allow structured_data even if raw_data is empty
            if (not raw_data or len(raw_data.strip()) == 0) and (not structured_data or not any(structured_data.values())):
                return {
                    "site": site_name,
                    "timestamp": datetime.now().isoformat(),
                    "raw_data_preview": "",
                    "ai_processed_data": None,
                    "error": "No data provided (neither raw data nor structured data)"
                }
            
            # Prepare data for AI processing
            data_summary = ""
            
            # If we have structured data from deep extraction, use it
            if structured_data:
                # Format structured data for AI
                tables_str = ""
                if structured_data.get("tables"):
                    for i, table in enumerate(structured_data["tables"][:3]):  # First 3 tables
                        tables_str += f"\nTable {i+1}:\n"
                        for row in table[:10]:  # First 10 rows
                            tables_str += " | ".join(str(cell) for cell in row[:8]) + "\n"
                
                lists_str = ""
                if structured_data.get("lists"):
                    for i, lst in enumerate(structured_data["lists"][:10]):  # Increased from 5 to 10 lists
                        lists_str += f"\nList {i+1}: " + ", ".join(lst[:20]) + "\n"  # Increased from 15 to 20 items
                
                headings_str = ""
                if structured_data.get("headings"):
                    headings_str = "\nHeadings: " + " | ".join(structured_data["headings"][:20]) + "\n"  # Increased from 10 to 20
                
                text_blocks_str = ""
                if structured_data.get("text_blocks"):
                    text_blocks_str = "\nKey Text Blocks: " + " | ".join(structured_data["text_blocks"][:40]) + "\n"  # Increased from 20 to 40
                
                stock_codes_str = ""
                if structured_data.get("stock_codes"):
                    stock_codes_str = f"\nStock Codes Found: {', '.join(structured_data['stock_codes'][:50])}\n"
                
                prices_str = ""
                if structured_data.get("prices"):
                    prices_str = f"\nPrices Found: {', '.join(structured_data['prices'][:30])}\n"
                
                followed_links_str = ""
                if structured_data.get("followed_links_data"):
                    followed_links_str = f"\nFollowed Links Data ({len(structured_data['followed_links_data'])} links):\n"
                    for i, link_data in enumerate(structured_data["followed_links_data"][:5]):  # First 5 links
                        followed_links_str += f"Link {i+1}: {link_data.get('title', 'N/A')}\n"
                        if link_data.get("tables"):
                            followed_links_str += f"  Tables: {len(link_data['tables'])}\n"
                        if link_data.get("text"):
                            followed_links_str += f"  Text preview: {link_data['text'][:200]}...\n"
                
                data_summary = f"""Structured Data from {site_name}:
{tables_str}
{lists_str}
{headings_str}
{text_blocks_str}
{stock_codes_str}
{prices_str}
{followed_links_str}
"""
            
            # Also include raw text (truncated)
            truncated_data = raw_data[:1500] if raw_data else ""
            if truncated_data:
                data_summary += f"\nRaw Text Preview:\n{truncated_data}"
            
            prompt = f"""Please analyze and organize the following stock market data from {site_name}. 
Extract all stock information, market indices, prices, changes, and news.

{data_summary}

IMPORTANT: You MUST return ONLY valid JSON. Do not include any explanatory text before or after the JSON. 
The response must be a single, valid JSON object that can be parsed directly.

Extract and structure the data as JSON with the following format (return ONLY the JSON, no other text):
{{
    "stocks": [
        {{
            "symbol": "stock symbol/code",
            "name": "company name",
            "price": "current price",
            "change": "price change",
            "change_percent": "percentage change",
            "volume": "trading volume"
        }}
    ],
    "indices": [
        {{
            "name": "index name (e.g., 上证指数, 深证成指)",
            "value": "index value",
            "change": "change amount",
            "change_percent": "percentage change"
        }}
    ],
    "market_overview": "brief market overview and summary",
    "top_gainers": ["top gaining stocks with their gains"],
    "top_losers": ["top losing stocks with their losses"],
    "news": ["important news headlines related to stocks"],
    "trading_summary": "overall trading summary if available"
}}

Focus on extracting actual stock codes (like 000001, 600000), prices, and percentage changes from the data.
If you find stock tables, extract each row as a stock entry.
Remember: Return ONLY valid JSON, no markdown code blocks, no explanations."""
            
            # Retry logic for handling timeouts
            max_retries = 2
            retry_delay = 5  # seconds
            ai_processed = None
            
            for attempt in range(max_retries + 1):
                try:
                    print(f"[Crawler] Calling Qwen API for {site_name} with {len(truncated_data)} chars of data... (attempt {attempt + 1}/{max_retries + 1})")
                    start_time = time.time()
                    
                    # Use OpenAI SDK to call Qwen
                    response = self.openai_client.chat.completions.create(
                        model="qwen-max",
                        messages=[
                            {"role": "user", "content": prompt}
                        ],
                        temperature=0.3,  # Lower temperature for faster, more deterministic responses
                        max_tokens=800,  # Reduced from 1024 for faster processing
                        timeout=60.0  # 60 seconds timeout
                    )
                    
                    elapsed_time = time.time() - start_time
                    print(f"[Crawler] Qwen API response received, took {elapsed_time:.2f}s")
                    
                    # Extract the text from the response
                    ai_processed = response.choices[0].message.content
                    
                    if not ai_processed:
                        return {
                            "site": site_name,
                            "timestamp": datetime.now().isoformat(),
                            "raw_data_preview": raw_data[:500],
                            "ai_processed_data": None,
                            "error": "Empty response from AI service"
                        }
                    
                    break  # Success, exit retry loop
                    
                except Exception as e:
                    error_str = str(e)
                    # Check if it's a timeout error
                    if "timeout" in error_str.lower() or "timed out" in error_str.lower():
                        if attempt < max_retries:
                            print(f"[Crawler] Timeout on attempt {attempt + 1}, retrying in {retry_delay}s...")
                            time.sleep(retry_delay)
                            continue
                        else:
                            # Final attempt failed
                            print(f"[Crawler] All {max_retries + 1} attempts timed out for {site_name}")
                            return {
                                "site": site_name,
                                "timestamp": datetime.now().isoformat(),
                                "raw_data_preview": raw_data[:500],
                                "ai_processed_data": None,
                                "error": f"AI processing request timed out (exceeded 60 seconds after 3 attempts): {error_str}"
                            }
                    else:
                        # Other error, don't retry
                        print(f"[Crawler] Error calling Qwen API for {site_name}: {error_str}")
                        return {
                            "site": site_name,
                            "timestamp": datetime.now().isoformat(),
                            "raw_data_preview": raw_data[:500],
                            "ai_processed_data": None,
                            "error": f"Request to AI service failed: {error_str}"
                        }
            
            # Process the response if we got one
            if not ai_processed:
                return {
                    "site": site_name,
                    "timestamp": datetime.now().isoformat(),
                    "raw_data_preview": raw_data[:500],
                    "ai_processed_data": None,
                    "error": "Failed to get response from Qwen API after all retries"
                }
            
            # Check if response looks like JSON before attempting to parse
            cleaned_response = ai_processed.strip()
            
            # Remove markdown code blocks if present
            if cleaned_response.startswith('```'):
                lines = cleaned_response.split('\n')
                json_lines = []
                in_code_block = False
                for line in lines:
                    if line.strip().startswith('```'):
                        in_code_block = not in_code_block
                        continue
                    if not in_code_block:
                        json_lines.append(line)
                cleaned_response = '\n'.join(json_lines).strip()
            
            # Check if response contains JSON (looks for { or [ anywhere)
            has_json_structure = '{' in cleaned_response or '[' in cleaned_response
            
            # Check if response contains JSON structure
            has_json_structure = '{' in cleaned_response or '[' in cleaned_response
            
            # Try to parse the AI response as JSON
            try:
                # Find JSON part in the response
                start_idx = cleaned_response.find('{')
                if start_idx == -1:
                    start_idx = cleaned_response.find('[')
                
                if start_idx == -1:
                    # No JSON structure found at all
                    if not has_json_structure:
                        print(f"[Crawler] Response from {site_name} contains no JSON structure, returning as raw text")
                        return {
                            "site": site_name,
                            "timestamp": datetime.now().isoformat(),
                            "raw_data_preview": raw_data[:500],
                            "ai_processed_data": {
                                "raw_response": ai_processed,
                                "note": "AI response contains no JSON structure, showing raw text"
                            },
                            "warning": "Response contains no JSON structure, displayed as raw text"
                        }
                    else:
                        # Has brackets but no valid structure
                        print(f"[Crawler] No valid JSON structure found in response from {site_name}")
                        return {
                            "site": site_name,
                            "timestamp": datetime.now().isoformat(),
                            "raw_data_preview": raw_data[:500],
                            "ai_processed_data": {
                                "raw_response": ai_processed,
                                "note": "No valid JSON structure found in response"
                            },
                            "warning": "No valid JSON structure found, showing raw response"
                        }
                
                # Find matching closing bracket
                end_idx = cleaned_response.rfind('}') + 1
                if end_idx == 0:  # rfind returns -1 if not found, so +1 = 0
                    end_idx = cleaned_response.rfind(']') + 1
                
                if end_idx <= start_idx:
                    # No valid JSON structure found
                    print(f"[Crawler] No valid JSON structure found in response from {site_name}")
                    return {
                        "site": site_name,
                        "timestamp": datetime.now().isoformat(),
                        "raw_data_preview": raw_data[:500],
                        "ai_processed_data": {
                            "raw_response": ai_processed,
                            "note": "No valid JSON structure found in response"
                        },
                        "warning": "No valid JSON structure found, showing raw response"
                    }
                
                json_str = cleaned_response[start_idx:end_idx]
                
                # Try to fix common JSON issues first
                # Remove trailing commas before closing brackets/braces
                json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
                
                try:
                    structured_data = json.loads(json_str)
                    
                    return {
                        "site": site_name,
                        "timestamp": datetime.now().isoformat(),
                        "raw_data_preview": raw_data[:500],
                        "ai_processed_data": structured_data
                    }
                except json.JSONDecodeError as je:
                    # JSON parsing failed - try to repair it
                    print(f"[Crawler] JSON parse error for {site_name}: {str(je)}")
                    print(f"[Crawler] Attempting to repair malformed JSON...")
                    
                    # Try to repair the JSON
                    repaired_data = repair_json(json_str)
                    
                    if repaired_data:
                        print(f"[Crawler] Successfully repaired JSON for {site_name}")
                        return {
                            "site": site_name,
                            "timestamp": datetime.now().isoformat(),
                            "raw_data_preview": raw_data[:500],
                            "ai_processed_data": repaired_data,
                            "warning": f"JSON was malformed but repaired. Original error: {str(je)}"
                        }
                    
                    # If repair failed, try to extract partial data
                    print(f"[Crawler] JSON repair failed, attempting partial extraction...")
                    partial_data = extract_partial_json(json_str)
                    
                    if partial_data:
                        print(f"[Crawler] Extracted partial data from malformed JSON for {site_name}")
                        return {
                            "site": site_name,
                            "timestamp": datetime.now().isoformat(),
                            "raw_data_preview": raw_data[:500],
                            "ai_processed_data": partial_data,
                            "warning": f"Extracted partial data from malformed JSON. Original error: {str(je)}"
                        }
                    
                    # If all else fails, return raw response
                    print(f"[Crawler] Could not repair or extract data, showing raw response")
                    return {
                        "site": site_name,
                        "timestamp": datetime.now().isoformat(),
                        "raw_data_preview": raw_data[:500],
                        "ai_processed_data": {
                            "raw_response": ai_processed,
                            "parse_error": str(je),
                            "note": "JSON parsing failed and could not be repaired, showing raw AI response"
                        },
                        "warning": f"JSON decode error: {str(je)}. Could not repair, showing raw response."
                    }
            except Exception as parse_error:
                print(f"[Crawler] Error processing response for {site_name}: {str(parse_error)}")
                return {
                    "site": site_name,
                    "timestamp": datetime.now().isoformat(),
                    "raw_data_preview": raw_data[:500],
                    "ai_processed_data": {
                        "raw_response": ai_processed,
                        "error": str(parse_error),
                        "note": "Error processing response, showing raw text"
                    },
                    "warning": f"Error processing response: {str(parse_error)}"
                }
                
        except Exception as e:
            # Catch any other unexpected errors
            print(f"[Crawler] Unexpected error in AI processing for {site_name}: {str(e)}")
            import traceback
            traceback.print_exc()
            return {
                "site": site_name,
                "timestamp": datetime.now().isoformat(),
                "raw_data_preview": raw_data[:500] if raw_data else "",
                "ai_processed_data": None,
                "error": f"Unexpected error in AI processing: {str(e)}"
            }
        except Exception as e:
            # Catch any other unexpected errors
            return {
                "site": site_name,
                "timestamp": datetime.now().isoformat(),
                "raw_data_preview": raw_data[:500] if raw_data else "",
                "ai_processed_data": None,
                "error": f"Unexpected error in AI processing: {str(e)}"
            }

    def crawl_akshare(self, bypass_rate_limit: bool = False) -> Dict:
        """Crawl comprehensive data using AKShare library"""
        if not self.akshare_fetcher:
            return {
                "site": "akshare",
                "timestamp": datetime.now().isoformat(),
                "error": "AKShare fetcher not initialized"
            }
        
        try:
            print("[Crawler] Fetching data from AKShare...")
            data = self.akshare_fetcher.get_comprehensive_data(bypass_rate_limit)
            return data
        except Exception as e:
            print(f"[Crawler] Error crawling with AKShare: {e}")
            import traceback
            traceback.print_exc()
            return {
                "site": "akshare",
                "timestamp": datetime.now().isoformat(),
                "error": f"Error fetching AKShare data: {str(e)}"
            }
    
    def crawl_all_sites(self, bypass_rate_limit: bool = False) -> Dict:
        """Crawl data from AKShare"""
        results = {}
        
        # Only use AKShare for comprehensive data
        if self.akshare_fetcher:
            results['akshare'] = self.crawl_akshare(bypass_rate_limit)
        
        return results

    def save_data(self, data: Dict, category: str = "general") -> str:
        """Save crawled data to a timestamped file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        category_dir = self.data_dir / category
        category_dir.mkdir(exist_ok=True)
        
        filename = f"stock_data_{category}_{timestamp}.json"
        filepath = category_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return str(filepath)