import asyncio
import requests
import json
from datetime import datetime
import os
import time
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
import fake_useragent
from pathlib import Path


class ChineseStockCrawler:
    def __init__(self, data_dir: str = "data", qwen_api_key: str = "sk-fc88e8c463e94a43bc41f1094a28fa1f"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': fake_useragent.UserAgent().random
        })
        
        # Qwen API configuration
        self.qwen_api_key = qwen_api_key
        self.qwen_api_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        
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

    def can_crawl(self, site_name: str) -> bool:
        """Check if we can crawl the site based on rate limiting"""
        current_time = time.time()
        last_crawl = self.last_crawl_times.get(site_name, 0)
        
        if current_time - last_crawl >= self.min_crawl_interval:
            return True
        return False

    def update_crawl_time(self, site_name: str):
        """Update the last crawl time for a site"""
        self.last_crawl_times[site_name] = time.time()

    def process_with_ai(self, raw_data: str, site_name: str) -> Dict:
        """Process raw data with Qwen AI API to organize it"""
        try:
            # Validate input
            if not raw_data or len(raw_data.strip()) == 0:
                return {
                    "site": site_name,
                    "timestamp": datetime.now().isoformat(),
                    "raw_data_preview": "",
                    "ai_processed_data": None,
                    "error": "Empty raw data provided"
                }

            headers = {
                'Authorization': f'Bearer {self.qwen_api_key}',
                'Content-Type': 'application/json'
            }
            
            # Ensure we have data to process (limit to 2000 chars)
            truncated_data = raw_data[:2000] if raw_data else ""
            
            prompt = f"""
            Please organize the following stock market data from {site_name}:
            {truncated_data}
            
            Extract and structure the data as JSON with the following format:
            {{
                "stocks": [
                    {{
                        "symbol": "stock symbol",
                        "name": "company name",
                        "price": "current price",
                        "change": "price change",
                        "change_percent": "percentage change",
                        "volume": "trading volume"
                    }}
                ],
                "market_overview": "brief market overview",
                "top_movers": ["top gaining stocks", "top losing stocks"],
                "news": ["important news headlines"]
            }}
            """
            
            payload = {
                "model": "qwen-max",
                "input": {
                    "prompt": prompt
                },
                "parameters": {
                    "temperature": 0.5,
                    "max_tokens": 1024
                }
            }
            
            try:
                response = requests.post(self.qwen_api_url, headers=headers, json=payload, timeout=30)
                
                if response.status_code == 200:
                    try:
                        result = response.json()
                        # Extract the text from the response
                        ai_processed = result.get("output", {}).get("text", "")
                        
                        if not ai_processed:
                            return {
                                "site": site_name,
                                "timestamp": datetime.now().isoformat(),
                                "raw_data_preview": raw_data[:500],
                                "ai_processed_data": None,
                                "error": "Empty response from AI service"
                            }
                            
                        # Try to parse the AI response as JSON
                        try:
                            # Find JSON part in the response
                            start_idx = ai_processed.find('{')
                            end_idx = ai_processed.rfind('}') + 1
                            
                            if start_idx != -1 and end_idx > start_idx:
                                json_str = ai_processed[start_idx:end_idx]
                                structured_data = json.loads(json_str)
                                
                                return {
                                    "site": site_name,
                                    "timestamp": datetime.now().isoformat(),
                                    "raw_data_preview": raw_data[:500],
                                    "ai_processed_data": structured_data
                                }
                        except json.JSONDecodeError as je:
                            # If JSON parsing fails, return the text as is with warning
                            return {
                                "site": site_name,
                                "timestamp": datetime.now().isoformat(),
                                "raw_data_preview": raw_data[:500],
                                "ai_processed_data": ai_processed,
                                "warning": f"Response parsed as text due to JSON decode error: {str(je)}"
                            }
                            
                    except ValueError as ve:  # JSON decode error
                        return {
                            "site": site_name,
                            "timestamp": datetime.now().isoformat(),
                            "raw_data_preview": raw_data[:500],
                            "ai_processed_data": None,
                            "error": f"Invalid JSON response from AI service: {str(ve)}"
                        }
                else:
                    error_msg = response.text if response.text else f"HTTP {response.status_code}"
                    return {
                        "site": site_name,
                        "timestamp": datetime.now().isoformat(),
                        "raw_data_preview": raw_data[:500],
                        "ai_processed_data": None,
                        "error": f"AI processing failed with status {response.status_code}: {error_msg}"
                    }
                    
            except requests.exceptions.Timeout:
                return {
                    "site": site_name,
                    "timestamp": datetime.now().isoformat(),
                    "raw_data_preview": raw_data[:500],
                    "ai_processed_data": None,
                    "error": "AI processing request timed out"
                }
            except requests.exceptions.RequestException as re:
                return {
                    "site": site_name,
                    "timestamp": datetime.now().isoformat(),
                    "raw_data_preview": raw_data[:500],
                    "ai_processed_data": None,
                    "error": f"Request to AI service failed: {str(re)}"
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

    def crawl_tonghuashun(self) -> Dict:
        """Crawl data from 同花顺"""
        if not self.can_crawl('tonghuashun'):
            return {"error": "Rate limit exceeded for 同花顺"}
        
        try:
            response = self.session.get(self.sites['tonghuashun'], timeout=10)
            response.raise_for_status()  # Raise an exception for bad status codes
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract relevant content with better error handling
            content = soup.get_text(strip=True) if soup.get_text() else ""
            
            if not content:
                return {
                    "site": 'tonghuashun',
                    "timestamp": datetime.now().isoformat(),
                    "error": "No content extracted from page"
                }
                
            processed_data = self.process_with_ai(content, 'tonghuashun')
            self.update_crawl_time('tonghuashun')
            return processed_data
            
        except requests.exceptions.HTTPError as he:
            return {
                "site": 'tonghuashun',
                "timestamp": datetime.now().isoformat(),
                "error": f"HTTP error occurred while crawling 同花顺: {str(he)}"
            }
        except requests.exceptions.ConnectionError as ce:
            return {
                "site": 'tonghuashun',
                "timestamp": datetime.now().isoformat(),
                "error": f"Connection error occurred while crawling 同花顺: {str(ce)}"
            }
        except requests.exceptions.Timeout as te:
            return {
                "site": 'tonghuashun',
                "timestamp": datetime.now().isoformat(),
                "error": f"Timeout occurred while crawling 同花顺: {str(te)}"
            }
        except Exception as e:
            return {
                "site": 'tonghuashun',
                "timestamp": datetime.now().isoformat(),
                "error": f"Unexpected error occurred while crawling 同花顺: {str(e)}"
            }

    def crawl_dongfangcaifu(self) -> Dict:
        """Crawl data from 东方财富"""
        if not self.can_crawl('dongfangcaifu'):
            return {"error": "Rate limit exceeded for 东方财富"}
        
        try:
            response = self.session.get(self.sites['dongfangcaifu'], timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            content = soup.get_text(strip=True) if soup.get_text() else ""
            
            if not content:
                return {
                    "site": 'dongfangcaifu',
                    "timestamp": datetime.now().isoformat(),
                    "error": "No content extracted from page"
                }
                
            processed_data = self.process_with_ai(content, 'dongfangcaifu')
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

    def crawl_xueqiu(self) -> Dict:
        """Crawl data from 雪球"""
        if not self.can_crawl('xueqiu'):
            return {"error": "Rate limit exceeded for 雪球"}
        
        try:
            response = self.session.get(self.sites['xueqiu'], timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            content = soup.get_text(strip=True) if soup.get_text() else ""
            
            if not content:
                return {
                    "site": 'xueqiu',
                    "timestamp": datetime.now().isoformat(),
                    "error": "No content extracted from page"
                }
                
            processed_data = self.process_with_ai(content, 'xueqiu')
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

    def crawl_tongdaxin(self) -> Dict:
        """Crawl data from 通达信 - may require special handling"""
        if not self.can_crawl('tongdaxin'):
            return {"error": "Rate limit exceeded for 通达信"}
        
        try:
            response = self.session.get(self.sites['tongdaxin'], timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            content = soup.get_text(strip=True) if soup.get_text() else ""
            
            if not content:
                return {
                    "site": 'tongdaxin',
                    "timestamp": datetime.now().isoformat(),
                    "error": "No content extracted from page"
                }
                
            processed_data = self.process_with_ai(content, 'tongdaxin')
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

    def crawl_caijinglian(self) -> Dict:
        """Crawl data from 财联社"""
        if not self.can_crawl('caijinglian'):
            return {"error": "Rate limit exceeded for 财联社"}
        
        try:
            response = self.session.get(self.sites['caijinglian'], timeout=10)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            content = soup.get_text(strip=True) if soup.get_text() else ""
            
            if not content:
                return {
                    "site": 'caijinglian',
                    "timestamp": datetime.now().isoformat(),
                    "error": "No content extracted from page"
                }
                
            processed_data = self.process_with_ai(content, 'caijinglian')
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

    def crawl_all_sites(self) -> Dict:
        """Crawl data from all sites"""
        results = {}
        
        results['tonghuashun'] = self.crawl_tonghuashun()
        results['dongfangcaifu'] = self.crawl_dongfangcaifu()
        results['xueqiu'] = self.crawl_xueqiu()
        results['tongdaxin'] = self.crawl_tongdaxin()
        results['caijinglian'] = self.crawl_caijinglian()
        
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