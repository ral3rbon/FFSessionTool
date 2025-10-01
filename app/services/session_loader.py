import os
import base64
from pathlib import Path
from sqlite3 import OperationalError
from typing import Dict, List, Tuple, Optional, Any

from app.utils.db_handler import DBHandler
from app.utils import Logger, tr, generate_url_hash
from app.src.session_parser import SessionParser


class SessionLoadingError(Exception):
    """Custom exception for session loading errors"""
    pass


class SessionLoader:
    """Service class responsible for loading and processing session files"""
    
    def __init__(self, db_handler: DBHandler):
        self.logger = Logger.get_logger("SessionLoader")
        self.db = db_handler
        self.session_processor = None
        self.json_data = None
        
    def load_session_file(self, path: str) -> Tuple[List[Dict], List[Dict], List[Dict]]:
        """
        Load a session file and return enriched data
        Args:
            path: Path to the session file
        Returns:
            Tuple of (enriched_tabs, groups, all_groups_info)
        Raises:
            SessionLoadingError: If loading fails
        """
        try:
            self.logger.info(f"Loading session file: {path}")
            
            if not os.path.exists(path):
                raise SessionLoadingError(f"{tr('Session file does not exist', 'session_loader')}: {path}")

            if not os.access(path, os.R_OK):
                raise SessionLoadingError(f"{tr('No read permission for file', 'session_loader')}: {path}")

            self.session_processor = SessionParser(path)
            self.json_data = self.session_processor.load_session()
            
            if not self.json_data:
                raise SessionLoadingError(tr("Failed to parse session data - empty result", "session_loader"))

            enriched_tabs, groups, all_groups_info = self.session_processor.get_enriched_tabs_and_groups()
            
            # Validate the loaded data
            if not isinstance(enriched_tabs, list):
                raise SessionLoadingError(tr("Invalid tabs data format", "session_loader"))
                
            # Ensure all tabs have required URL hashes
            self._ensure_url_hashes(enriched_tabs)

            self.logger.info(tr('Successfully loaded {0} tabs from {1} groups', 'session_loader', len(enriched_tabs), len(groups)))

            return enriched_tabs, groups, all_groups_info
            
        except OperationalError as e:
            self.logger.error(f"({tr('Database error while loading session', 'session_loader')}) {e} |#| ({type(e).__name__})", exc_info=True)
            raise SessionLoadingError(f"{tr('Database error', 'session_loader')}: {e}")
        except Exception as e:
            self.logger.error(f"({tr('Unexpected error loading session file', 'session_loader')}) {path}: {e} |#| ({type(e).__name__})", exc_info=True)
            raise SessionLoadingError(f"{tr('Failed to load session', 'session_loader')}: {e}")

    def _ensure_url_hashes(self, tabs: List[Dict]) -> None:
        """Ensure all tabs have URL hashes for tracking"""
        for tab in tabs:
            if not tab.get("url_hash") and tab.get("url"):
                try:
                    tab["url_hash"] = generate_url_hash(tab["url"])
                    self.logger.debug(f"{tr('Generated URL hash for tab', 'session_loader')}: {tab.get('title', 'Unknown')}")
                except Exception as e:
                    self.logger.warning(f"{tr('Failed to generate URL hash for tab', 'session_loader')}: {e} |#| ({type(e).__name__})", exc_info=True)

    def get_session_id(self, path: str) -> Optional[int]:
        """Get or create session ID in database"""
        try:
            return self.db.get_or_create_session_id(path)
        except Exception as e:
            self.logger.error(f"{tr('Failed to get/create session ID for', 'session_loader')} {path}: {e} |#| ({type(e).__name__})", exc_info=True)
            return None
    