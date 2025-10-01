from PySide6.QtCore import QSettings
from pathlib import Path

class AppSettings:
    def __init__(self, path="user_data/config/settings.ini"):
        self._settings = QSettings(path, QSettings.IniFormat)
        self._defaults = {
            "image_cache_dir": "user_data/img",
            "favicon_cache_dir": "user_data/favicons",
            "language": "auto",  # "auto" or specific language code like "en", "de"
            "your_timezone": 2,
            "theme": "auto",     # "light", "dark", "auto"
            
            "Plugins/xpath_enabled": True,
            
            "browser_agent/User-Agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            "browser_agent/Accept": 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            "browser_agent/Accept-Language": 'en-US,en;q=0.5',
            "browser_agent/Accept-Encoding": 'gzip, deflate, br',
            "browser_agent/Connection": 'keep-alive',
            "browser_agent/Upgrade-Insecure-Requests": '1',
            "browser_agent/Sec-Fetch-Dest": 'document',
            "browser_agent/Sec-Fetch-Mode": 'navigate',
            "browser_agent/Sec-Fetch-Site": 'none',
            "browser_agent/Sec-Fetch-User": '?1'
        }

        try:
            import playwright
            self._defaults["Plugins/scraping_engine"] = "playwright"
        except ImportError:
            self._defaults["Plugins/scraping_engine"] = "requests"

    def get(self, key, default=None, type=None):
        effective_default = self._defaults.get(key, default)
        value = self._settings.value(key, effective_default)
        if isinstance(effective_default, list) and isinstance(value, str):
            value = [v.strip() for v in value.split(",") if v.strip()]
        if type is not None:
            if type is bool:
                if isinstance(value, str):
                    value = value.lower() == 'true'
            else:
                value = type(value)
        return value

    def set(self, key, value):
        if isinstance(value, list):
            value = ",".join(value)
        self._settings.setValue(key, value)

    def sync(self):
        self._settings.sync()