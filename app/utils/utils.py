#app/utils/utils.py
import os
import math
import hashlib
from datetime import datetime
from urllib.parse import urlparse
from app.utils.ui_translator import tr

class UtilsHelper:
    """Helper class for utility functions with logger and status_bar support"""

    def __init__(self, logger=None, status_bar=None, session_loader=None, parent_widget=None):
        self.logger = logger
        self.status_bar = status_bar
        self.session_loader = session_loader
        self.parent_widget = parent_widget
    
    def extract_domain(self, url: str) -> str:
        """Extrahiert den Hostnamen aus einer URL, ohne 'www.' am Anfang."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.split(':')[0] # Remove Port if available
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception as e:
            error_log = f"{tr('Error at extracting domain:', 'utils')} {url}: {e})"
            if self.logger:
                self.logger.error(f"Error extracting domain from {url}: {e}", exc_info=True)
            if self.status_bar:
                self.status_bar.show_message(tr("Error extracting domain", "error"), message_type="error")
            return error_log

    def generate_url_hash(self, url: str, length: int = 12) -> str:
        if not url:
            return None

        try:
            normalized_url = url.lower().rstrip('/')

            # Generating SHA256 Hash
            hash_object = hashlib.sha256(normalized_url.encode('utf-8'))
            full_hash = hash_object.hexdigest()

            return full_hash[:length]
        except Exception as e:
            self.logger.error(f"Error generating hash for URL {url}: {e}", exc_info=True)
            self.status_bar.show_message(tr("Error generating URL hash", "error"), message_type="error")
            return None

    def extract_path(self, url: str) -> str:
        """Extrahiert den Pfadteil einer URL (alles nach der Domain)"""
        try:
            parsed = urlparse(url)
            path = parsed.path
            if parsed.query:
                path += "?" + parsed.query
            if parsed.fragment:
                path += "#" + parsed.fragment
            return path
        except Exception as e:
            self.logger.error(f"Error extracting path from {url}: {e}", exc_info=True)
            self.status_bar.show_message(tr("Error extracting path", "error"), message_type="error")
            return None

    def get_domain_without_tld(self, url: str) -> str:
        netloc = urlparse(url).netloc
        # Remove 'www.' falls vorhanden
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        # Remove TLD (z.B. .com, .de)
        domain_parts = netloc.split('.')
        if len(domain_parts) >= 2:
            # Take the second-to-last element as domain (e.g. example for example.com)
            return domain_parts[-2]
        return netloc

    def format_size(self, size_bytes, decimals=2):
        # Found at the awesome folks from https://www.digitalocean.com/community/tutorials/how-to-get-file-size-in-python
        if size_bytes == 0:
            return "0 Bytes"
        
        # Define the units and the factor for conversion (1024)
        power = 1024
        units = ["Bytes", "KB", "MB", "GB", "TB", "PB"]
        
        # Calculate the appropriate unit
        i = int(math.floor(math.log(size_bytes, power)))
        
        # Format the result
        return f"{size_bytes / (power ** i):.{decimals}f} {units[i]}"

    def find_firefox_profiles(self):
        try:
            if os.name == 'nt':  # Windows
                appdata = os.getenv('APPDATA')
                if not appdata:
                    raise ValueError("Umgebungsvariable 'APPDATA' nicht gefunden.")
                profiles_dir = os.path.join(appdata, 'Mozilla', 'Firefox', 'Profiles')

            elif os.uname().sysname == 'Darwin':  # MacOS
                home = os.path.expanduser('~')
                profiles_dir = os.path.join(home, 'Library', 'Application Support', 'Firefox', 'Profiles')

            else:  # Linux (first check for Flatpak installation)
                home = os.path.expanduser('~')
                flatpak_path = os.path.join(home, '.var', 'app', 'org.mozilla.firefox', '.mozilla', 'firefox', 'profiles')
                snap_path = os.path.join(home, 'snap', 'firefox', 'common', '.mozilla', 'firefox')
                
                # If Flatpak path exists, use it; otherwise test for snap, else: try the standard path
                if os.path.exists(flatpak_path):
                    profiles_dir = flatpak_path
                elif os.path.exists(snap_path): 
                    profiles_dir = snap_path
                else:
                    profiles_dir = os.path.join(home, '.mozilla', 'firefox', 'profiles')

        except Exception as e:
            self.logger.error(f"{tr('Error finding Firefox profiles directory', 'utils')}: {e} |#| ({type(e).__name__})", exc_info=True)
            self.status_bar.show_message(tr("Error finding Firefox profiles directory", "error"), message_type="error")
            profiles_dir = None
            raise

        if os.path.exists(profiles_dir):
            return [os.path.join(profiles_dir, d) for d in os.listdir(profiles_dir) if os.path.isdir(os.path.join(profiles_dir, d))]
        return []

    def create_backup_dir(self, base_path):
        date_str = datetime.now().strftime("%Y-%m-%d")
        base_name = f"Sessionstore-Backup {date_str}"
        backup_path = os.path.join(base_path, base_name)
        
        counter = 0
        while os.path.exists(backup_path):
            counter += 1
            backup_path = os.path.join(base_path, f"{base_name}-{counter}")
        
        untouched_path = os.path.join(backup_path, "untouched-backups")
        json_target_dir = os.path.join(backup_path,"decompiled JSON")

        os.makedirs(backup_path)
        os.makedirs(untouched_path)
        os.makedirs(json_target_dir)
        
        self.logger.info(f"Created backup directory: {backup_path}")
        
        return backup_path
    
    def export_as_json(self):
        from PySide6.QtWidgets import QFileDialog
        import json

        self.json_data = self.session_loader.session_processor.json_data
        if not self.json_data:
            self.status_bar.show_message(tr("No session data loaded to export.", "warning"), message_type="warning")
            return
            
    
        if hasattr(self, "processor"):
            self.session_loader.processor.sync_enriched_to_raw()

        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getSaveFileName(
            self.parent_widget, tr("Save Session as JSON", "General"), "modded-sessionstore.json", "JSON Files (*.json);;All Files (*)", options=options
        )
    
        if fileName:
            try:
                with open(fileName, 'w', encoding='utf-8') as f:
                    json.dump(self.json_data, f, indent=4)
                self.status_bar.show_message(tr("Session saved as JSON successfully.", "info"), message_type="success")

            except Exception as e:
                self.status_bar.show_message(f"{tr('Could not save file', 'error')}: {e}", message_type="error")
                self.logger.error(f"{tr('Could not save file', 'error')} {fileName}: {e} |#| ({type(e).__name__})", exc_info=True)

    def apply_search_filter(self, text):
        from PySide6.QtWidgets import QTreeWidgetItem
        text = text.strip().lower()

        if not text:
            self.parent_widget.populate_group_and_tabs(self.parent_widget.session_tabs, self.parent_widget.group_list)
            return

        filtered_tabs = []
        for tab in self.parent_widget.session_tabs:
            title = tab.get("title", "").lower()
            url = tab.get("url", "").lower()
            uuid = tab.get("uuid", "").lower()
            if text in title or text in url or text in uuid:
                filtered_tabs.append(tab)

        if not filtered_tabs:
            self.parent_widget.ccw.session_widget.clear()
            QTreeWidgetItem(self.parent_widget.ccw.session_widget, [tr("No results for '{0}'", "search", text)])
            return
        self.parent_widget.populate_group_and_tabs(filtered_tabs, self.parent_widget.group_list)

    def find_duplicates(self):
        import re
        from collections import defaultdict
        from PySide6.QtWidgets import QTreeWidgetItem
        from PySide6.QtCore import Qt

        if not self.parent_widget.session_tabs:
            #QMessageBox.warning(self, "Error", "No Tabs loaded.")
            return

        if not (self.parent_widget.lcw.dup_title_cb.isChecked() or self.parent_widget.lcw.dup_url_cb.isChecked()):
            self.parent_widget.populate_group_and_tabs(self.parent_widget.session_tabs, self.parent_widget.group_list)
            return

        duplicates = defaultdict(list)

        for tab in self.parent_widget.session_tabs:
            key_parts = []

            if self.parent_widget.lcw.dup_title_cb.isChecked():
                key_parts.append(tab.get('title', '').lower().strip())

            if self.parent_widget.lcw.dup_url_cb.isChecked():
                url_to_compare = tab.get('url', '').strip()
                if self.parent_widget.lcw.regex_checkbox.isChecked() and self.parent_widget.lcw.regex_input.currentText():
                    try:
                        regex_pattern = self.parent_widget.lcw.regex_input.currentText()
                        match = re.search(regex_pattern, url_to_compare)
                        if match:
                            url_key_part = "".join(match.groups())
                        else:
                            url_key_part = url_to_compare
                    except re.error as e:
                        self.parent_widget.ccw.session_widget.clear()
                        QTreeWidgetItem(self.parent_widget.ccw.session_widget, [tr("Invalid RegEx: {0}", "Tools", e)])

                        return
                else:
                    url_key_part = url_to_compare
                key_parts.append(url_key_part)

            if key_parts:
                duplicates[tuple(key_parts)].append(tab)

        self.parent_widget.ccw.session_widget.clear()
        dupe_num = 0
        found_duplicates = False

        for key, tab_list in duplicates.items():
            if len(tab_list) < 2:
                continue
            found_duplicates = True
            dupe_num += 1
            
            key_text = " / ".join([p for p in key if p])
            dupe_item = QTreeWidgetItem(self.parent_widget.ccw.session_widget,
                                        [f"Dup: {dupe_num}: {key_text}"])

            if self.parent_widget.lcw.dup_keep_group.isChecked():
                # Fenster → Gruppen → Tabs
                wnd_group_map = defaultdict(lambda: defaultdict(list))
                for tab in tab_list:
                    wnd = tab.get("window_index", 0)
                    group = tab.get("group_name", tr("Ungrouped", "Groups"))
                    wnd_group_map[wnd][group].append(tab)
                for wnd, group_map in sorted(wnd_group_map.items()):
                    wnd_label = f"Fenster {wnd + 1}"
                    wnd_item = QTreeWidgetItem(dupe_item, [wnd_label])
                    for group_name, tabs in sorted(group_map.items()):
                        group_item = QTreeWidgetItem(wnd_item, [group_name])
                        for tab in tabs:
                            title = tab.get("title", "")
                            url = tab.get("url", "")
                            label = f"{title} ({url})"
                            tab_item = QTreeWidgetItem(group_item, [label])
                            tab_item.setData(0, Qt.UserRole, tab)
            else:
                for tab in tab_list:
                    title = tab.get('title', '')
                    group_name = tab.get('group_name', tr("Ungrouped", "Groups"))
                    label = f"{title} ({group_name})"
                    tab_item = QTreeWidgetItem(dupe_item, [label])
                    tab_item.setData(0, Qt.UserRole, tab)

        if not found_duplicates:
            self.parent_widget.ccw.session_widget.clear()
            QTreeWidgetItem(self.parent_widget.ccw.session_widget, [tr("No duplications found", "Tools")])

             
             

# Keep backward compatibility with standalone functions as long i didn't refactor all imports
def extract_domain(url: str) -> str:
    helper = UtilsHelper()
    return helper.extract_domain(url)

def generate_url_hash(url: str, length: int = 12) -> str:
    helper = UtilsHelper()
    return helper.generate_url_hash(url, length)

def extract_path(url: str) -> str:
    helper = UtilsHelper()
    return helper.extract_path(url)

def get_domain_without_tld(url: str) -> str:
    helper = UtilsHelper()
    return helper.get_domain_without_tld(url)

def format_size(size_bytes, decimals=2):
    helper = UtilsHelper()
    return helper.format_size(size_bytes, decimals)

def find_firefox_profiles():
    helper = UtilsHelper()
    return helper.find_firefox_profiles()

def create_backup_dir(base_path):
    helper = UtilsHelper()
    return helper.create_backup_dir(base_path)