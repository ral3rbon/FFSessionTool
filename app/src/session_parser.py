import os
import json
import pprint
import lz4.block
from app.utils import extract_domain, generate_url_hash, tr, Logger

class SessionParser:
    def __init__(self, session_file_path: str):
        self.session_file_path = session_file_path
        self.json_data = None
        self.logger = Logger.get_logger("SessionParser")
        self.err_count = 0

    def load_session(self) -> dict:
        if not os.path.exists(self.session_file_path):
            raise FileNotFoundError(f"{tr('Session file not found:', 'session_parser_error')} {self.session_file_path}")

        with open(self.session_file_path, "rb") as f:
            magic = f.read(8)
            if magic != b"mozLz40\0":
                raise ValueError(tr("Invalid jsonLz4 file format", "session_parser_error"))
            compressed_data = f.read()

        try:
            decompressed_data = lz4.block.decompress(compressed_data)
            self.json_data = json.loads(decompressed_data)
            self.logger.info(tr("Session data loaded successfully.", "session_parser"))
            return self.json_data
        
        except lz4.block.LZ4BlockError as e:
            self.logger.error(f"{tr('Failed to decompress session data', 'session_parser_error')}: {e} |#| ({type(e).__name__})", exc_info=True)
            raise ValueError(tr('Failed to decompress session data.', 'session_parser_error')) from e
        except json.JSONDecodeError as e:
            self.logger.error(f"{tr('Failed to parse session data', 'session_parser_error')}: {e} |#| ({type(e).__name__})", exc_info=True)
            raise ValueError(tr('Failed to parse session data.', 'session_parser_error')) from e
        except Exception as e:
            self.logger.error(f"{tr('Unexpected error loading session data', 'session_parser_error')}: {e} |#| ({type(e).__name__})", exc_info=True)
            raise RuntimeError(tr('Unexpected error loading session data', 'session_parser_error')) from e

    def save_as_json(self, output_path: str):
        if self.json_data is None:
            raise ValueError(tr("Session data not loaded.", "session_parser_error"))

        self.sync_enriched_to_raw()
        clean_data = json.loads(json.dumps(self.json_data))
        for window in clean_data.get("windows", []):
            for tab in window.get("tabs", []):
                if "raw_tab" in tab:
                    del tab["raw_tab"]
        output_data = clean_data

        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, intend=2, ensure_ascii=False)
            return True
        except Exception as e:
            self.logger.error(f"{tr('Failed to save session data', 'session_parser_error')}: {e} |#| ({type(e).__name__})", exc_info=True)
            raise RuntimeError(tr('Failed to save session data.', 'session_parser_error')) from e

    def get_raw_data(self) -> dict:
        if self.json_data is None:
            self.logger.error(tr("Session data not loaded.", "session_parser_error"))
            raise RuntimeError(tr("Session data not loaded.", "session_parser_error"))
        return self.json_data

    def get_enriched_tabs_and_groups(self):
        if self.json_data is None:
            raise RuntimeError(tr("Session data not loaded.", "session_parser"))

        windows = self.json_data.get('windows', [])
        enriched_tabs = []
        groups = {}
        all_groups = []

        for window in windows:
            group_defs = window.get("groups", [])
            all_groups.extend(group_defs)
            
            for group in group_defs:
                gid = group.get("id")
                gname = group.get("name", f"{tr('Group', 'session_parser')} {gid}")

                if gid:
                    groups[gid] = gname
                
            tabs = window.get('tabs', [])
            for tab in tabs:
                entries = tab.get('entries', [])
                if not entries:
                    continue

                current_entry = entries[tab.get('index', 1) - 1]  # index is 1-based
                url = current_entry.get('url', '')
                uuid = current_entry.get("docshellUUID", "").replace("{", "").replace("}", "")
                title = current_entry.get('title', tr("Without Title", "session_parser"))
                favicon = tab.get('image', '')
                group_id = tab.get('groupId', None)
                group_name = groups.get(group_id, tr("Ungrouped", "session_parser"))
                url_hash = generate_url_hash(url) if url else None
                domain = extract_domain(url) if url else None
                pinned = tab.get('pinned', False)
                hidden = tab.get('hidden', False)
                
                enriched_tabs.append({
                    'title': title,
                    'url': url,
                    'uuid': uuid,
                    'url_hash': url_hash,
                    'favicon': favicon,
                    'domain': domain,
                    'group_id': group_id,
                    'group_name': group_name,
                    'window_index': windows.index(window),
                    'pinned': pinned,
                    'hidden': hidden,
                    'last_accessed': tab.get('lastAccessed', 0),
                    'status': 'active',
                    'raw_tab': tab
                })

        self.enriched_tabs = enriched_tabs
        self.group_map = groups
        self.group_infos = all_groups
        return enriched_tabs, groups, all_groups

    def get_extra_tabs_data(self):
        """
        Extrahiert alle geschlossenen Tabs, Gruppen und Fenster aus der Session.
        """
        if not self.json_data:
            raise RuntimeError(tr("No data are loaded", "session_parser"))

        closed_data = {
            'closed_tabs': [],
            'closed_groups': [],
            'closed_windows': [],
            'saved_groups': [],
            'counting_tabs': []  # For statistics
        }

        windows = self.json_data.get("windows", [])
        self.err_count = 0
        # Geschlossene Tabs und Gruppen aus aktiven Fenstern
        for window_idx, window in enumerate(windows):
            # Geschlossene Tabs im Fenster
            closed_tabs = window.get("_closedTabs", [])
            for closed_tab in closed_tabs:
                processed_tab = self._process_extra_tab_data(
                    closed_tab,
                    "closed_tab",
                    window_index=window_idx,
                    closed_at=closed_tab.get("closedAt", 0),
                    pinned=closed_tab.get("pinned", False),
                    hidden=closed_tab.get("hidden", False)
                )
                if processed_tab is not None:
                    closed_data['closed_tabs'].append(processed_tab)
                    closed_data['counting_tabs'].append(processed_tab)

            # Geschlossene Gruppen im Fenster
            closed_groups = window.get("closedGroups", [])
            for closed_group in closed_groups:
                group_id = closed_group.get("id", "")
                group_name = closed_group.get("name", f"Group {group_id}")
                group_color = closed_group.get("color", "")
                closed_at = closed_group.get("closedAt", 0)
                # Tabs in der geschlossenen Gruppe
                group_tabs = []
                for tab in closed_group.get("tabs", []):
                    processed_tab = self._process_extra_tab_data(
                        tab,
                        "closed_tab_in_group",
                        window_index=window_idx,
                        closed_at=tab.get("closedAt", closed_at),
                        group_name=group_name,
                        pinned=tab.get("pinned", False),
                        hidden=tab.get("hidden", False)
                    )
                    if processed_tab is not None:
                        group_tabs.append(processed_tab)
                        closed_data['counting_tabs'].append(processed_tab)


                processed_group = {
                    "type": "closed_group",
                    "window_index": window_idx,
                    "id": group_id,
                    "name": group_name,
                    "color": group_color,
                    "closed_at": closed_at,
                    "tabs": group_tabs
                }

                closed_data['closed_groups'].append(processed_group)

        # Geschlossene Fenster
        closed_windows = self.json_data.get("_closedWindows", [])
        for closed_window in closed_windows:
            closed_at = closed_window.get("closedAt", 0)
            # Gruppen aus dem geschlossenen Fenster für Namensauflösung
            window_groups_map = {}
            for group in closed_window.get("groups", []):
                gid = group.get("id", "")
                name = group.get("name", f"Group {gid}")
                if gid:
                    window_groups_map[gid] = name

            # Tabs im geschlossenen Fenster
            window_tabs = []
            for tab in closed_window.get("tabs", []):
                group_id = tab.get("groupId", "")

                processed_tab = self._process_extra_tab_data(
                    tab,
                    "closed_window_tab",
                    closed_at=closed_at,
                    group_name=window_groups_map.get(group_id,
                                                     tr("Ungrouped", "session_parser")) if group_id else tr(
                        "Ungrouped", "session_parser"),
                    pinned=tab.get("pinned", False),
                    hidden=tab.get("hidden", False)
                )
                if processed_tab is not None:
                    window_tabs.append(processed_tab)
                    closed_data['counting_tabs'].append(processed_tab)

            # Gruppen im geschlossenen Fenster
            window_groups = []
            for group in closed_window.get("groups", []):
                processed_group = {
                    "type": "closed_window_group",
                    "id": group.get("id", ""),
                    "name": group.get("name", ""),
                    "color": group.get("color", "")
                }
                window_groups.append(processed_group)

            # Geschlossene Tabs im geschlossenen Fenster
            window_closed_tabs = []
            for closed_tab in closed_window.get("_closedTabs", []):
                processed_tab = self._process_extra_tab_data(
                    closed_tab,
                    "closed_window_closed_tab",
                    closed_at=closed_tab.get("closedAt", closed_at),
                    source_window_id=closed_tab.get("sourceWindowId", ""),
                    group_name=window_groups_map.get(group_id,
                                                     tr("Ungrouped", "session_parser")) if group_id else tr(
                        "Ungrouped", "session_parser"),
                    pinned=closed_tab.get("pinned", False),
                    hidden=closed_tab.get("hidden", False)
                )
                if processed_tab is not None:
                    window_closed_tabs.append(processed_tab)
                    closed_data['counting_tabs'].append(processed_tab)

            # Geschlossene Gruppen im geschlossenen Fenster
            window_closed_groups = []
            for closed_group in closed_window.get("closedGroups", []):
                group_id = closed_group.get("id", "")
                group_name = closed_group.get("name", f"Group {group_id}")
                group_color = closed_group.get("color", "")
                closed_at_group = closed_group.get("closedAt", closed_at)

                # Tabs in der geschlossenen Gruppe des geschlossenen Fensters
                closed_group_tabs = []
                for tab in closed_group.get("tabs", []):
                    processed_tab = self._process_extra_tab_data(
                        tab,
                        "closed_window_closed_group_tab",
                        closed_at=tab.get("closedAt", closed_at_group),
                        group_name=group_name,
                        pinned=tab.get("pinned", False),
                        hidden=tab.get("hidden", False)
                    )
                    if processed_tab is not None:
                        closed_group_tabs.append(processed_tab)
                        closed_data['counting_tabs'].append(processed_tab)

                processed_closed_group = {
                    "type": "closed_window_closed_group",
                    "id": group_id,
                    "name": group_name,
                    "color": group_color,
                    "closed_at": closed_at_group,
                    "tabs": closed_group_tabs
                }
                window_closed_groups.append(processed_closed_group)

            processed_window = {
                "type": "closed_window",
                "closed_at": closed_at,
                "tabs": window_tabs,
                "groups": [{"id": gid, "name": name, "color": ""} for gid, name in window_groups_map.items()],
                "closed_tabs": window_closed_tabs,
                "closed_groups": window_closed_groups
            }

            closed_data['closed_windows'].append(processed_window)

        # Gespeicherte Gruppen
        saved_groups = self.json_data.get("savedGroups", [])
        for saved_group in saved_groups:
            group_id = saved_group.get("id", "")
            group_name = saved_group.get("name", f"Saved Group {group_id}")
            group_color = saved_group.get("color", "")

            # Tabs in der gespeicherten Gruppe verarbeiten
            saved_tabs = []
            for tab in saved_group.get("tabs", []):
                processed_tab = self._process_extra_tab_data(
                    tab,
                    "saved_group_tab",
                    default_group_id=group_id,
                    group_name=group_name,
                )
                if processed_tab is not None:
                    saved_tabs.append(processed_tab)
                    closed_data['counting_tabs'].append(processed_tab)

            processed_group = {
                "type": "saved_group",
                "id": group_id,
                "name": group_name,
                "color": group_color,
                "tabs": saved_tabs,
                "collapsed": saved_group.get("collapsed", False)
            }
            closed_data['saved_groups'].append(processed_group)

        return closed_data

    def _process_extra_tab_data(self, tab, tab_type, **kwargs):
        """
        Helper-Methode zur Verarbeitung von Tab-Daten.
        Gibt None zurück wenn die Daten ungültig sind.
        """

        # Basis-Daten extrahieren
        if tab_type in ["closed_tab", "closed_tab_in_group"]:
            state = tab.get("state", {})
            entries = state.get("entries", [])
            image_fallback = tab.get("image", "")
            image = state.get("image", image_fallback)
            last_accessed = state.get("lastAccessed", 0)
            group_id = state.get("groupId", "")
        elif tab_type in ["saved_group_tab"]:
            state = tab.get("state", {})
            entries = state.get("entries", [])
            image = tab.get("image", "")
            last_accessed = tab.get("lastAccessed", 0)
            group_id = tab.get("groupId", kwargs.get("default_group_id", ""))
        elif tab_type in ["closed_window_tab"]:
            entries = tab.get("entries", [])
            last_accessed = tab.get("lastAccessed", 0)
            image = tab.get("image", "")
            group_id = tab.get("groupId", "")
        else:  # closed_window_* types
            state = tab.get("state", {})
            image_fallback = tab.get("image", "")
            entries = state.get("entries", [])
            image = state.get("image", image_fallback)
            last_accessed = state.get("lastAccessed", 0)
            group_id = state.get("groupId", "")
        

        # Validierung der entries
        if not isinstance(entries, list) or not entries:
            self.logger.warning(f"{tr('Tab with no entries found, skipping', 'warning')}: {tab_type}")
            self.logger.debug(f"Tab Data: \n {pprint.pformat(tab)}")
            self.err_count += 1
            return None

        last_entry = entries[-1]
        if not isinstance(last_entry, dict):
            self.logger.error(f"({tr('Unexpected type for last entry', 'error')}): {type(last_entry).__name__}")
            self.err_count += 1
            return None

        # Basis-Tab-Objekt erstellen
        processed_tab = {
            "type": tab_type,
            "last_accessed": last_accessed,
            "image": image,
            "group_id": group_id,
            "entries": entries,
            "title": last_entry.get("title", tr("Without Title", "session_parser")),
            "url": last_entry.get("url", ""),
            "domain": extract_domain(last_entry.get("url", "")),
            "url_hash": generate_url_hash(last_entry.get("url", ""))
        }

        # Optionale Felder hinzufügen
        if "window_index" in kwargs:
            processed_tab["window_index"] = kwargs["window_index"]
        if "closed_at" in kwargs:
            processed_tab["closed_at"] = kwargs["closed_at"]
        if "group_name" in kwargs:
            processed_tab["group_name"] = kwargs["group_name"]
        if "source_window_id" in kwargs:
            processed_tab["source_window_id"] = kwargs["source_window_id"]
        if "pinned" in kwargs:
            processed_tab["pinned"] = kwargs["pinned"]
        if "hidden" in kwargs:
            processed_tab["hidden"] = kwargs["hidden"]

        return processed_tab
    
    def sync_enriched_to_raw(self):
        if not self.enriched_tabs or not self.json_data:
            return

        # For planned "Pending Changes" implementation: Check if status is not "delete
        active_tabs = [etab for etab in self.enriched_tabs if etab["status"] != "delete"]
        
        for window in self.json_data.get("windows", []):
            window["tabs"] = []

        for etab in active_tabs:
            window_index = etab.get("window_index")
            if 0 <= window_index < len(self.json_data["windows"]):
                window = self.json_data["windows"][window_index]
                window["tabs"].append(etab["raw_tab"])
        
        for etab in active_tabs:
            raw_tab = etab.get("raw_tab")
            if not raw_tab:
                continue
            entries = raw_tab.get("entries", [])
            if entries:
                entries[-1]["title"] = etab["title"]
                entries[-1]["url"] = etab["url"]
            raw_tab["groupId"] = etab.get("group_id", "")
            gid = etab.get("group_id", "")
            gname = etab.get("group_name", "")
            if gid and gname:
                self.group_map[gid] = gname

        for window in self.json_data.get("windows", []):
            groups_list = window.get("groups", [])
            for gdef in groups_list:
                gid = gdef.get("id")
                if gid in self.group_map:
                    gdef["name"] = self.group_map[gid]


    def write_jsonlz4(self):
        import lz4.block
        import json
        magic = b'mozLz40\0'
        json_bytes = json.dumps(self.json_data, ensure_ascii=False).encode('utf-8')
        compressed_data = lz4.block.compress(json_bytes)
        with open(self.session_file_path, 'wb') as f:
            f.write(magic + compressed_data)