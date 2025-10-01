import pprint
from urllib.parse import urlparse
import requests
from lxml import html
from PySide6.QtCore import QThread, Signal
from pathlib import Path
from app.utils.db_handler import DBHandler
from app.src.settings import AppSettings
from app.utils import Logger

class XPathWorkerRequests(QThread):
    extraction_done = Signal(dict)  # {url: extracted_data}
    error_occurred = Signal(str)

    def __init__(self, db: DBHandler, settings: AppSettings, url: str, rules: list, url_hash: str):
        super().__init__()
        self.db = db
        self.settings = settings
        self.url = url
        self.rules = rules
        self.url_hash = url_hash
        self.logger = Logger.get_logger("XPathWorkerRequests")

    def run(self):
        try:
            domain = urlparse(self.url).netloc
            url_contains = ""  # Extract from URL path if needed
            self.logger.debug(f"Processing URL: {self.url}, Domain: {domain}")
            
            # Get headers from settings with fallback
            # **Begründung**: Konfigurierbare Browser-Headers für bessere Kompatibilität
            try:
                settings_headers = {k.split("/")[1]: self.settings.get(f"browser_agent/{k.split('/')[1]}") for k in self.settings._defaults if k.startswith("browser_agent/")}
            except Exception as e:
                self.logger.warning(f"Failed to load headers from settings: {e} |#| ({type(e).__name__})", exc_info=True)
                settings_headers = {}
            
            # Default headers with settings override
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }
            
            # Override with settings if available
            headers.update(settings_headers)
            
            response = requests.get(self.url, headers=headers, timeout=30)
            response.raise_for_status()
            
            tree = html.fromstring(response.content)
            extracted = {}
            image_count = 0

            self.logger.debug(f"Processing {len(self.rules)} rules")

            for rule in self.rules:
                rule_name = rule.get('name', 'Unknown')  # Use 'name' field
                xpath_expr = rule.get('xpath', '')
                is_image = rule.get('is_image', False)
                
                if not xpath_expr:
                    continue
                    
                try:
                    elements = tree.xpath(xpath_expr)
                    values = []
                    
                    for el in elements:
                        if is_image:
                            # Handle image sources
                            src = el.get('src') or el.get('data-src') or el.get('data-image')
                            if src:
                                # Download image if needed
                                self._download_image(src, self.url_hash, image_count)
                                values.append(src)
                                image_count += 1
                        else:
                            # Handle text content
                            if hasattr(el, 'text_content'):
                                text = el.text_content().strip()
                            elif isinstance(el, str):
                                text = el.strip()
                            else:
                                text = str(el).strip()
                            
                            if text:
                                values.append(text)
                    
                    # **Begründung**: Konsistentes Datenformat für bessere Verarbeitung
                    extracted[rule_name] = {
                        'values': values,
                        'is_filter': rule.get('is_filter', False),
                        'priority': rule.get('priority', 0)
                    }
                    
                except Exception as e:
                    self.logger.error(f"Error processing XPath rule '{rule_name}': {e}")
                    extracted[rule_name] = {
                        'values': [],
                        'is_filter': rule.get('is_filter', False),
                        'priority': rule.get('priority', 99)
                    }

            # Emit data in the expected format
            self.extraction_done.emit({self.url: extracted})
            
        except Exception as e:
            self.logger.error(f"Extraction failed: {e} |#| ({type(e).__name__})", exc_info=True)
            self.error_occurred.emit(str(e))

    def _download_image(self, src, url_hash, count):
        cache_dir = Path(self.settings.get("image_cache_dir"))
        cache_dir.mkdir(exist_ok=True)
        suffix = f"-{count}" if count > 0 else ""
        filename = f"{url_hash}{suffix}.jpg"  # Assume JPG, adjust as needed
        response = requests.get(src)
        with open(cache_dir / filename, 'wb') as f:
            f.write(response.content)
