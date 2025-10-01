import asyncio
import re
import os
from urllib.parse import urlparse
from playwright.async_api import async_playwright
from lxml import html
from PySide6.QtCore import QThread, Signal, QUrl
from pathlib import Path
from app.utils.db_handler import DBHandler
from app.src.settings import AppSettings
from app.utils import Logger
import requests

class XPathWorkerPlaywright(QThread):
    extraction_done = Signal(dict)
    error_occurred = Signal(str)
    image_ready = Signal(bytes, str)  # Added signal for image bytes

    def __init__(self, db: DBHandler, settings: AppSettings, url: str, rules: list, url_hash: str):
        super().__init__()
        self.db = db
        self.settings = settings
        self.url = url
        self.rules = rules
        self.url_hash = url_hash
        self.logger = Logger.get_logger("XPathWorkerPlaywright")
        self.browser = None
        self.page = None

    def run(self):
        asyncio.run(self._async_run())

    async def _async_run(self):
        playwright_instance = None
        browser = None
        context = None
        
        try:
            playwright_instance = await async_playwright().start()
            browser = await playwright_instance.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()
            
            # Set custom headers from settings
            try:
                settings_headers = {
                    k.split("/")[1]: self.settings.get(f"browser_agent/{k.split('/')[1]}") 
                    for k in self.settings._defaults 
                    if k.startswith("browser_agent/")
                }
                if settings_headers:
                    await page.set_extra_http_headers(settings_headers)
            except Exception as e:
                self.logger.warning(f"Failed to set custom headers: {e} |#| ({type(e).__name__})", exc_info=True)
            
            # Navigate to page
            await page.goto(self.url, wait_until='domcontentloaded', timeout=30000)
            
            # Handle Cloudflare or similar protection
            title = await page.title()
            if "just a moment" in title.lower() or "bitte warten" in title.lower():
                await page.wait_for_timeout(5000)
            
            # Get page content and parse with lxml
            content = await page.content()
            tree = html.fromstring(content)
            
            extracted = {}
            image_count = 0
            image_tasks = []  # Collect image download tasks
            
            for rule in self.rules:
                rule_name = rule.get('name', 'Unknown')
                xpath = rule['xpath']
                self.logger.debug(f"Processing rule '{rule_name}': XPath='{xpath}'")
                
                try:
                    # Handle XPath attribute extraction
                    attr_match = re.match(r"^(.*)/@([\w-]+)$", xpath.strip())
                    if attr_match:
                        base_xpath, attr = attr_match.groups()
                        elements = tree.xpath(base_xpath)
                        values = [e.get(attr) for e in elements if e.get(attr)]
                    else:
                        # Regular XPath text extraction
                        elements = tree.xpath(xpath)
                        values = []
                        for elem in elements:
                            if isinstance(elem, str):
                                values.append(elem.strip())
                            elif hasattr(elem, 'text_content'):
                                text = elem.text_content().strip()
                                if text:
                                    values.append(text)
                            elif hasattr(elem, 'text'):
                                text = elem.text.strip() if elem.text else ""
                                if text:
                                    values.append(text)
                            else:
                                try:
                                    text = " ".join(elem.xpath(".//text()")).strip()
                                    if text:
                                        values.append(text)
                                except Exception as e:
                                    self.logger.error(f"Failed to extract text from element: {e} |#| ({type(e).__name__})", exc_info=True)
                    
                    # Filter empty values
                    values = [v for v in values if v]
                    self.logger.debug(f"Rule '{rule_name}': Found {len(values)} values: {values[:5]}...")  # Log first 5 values
                    
                    # Handle image downloads - keep context alive for these
                    if rule.get('is_image', False) and values:
                        for src in values:
                            # Create task for image download, passing context to keep it alive
                            task = asyncio.create_task(self._download_image(src, self.url_hash, image_count, context))
                            image_tasks.append(task)
                            image_count += 1
                    
                    # Store consistent data format - always add to extracted, even if empty
                    extracted[rule_name] = {
                        'values': values,
                        'is_filter': rule.get('is_filter', False),
                        'priority': rule.get('priority', 0)
                    }
                        
                except Exception as e:
                    self.logger.error(f"Error processing rule '{rule_name}': {e} |#| ({type(e).__name__})", exc_info=True)
                    # Still add empty entry to extracted
                    extracted[rule_name] = {
                        'values': [],
                        'is_filter': rule.get('is_filter', False),
                        'priority': rule.get('priority', 99)
                    }
            
            self.logger.debug(f"Final extracted data: {list(extracted.keys())}")  # Log rule names
            
            # Emit extracted data immediately after processing all rules
            self.extraction_done.emit(extracted)
            
            # Wait for all image downloads to complete BEFORE cleanup
            if image_tasks:
                self.logger.debug(f"Waiting for {len(image_tasks)} image download tasks to complete...")
                # Use a longer timeout and handle exceptions properly
                completed_tasks = await asyncio.wait_for(
                    asyncio.gather(*image_tasks, return_exceptions=True),
                    timeout=30.0  # 30 second timeout for all image downloads
                )
                self.logger.debug("All image download tasks completed")
                
                # Log any failed downloads
                for i, result in enumerate(completed_tasks):
                    if isinstance(result, Exception):
                        self.logger.warning(f"Image download task {i} failed: {result}")
            
        except asyncio.TimeoutError:
            self.logger.warning("Image download timeout reached, proceeding with cleanup")
        except Exception as e:
            self.logger.error(f"Extraction failed: {e} |#| ({type(e).__name__})", exc_info=True)
            self.error_occurred.emit(str(e))
        finally:
            # Ensure proper cleanup in reverse order - context should still be alive here
            try:
                if context and not getattr(context._impl_obj, '_disposed', False):
                    await context.close()
                    self.logger.debug("Browser context closed")
                if browser:
                    await browser.close()
                    self.logger.debug("Browser closed")
                if playwright_instance:
                    await playwright_instance.stop()
                    self.logger.debug("Playwright stopped")
            except Exception as e:
                self.logger.error(f"Error during cleanup: {e} |#| ({type(e).__name__})", exc_info=True)

    async def _download_image(self, src, url_hash, count, context):
        """Download image and emit bytes for main thread to save"""
        try:
            # Ensure we have a proper URL
            if not src.startswith(('http://', 'https://')):
                base_url = QUrl(self.url)
                absolute_url = base_url.resolved(QUrl(src)).toString()
                src = absolute_url

            # Check if context is still valid before using it (corrected typo)
            if not context or getattr(context._impl_obj, '_disposed', False):
                self.logger.warning("Browser context is disposed, using fallback download method")
                await self._download_image_fallback(src, url_hash, count)
                return

            # Get cookies from Playwright context for authenticated requests
            cookies = await context.cookies()
            
            # Download with proper headers and cookies
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Referer': self.url
            }
            
            session = requests.Session()
            session.headers.update(headers)
            
            # Convert Playwright cookies to requests format
            for cookie in cookies:
                session.cookies.set(
                    cookie['name'], 
                    cookie['value'], 
                    domain=cookie.get('domain', ''),
                    path=cookie.get('path', '/')
                )
            
            response = session.get(src, timeout=10, stream=True)
            response.raise_for_status()
            
            # Check if it's actually an image
            content_type = response.headers.get('content-type', '').lower()
            if not content_type.startswith('image/'):
                self.logger.warning(f"URL does not return an image: {src} (Content-Type: {content_type})")
                return
            
            # Collect bytes
            image_bytes = b''
            for chunk in response.iter_content(chunk_size=8192):
                image_bytes += chunk
            
            # Emit bytes to main thread
            suffix = f"-{count}" if count > 0 else ""
            filename_hash = f"{url_hash}{suffix}"
            self.image_ready.emit(image_bytes, filename_hash)
            
            self.logger.debug(f"Emitted image bytes for: {filename_hash} from {src}")
            
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to download image from {src}: {e} |#| ({type(e).__name__})", exc_info=True)
        except Exception as e:
            self.logger.error(f"Unexpected error downloading image: {e} |#| ({type(e).__name__})", exc_info=True)
            # Try fallback on any error
            try:
                await self._download_image_fallback(src, url_hash, count)
            except Exception as fallback_error:
                self.logger.error(f"Fallback download also failed: {fallback_error} |#| ({type(fallback_error).__name__})", exc_info=True)

    async def _download_image_fallback(self, src, url_hash, count):
        """Fallback image download without browser context"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Referer': self.url
            }
            
            response = requests.get(src, headers=headers, timeout=10, stream=True)
            response.raise_for_status()
            
            # Check if it's actually an image
            content_type = response.headers.get('content-type', '').lower()
            if not content_type.startswith('image/'):
                self.logger.warning(f"URL does not return an image: {src} (Content-Type: {content_type})")
                return
            
            # Collect bytes
            image_bytes = b''
            for chunk in response.iter_content(chunk_size=8192):
                image_bytes += chunk
            
            # Emit bytes to main thread
            suffix = f"-{count}" if count > 0 else ""
            filename_hash = f"{url_hash}{suffix}"
            self.image_ready.emit(image_bytes, filename_hash)
            
            self.logger.debug(f"Emitted image bytes (fallback) for: {filename_hash} from {src}")
            
        except Exception as e:
            self.logger.error(f"Fallback image download failed for {src}: {e} |#| ({type(e).__name__})", exc_info=True)

