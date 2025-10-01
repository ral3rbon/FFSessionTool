import os
import base64
from collections import defaultdict, Counter
from typing import Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap, QFont, QColor
from PySide6.QtWidgets import QTreeWidgetItem

from app.utils import Logger, tr
from app.ui.helpers import COLORS, colored_svg_icon
from app.ui.helpers.ui_icon_loader import load_icon


class SessionPopulator:
    """Service class for populating UI elements with session data"""
    
    def __init__(self, favicon_cache: Dict[str, QIcon], cache_dir_favicon: str, icon_default_tab: QIcon):
        self.logger = Logger.get_logger("Session_Populator_Error")
        self.favicon_cache = favicon_cache
        self.cache_dir_favicon = cache_dir_favicon
        self.icon_default_tab = icon_default_tab
    
    def populate_session_tree(self, session_widget, tabs: List[Dict], group_list: List[Dict], file_path: str) -> List[Dict]:
        """
        Populate the session tree widget with tabs and groups
        
        Returns:
            List of window data for multi-window sessions
        """
        try:
            session_widget.setHeaderLabel(f"{file_path} ({len(tabs)} {tr('Tabs', 'main')})")
            session_widget.clear()

            group_map = {group['id']: group for group in group_list} if group_list else {}

            window_count = len(set(t.get("window_index") for t in tabs))
            multi_window = window_count > 1
            window_data = []
            
            # Organize data by windows
            windows_map = defaultdict(list)
            windows_group_counts = {}
            windows_tab_counts = {}
            
            for tab in tabs:
                win_idx = tab["window_index"]
                gid = tab.get("group_id", None)
                group_data = group_map.get(gid, {})
                gname = group_data.get("name", "Ungrouped")
                windows_group_counts.setdefault(win_idx, Counter())[gname] += 1
                windows_tab_counts[win_idx] = windows_tab_counts.get(win_idx, 0) + 1
                windows_map[win_idx].append(tab)
            
            # Create window structure
            for win_idx in sorted(set(t["window_index"] for t in tabs)):
                win_item = self._create_window_item(
                    session_widget, win_idx, multi_window, 
                    windows_group_counts, windows_tab_counts, windows_map
                )
                
                if multi_window:
                    first_tab_title = windows_map[win_idx][0].get("title", f"Window {win_idx+1}")
                    window_data.append({"index": win_idx, "title": first_tab_title})
                
                # Create groups and populate with tabs
                self._populate_groups_and_tabs(
                    win_item, windows_map[win_idx], group_map, group_list, 
                    windows_group_counts[win_idx], multi_window, session_widget
                )
            
            # Expand all top-level items
            for i in range(session_widget.topLevelItemCount()):
                session_widget.topLevelItem(i).setExpanded(True)

            return window_data
            
        except Exception as e:
            self.logger.error(f"({tr('Error populating session tree', 'session_populator')}): {e} |#| ({type(e).__name__})", exc_info=True)
            raise
    
    def _create_window_item(self, session_widget, win_idx: int, multi_window: bool, 
                           windows_group_counts: Dict, windows_tab_counts: Dict, 
                           windows_map: Dict):
        """Create window item for multi-window sessions"""
        if multi_window:
            win_label = f"{tr('Window', 'main')} {win_idx + 1} ({len(windows_group_counts[win_idx])} G / {windows_tab_counts[win_idx]} T)"
            win_item = QTreeWidgetItem(session_widget, [win_label])
            win_item.setIcon(0, load_icon("app-window"))
            win_item.setData(0, Qt.UserRole, {"type": "window", "window_index": win_idx})
            return win_item
        else:
            return session_widget
    

    def _populate_groups_and_tabs(self, parent_item, tabs: List[Dict], group_map: Dict, 
                                 group_list: List[Dict], group_counts: Counter, 
                                 multi_window: bool, session_widget):
        """Populate groups and tabs under a parent item"""
        group_items_list = {}
        
        # Track which special groups we actually need
        has_pinned = any(tab.get("pinned", False) for tab in tabs)
        has_hidden = any(tab.get("hidden", False) for tab in tabs)
        
        # Calculate ungrouped tabs that are NOT pinned or hidden
        ungrouped_tabs = [tab for tab in tabs 
                         if (tab.get("group_id") is None or 
                             group_map.get(tab.get("group_id"), {}).get("name", "Ungrouped") == "Ungrouped")
                         and not tab.get("pinned", False) 
                         and not tab.get("hidden", False)]
        has_ungrouped = len(ungrouped_tabs) > 0
        
        # Add special groups in the correct order: Pinned -> Hidden -> Ungrouped
        if has_pinned:
            pinned_count = sum(1 for tab in tabs if tab.get("pinned", False))
            pinned_group = self._create_special_group_item("pinned", pinned_count)
            if multi_window:
                parent_item.addChild(pinned_group)
            else:
                session_widget.addTopLevelItem(pinned_group)
            group_items_list["__pinned__"] = pinned_group
        
        if has_hidden:
            hidden_count = sum(1 for tab in tabs if tab.get("hidden", False))
            hidden_group = self._create_special_group_item("hidden", hidden_count)
            if multi_window:
                parent_item.addChild(hidden_group)
            else:
                session_widget.addTopLevelItem(hidden_group)
            group_items_list["__hidden__"] = hidden_group
        
        if has_ungrouped:
            ungrouped_count = len(ungrouped_tabs)
            ungrouped_group = self._create_special_group_item("ungrouped", ungrouped_count)
            if multi_window:
                parent_item.addChild(ungrouped_group)
            else:
                session_widget.addTopLevelItem(ungrouped_group)
            group_items_list["__ungrouped__"] = ungrouped_group
        
        # Add regular groups (all except "Ungrouped")
        for gname, count in group_counts.items():
            if gname == "Ungrouped":
                continue 
                
            group_item = self._create_group_item(gname, count, group_map, group_list)
            
            if multi_window:
                parent_item.addChild(group_item)
            else:
                session_widget.addTopLevelItem(group_item)
            
            group_items_list[gname] = group_item
        
        # Populate tabs into appropriate groups
        for tab in tabs:
            tab_item = self._create_tab_item(tab)
            
            # Check for special tab types first
            if tab.get("pinned", False):
                if "__pinned__" in group_items_list:
                    group_items_list["__pinned__"].addChild(tab_item)
                    self._apply_pinned_styling(tab_item)
                continue
                
            if tab.get("hidden", False):
                if "__hidden__" in group_items_list:
                    group_items_list["__hidden__"].addChild(tab_item)
                    self._apply_hidden_styling(tab_item)
                continue
            
            # Regular grouped/ungrouped tabs
            gid = tab.get("group_id", None)
            group_info = group_map.get(gid, {})
            gname = group_info.get("name", "Ungrouped")
            
            # Handle ungrouped tabs specially
            if gname == "Ungrouped":
                if "__ungrouped__" in group_items_list:
                    group_items_list["__ungrouped__"].addChild(tab_item)
            else:
                if gname in group_items_list:
                    group_items_list[gname].addChild(tab_item)


    
    def _create_special_group_item(self, group_type: str, count: int) -> QTreeWidgetItem:
        """Create a special group item with proper count and styling"""
        if group_type == "pinned":
            label = f"{tr('Pinned Tabs', 'main')} ({count} {tr('Tab', 'main') if count == 1 else tr('Tabs', 'main')})"
            icon_name = "pinned"
            icon_name_open = "pinned"
        elif group_type == "hidden":
            label = f"{tr('Hidden Tabs', 'main')} ({count} {tr('Tab', 'main') if count == 1 else tr('Tabs', 'main')})"
            icon_name = "eye-dotted"
            icon_name_open = "eye-dotted"
        elif group_type == "ungrouped":
            label = f"{tr('Ungrouped', 'main')} ({count} {tr('Tab', 'main') if count == 1 else tr('Tabs', 'main')})"
            icon_name = "folder-outline"
            icon_name_open = "folder-open"
        else:
            label = f"{group_type} ({count})"
            icon_name = "folder"
        
        group_item = QTreeWidgetItem([label])
        group_item.setIcon(0, load_icon(icon_name))
        group_item.setData(0, Qt.UserRole, {"type": "special_group", "group_type": group_type})
        
        # Store icon paths for expand/collapse functionality (special groups keep same icon)
        group_item.setData(0, Qt.UserRole + 2, f"assets/icons/{icon_name}.svg")  # Collapsed icon
        group_item.setData(0, Qt.UserRole + 3, f"assets/icons/{icon_name_open}.svg")  # Expanded icon (same)
        
        return group_item
    
    def _create_group_item(self, gname: str, count: int, group_map: Dict, group_list: List[Dict]) -> QTreeWidgetItem:
        """Create a group item with proper styling and icons"""
        group_label = f"{gname} ({count} {tr('Tab', 'main') if count == 1 else tr('Tabs', 'main')})"
        group_item = QTreeWidgetItem([group_label])
        
        if gname == "Ungrouped":
            group_item.setIcon(0, load_icon("folder-outline"))
        else:
            group_data = next((g for g in group_list if g['name'] == gname), None)
            
            if group_data and group_data.get("color") in COLORS:
                color = COLORS[group_data.get("color")]
                colored_icon = colored_svg_icon("assets/icons/folder.svg", color)
                group_item.setIcon(0, colored_icon)
                group_item.setData(0, Qt.UserRole + 1, color)
            else:
                group_item.setIcon(0, load_icon("folder"))
            
            group_item.setData(0, Qt.UserRole + 2, "assets/icons/folder.svg")
            group_item.setData(0, Qt.UserRole + 3, "assets/icons/folder-open.svg")
            group_item.setData(0, Qt.UserRole, {
                "type": "group", 
                "group_name": gname, 
                "group_id": group_data.get("id") if group_data else None
            })
        
        return group_item
    
    def _create_tab_item(self, tab_data: Dict) -> QTreeWidgetItem:
        """Create a tab item with all associated data"""
        tab_item = QTreeWidgetItem([tab_data.get('title', tr("No Title", "main"))])
        
        # Set favicon
        domain = tab_data.get("domain", "")
        url = tab_data.get("url", "")
        favicon = tab_data.get("favicon", None)
        tab_item.setIcon(0, self._get_favicon_icon(domain, url, favicon))
        
        # Store data in UserRole
        item_data = self._prepare_tab_data(tab_data)
        tab_item.setData(0, Qt.UserRole, item_data)
        
        return tab_item
    
    def _prepare_tab_data(self, tab_data: Dict) -> Dict:
        """Prepare tab data for storage in QTreeWidgetItem"""
        extracted_data = tab_data.get("db_tags", [])
        item_data = tab_data.copy()
        
        item_data.update({
            'type': 'tab_item',
            'data_entries': [],
            'filterable_values': []
        })
        
        if extracted_data:
            filterable_values = []
            for entry in extracted_data:
                if entry.get('is_filter', False):
                    for value in entry.get('values', []):
                        clean_value = value.strip().lower()
                        filterable_values.append(clean_value)
            
            item_data['data_entries'] = extracted_data
            item_data['filterable_values'] = filterable_values
        
        return item_data
    
    def _apply_pinned_styling(self, tab_item: QTreeWidgetItem):
        """Apply visual styling for pinned tabs"""
        font = tab_item.font(0)
        font.setBold(True)
        tab_item.setFont(0, font)
    
    def _apply_hidden_styling(self, tab_item: QTreeWidgetItem):
        """Apply visual styling for hidden tabs"""
        font = tab_item.font(0)
        font.setItalic(True)
        tab_item.setFont(0, font)
    
    def _get_favicon_icon(self, domain: str, url: str, favicon: Optional[str]) -> QIcon:
        """Get favicon icon for a tab"""
        if not url.startswith("http://") and not url.startswith("https://"):
            return self.icon_default_tab
        
        if not domain:
            return self.icon_default_tab
        
        if domain in self.favicon_cache:
            return self.favicon_cache[domain]
        
        cache_file = os.path.join(self.cache_dir_favicon, f"{domain}.png")
        
        if os.path.exists(cache_file):
            try:
                pixmap = QPixmap(cache_file)
                icon = QIcon(pixmap)
                self.favicon_cache[domain] = icon
                return icon
            except Exception as e:
                self.logger.warning(f"({tr('Failed to load cached favicon for', 'session_populator')}) {domain}: {e}|#| ({type(e).__name__})", exc_info=True)
        
        if favicon and favicon.startswith("data:image"):
            try:
                base64_string = favicon.split(",")[1]
                decoded_data = base64.b64decode(base64_string)
                
                pixmap = QPixmap()
                if pixmap.loadFromData(decoded_data):
                    # Skaliere nur, wenn größer als 32x32 (nur verkleinern, nicht vergrößern)
                    if pixmap.width() > 32 or pixmap.height() > 32:
                        pixmap = pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    
                    # Speichere das (skalierte) Pixmap als PNG (nur einmal)
                    os.makedirs(self.cache_dir_favicon, exist_ok=True)
                    pixmap.save(cache_file, "PNG")
                    
                    icon = QIcon(pixmap)
                    self.favicon_cache[domain] = icon
                    return icon
                else:
                    self.logger.warning(f"({tr('Failed to load pixmap from base64 data for', 'session_populator')}) {domain}")
            except Exception as e:
                self.logger.warning(f"({tr('Error processing favicon for', 'session_populator')}) {domain}: {e} |#| ({type(e).__name__})", exc_info=True)
        
        return self.icon_default_tab
    
    def populate_closed_tabs(self, closed_session_widget, closed_tabs_data, format_timestamp_func):
        """Populate the closed tabs tree view"""

        #TODO: Check for reorder the list: Closed Window -> Closed Groups AND Closed Tabs. (check json data if it is possible)
        # For now every "combinantion" is displayed seperately

        if not closed_tabs_data:
            return

        closed_session_widget.clear()

        # Closed Windows
        if closed_tabs_data['closed_windows']:
            closed_windows_item = QTreeWidgetItem(closed_session_widget,
                                                  [f"{tr('Closed Windows', 'ClosedTabs')} ({len(closed_tabs_data['closed_windows'])})"])
            closed_windows_item.setIcon(0, load_icon("app-window"))

            for window in closed_tabs_data['closed_windows']:
                closed_at = format_timestamp_func(window.get('closed_at', 0))
                window_item = QTreeWidgetItem(closed_windows_item,
                                              [f"{tr('Window closed at', 'ClosedTabs')} {closed_at}"])
                window_item.setIcon(0, load_icon("layout-grid"))

                # Check if window has groups
                window_groups = window.get('groups', [])
                window_tabs = window.get('tabs', [])
                window_closed_tabs = window.get('closed_tabs', [])
                window_closed_groups = window.get('closed_groups', [])
                                
                # All tabs in this window (regular + closed)
                all_window_tabs = window_tabs + window_closed_tabs
                
                # Build group map for easy lookup
                group_map = {group.get('id'): group for group in window_groups}
                
                # Process regular groups first (from window.groups)
                if window_groups:
                    # Organize tabs by group_id
                    tabs_by_group = {}
                    ungrouped_tabs = []
                    
                    for tab in all_window_tabs:
                        tab_group_id = tab.get('group_id')
                        
                        if tab_group_id and tab_group_id in group_map:
                            if tab_group_id not in tabs_by_group:
                                tabs_by_group[tab_group_id] = []
                            tabs_by_group[tab_group_id].append(tab)
                        else:
                            ungrouped_tabs.append(tab)
                    
                    # Display groups and their tabs
                    for group in window_groups:
                        group_id = group.get('id')
                        group_name = group.get('name', tr('Unnamed Group', 'ClosedTabs'))
                        group_color = group.get('color', '')
                        group_tabs = tabs_by_group.get(group_id, [])
                        
                        # Only show groups that have tabs
                        if group_tabs:
                            group_item = QTreeWidgetItem(window_item,
                                                        [f"{group_name} ({len(group_tabs)} {tr('tabs', 'ClosedTabs')})"])
                            
                            # Set group icon with color if available
                            if group_color and group_color in COLORS:
                                color = COLORS[group_color]
                                group_item.setIcon(0, colored_svg_icon("assets/icons/folder.svg", color))
                            else:
                                group_item.setIcon(0, load_icon("folder"))
                            
                            # Store group data
                            group_item.setData(0, Qt.UserRole, {
                                "type": "closed_group",
                                "group_name": group_name,
                                "group_id": group_id,
                                "color": group_color
                            })
                            
                            # Add tabs to group
                            for tab in group_tabs:
                                tab_item = self._create_closed_tab_item(tab, group_item, format_timestamp_func)
                    
                    # Display ungrouped tabs if any exist
                    
                    if ungrouped_tabs:
                        ungrouped_item = QTreeWidgetItem(window_item,
                                                        [f"{tr('Ungrouped', 'ClosedTabs')} ({len(ungrouped_tabs)} {tr('tabs', 'ClosedTabs')})"])
                        ungrouped_item.setIcon(0, load_icon("folder-outline"))
                        
                        for tab in ungrouped_tabs:
                            tab_item = self._create_closed_tab_item(tab, ungrouped_item, format_timestamp_func)
                
                # Process closed groups (these are complete groups with their own tabs)
                if window_closed_groups:
                    for closed_group in window_closed_groups:
                        group_name = closed_group.get('name', tr('Unnamed Group', 'ClosedTabs'))
                        group_color = closed_group.get('color', '')
                        group_tabs = closed_group.get('tabs', [])
                        closed_at = format_timestamp_func(closed_group.get('closed_at', 0))
                        
                        group_item = QTreeWidgetItem(window_item,
                                                    [f"{group_name} - {tr('closed at', 'ClosedTabs')} {closed_at} ({len(group_tabs)} {tr('tabs', 'ClosedTabs')})"])
                        
                        # Set group icon with color if available
                        if group_color and group_color in COLORS:
                            color = COLORS[group_color]
                            group_item.setIcon(0, colored_svg_icon("assets/icons/folder.svg", color))
                        else:
                            group_item.setIcon(0, load_icon("folder-cancel"))
                        
                        # Add tabs to closed group
                        for tab in group_tabs:
                            tab_item = self._create_closed_tab_item(tab, group_item, format_timestamp_func)
                
                # Fallback: if no structure, display all tabs directly
                if not window_groups and not window_closed_groups and (window_tabs or window_closed_tabs):
                    if window_tabs:
                        tabs_item = QTreeWidgetItem(window_item,
                                                    [f"{tr('Tabs', 'ClosedTabs')} ({len(window_tabs)})"])
                        tabs_item.setIcon(0, load_icon("label-off"))

                        for tab in window_tabs:
                            tab_item = self._create_closed_tab_item(tab, tabs_item, format_timestamp_func)
        
        # Closed Groups from active windows
        if closed_tabs_data['closed_groups']:
            closed_groups_item = QTreeWidgetItem(closed_session_widget,
                                                 [f"{tr('Closed Groups', 'ClosedTabs')} ({len(closed_tabs_data['closed_groups'])})"])
            closed_groups_item.setIcon(0, load_icon("folder-cancel"))

            for group in closed_tabs_data['closed_groups']:
                closed_at = format_timestamp_func(group.get('closed_at', 0))
                group_name = group.get('name', tr('Unnamed Group', 'ClosedTabs'))

                group_item = QTreeWidgetItem(closed_groups_item,
                                             [f"{group_name} - {tr('closed at', 'ClosedTabs')} {closed_at}"])

                if group.get('color') and group['color'] in COLORS:
                    color = COLORS[group['color']]
                    group_item.setIcon(0, colored_svg_icon("assets/icons/folder.svg", color))
                else:
                    group_item.setIcon(0, load_icon("folder"))

                # Tabs in der geschlossenen Gruppe
                for tab in group.get('tabs', []):
                    tab_item = self._create_closed_tab_item(tab, group_item, format_timestamp_func)

        # Closed individual tabs from active windows
        if closed_tabs_data['closed_tabs']:
            closed_tabs_item = QTreeWidgetItem(closed_session_widget,
                                               [f"{tr('Closed Tabs', 'ClosedTabs')} ({len(closed_tabs_data['closed_tabs'])})"])
            closed_tabs_item.setIcon(0, load_icon("label-off"))

            # Group by window
            tabs_by_window = {}
            for tab in closed_tabs_data['closed_tabs']:
                window_idx = tab.get('window_index', 0)
                if window_idx not in tabs_by_window:
                    tabs_by_window[window_idx] = []
                tabs_by_window[window_idx].append(tab)

            for window_idx, tabs in tabs_by_window.items():
                window_item = QTreeWidgetItem(closed_tabs_item,
                                              [f"{tr('Window', 'ClosedTabs')} {window_idx + 1} ({len(tabs)} {tr('tabs', 'ClosedTabs')})"])
                window_item.setIcon(0, load_icon("app-window"))

                for tab in tabs:
                    tab_item = self._create_closed_tab_item(tab, window_item, format_timestamp_func)

        # Saved Groups
        if closed_tabs_data['saved_groups']:
            saved_groups_item = QTreeWidgetItem(closed_session_widget,
                                                [f"{tr('Saved Groups', 'ClosedTabs')} ({len(closed_tabs_data['saved_groups'])})"])
            saved_groups_item.setIcon(0, load_icon("device-floppy"))

            for group in closed_tabs_data['saved_groups']:
                group_name = group.get('name', tr('Unnamed Group', 'ClosedTabs'))
                tab_count = len(group.get('tabs', []))

                # Gruppenname mit Tab-Anzahl
                display_text = f"{group_name} ({tab_count} {tr('tabs', 'ClosedTabs')})"

                group_item = QTreeWidgetItem(saved_groups_item, [display_text])

                if group.get('color') and group['color'] in COLORS:
                    color = COLORS[group['color']]
                    group_item.setIcon(0, colored_svg_icon("assets/icons/folder.svg", color))
                else:
                    group_item.setIcon(0, load_icon("folder"))

                # Gruppendaten in UserRole speichern
                group_item.setData(0, Qt.UserRole, group)

                # Tabs in der gespeicherten Gruppe hinzufügen
                for tab in group.get('tabs', []):
                    tab_item = self._create_closed_tab_item(tab, group_item, format_timestamp_func)

        # Expand all
        closed_session_widget.expandAll()

    def _create_closed_tab_item(self, tab, parent_item, format_timestamp_func):
        """Erstellt ein TreeWidgetItem für einen geschlossenen Tab"""
        title = tab.get('title', tr('No Title', 'ClosedTabs'))
        tab_type = tab.get('type', '')

        if tab_type == 'saved_group_tab':
            timestamp = format_timestamp_func(tab.get('last_accessed', 0))
            time_label = tr('last accessed', 'ClosedTabs') if timestamp else ""
        else:
            timestamp = format_timestamp_func(tab.get('closed_at', 0))
            time_label = tr('closed', 'ClosedTabs') if timestamp else ""

        # Basis-Titel
        display_text = f"{title}"

        if tab.get('pinned', True) and not tab_type == 'saved_group_tab':
            display_text = f"📍 {display_text}"
        elif tab.get('hidden', True) and not tab_type == 'saved_group_tab':
            display_text = f"👁️ {display_text}"

        # Vollständiger Titel mit Status und Zeitstempel
        display_text = f"{display_text}"
        if timestamp and time_label:
            display_text += f" - {time_label} {timestamp}"

        tab_item = QTreeWidgetItem(parent_item, [display_text])

        # Spezielle Styling für versteckte Tabs
        if tab.get('hidden', False):
            self._apply_hidden_styling(tab_item)
            # Etwas transparenter erscheinen lassen
            tab_item.setForeground(0, QColor(128, 128, 128))

        # Spezielle Styling für gepinnte Tabs
        if tab.get('pinned', False):
            self._apply_pinned_styling(tab_item)

        # Icon setzen (Favicon wenn vorhanden)
        domain = tab.get('domain', '')
        url = tab.get('url', '')
        favicon = tab.get('image', '')

        if domain and url:
            tab_item.setIcon(0, self._get_favicon_icon(domain, url, favicon))
        else:
            # For now only if favicon isn't available, set special icons - maybe remove this for Closed Tabs... and only mark in the title 📍
            # (Impossible to sort because of the amount of combinations [closed tab, closed tab in closed window, closed group in window, and so on])
            if tab.get('pinned', False):
                tab_item.setIcon(0, load_icon("pinned"))
            elif tab.get('hidden', False):
                tab_item.setIcon(0, load_icon("eye-off"))
            else:
                tab_item.setIcon(0, load_icon("label"))

        # Tab-Daten in UserRole speichern
        tab_item.setData(0, Qt.UserRole, tab)

        return tab_item
