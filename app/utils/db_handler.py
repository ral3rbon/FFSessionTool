##*** app/db_handler.py
import sqlite3
import threading
import time
from datetime import datetime
from contextlib import contextmanager
from collections import defaultdict
from app.utils import Logger

class DBHandler:
    """
    Database handler for managing XPath rules, extracted data, and session information.
    
    This class provides a SQLite-based storage system for:
    - Domain-specific XPath rules for data extraction
    - Extracted data from web pages using XPath rules
    - Session and tab tracking for Firefox session files
    - Extended URL mappings for enhanced data organization
    
    """
    
    def __init__(self, db_path="sites.db"):
        self.db_path = db_path
        self._lock = threading.Lock()
        self.logger = Logger.get_logger("DBHandler")
        self._initialize_database()

        self.logger.info(f"Database initialized at {db_path}")

    def _initialize_database(self):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS xpath_domains (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain TEXT NOT NULL,
                    url_contains TEXT DEFAULT '',
                    UNIQUE(domain, url_contains)
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS xpath_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain_id INTEGER,
                    name TEXT,
                    xpath TEXT,
                    is_filter INTEGER DEFAULT 0,
                    is_image INTEGER DEFAULT 0,
                    priority INTEGER DEFAULT 0,
                    is_global INTEGER DEFAULT 0,
                    FOREIGN KEY (domain_id) REFERENCES xpath_domains(id) ON DELETE CASCADE
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filepath TEXT UNIQUE,
                    import_date TEXT DEFAULT (datetime('now'))
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS xpath_tabs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id INTEGER,
                    url_hash TEXT,
                    url TEXT,
                    token TEXT
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS xpath_extracted_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tab_id INTEGER,
                    rule_id INTEGER,
                    value TEXT,
                    extracted_at TEXT,
                    FOREIGN KEY(tab_id) REFERENCES xpath_tabs(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS main_user_tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tab_id INTEGER,
                    name TEXT,
                    value TEXT,
                    added_at TEXT,
                    FOREIGN KEY(tab_id) REFERENCES xpath_tabs(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS xpath_extended_urls (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    tab_id       INTEGER NOT NULL,
                    group_name   TEXT    NOT NULL,
                    extended_url TEXT    NOT NULL,
                    FOREIGN KEY(tab_id) REFERENCES xpath_tabs(id) ON DELETE CASCADE
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS xpath_url_extensions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    internal_name TEXT NOT NULL UNIQUE,
                    value TEXT NOT NULL,
                    template TEXT DEFAULT '',
                    sort_order INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS prefix_filters (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prefix TEXT NOT NULL UNIQUE,
                    is_active INTEGER DEFAULT 1,
                    sort_order INTEGER DEFAULT 0
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS app_info (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    setting_key TEXT NOT NULL UNIQUE,
                    setting_value TEXT,
                    setting_type TEXT DEFAULT 'string'
                )
            """)

            cursor.execute("CREATE INDEX IF NOT EXISTS idx_xpath_url_extensions_sort ON xpath_url_extensions(sort_order);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_prefix_filters_sort ON prefix_filters(prefix);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_app_info_key ON app_info(setting_key);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_extracted_rule ON xpath_extracted_data(rule_id);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_extracted_value ON xpath_extracted_data(value);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_extracted_rule_value ON xpath_extracted_data(rule_id, value);")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_extracted_tab ON xpath_extracted_data(tab_id);")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_tab_rule_value ON xpath_extracted_data (tab_id, rule_id, value);")
        
            cursor.execute("PRAGMA journal_mode=WAL;")  # Enable WAL for crash resistance
            conn.commit()
                


    @contextmanager
    def get_db_connection(self):
        with self._lock:
            retries = 3
            for attempt in range(retries):
                try:
                    conn = sqlite3.connect(self.db_path, timeout=10)  # Add timeout
                    yield conn
                    break
                except sqlite3.OperationalError as e:
                    if attempt < retries - 1:
                        self.logger.warning(f"DB connection failed, retrying in 0.5s: {e}")
                        time.sleep(0.5)
                    else:
                        self.logger.error(f"DB connection failed after {retries} attempts: {e} |#| ({type(e).__name__})", exc_info=True)
                        raise

    def get_xpath_rules(self, domain: str, url_contains: str):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            if not domain:
                # Alle Regeln (Startzustand im Dialog)
                cursor.execute("""
                    SELECT r.id, r.name, r.xpath, r.is_filter, r.is_image, r.priority, r.is_global,
                           d.domain, d.url_contains
                    FROM xpath_rules r
                    JOIN xpath_domains d ON d.id = r.domain_id
                    ORDER BY 
                        r.is_global DESC,
                        CASE WHEN r.priority = 0 THEN 1 ELSE 0 END ASC,
                        r.priority ASC,
                        r.id ASC
                """)
            elif not url_contains:
                # Alle Regeln für Domain (alle url_contains + globale)
                cursor.execute("""
                    SELECT r.id, r.name, r.xpath, r.is_filter, r.is_image, r.priority, r.is_global,
                           d.domain, d.url_contains
                    FROM xpath_rules r
                    JOIN xpath_domains d ON d.id = r.domain_id
                    WHERE d.domain = ?
                    ORDER BY 
                        r.is_global DESC,
                        CASE WHEN r.priority = 0 THEN 1 ELSE 0 END ASC,
                        r.priority ASC,
                        r.id ASC
                """, (domain,))
            else:
                # Regeln für Domain + spezifisches url_contains, plus globale
                cursor.execute("""
                    SELECT r.id, r.name, r.xpath, r.is_filter, r.is_image, r.priority, r.is_global,
                           d.domain, d.url_contains
                    FROM xpath_rules r
                    JOIN xpath_domains d ON d.id = r.domain_id
                    WHERE d.domain = ? AND (d.url_contains = ? OR r.is_global = 1)
                    ORDER BY 
                        r.is_global DESC,
                        CASE WHEN r.priority = 0 THEN 1 ELSE 0 END ASC,
                        r.priority ASC,
                        r.id ASC
                """, (domain, url_contains))
            rows = cursor.fetchall()
        return [
            {
                "id": row[0],
                "name": row[1],
                "xpath": row[2],
                "is_filter": bool(row[3]),
                "is_image": bool(row[4]),
                "priority": row[5],
                "is_global": bool(row[6]),
                "domain": row[7],
                "url_contains": row[8] or ""
            } for row in rows
        ]
    
    def get_tabs_by_extracted_value(self, rule_id: int, value: str):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.session_id, t.url_hash
                FROM xpath_extracted_data ed
                JOIN xpath_tabs t ON ed.tab_id = t.id
                WHERE ed.rule_id = ? AND ed.value = ?
            """, (rule_id, value))
            return cursor.fetchall()

    def save_extracted_data(self, tab_id, rule_id, value, extracted_at=None, avoid_duplicates=True):
        """Saves a single value for Tab+Rule combination."""
        if extracted_at is None:
            extracted_at = datetime.utcnow().isoformat()

        # Ensure value is a string
        value = str(value) if value is not None else ""

        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                conn.execute("BEGIN")  # Start transaction
                if avoid_duplicates:
                    cursor.execute("""
                        SELECT 1 
                        FROM xpath_extracted_data
                        WHERE tab_id = ? AND rule_id = ? AND value = ?
                        LIMIT 1
                    """, (tab_id, rule_id, value))
                    if cursor.fetchone():
                        return  # Value already exists → don't insert again

                cursor.execute("""
                    INSERT INTO xpath_extracted_data (tab_id, rule_id, value, extracted_at)
                    VALUES (?, ?, ?, ?)
                """, (tab_id, rule_id, value, extracted_at))
                conn.commit()
                self.logger.info(f"Saved extracted data: tab_id={tab_id}, rule_id={rule_id}")
            except Exception as e:
                conn.rollback()
                self.logger.error(f"Failed to save extracted data: {e} |#| ({type(e).__name__})", exc_info=True)
                raise

    def load_extracted_data_for_url(self, url: str):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT r.id, r.name, ed.value, r.is_filter, r.is_image, r.priority
            FROM xpath_extracted_data ed
            JOIN xpath_rules r ON ed.rule_id = r.id
            JOIN xpath_tabs t ON ed.tab_id = t.id
            WHERE t.url LIKE ?
            ORDER BY r.priority ASC
            """, (f"%{url}%",))
            rows = cursor.fetchall()
            data = {}
            for rule_id, name, value, is_filter, is_image, priority in rows:
                key = (rule_id, name)
                if key not in data:
                    data[key] = {
                        "rule_id": rule_id,
                        "name": name,
                        "values": [],
                        "is_filter": bool(is_filter),
                        "is_image": bool(is_image),
                        "priority": priority
                    }
                data[key]["values"].append(value)
            return sorted(data.values(), key=lambda x: x["priority"])

    def get_tab_id_by_url(self, url: str):
        """
        Retrieves the tab_id from the tabs table using the given url.
        """
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM xpath_tabs WHERE url = ?", (url,))
            result = cursor.fetchone()
            return result[0] if result else None
    
    def get_extracted_data_for_tab(self, tab_id: int):
        """
        Retrieves and groups all extracted data entries for a specific tab_id,
        joining with the 'rules' table to get the name and priority.
        """
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT
                    ed.rule_id,
                    r.name,
                    ed.value,
                    r.is_filter,
                    r.is_image,
                    r.priority
                FROM xpath_extracted_data AS ed
                JOIN xpath_rules AS r ON ed.rule_id = r.id
                WHERE ed.tab_id = ?
                ORDER BY r.priority ASC, ed.id ASC
            """, (tab_id,))
            rows = cursor.fetchall()

            
            # Gruppieren der Werte basierend auf der Regel-ID
            grouped_data = defaultdict(lambda: {
                'name': '',
                'values': [],
                'is_filter': False,
                'is_image': False,
                'priority': 0
            })
            
            for row in rows:
                rule_id, name, value, is_filter, is_image, priority = row
                
                # Sammeln Sie alle Werte für dasselbe name in einer Liste
                grouped_data[rule_id]['name'] = name
                grouped_data[rule_id]['values'].append(value)
                grouped_data[rule_id]['is_filter'] = bool(is_filter)
                grouped_data[rule_id]['is_image'] = bool(is_image)
                grouped_data[rule_id]['priority'] = priority

            # Konvertieren des defaultdict in eine Liste von Dictionaries
            extracted_data = list(grouped_data.values())
            
            return extracted_data

    def get_url_contains_for_domain(self, domain: str) -> list[str]:
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT url_contains
                FROM xpath_domains
                WHERE domain = ?
                ORDER BY url_contains ASC
            """, (domain,))
            rows = cursor.fetchall()
        return [r[0] for r in rows if r and r[0] is not None]

    def get_or_create_session_id(self, filepath: str) -> int:
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM app_sessions WHERE filepath = ?", (filepath,))
            row = cursor.fetchone()
            if row:
                return row[0]
            cursor.execute("INSERT INTO app_sessions (filepath) VALUES (?)", (filepath,))
            conn.commit()
            return cursor.lastrowid

    def get_tab_id(self, session_id, url_hash):
        with (self.get_db_connection() as conn):
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM xpath_tabs WHERE session_id = ? AND url_hash = ?", (session_id, url_hash))
            row = cursor.fetchone()
            if row:
                return row[0]
            else:
                return None
    


    def write_tab_id(self, session_id, url_hash, url) -> int:
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO xpath_tabs (session_id, url_hash, url) VALUES (?, ?, ?)", (session_id, url_hash, url))
            conn.commit()
            return cursor.lastrowid

    def get_rule_id_by_name(self, name):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM xpath_rules WHERE name = ?", (name,))
            row = cursor.fetchone()
            if row:
                return row[0]
            return None

    def xpath_rules_exist(self, domain, url_contains):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) 
                FROM xpath_rules r
                JOIN xpath_domains d ON r.domain_id = d.id
                WHERE d.domain = ? AND d.url_contains = ?
            """, (domain, url_contains))
            count = cursor.fetchone()[0]
            return count > 0

    def find_matching_url_part(self, domain, url):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT url_contains FROM xpath_domains
                WHERE domain = ?
            """, (domain,))
            results = [row[0] for row in cursor.fetchall() if row and row[0]]

        # Wähle den längsten passenden Teilstring (spezifischste Regel)
        best_match = ""
        for uc in sorted(results, key=lambda s: len(s), reverse=True):
            if uc and uc in url:
                best_match = uc
                break

        return best_match

    def save_xpath_rules(self, domain: str, url_contains: str, rules: list[dict]):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                conn.execute("BEGIN")  # Start transaction
                # Domain check or insert
                cursor.execute("""
                    INSERT OR IGNORE INTO xpath_domains (domain, url_contains)
                    VALUES (?, ?)
                """, (domain, url_contains))
                cursor.execute("""
                    SELECT id FROM xpath_domains WHERE domain = ? AND url_contains = ?
                """, (domain, url_contains))
                domain_id = cursor.fetchone()[0]

                # Nur upsert – keine Löschung anderer Regeln mehr
                for rule in rules:
                    name = rule["name"].strip()
                    xpath = rule["xpath"].strip()
                    is_filter = int(rule.get("is_filter", False))
                    is_image = int(rule.get("is_image", False))
                    priority = int(rule.get("priority", 0))
                    is_global = int(rule.get("is_global", False))
                    rule_id = rule.get("id")

                    if rule_id:
                        cursor.execute("""
                            UPDATE xpath_rules 
                            SET name = ?, xpath = ?, is_filter = ?, is_image = ?, priority = ?, is_global = ?
                            WHERE id = ? AND domain_id = ?
                        """, (name, xpath, is_filter, is_image, priority, is_global, rule_id, domain_id))
                    else:
                        cursor.execute("""
                            INSERT INTO xpath_rules (domain_id, name, xpath, is_filter, is_image, priority, is_global)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (domain_id, name, xpath, is_filter, is_image, priority, is_global))

                conn.commit()
                self.logger.info(f"Saved/updated {len(rules)} XPath rule(s) for domain={domain} (url_contains='{url_contains}')")
            except Exception as e:
                conn.rollback()
                self.logger.error(f"Failed to save XPath rules: {e} |#| ({type(e).__name__})", exc_info=True)
                raise

    def delete_xpath_rule(self, rule_id: int):
        """Delete a single xpath_rule by id."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM xpath_rules WHERE id = ?", (rule_id,))
            conn.commit()

    def save_extended_url(self, tab_id: int, group_name: str, extended_url: str):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO xpath_extended_urls (tab_id, group_name, extended_url)
                VALUES (?, ?, ?)
            """, (tab_id, group_name, extended_url))
            conn.commit()

    def get_extended_urls_for_tab(self, tab_id: int):
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT extended_url FROM xpath_extended_urls WHERE tab_id=?", (tab_id,))
            return [r[0] for r in cursor.fetchall()]

    def get_domain_url_contains(self, domain):
        """Get all url_contains values for a specific domain"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT url_contains FROM xpath_domains WHERE domain = ?", (domain,))
            results = cursor.fetchall()
            return [row[0] for row in results if row[0]]  # Filter out empty strings
            
    def get_app_info(self, setting_key, default_value=None):
        """Holt eine App-Info aus der Datenbank"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT setting_value, setting_type FROM app_info WHERE setting_key = ?",
                           (setting_key,))
            result = cursor.fetchone()
            
            if result:
                value, setting_type = result
                # Typ-Konvertierung
                if setting_type == 'boolean':
                    return value.lower() == 'true'
                elif setting_type == 'integer':
                    return int(value)
                else:
                    return value
            return default_value

    def set_app_info(self, setting_key, setting_value):
        """Setzt eine App-Info in der Datenbank"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Typ ermitteln
            if isinstance(setting_value, bool):
                value_str = 'true' if setting_value else 'false'
                setting_type = 'boolean'
            elif isinstance(setting_value, int):
                value_str = str(setting_value)
                setting_type = 'integer'
            else:
                value_str = str(setting_value)
                setting_type = 'string'
            
            cursor.execute("""
                INSERT OR REPLACE INTO app_info (setting_key, setting_value, setting_type) 
                VALUES (?, ?, ?)
            """, (setting_key, value_str, setting_type))
            conn.commit()


    def batch_get_url_extensions(self):
        """Holt alle URL Extensions aus der Datenbank"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, internal_name, value, template, sort_order, is_active 
                FROM xpath_url_extensions 
                ORDER BY sort_order ASC
            """)
            rows = cursor.fetchall()
            
            return [
                {
                    "id": row[0],
                    "internal_name": row[1],
                    "value": row[2],
                    "template": row[3],
                    "sort_order": row[4],
                    "is_active": bool(row[5])
                } for row in rows
            ]

    def batch_get_active_url_extensions(self):
        """Holt nur die aktiven URL Extensions"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, internal_name, value, template, sort_order 
                FROM xpath_url_extensions 
                WHERE is_active = 1 
                ORDER BY sort_order ASC
            """)
            rows = cursor.fetchall()
            
            return [
                {
                    "id": row[0],
                    "internal_name": row[1],
                    "value": row[2],
                    "template": row[3],
                    "sort_order": row[4]
                } for row in rows
            ]
        
    def batch_save_url_extension(self, ext_data):
        """
        Fügt einen neuen URL-Extension-Eintrag hinzu.
        ext_data: dict mit keys: internal_name, value, template, sort_order, is_active
        Return: neue ID
        """
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                conn.execute("BEGIN")
                cursor.execute("""
                    INSERT INTO xpath_url_extensions (internal_name, value, template, sort_order, is_active)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    ext_data.get('internal_name', '').strip(),
                    ext_data.get('value', '').strip(),
                    ext_data.get('template', 'CUSTOM'),
                    ext_data.get('sort_order', 0),
                    ext_data.get('is_active', 1)
                ))
                conn.commit()
                new_id = cursor.lastrowid
                self.logger.info(f"Saved URL extension: id={new_id}, name={ext_data.get('internal_name')}")
                return new_id
            except Exception as e:
                conn.rollback()
                self.logger.error(f"Failed to save URL extension: {e}", exc_info=True)
                raise

    def batch_update_url_extension(self, ext_id, internal_name, value, template, sort_order, is_active):
        """
        Updated einen bestehenden URL-Extension-Eintrag anhand der ID.
        """
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                conn.execute("BEGIN")
                cursor.execute("""
                    UPDATE xpath_url_extensions
                    SET internal_name = ?,
                        value = ?,
                        template = ?,
                        sort_order = ?,
                        is_active = ?
                    WHERE id = ?
                """, (internal_name.strip(), value.strip(), template, sort_order, is_active, ext_id))
                conn.commit()
                self.logger.info(f"Updated URL extension: id={ext_id}")
            except Exception as e:
                conn.rollback()
                self.logger.error(f"Failed to update URL extension: {e}", exc_info=True)
                raise

    def batch_delete_url_extension(self, ext_id):
        """
        Löscht einen URL-Extension-Eintrag anhand der ID.
        """
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            try:
                conn.execute("BEGIN")
                cursor.execute("DELETE FROM xpath_url_extensions WHERE id = ?", (ext_id,))
                conn.commit()
                self.logger.info(f"Deleted URL extension: id={ext_id}")
            except Exception as e:
                conn.rollback()
                self.logger.error(f"Failed to delete URL extension: {e}", exc_info=True)
                raise

    def batch_get_prefix_filters(self):
        """Holt alle Prefix Filter aus der Datenbank"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, prefix, is_active 
                FROM prefix_filters 
                ORDER BY id ASC
            """)
            rows = cursor.fetchall()
            
            return [
                {
                    "id": row[0],
                    "prefix": row[1],
                    "is_active": bool(row[2])
                } for row in rows
            ]

    def batch_get_active_prefix_filters(self):
        """Holt nur die aktiven Prefix Filter als Liste von Strings"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT prefix 
                FROM prefix_filters 
                WHERE is_active = 1 
                ORDER BY id ASC
            """)
            rows = cursor.fetchall()
            
            return [row[0] for row in rows]

    def batch_save_prefix_filters(self, prefix, is_active):
        """Speichert Prefix Filter in die Datenbank"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                    INSERT INTO prefix_filters (prefix, is_active)
                    VALUES (?, ?)
                """, (
                    prefix,
                    1 if is_active else 0
                ))

            conn.commit()
            return cursor.lastrowid

    def batch_update_prefix_filter(self, prefix_id, prefix, is_active):
        """Aktualisiert einen vorhandenen Prefix-Filter"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE prefix_filters
                SET prefix = ?, is_active = ?
                WHERE id = ?
            """, (prefix, 1 if is_active else 0, prefix_id))
            conn.commit()

    
    def batch_delete_prefix_filter(self, prefix_id):
        """Löscht einen Prefix-Filter anhand der ID"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM prefix_filters WHERE id = ?", (prefix_id,))
            conn.commit()

    def get_groups(self):
        """Alle Gruppen-Namen aus der DB (xpath_extended_urls) zurückgeben."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT group_name FROM xpath_extended_urls WHERE group_name IS NOT NULL ORDER BY group_name ASC")
            return [row[0] for row in cursor.fetchall()]

    def get_urls_by_group(self, group):
        """Alle ExtendedUrls für eine bestimmte Gruppe zurückgeben."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT extended_url FROM xpath_extended_urls WHERE group_name LIKE ?", (f"%{group}%",))
            return [row[0] for row in cursor.fetchall()]

    def count_urls_by_group(self, group):
        """Zählt, wie viele Tabs noch keine ExtendedUrl besitzen (für Bonus-Anzeige)."""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM xpath_extended_urls WHERE group_name LIKE ? AND extended_url IS NULL", (f"%{group}%",))
            return cursor.fetchone()[0]

    def get_extracted_data_for_rule(self, tab_id: int, rule_id: int) -> list:
        """
        Get extracted data values for a specific rule.
        
        :param tab_id: Tab ID
        :param rule_id: Rule ID
        :return: List of extracted values
        """
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT value FROM xpath_extracted_data 
                    WHERE tab_id = ? AND rule_id = ?
                    ORDER BY extracted_at DESC
                """, (tab_id, rule_id))
                
                results = cursor.fetchall()
                return [row[0] for row in results if row[0]]  # Filter out None/empty values
                
        except Exception as e:
            self.logger.error(f"Error getting extracted data for rule: {e} |#| ({type(e).__name__})", exc_info=True)
            return []