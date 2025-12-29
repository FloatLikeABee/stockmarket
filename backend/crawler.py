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
        # Initialize OpenAI client for Qwen
        self.openai_client = OpenAI(
            api_key=self.qwen_api_key,
            base_url=self.qwen_api_url
        )
        
        # Sites to crawl
        self.sites = {
            'tonghuashun': 'http://stock.10jqka.com.cn/',
            'tongdaxin': 'https://www.tdx.com.cn/',
            'dongfangcaifu': 'https://quote.eastmoney.com/',
            'xueqiu': 'https://xueqiu.com/',
            'caijinglian': 'https://www.cls.cn/'
        }
        
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
                "news": [],
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

    def deep_extract_data(self, soup: BeautifulSoup, site_name: str) -> Dict:
        """Deep extract structured data from HTML"""
        extracted_data = {
            "tables": [],
            "lists": [],
            "links": [],
            "text_blocks": [],
            "numbers": [],
            "headings": []
        }
        
        try:
            # Extract tables (often contain stock data)
            tables = soup.find_all('table')
            for table in tables[:5]:  # Limit to first 5 tables
                rows = []
                for tr in table.find_all('tr')[:20]:  # Limit rows
                    cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
                    if cells:
                        rows.append(cells)
                if rows:
                    extracted_data["tables"].append(rows)
            
            # Extract lists (often contain stock symbols or news)
            lists = soup.find_all(['ul', 'ol'])
            for lst in lists[:10]:  # Limit to first 10 lists
                items = [li.get_text(strip=True) for li in lst.find_all('li')[:20]]
                if items:
                    extracted_data["lists"].append(items)
            
            # Extract links (may lead to more data)
            links = soup.find_all('a', href=True)
            for link in links[:50]:  # Limit to first 50 links
                text = link.get_text(strip=True)
                href = link.get('href', '')
                if text and len(text) < 200:  # Filter out very long text
                    extracted_data["links"].append({"text": text, "href": href})
            
            # Extract text blocks with numbers (likely stock prices)
            text_elements = soup.find_all(['div', 'span', 'p'])
            for elem in text_elements[:100]:  # Limit to first 100 elements
                text = elem.get_text(strip=True)
                # Look for patterns that might be stock data (numbers, percentages, stock codes)
                if text and (any(char.isdigit() for char in text) or '%' in text or '涨' in text or '跌' in text):
                    if 5 < len(text) < 200:  # Reasonable length
                        extracted_data["text_blocks"].append(text)
            
            # Extract headings (often contain market summaries)
            headings = soup.find_all(['h1', 'h2', 'h3', 'h4'])
            for heading in headings[:20]:
                text = heading.get_text(strip=True)
                if text:
                    extracted_data["headings"].append(text)
            
            # Extract numbers that might be prices
            import re
            all_text = soup.get_text()
            # Find patterns like prices: numbers with decimals
            price_pattern = r'\d+\.\d{2,4}'
            prices = re.findall(price_pattern, all_text)
            extracted_data["numbers"] = list(set(prices[:50]))  # Unique prices, limit to 50
            
        except Exception as e:
            print(f"[Crawler] Error in deep extraction for {site_name}: {str(e)}")
        
        return extracted_data
    
    def process_with_ai(self, raw_data: str, site_name: str, structured_data: Optional[Dict] = None) -> Dict:
        """Process raw data with Qwen AI API to organize it"""
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
                    for i, lst in enumerate(structured_data["lists"][:5]):  # First 5 lists
                        lists_str += f"\nList {i+1}: " + ", ".join(lst[:15]) + "\n"
                
                headings_str = ""
                if structured_data.get("headings"):
                    headings_str = "\nHeadings: " + " | ".join(structured_data["headings"][:10]) + "\n"
                
                text_blocks_str = ""
                if structured_data.get("text_blocks"):
                    text_blocks_str = "\nKey Text Blocks: " + " | ".join(structured_data["text_blocks"][:20]) + "\n"
                
                data_summary = f"""Structured Data from {site_name}:
{tables_str}
{lists_str}
{headings_str}
{text_blocks_str}
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
            
            # Try to parse the AI response as JSON
            try:
                # Clean the response - remove markdown code blocks if present
                cleaned_response = ai_processed.strip()
                if cleaned_response.startswith('```'):
                    # Remove markdown code blocks
                    lines = cleaned_response.split('\n')
                    # Find the JSON part (skip first line with ```json or ```)
                    json_lines = []
                    in_code_block = False
                    for line in lines:
                        if line.strip().startswith('```'):
                            in_code_block = not in_code_block
                            continue
                        if not in_code_block:
                            json_lines.append(line)
                    cleaned_response = '\n'.join(json_lines).strip()
                
                # Find JSON part in the response
                start_idx = cleaned_response.find('{')
                end_idx = cleaned_response.rfind('}') + 1
                
                if start_idx != -1 and end_idx > start_idx:
                    json_str = cleaned_response[start_idx:end_idx]
                    
                    # Try to fix common JSON issues
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
                        # Try to extract partial data even if JSON is malformed
                        print(f"[Crawler] JSON parse error for {site_name}: {str(je)}")
                        print(f"[Crawler] Attempting to extract partial data from malformed JSON...")
                        
                        # Try to extract indices from the raw text as fallback
                        partial_data = self._extract_data_from_text(ai_processed, raw_data[:500])
                        
                        if partial_data:
                            return {
                                "site": site_name,
                                "timestamp": datetime.now().isoformat(),
                                "raw_data_preview": raw_data[:500],
                                "ai_processed_data": partial_data,
                                "warning": f"Partial data extracted. JSON parse error: {str(je)}"
                            }
                        
                        # If all else fails, return text with warning
                        return {
                            "site": site_name,
                            "timestamp": datetime.now().isoformat(),
                            "raw_data_preview": raw_data[:500],
                            "ai_processed_data": ai_processed,
                            "warning": f"Response parsed as text due to JSON decode error: {str(je)}"
                        }
            except Exception as parse_error:
                print(f"[Crawler] Error parsing JSON for {site_name}: {str(parse_error)}")
                return {
                    "site": site_name,
                    "timestamp": datetime.now().isoformat(),
                    "raw_data_preview": raw_data[:500],
                    "ai_processed_data": ai_processed,
                    "warning": f"Error parsing response: {str(parse_error)}"
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

    def crawl_tonghuashun(self, bypass_rate_limit: bool = False) -> Dict:
        """Deep crawl data from 同花顺"""
        if not self.can_crawl('tonghuashun', bypass_rate_limit):
            return {
                "site": 'tonghuashun',
                "timestamp": datetime.now().isoformat(),
                "error": "Rate limit exceeded for 同花顺"
            }
        
        try:
            response = self.session.get(self.sites['tonghuashun'], timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Deep extract structured data
            print(f"[Crawler] Performing deep extraction from tonghuashun...")
            structured_data = self.deep_extract_data(soup, 'tonghuashun')
            print(f"[Crawler] Extracted {len(structured_data.get('tables', []))} tables, {len(structured_data.get('lists', []))} lists")
            
            # Also get full text for fallback
            content = soup.get_text(strip=True) if soup.get_text() else ""
            
            if not content and not structured_data.get('tables'):
                return {
                    "site": 'tonghuashun',
                    "timestamp": datetime.now().isoformat(),
                    "error": "No content extracted from page",
                    "raw_data_preview": ""
                }
            
            print(f"[Crawler] Successfully fetched {len(content)} characters from tonghuashun")
            processed_data = self.process_with_ai(content, 'tonghuashun', structured_data)
            self.update_crawl_time('tonghuashun')
            
            # Log if AI processing failed
            if processed_data.get('error'):
                print(f"[Crawler] AI processing failed for tonghuashun: {processed_data.get('error')}")
            elif not processed_data.get('ai_processed_data'):
                print(f"[Crawler] Warning: No AI processed data for tonghuashun, but raw_data_preview available")
            
            return processed_data
            
        except requests.exceptions.HTTPError as he:
            error_msg = f"HTTP error occurred while crawling 同花顺: {str(he)}"
            print(f"[Crawler] {error_msg}")
            return {
                "site": 'tonghuashun',
                "timestamp": datetime.now().isoformat(),
                "error": error_msg,
                "raw_data_preview": ""
            }
        except requests.exceptions.ConnectionError as ce:
            error_msg = f"Connection error occurred while crawling 同花顺: {str(ce)}"
            print(f"[Crawler] {error_msg}")
            return {
                "site": 'tonghuashun',
                "timestamp": datetime.now().isoformat(),
                "error": error_msg,
                "raw_data_preview": ""
            }
        except requests.exceptions.Timeout as te:
            error_msg = f"Timeout occurred while crawling 同花顺: {str(te)}"
            print(f"[Crawler] {error_msg}")
            return {
                "site": 'tonghuashun',
                "timestamp": datetime.now().isoformat(),
                "error": error_msg,
                "raw_data_preview": ""
            }
        except Exception as e:
            error_msg = f"Unexpected error occurred while crawling 同花顺: {str(e)}"
            print(f"[Crawler] {error_msg}")
            import traceback
            traceback.print_exc()
            return {
                "site": 'tonghuashun',
                "timestamp": datetime.now().isoformat(),
                "error": error_msg,
                "raw_data_preview": ""
            }

    def crawl_dongfangcaifu(self, bypass_rate_limit: bool = False) -> Dict:
        """Deep crawl data from 东方财富"""
        if not self.can_crawl('dongfangcaifu', bypass_rate_limit):
            return {
                "site": 'dongfangcaifu',
                "timestamp": datetime.now().isoformat(),
                "error": "Rate limit exceeded for 东方财富"
            }
        
        try:
            response = self.session.get(self.sites['dongfangcaifu'], timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Deep extract structured data
            print(f"[Crawler] Performing deep extraction from dongfangcaifu...")
            structured_data = self.deep_extract_data(soup, 'dongfangcaifu')
            print(f"[Crawler] Extracted {len(structured_data.get('tables', []))} tables, {len(structured_data.get('lists', []))} lists")
            
            content = soup.get_text(strip=True) if soup.get_text() else ""
            
            if not content and not structured_data.get('tables'):
                return {
                    "site": 'dongfangcaifu',
                    "timestamp": datetime.now().isoformat(),
                    "error": "No content extracted from page",
                    "raw_data_preview": ""
                }
                
            processed_data = self.process_with_ai(content, 'dongfangcaifu', structured_data)
            self.update_crawl_time('dongfangcaifu')
            return processed_data
            
        except requests.exceptions.HTTPError as he:
            return {
                "site": 'dongfangcaifu',
                "timestamp": datetime.now().isoformat(),
                "error": f"HTTP error occurred while crawling 东方财富: {str(he)}"
            }
        except requests.exceptions.ConnectionError as ce:
            return {
                "site": 'dongfangcaifu',
                "timestamp": datetime.now().isoformat(),
                "error": f"Connection error occurred while crawling 东方财富: {str(ce)}"
            }
        except requests.exceptions.Timeout as te:
            return {
                "site": 'dongfangcaifu',
                "timestamp": datetime.now().isoformat(),
                "error": f"Timeout occurred while crawling 东方财富: {str(te)}"
            }
        except Exception as e:
            return {
                "site": 'dongfangcaifu',
                "timestamp": datetime.now().isoformat(),
                "error": f"Unexpected error occurred while crawling 东方财富: {str(e)}"
            }

    def crawl_xueqiu(self, bypass_rate_limit: bool = False) -> Dict:
        """Deep crawl data from 雪球"""
        if not self.can_crawl('xueqiu', bypass_rate_limit):
            return {
                "site": 'xueqiu',
                "timestamp": datetime.now().isoformat(),
                "error": "Rate limit exceeded for 雪球"
            }
        
        try:
            response = self.session.get(self.sites['xueqiu'], timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Deep extract structured data
            print(f"[Crawler] Performing deep extraction from xueqiu...")
            structured_data = self.deep_extract_data(soup, 'xueqiu')
            print(f"[Crawler] Extracted {len(structured_data.get('tables', []))} tables, {len(structured_data.get('lists', []))} lists")
            
            content = soup.get_text(strip=True) if soup.get_text() else ""
            
            if not content and not structured_data.get('tables'):
                return {
                    "site": 'xueqiu',
                    "timestamp": datetime.now().isoformat(),
                    "error": "No content extracted from page",
                    "raw_data_preview": ""
                }
                
            processed_data = self.process_with_ai(content, 'xueqiu', structured_data)
            self.update_crawl_time('xueqiu')
            return processed_data
            
        except requests.exceptions.HTTPError as he:
            return {
                "site": 'xueqiu',
                "timestamp": datetime.now().isoformat(),
                "error": f"HTTP error occurred while crawling 雪球: {str(he)}"
            }
        except requests.exceptions.ConnectionError as ce:
            return {
                "site": 'xueqiu',
                "timestamp": datetime.now().isoformat(),
                "error": f"Connection error occurred while crawling 雪球: {str(ce)}"
            }
        except requests.exceptions.Timeout as te:
            return {
                "site": 'xueqiu',
                "timestamp": datetime.now().isoformat(),
                "error": f"Timeout occurred while crawling 雪球: {str(te)}"
            }
        except Exception as e:
            return {
                "site": 'xueqiu',
                "timestamp": datetime.now().isoformat(),
                "error": f"Unexpected error occurred while crawling 雪球: {str(e)}"
            }

    def crawl_tongdaxin(self, bypass_rate_limit: bool = False) -> Dict:
        """Deep crawl data from 通达信"""
        if not self.can_crawl('tongdaxin', bypass_rate_limit):
            return {
                "site": 'tongdaxin',
                "timestamp": datetime.now().isoformat(),
                "error": "Rate limit exceeded for 通达信"
            }
        
        try:
            response = self.session.get(self.sites['tongdaxin'], timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Deep extract structured data
            print(f"[Crawler] Performing deep extraction from tongdaxin...")
            structured_data = self.deep_extract_data(soup, 'tongdaxin')
            print(f"[Crawler] Extracted {len(structured_data.get('tables', []))} tables, {len(structured_data.get('lists', []))} lists")
            
            content = soup.get_text(strip=True) if soup.get_text() else ""
            
            if not content and not structured_data.get('tables'):
                return {
                    "site": 'tongdaxin',
                    "timestamp": datetime.now().isoformat(),
                    "error": "No content extracted from page",
                    "raw_data_preview": ""
                }
                
            processed_data = self.process_with_ai(content, 'tongdaxin', structured_data)
            self.update_crawl_time('tongdaxin')
            return processed_data
            
        except requests.exceptions.HTTPError as he:
            return {
                "site": 'tongdaxin',
                "timestamp": datetime.now().isoformat(),
                "error": f"HTTP error occurred while crawling 通达信: {str(he)}"
            }
        except requests.exceptions.ConnectionError as ce:
            return {
                "site": 'tongdaxin',
                "timestamp": datetime.now().isoformat(),
                "error": f"Connection error occurred while crawling 通达信: {str(ce)}"
            }
        except requests.exceptions.Timeout as te:
            return {
                "site": 'tongdaxin',
                "timestamp": datetime.now().isoformat(),
                "error": f"Timeout occurred while crawling 通达信: {str(te)}"
            }
        except Exception as e:
            return {
                "site": 'tongdaxin',
                "timestamp": datetime.now().isoformat(),
                "error": f"Unexpected error occurred while crawling 通达信: {str(e)}"
            }

    def crawl_caijinglian(self, bypass_rate_limit: bool = False) -> Dict:
        """Deep crawl data from 财联社"""
        if not self.can_crawl('caijinglian', bypass_rate_limit):
            return {
                "site": 'caijinglian',
                "timestamp": datetime.now().isoformat(),
                "error": "Rate limit exceeded for 财联社"
            }
        
        try:
            response = self.session.get(self.sites['caijinglian'], timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Deep extract structured data
            print(f"[Crawler] Performing deep extraction from caijinglian...")
            structured_data = self.deep_extract_data(soup, 'caijinglian')
            print(f"[Crawler] Extracted {len(structured_data.get('tables', []))} tables, {len(structured_data.get('lists', []))} lists")
            
            content = soup.get_text(strip=True) if soup.get_text() else ""
            
            if not content and not structured_data.get('tables'):
                return {
                    "site": 'caijinglian',
                    "timestamp": datetime.now().isoformat(),
                    "error": "No content extracted from page",
                    "raw_data_preview": ""
                }
                
            processed_data = self.process_with_ai(content, 'caijinglian', structured_data)
            self.update_crawl_time('caijinglian')
            return processed_data
            
        except requests.exceptions.HTTPError as he:
            return {
                "site": 'caijinglian',
                "timestamp": datetime.now().isoformat(),
                "error": f"HTTP error occurred while crawling 财联社: {str(he)}"
            }
        except requests.exceptions.ConnectionError as ce:
            return {
                "site": 'caijinglian',
                "timestamp": datetime.now().isoformat(),
                "error": f"Connection error occurred while crawling 财联社: {str(ce)}"
            }
        except requests.exceptions.Timeout as te:
            return {
                "site": 'caijinglian',
                "timestamp": datetime.now().isoformat(),
                "error": f"Timeout occurred while crawling 财联社: {str(te)}"
            }
        except Exception as e:
            return {
                "site": 'caijinglian',
                "timestamp": datetime.now().isoformat(),
                "error": f"Unexpected error occurred while crawling 财联社: {str(e)}"
            }

    def crawl_all_sites(self, bypass_rate_limit: bool = False) -> Dict:
        """Crawl data from all sites"""
        results = {}
        
        results['tonghuashun'] = self.crawl_tonghuashun(bypass_rate_limit)
        results['dongfangcaifu'] = self.crawl_dongfangcaifu(bypass_rate_limit)
        results['xueqiu'] = self.crawl_xueqiu(bypass_rate_limit)
        results['tongdaxin'] = self.crawl_tongdaxin(bypass_rate_limit)
        results['caijinglian'] = self.crawl_caijinglian(bypass_rate_limit)
        
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