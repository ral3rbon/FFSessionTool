import os
import re
import traceback
import webbrowser
import json
import base64                       # for encoding favicons and history entries
import shutil                       # for copying session files


from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import defaultdict, Counter
from urllib.parse import urlparse
from shiboken6 import isValid       #only for "_apply_chip_filter"

from PySide6.QtCore import Qt, QUrl, QThread, QTimer, Slot, QMetaObject, QBuffer, QIODevice, QSize, QRect, QByteArray, QCoreApplication, QPoint, QMargins, QEvent
from PySide6.QtGui import QPixmap, QIcon, QFont, QColor, QPainter
from PySide6.QtSvgWidgets import QSvgWidget
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFrame, QMenuBar, QGroupBox, QLayout, QTableWidgetItem, QInputDialog,
    QPushButton, QMenu, QLabel, QCheckBox, QComboBox, QListWidgetItem, QSplitter, QTableWidget, QHeaderView,
    QSpacerItem, QSizePolicy, QFileDialog, QLineEdit, QFormLayout, QScrollArea, QTreeWidget, QTabWidget,
    QTreeWidgetItem, QTreeWidgetItemIterator, QListWidget, QDialog, QMessageBox, QApplication, QPlainTextEdit,
    QProgressBar
)

import pprint
from sqlite3 import OperationalError
from app.utils.db_handler import DBHandler
#from app.utils import Logger, tr, find_firefox_profiles, create_backup_dir
from app.utils import Logger, tr, UtilsHelper
from app.ui.helpers import get_theme_color_hex, StatusBar, StatusButton, COLORS, GUI_COLORS, get_color, get_color_hex, colored_svg_icon
from app.ui.helpers.ui_themes import theme_manager, is_dark_mode
from app.ui.helpers.ui_icon_loader import load_icon
from app.ui.dialogs import OpenRecentProjectFileDialog, FFProfileSelectionDialog, FileSelectionDialog, ExportBookmarksDialog, TitleCleanerDialog, GroupEditor
from app.ui._ui_left_column import LeftColumnWidget
from app.ui._ui_center_column import CenterColumnWidget
from app.ui._ui_right_column import RightColumnWidget
from app.src.session_parser import SessionParser
from app.services.session_loader import SessionLoader, SessionLoadingError
from app.services.session_populator import SessionPopulator
from app.src.session_helpers import SessionHelper
from app.src.bookmark_exporter import BookmarkExporter
try:
    import requests
    from lxml import html
    from app.services.xpath_worker_requests import XPathWorkerRequests
except:
    pass

try:
    from playwright.async_api import async_playwright
    from app.services.xpath_worker_playwright import XPathWorkerPlaywright
except:
    pass

class FFsessionToolMainWindow(QMainWindow):
    def __init__(self, settings, translator, parent=None):
        super().__init__(parent)
        self.logger = Logger.get_logger("MainGUI")
        self.settings = settings
        self.translator = translator

        os.makedirs("user_data", exist_ok=True)
        self.db = DBHandler("user_data/sessions.db")
        
        # Initialize services
        self.session_loader = SessionLoader(self.db)
        self.favicon_cache = {}
        self.cache_dir_favicon = self.settings._settings.value("favicon_cache_dir", "user_data/favicons", type=str)

        # Initialize session and utilshelper - status_bar will be set after UI creation
        self.session_helper = SessionHelper(self.logger, None, self.session_loader, self)
        self.utils_helper = UtilsHelper(self.logger, None, self.session_loader, self)

        # Load default icons
        self.icon_default_tab = load_icon("label")
        
        self.session_populator = SessionPopulator(
            self.favicon_cache, 
            self.cache_dir_favicon, 
            self.icon_default_tab
        )
        
        # Flag um zu verfolgen wann die UI Daten lädt
        self.not_the_human = False
        self.group_id_to_color = {}
        self._main_ui()
        
        # Initialize extracted data renderer after UI is created
        self.data_renderer = self.rcw.get_data_renderer(self.db, self.logger)
        #self.data_renderer.set_refresh_callback(self._refresh_extracted_data)
        #self.data_renderer.set_filter_callback(self._apply_chip_filter)
        
        # Set status_bar reference in helpers after UI is created
        self.session_helper.status_bar = self.status_bar
        self.utils_helper.status_bar = self.status_bar

        self._ui_update_btn_states()
        self.update_theme()
        self._connect_gui_signals()

        self.favicon_cache = {}
        # Hold running workers to prevent GC
        self._workers = set()

    def _main_ui(self):
        self.setWindowTitle("FFSessionTool")
        win_pos_x = (QApplication.primaryScreen().size().width() - 1280) // 2
        win_pos_y = (QApplication.primaryScreen().size().height() - 800) // 2
        self.setGeometry(win_pos_x, win_pos_y, 1280, 800)
        app_mainwindow = QWidget()
        self.setCentralWidget(app_mainwindow)
        
        self.full_layout = QVBoxLayout(app_mainwindow)
        self.full_layout.setContentsMargins(0, 0, 0, 0)
        self.full_layout.setSpacing(0)

        app_content = QWidget()
        self.app_layout = QHBoxLayout(app_content)

        #for not scrolling endless through the ui code -> split into separate files
        self.lcw = LeftColumnWidget()
        
        self.app_splitter = QSplitter(Qt.Horizontal)
        self.app_splitter.addWidget(self.lcw)

        self.ccw = CenterColumnWidget()
        self.app_splitter.addWidget(self.ccw)

        self.right_splitter = QSplitter(Qt.Vertical) 

        self.rcw = RightColumnWidget()
        self.right_splitter.addWidget(self.rcw)
        #self.app_splitter.addWidget(self.right_splitter)
        self.status_bar = StatusBar()

        self.app_layout.addWidget(self.app_splitter) # main splitter -> app_splitter
        self.app_layout.addWidget(self.right_splitter)
        self.full_layout.addWidget(app_content)
        self.full_layout.addWidget(self.status_bar)

        self.status_bar.show_message(tr("Ready", "statusbar"))

    def _ui_update_btn_states(self, file_loaded=False):
        if file_loaded:
            # Left Column
            self.lcw.save_btn.setEnabled(True)
            self.lcw.export_btn.setEnabled(True)
            self.lcw.replace_btn.setEnabled(True)
            self.lcw.dup_title_cb.setEnabled(True)
            self.lcw.dup_url_cb.setEnabled(True)   
            self.lcw.regex_checkbox.setEnabled(True)
            self.lcw.regex_input.setEnabled(True)
            self.lcw.save_regex_btn.setEnabled(True)
            self.lcw.dup_keep_group.setEnabled(True)
            self.lcw.export_bkm_btn.setEnabled(True)
            self.lcw.tc_btn.setEnabled(True)
            self.lcw.ge_btn.setEnabled(True)
            self.lcw.lbi_btn.setEnabled(False) # coming soon...
            self.lcw.ext_url_btn.setEnabled(False) # coming soon...
            self.lcw.xph_edit_rules_btn.setEnabled(True)

            self.ccw.filter_input.setEnabled(True)
            self.ccw.show_closed_tabs_btn.setEnabled(True)

            # Right Column
            self.rcw.xph_scrape_url_btn.setEnabled(True)
            self.rcw.xph_scrape_group_btn.setEnabled(True)
            self.rcw.xph_scrape_window_btn.setEnabled(True)
            self.rcw.image_frame.setVisible(True)
            self.rcw.load_image_button.setEnabled(True)

        else:
            # Left Column
            self.lcw.save_btn.setEnabled(False)
            self.lcw.export_btn.setEnabled(False)
            self.lcw.replace_btn.setEnabled(False)
            self.lcw.dup_title_cb.setEnabled(False)
            self.lcw.dup_url_cb.setEnabled(False)   
            self.lcw.regex_checkbox.setEnabled(False)
            self.lcw.regex_input.setEnabled(False)
            self.lcw.save_regex_btn.setEnabled(False)
            self.lcw.dup_keep_group.setEnabled(False)
            self.lcw.export_bkm_btn.setEnabled(False)
            self.lcw.tc_btn.setEnabled(False)
            self.lcw.ge_btn.setEnabled(False)
            self.lcw.lbi_btn.setEnabled(False)
            self.lcw.ext_url_btn.setEnabled(False)
            self.lcw.xph_edit_rules_btn.setEnabled(False)

            # Center Column
            self.ccw.filter_input.setEnabled(False)
            self.ccw.show_closed_tabs_btn.setEnabled(False)

            # Right Column
            self.rcw.xph_scrape_url_btn.setEnabled(False)
            self.rcw.xph_scrape_group_btn.setEnabled(False)
            self.rcw.xph_scrape_window_btn.setEnabled(False)
            self.rcw.image_frame.setVisible(False)
            self.rcw.load_image_button.setEnabled(False)

    def _connect_gui_signals(self):
        ### Signals  ###
        self.ccw.session_widget.itemSelectionChanged.connect(self._on_session_item_selected)
        self.ccw.session_widget.itemExpanded.connect(self._on_item_expanded)
        self.ccw.session_widget.itemCollapsed.connect(self._on_item_collapsed)
        # self.ccw.closed_session_widget.itemSelectionChanged.connect(self._on_closed_tree_item_selected) #? aktuell den "normalen" nehmen, oder besondere Werkzeuge zur verfügung stellen? (Exportieren etc.)?
        self.ccw.show_closed_tabs_btn.toggled.connect(self.toggle_closed_tabs_view)
        # 
        self.lcw.load_btn.clicked.connect(self.open_recent_files_dialog)
        self.lcw.import_btn.clicked.connect(self.copy_profile_session)
        self.lcw.save_btn.clicked.connect(self.save_session_changes)
        self.lcw.export_btn.clicked.connect(self.utils_helper.export_as_json)
        self.lcw.replace_btn.clicked.connect(self.replace_session)
        self.lcw.settings_btn.clicked.connect(self.open_settings_dialog)
        # 
        self.lcw.dup_title_cb.stateChanged.connect(self.utils_helper.find_duplicates)
        self.lcw.dup_url_cb.stateChanged.connect(self.utils_helper.find_duplicates)
        self.lcw.regex_input.currentTextChanged.connect(self.utils_helper.find_duplicates)
        # self.lcw.save_regex_btn.clicked.connect(self.save_regex)
        self.lcw.dup_keep_group.stateChanged.connect(self.utils_helper.find_duplicates)
        self.lcw.regex_checkbox.stateChanged.connect(self.utils_helper.find_duplicates)
         
        self.lcw.export_bkm_btn.clicked.connect(self.export_bookmarks)
        self.lcw.tc_btn.clicked.connect(self.open_title_cleaner_dialog)
        self.lcw.ge_btn.clicked.connect(self.open_group_editor)
        self.lcw.xph_edit_rules_btn.clicked.connect(self.open_xpath_editor)

        # self.lcw.lbi_btn.clicked.connect(self.open_missing_covers_dialog)
        # self.lcw.ext_url_btn.clicked.connect(self.show_extended_urls) # OLD: "open_extendedurl_list"

        self.ccw.filter_input.textChanged.connect(self.utils_helper.apply_search_filter)
        self.ccw.closed_session_widget.itemSelectionChanged.connect(self._on_closed_item_selected)

        # self.rcw.btn_update_title.clicked.connect(self.fetch_title_from_url)
        self.rcw.title_edit.editingFinished.connect(self.update_data_from_ui)
        self.rcw.url_edit.editingFinished.connect(self.update_data_from_ui)
        self.rcw.group_combo.currentIndexChanged.connect(self.update_data_from_ui)
        # self.rcw.btn_delete.clicked.connect(self.delete_selected_item)

        # self.rcw.xph_scrape_group_btn.clicked.connect(self.xpath_handler.on_process_group_clicked)
        # self.rcw.xph_scrape_window_btn.clicked.connect(self.xpath_handler.on_process_window_clicked)
        self.rcw.xph_scrape_url_btn.clicked.connect(self._on_scrape_current_tab_clicked)
        self.rcw.load_image_button.clicked.connect(self._on_load_images_clicked)

        # Theme change signal
        theme_manager.theme_changed.connect(self.on_theme_changed)

        # self.load_regexes() # Load saved regexes from settingsfile
        pass

    def update_theme(self):
        bg_color = get_theme_color_hex("background")
        text_color = get_theme_color_hex("text")

    def on_theme_changed(self):
        #TODO: Auto Update Theme dosn't work yet
        self.update_theme()

    # == session / UI related functions ==
    def populate_group_and_tabs(self, tabs, group_list):
        try:
            self.session_data = self.session_populator.populate_session_tree(
                self.ccw.session_widget, 
                tabs, 
                group_list, 
                getattr(self, 'current_file_path', 'Unknown')
            )
            
            self.ccw.filter_input.setEnabled(True)
            self.ccw.show_closed_tabs_btn.setEnabled(True)
            
        except Exception as e:
            self.logger.error(f"({tr('Error in populate_group_and_tabs', 'error')}): {e} |#| ({type(e).__name__})", exc_info=True)
            self.status_bar.show_message(tr("Error displaying session data.", "error"), message_type="error")

    def _ui_update_group_combo(self):
        # For colored icons in the group combo box with window organization
        if not hasattr(self, 'group_list') or not self.group_list:
            self.rcw.group_combo.blockSignals(True)
            self.rcw.group_combo.clear()
            self.rcw.group_combo.addItem(tr("Ungrouped", "main"))
            self.rcw.group_combo.blockSignals(False)
            # Initialize empty mapping for consistency
            self.group_to_window_map = {}
            self.combo_index_to_window = {}
            return
        
        self.rcw.group_combo.blockSignals(True)
        self.rcw.group_combo.clear()

        # --- Build groups_by_window with correct window_index for each tab ---
        groups_by_window = {}
        if hasattr(self, 'session_tabs') and self.session_tabs:
            for tab in self.session_tabs:
                window_index = tab.get('window_index', 0)
                group_id = tab.get('group_id')
                if window_index not in groups_by_window:
                    groups_by_window[window_index] = set()
                if group_id:
                    groups_by_window[window_index].add(group_id)
        
        # If no windows found, create at least one default window
        if not groups_by_window:
            groups_by_window[0] = set()
        # --- ENDE Fix ---

        # Convert sets to lists and get group objects
        for window_index in groups_by_window:
            group_objects = []
            for group_id in groups_by_window[window_index]:
                group_info = next((g for g in self.group_list if g.get('id') == group_id), None)
                if group_info:
                    group_info['window_index'] = window_index  # Ensure window_index is set
                    group_objects.append(group_info)
            groups_by_window[window_index] = group_objects

        # Build combo box mapping
        self.group_to_window_map = {}
        self.combo_index_to_window = {}

        # --- Debug: Log mapping keys ---
        debug_mapping_keys = []

        # Sort windows by index for consistent ordering
        for window_index in sorted(groups_by_window.keys()):
            window_groups = groups_by_window[window_index]
            
            # Add window header (non-selectable)
            window_header = f"━━━ {tr('Window', 'main')} {window_index + 1} ━━━"
            self.rcw.group_combo.addItem(window_header)
            # Make window header non-selectable
            model = self.rcw.group_combo.model()
            last_item = model.item(model.rowCount() - 1)
            last_item.setFlags(last_item.flags() & ~Qt.ItemIsEnabled)
            last_item.setData(QFont().bold(), Qt.FontRole)
            
            # Store window index for this header
            self.combo_index_to_window[self.rcw.group_combo.count() - 1] = window_index

            # Add ungrouped option for this window
            ungrouped_display = tr('Ungrouped', 'main')
            self.rcw.group_combo.addItem(load_icon("folder-outline"), ungrouped_display)
            self.combo_index_to_window[self.rcw.group_combo.count() - 1] = window_index
            key_ungrouped = f"W{window_index}_{ungrouped_display}"
            self.group_to_window_map[key_ungrouped] = self.rcw.group_combo.count() - 1
            debug_mapping_keys.append(key_ungrouped)

            # Add groups for this window
            for group in window_groups:
                gname = group['name']
                if group.get("color") in COLORS:
                    color = COLORS[group.get("color")]
                    colored_icon = colored_svg_icon("assets/icons/folder.svg", color, size=16)
                    self.rcw.group_combo.addItem(colored_icon, gname)
                else:
                    self.rcw.group_combo.addItem(load_icon("folder"), gname)
                combo_index = self.rcw.group_combo.count() - 1
                self.combo_index_to_window[combo_index] = window_index
                key_group = f"W{window_index}_{gname}"
                self.group_to_window_map[key_group] = combo_index
                debug_mapping_keys.append(key_group)

            # Add separator between windows (except after last window)
            if window_index != max(groups_by_window.keys()):
                self.rcw.group_combo.insertSeparator(self.rcw.group_combo.count())

        self.rcw.group_combo.blockSignals(False)
        self.logger.info(f"Updated group combo with {len(groups_by_window)} windows")
        self.logger.debug(f"Group-to-window mapping keys: {debug_mapping_keys}")

    def _on_session_item_selected(self):

        selected = self.ccw.session_widget.selectedItems()
        if selected:
            # Clear closed tabs selection without triggering signals
            self.ccw.closed_session_widget.blockSignals(True)
            self.ccw.closed_session_widget.clearSelection()
            self.ccw.closed_session_widget.blockSignals(False)
        

        if not selected:
            self.rcw.clear_details()
            #self.populate_history([])
            self.rcw.btn_delete.setEnabled(False)
            
            self.rcw.xph_scrape_window_btn.setVisible(False)
            self.rcw.xph_scrape_group_btn.setVisible(False)
            self.rcw.xph_scrape_url_btn.setVisible(False)
            self.rcw.load_image_button.setVisible(False)
            self.rcw.image_frame.setVisible(False)
            return
        
        item = selected[0]
        item_data = item.data(0, Qt.UserRole)

        if not self.settings._settings.value("Plugins/xpath_enabled", False, type=bool):
            self.rcw.xpath_buttons_container.setVisible(False)
            self.rcw.image_frame.setVisible(False)
        else:
            self.rcw.xpath_buttons_container.setVisible(True)
            if isinstance(item_data, dict) and item_data.get('type') == 'group':
                self.rcw.xph_scrape_window_btn.setVisible(False)
                self.rcw.xph_scrape_group_btn.setVisible(True)
                self.rcw.xph_scrape_url_btn.setVisible(False)
                self.rcw.load_image_button.setVisible(False)
                self.rcw.image_frame.setVisible(False) # Maybe for previewing 4 images in 2x2 grid?

                self.rcw.btn_delete.setEnabled(False)
                self.rcw.xph_scrape_group_btn.setEnabled(True)
                self.selected_group = item
                self.selected_window = None
            elif isinstance(item_data, dict) and item_data.get('type') == 'window':
                self.rcw.xph_scrape_window_btn.setVisible(True)
                self.rcw.xph_scrape_group_btn.setVisible(False)
                self.rcw.xph_scrape_url_btn.setVisible(False)
                self.rcw.load_image_button.setVisible(False)
                self.rcw.image_frame.setVisible(False) # Maybe for previewing 4 images in 2x2 grid?

                self.rcw.btn_delete.setEnabled(False)
                self.rcw.xph_scrape_window_btn.setEnabled(True)
                self.selected_window = item
                self.selected_group = None
            else:
                self.rcw.xph_scrape_window_btn.setVisible(False)
                self.rcw.xph_scrape_group_btn.setVisible(False)
                self.rcw.xph_scrape_url_btn.setVisible(True)
                self.rcw.load_image_button.setVisible(True)
                self.rcw.image_frame.setVisible(True)

                self.rcw.btn_delete.setEnabled(True)
                self.rcw.xph_scrape_url_btn.setEnabled(True)
                self.selected_group = None
                self.selected_window = None

        if not isinstance(item_data, dict):
            self.rcw.clear_details()
            self.rcw.btn_delete.setEnabled(False)
            return
        

        self.rcw.show_active_tab_info()
        self.not_the_human = True
        self.rcw.title_edit.blockSignals(True)
        self.rcw.url_edit.blockSignals(True)
        self.rcw.group_combo.blockSignals(True)

        self.current_url_hash = item_data.get('url_hash')
        self.current_url = item_data.get('url', '')
        self.current_title = item_data.get('title', '')
        self.current_last_accessed = self._format_timestamp(item_data.get('last_accessed', ''))
        self.current_tab_info = item_data

        group_id = item_data.get('group_id')
        group_name = self.session_groups.get(group_id, tr("Ungrouped", "main"))

        self._ui_update_group_combo()

        if isinstance(item_data, dict) and item_data.get('type') not in ('group', 'window'):
            combo_index = -1
            current_tab_window_index = item_data.get('window_index', 0)
            
            # Check if mapping exists and is properly initialized
            if not hasattr(self, 'group_to_window_map') or not self.group_to_window_map:
                # Fallback: just set to first item (usually "Ungrouped")
                if self.rcw.group_combo.count() > 0:
                    self.rcw.group_combo.setCurrentIndex(0)
            else:
                # Original mapping logic with validation
                if group_name == tr("Ungrouped", "main") or group_id is None:
                    lookup_key = f"W{current_tab_window_index}_{tr('Ungrouped', 'main')}"
                else:
                    lookup_key = f"W{current_tab_window_index}_{group_name}"
                
                combo_index = self.group_to_window_map.get(lookup_key, -1)
                if combo_index >= 0 and combo_index < self.rcw.group_combo.count():
                    self.rcw.group_combo.setCurrentIndex(combo_index)
                    self.logger.debug(f"Set combo to index {combo_index} for group '{group_name}' in window {current_tab_window_index}")
                else:
                    # Fallback: try to find by text or use first item
                    text_index = self.rcw.group_combo.findText(group_name)
                    if text_index >= 0:
                        self.rcw.group_combo.setCurrentIndex(text_index)
                        self.logger.debug(f"Found group '{group_name}' by text at index {text_index}")
                    else:
                        # Last fallback: use first item
                        if self.rcw.group_combo.count() > 0:
                            self.rcw.group_combo.setCurrentIndex(0)
                        self.logger.debug(f"Could not find mapping for '{lookup_key}', using fallback")

        self.rcw.title_edit.setText(self.current_title)
        self.rcw.url_edit.setText(self.current_url)
        self.rcw.last_accessed_label.setText(self.current_last_accessed)
        self.rcw.title_edit.setCursorPosition(0)
        self.rcw.url_edit.setCursorPosition(0)

        # For normal tabs, get the original tab data from 'raw_tab', for closed tabs it's directly in item_data
        raw_tab_data = item_data.get('raw_tab', item_data)
        entries = raw_tab_data.get('entries', [])
        self.populate_history_its(entries)
        
        # Populate debug fields with raw tab data
        self.rcw.populate_debug_fields(raw_tab_data)
        
        # Load extracted data for the current URL
        if self.current_url and hasattr(self, 'data_renderer'):
            tab_id = self.db.get_tab_id_by_url(self.current_url)
            if tab_id:
                stored_data = self.db.load_extracted_data_for_url(self.current_url)
                # Set current context for the renderer
                self.data_renderer.set_current_context(
                    self.current_session_id,
                    self.current_url, 
                    self.current_url_hash,
                    getattr(self, 'current_xpath_rules', [])
                )
                self.data_renderer.render_extracted_data(stored_data)
            else:
                # Clear data if no tab found
                self.data_renderer._clear_data_container()

        # Load and display image for the selected item
        self._load_and_display_image(self.current_url_hash)

        # Entsperre Signale und Reset Flag
        self.rcw.title_edit.blockSignals(False)
        self.rcw.url_edit.blockSignals(False)
        self.rcw.group_combo.blockSignals(False)
        
        # After loading all data, set the flag back to False, so user changes are processed
        self.not_the_human = False

    def _on_closed_item_selected(self):
        """Behandelt die Auswahl eines geschlossenen Tabs"""
        selected = self.ccw.closed_session_widget.selectedItems()
        if selected:
            # Clear session tree selection without triggering signals
            self.ccw.session_widget.blockSignals(True)
            self.ccw.session_widget.clearSelection()
            self.ccw.session_widget.blockSignals(False)

        if not selected:
            self.rcw.clear_details()
            return

        item = selected[0]
        tab_data = item.data(0, Qt.UserRole)

        if not tab_data or not isinstance(tab_data, dict):
            self.rcw.clear_details()
            return

        # Zeige UI für geschlossene Tabs an
        self.rcw.show_closed_tab_info()
        
        # UI lädt gerade neue Daten
        self.not_the_human = True

        # Tab-spezifische Felder anzeigen
        self.rcw.title_edit.blockSignals(True)
        self.rcw.url_edit.blockSignals(True)
        self.rcw.group_combo.blockSignals(True)

        title = tab_data.get('title', '')
        

        status_info = []
        if tab_data.get('pinned', False):
            status_info.append(f"📍 {tr('Pinned', 'main')}")
        if tab_data.get('hidden', False):
            status_info.append(f"👁️ {tr('Hidden', 'main')}")

        if status_info:
            title = f"{' '.join(status_info)} | {title}"

        self.rcw.title_edit.setText(title)
        self.rcw.url_edit.setText(tab_data.get('url', ''))
        self.current_last_accessed = self._format_timestamp(tab_data.get('last_accessed', ''))
        self.rcw.last_accessed_label.setText(f"{self.current_last_accessed}")
        
        self.rcw.title_edit.setCursorPosition(0)
        self.rcw.url_edit.setCursorPosition(0)

        # Modifying closed tab? Why?
        self.rcw.title_edit.setEnabled(False)
        self.rcw.url_edit.setEnabled(False)
        self.rcw.group_combo.setEnabled(False)

        # Setze das "Closed at:" Feld
        closed_at = self._format_timestamp(tab_data.get('closed_at', ''))
        self.rcw.closed_at_label.setText(f"{closed_at}")

        group_name = tab_data.get('group_name', tr("Ungrouped", "Groups"))
        #self.group_combo.setCurrentText(group_name)

        self._ui_update_group_combo()
        # Gruppe setzen falls vorhanden
        combo_index = self.rcw.group_combo.findText(group_name)
        if combo_index >= 0:
            self.rcw.group_combo.setCurrentIndex(combo_index)
        else:
            self.rcw.group_combo.setCurrentText(group_name)
            self.rcw.group_combo.setCurrentIndex(combo_index)

        self.rcw.title_edit.blockSignals(False)
        self.rcw.url_edit.blockSignals(False)
        self.rcw.group_combo.blockSignals(False)

        # History Tab befüllen
        entries = tab_data.get('entries', [])
        self.populate_history_its(entries)
        
        # Populate debug fields with closed tab data
        self.rcw.populate_debug_fields(tab_data)
        
        # Load and display image for the selected closed item (if url_hash available)
        url_hash = tab_data.get('url_hash')
        if url_hash:
            self._load_and_display_image(url_hash)
        
        # UI-Loading beendet
        self.not_the_human = False

    # == Closed Tabs View ==
    def toggle_closed_tabs_view(self, checked):
        if checked:
            self.ccw.session_widget.setVisible(True) # Splitview
            self.ccw.closed_session_widget.setVisible(True)
            # start populating closed tabs widget
            self.session_populator.populate_closed_tabs(
                self.ccw.closed_session_widget, 
                self.closed_tabs_data, 
                self._format_timestamp
            )
            self.ccw.show_closed_tabs_btn.setText(tr("Hide Closed Tabs", "main"))
        else:
            self.ccw.closed_session_widget.setVisible(False)
            self.ccw.show_closed_tabs_btn.setText(tr("Show Closed Tabs", "main"))

    # == Session Item Helplers ==
    def _on_item_expanded(self, item):
        if self._get_item_depth(item) == 1:
            # Check if this is a regular group with color (UserRole + 1)
            color = item.data(0, Qt.UserRole + 1)
            
            if color:
                # Regular group: use colored folder-open icon
                item.setIcon(0, colored_svg_icon("assets/icons/folder-open.svg", color, size=16))
            else:
                # Special group or regular group without color: check for specific icon path
                open_icon_path = item.data(0, Qt.UserRole + 3)  # Expanded icon
                if open_icon_path:
                    icon_name = os.path.splitext(os.path.basename(open_icon_path))[0]
                    item.setIcon(0, load_icon(icon_name))
                else:
                    # Fallback to generic folder-open
                    item.setIcon(0, load_icon("folder-open"))

    def _on_item_collapsed(self, item):
        if self._get_item_depth(item) == 1:
            # Check if this is a regular group with color (UserRole + 1)
            color = item.data(0, Qt.UserRole + 1)
            
            if color:
                # Regular group: use colored folder icon
                item.setIcon(0, colored_svg_icon("assets/icons/folder.svg", color, size=16))
            else:
                # Special group or regular group ohne Farbe: Überprüfen Sie den spezifischen Icon-Pfad
                closed_icon_path = item.data(0, Qt.UserRole + 2)  # Collapsed icon
                if closed_icon_path:
                    icon_name = os.path.splitext(os.path.basename(closed_icon_path))[0]
                    item.setIcon(0, load_icon(icon_name))
                else:
                    # Fallback to generic folder
                    item.setIcon(0, load_icon("folder"))

    def _get_item_depth(self, item):
        depth = 0
        while item.parent() is not None:
            item = item.parent()
            depth += 1
        return depth

    # == File Operations ==
    def copy_profile_session(self):
        # search for existing profile folders
        all_profiles = self.utils_helper.find_firefox_profiles()
        if not all_profiles:
            self.status_bar.show_message(tr("No Firefox profiles folder found.", "error"), message_type="error")
            return

        ffp_dialog = FFProfileSelectionDialog(all_profiles, self)
        if ffp_dialog.exec() == QDialog.Accepted:
            selected_paths = ffp_dialog.selected_paths
            if selected_paths:
                base_target_dir = QFileDialog.getExistingDirectory(self, tr("Select Target Directory", "dialog"), os.getcwd())
                if not base_target_dir:
                    self.status_bar.show_message(tr("No target directory selected.", "error"), message_type="error")
                    return
                target_dir = self.utils_helper.create_backup_dir(base_target_dir)

                self._copy_files(selected_paths, target_dir)
            else:
                self.status_bar.show_message(tr("No profiles selected.", "warning"), message_type="warning")
    
    def open_recent_files_dialog(self):
        """Open dialog to select from recent files with improved error handling"""
        try:
            recent_files = self.settings._settings.value("RecentFiles", [], type=list)
            if isinstance(recent_files, str):
                recent_files = [recent_files]
            
            recent = []
            for path in recent_files:
                try:
                    if os.path.isfile(path):
                        folder = os.path.dirname(path)
                    else:
                        folder = path
                    if folder not in recent and os.path.exists(folder):
                        recent.append(folder)
                except Exception as e:
                    self.status_bar.show_message(tr("Error with recent file path.", "warning"), message_type="warning")
                    self.logger.warning(f"({tr('Invalid recent file path', 'warning')}): {path} - {e} |#| ({type(e).__name__})", exc_info=True)
                    
            dialog = OpenRecentProjectFileDialog(parent=self, recent_files=recent)
            dialog.file_selected.connect(self._load_selected_file)
            dialog.exec()
            
        except Exception as e:
            self.logger.error(f"({tr('Error opening recent files dialog', 'error')}): {e} |#| ({type(e).__name__})", exc_info=True)
            self.status_bar.show_message(tr("Error opening recent files.", "error"), message_type="error")

    def _load_selected_file(self, path: str):
        """Load a selected file with improved error handling and validation"""
        self.path = path # to access in closed tabs view
        try:
            self.status_bar.show_message(tr("Loading session...", "statusbar"))
            
            if not path:
                self.status_bar.show_message(tr("No file path provided.", "error"), message_type="error")
                return
            
            if not os.path.exists(path):
                self.status_bar.show_message(tr("Selected file does not exist (anymore).", "error"), message_type="error")
                self.logger.error(f"({tr('File does not exist', 'error')}): {path}")
                self._remove_from_recent_files(path)  # Clean up invalid entries
                return
            
            if not os.access(path, os.R_OK):
                self.status_bar.show_message(tr("No permission to read file.", "error"), message_type="error")
                self.logger.error(f"({tr('No read permission for file', 'error')}): {path}")
                return
            
            self.load_session_file(path)
            
        except Exception as e:
            self.logger.error(f"({tr('Unexpected error loading file', 'error')}): {path}: {e} |#| ({type(e).__name__})", exc_info=True)
            self.status_bar.show_message(tr("Unexpected error loading file", "error"), message_type="error")
        
    def load_session_file(self, path: str):
        """Load session file using the SessionLoader service"""
        try:          
            # Load session data using service
            enriched_tabs, groups, all_groups_info = self.session_loader.load_session_file(path)
            
            # Reset state
            self.favicon_download_asked = False
            self.failed_favicon_domains = set()
            
            # Store loaded data
            self.session_tabs = enriched_tabs
            self.session_groups = groups
            self.group_list = all_groups_info
            self.current_file_path = path
            
            # Get session ID from database
            self.current_session_id = self.session_loader.get_session_id(path)
            if not self.current_session_id:
                self.logger.warning(f"({tr('Failed to get session ID for', 'warning')}): {path}")
            
            # Update recent files
            self.save_to_recent_files(path)
            
            # Populate UI using service
            self.window_data = self.session_populator.populate_session_tree(
                self.ccw.session_widget, 
                self.session_tabs, 
                self.group_list, 
                path
            )

            self.closed_tabs_data = self.session_loader.session_processor.get_extra_tabs_data()

            # Update UI state
            self._ui_update_btn_states(file_loaded=True)
            self._ui_update_group_combo()

            self.status_bar.show_message(tr('Successfully loaded session with {0} active tabs (and {1} Closed tabs)', 'main', len(enriched_tabs), len(self.closed_tabs_data['counting_tabs'])), message_type="success")
            self.logger.info(tr('Successfully loaded session with {0} tabs', 'main', len(enriched_tabs)))

        except SessionLoadingError as e:
            self.status_bar.show_message(tr("Failed to load session file", "error"), message_type="error")
            self.logger.error(f"{tr('Failed to load session file', 'error')}: {e} |#| ({type(e).__name__})", exc_info=True)
        except Exception as e:
            self.status_bar.show_message(tr("Unexpected error loading session", "error"), message_type="error")
            self.logger.error(f"{tr('Unexpected error loading session', 'error')}: {e} |#| ({type(e).__name__})", exc_info=True)

    def save_to_recent_files(self, path: str):
        """Save file to recent files list with validation"""
        try:
            if not path or not os.path.exists(path):
                return
                
            recent_files = self.settings._settings.value("RecentFiles", [], type=list)
            if isinstance(recent_files, str):
                recent_files = [recent_files]
            
            # Remove if already exists
            if path in recent_files:
                recent_files.remove(path)
            
            # Add to front
            recent_files.insert(0, path)
            
            # Limit to 10 entries and validate all paths
            validated_files = []
            for file_path in recent_files[:10]:
                if os.path.exists(file_path):
                    validated_files.append(file_path)
                else:
                    self.logger.debug(f"({tr('Removing invalid recent file', 'debug')}): {file_path}")
            
            self.settings._settings.setValue("RecentFiles", validated_files)
            
        except Exception as e:
            self.logger.error(f"({tr('Error updating recent files', 'error')}): {e} |#| ({type(e).__name__})", exc_info=True)

    def _remove_from_recent_files(self, path: str):
        """Remove invalid file from recent files list"""
        try:
            recent_files = self.settings._settings.value("RecentFiles", [], type=list)
            if isinstance(recent_files, str):
                recent_files = [recent_files]
            
            if path in recent_files:
                recent_files.remove(path)
                self.settings._settings.setValue("RecentFiles", recent_files)
                self.logger.debug(f"({tr('Removed invalid file from recent files', 'debug')}): {path}")
                
        except Exception as e:
            self.logger.error(f"({tr('Error removing file from recent files', 'error')}): {e} |#| ({type(e).__name__})", exc_info=True)

    # == Helpers ==

    def _format_timestamp(self, timestamp):
        """convert timestamp to local datetime string"""
        if not timestamp:
            return ""
        dt = ""
        forced_tz = self.settings._settings.value("force_timezone", True, type=bool)
        if forced_tz:
            tz = int(self.settings._settings.value("your_timezone", 0, type=int))
            tz_offset = timezone(timedelta(hours=tz))
            dt = self._format_timestamp_now_for_real(timestamp, tz_offset)

        else:
            try: 
                #first try to get local timezone from System
                tz_offset = datetime.now().astimezone().tzinfo
                dt = self._format_timestamp_now_for_real(timestamp, tz_offset)
            except Exception as e:
                self.logger.warning(f"({tr('Failed to convert to local timezone', 'warning')}): {e} |#| ({type(e).__name__})", exc_info=True)
                # If something went wrong, try to get timezone from settings (otherwise +0)
                try:
                    tz = int(self.settings._settings.value("your_timezone", 0, type=int))
                    tz_offset = timezone(timedelta(hours=tz))
                    dt = self._format_timestamp_now_for_real(timestamp, tz_offset)
                except Exception as e:
                    self.logger.warning(f"({tr('Failed to get timezone from settings', 'warning')}): {e} |#| ({type(e).__name__})", exc_info=True)
        return dt

    def _format_timestamp_now_for_real(self, timestamp, tz_offset):
        try:
            ts_sec = timestamp / 1000 if timestamp > 1e10 else timestamp
            dt = datetime.fromtimestamp(ts_sec, timezone.utc)
            dt = dt.astimezone(tz_offset)
            return dt.strftime("%d.%m.%Y %H:%M")
        except (ValueError, OSError) as e:
            self.logger.warning(f"({tr('Failed to format timestamp', 'warning')}): {e} |#| ({type(e).__name__})", exc_info=True)
            return ""
        
    def populate_history_its(self, entries):
        while self.rcw.its_his_container_layout.count():
            child = self.rcw.its_his_container_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        if not entries:
            no_data_label = QLabel(tr("No History available.", "Addon_History"))
            no_data_label.setStyleSheet("color: grey; font-style: italic;")
            self.rcw.its_his_container_layout.addWidget(no_data_label, alignment=Qt.AlignCenter)
            return

        for i, entry in reversed(list(enumerate(entries))):
            entry_frame = QFrame()
            entry_layout = QVBoxLayout(entry_frame)
            entry_layout.setContentsMargins(0, 0, 0, 0)
            entry_layout.setSpacing(3)
            
            url = entry.get("url", "")
            if url != "about:newtab":
                title_text = entry.get("title", f"Entry [{i}]")
                title_label = QLabel(f"<b>{title_text}</b>")
                title_label.setToolTip(title_text)
                entry_layout.addWidget(title_label)
                url_button = QPushButton(icon=load_icon("external-link"), text=tr("Open in Browser", "General"))
                url_button.setToolTip('\n'.join([url[i:i+80] for i in range(0, len(url), 80)]))
                url_button.setCursor(Qt.PointingHandCursor)
                url_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                url_button.setMaximumWidth(350)
                url_button.clicked.connect(lambda _, u=url: self.open_link_in_browser(u))
                entry_layout.addWidget(url_button)
                if i < len(entries) - 1:
                    icon_container = QWidget()
                    icon_container.setFixedWidth(350)
                    h_layout = QHBoxLayout(icon_container)
                    h_layout.addStretch(1)
                    arrow_icon = QSvgWidget("assets/icons/arrow-badge-up.svg")
                    arrow_icon.setFixedSize(20, 20)
                    h_layout.addWidget(arrow_icon)
                    h_layout.addStretch(1)
                    self.rcw.its_his_container_layout.addWidget(icon_container)
            else:
                pass

            self.rcw.its_his_container_layout.addWidget(entry_frame)
        
        try:
            base64_raw = None
            if entries:
                for pos in [0, -1]:
                    triggering = entries[pos].get("triggeringPrincipal_base64")
                    if triggering:
                        base64_raw = triggering
                        break
            if base64_raw:
                decoded = json.loads(base64_raw)
                url_str = None
                if isinstance(decoded, dict):
                    for k1 in decoded.values():
                        if isinstance(k1, dict):
                            url_str = list(k1.values())[0] if k1 else None
                            break
                if url_str:
                    entry_frame = QFrame()
                    entry_layout = QVBoxLayout(entry_frame)
                    entry_layout.setContentsMargins(0, 0, 0, 0)
                    entry_layout.setSpacing(3)
                    
                    title_label = QLabel(f"<b>Parent Tab:</b>")
                    #short_url = QUrl(url_str).toDisplayString(QUrl.RemoveQuery | QUrl.RemoveFragment)
                    if len(url_str) > 50:
                        url_str = url_str[:47] + '...'
                    url_button = QPushButton(icon=load_icon("external-link"), text=url_str)
                    url_button.setStyleSheet("text-align: left;")
                    url_button.setToolTip('\n'.join([url_str[i:i+80] for i in range(0, len(url_str), 80)])) # maybe using with textwrap.wrap(url_str, width=80) ? 
                    url_button.setCursor(Qt.PointingHandCursor)
                    url_button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                    url_button.setMaximumWidth(350)
                    url_button.clicked.connect(lambda _, u=url_str: self.open_link_in_browser(u))


                    icon_container = QWidget()
                    icon_container.setFixedWidth(350)
                    h_layout = QHBoxLayout(icon_container)
                    h_layout.addStretch(1)
                    newtab_icon = QSvgWidget("assets/icons/plus.svg")
                    newtab_icon.setFixedSize(20, 20)
                    h_layout.addWidget(newtab_icon)
                    h_layout.addStretch(1)

                    self.rcw.its_his_container_layout.addWidget(icon_container)
                    entry_layout.addWidget(title_label)
                    entry_layout.addWidget(url_button)
                    self.rcw.its_his_container_layout.addWidget(entry_frame)
                else:
                    pass
                    
        except Exception as ex:
            self.status_bar.show_message(tr("Error displaying History data", "error"), message_type="Error")
            self.logger.error(f"({tr('Error displaying History data', 'Error')}): {ex} |#| ({type(ex).__name__})", exc_info=True)

        self.rcw.its_his_container_layout.addStretch(1)

    def _copy_files(self, source_paths, target_dir):
        
        copied_files = {}
        untouched_target_dir = os.path.join(target_dir,"untouched-backups")
        json_target_dir = os.path.join(target_dir,"decompiled JSON")

        try:
            for source_path in source_paths:
                filename = os.path.basename(source_path)
                target_lz4_path = os.path.join(target_dir, filename)
                target_lz4backup_path = os.path.join(untouched_target_dir, filename.replace('.jsonlz4', '-untouched.jsonlz4'))
                target_json_path = os.path.join(json_target_dir, filename.replace('.jsonlz4', '.json'))
                
                shutil.copy2(source_path, target_lz4_path)
                shutil.copy2(source_path, target_lz4backup_path)
                
                with open(target_lz4_path, "rb") as f:
                    magic = f.read(8)
                    if magic != b"mozLz40\0":
                        raise ValueError(tr("Invalid jsonlz4 file header", "Raise"))
                    compressed_data = f.read()
                import lz4.block
                decompressed_data = lz4.block.decompress(compressed_data)
                json_str = decompressed_data.decode('utf-8')
                json_data = json.loads(json_str)

                with open(target_json_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=2, ensure_ascii=False)
                    
                    copied_files[filename] = target_lz4_path
                
                
        except Exception as e:
            QMessageBox.critical(
                self,
                tr("Copy Error", "MessageBox_err"),
                tr("There is an error: {0}", "MessageBox_err", e),
            )
            self._set_ui_enabled_state(False)
            return

        try:
            import_date = datetime.now().strftime("%d.%m.%Y %H:%M")
            source_profile = os.path.basename(os.path.dirname(source_path))
            if source_profile == "sessionstore-backups":
                source_profile = os.path.basename(os.path.dirname(os.path.dirname(source_path)))
            
            with open(os.path.join(os.path.dirname(target_lz4_path), "profile.txt"), "w", encoding="utf-8") as f:
                    f.write(f"{source_profile}|{import_date}")
        
        except OSError as e:
            QMessageBox.critical(
                self,
                tr("Copy Error", "MessageBox_err"),
                tr("Error writing the file: {0}", "MessageBox_err", e),
            )

        if len(copied_files) > 1:
            session_path = copied_files.get('sessionstore.jsonlz4')
            recovery_path = copied_files.get('recovery.jsonlz4')
            previous_path = copied_files.get('previous.jsonlz4')
            
            dialog = FileSelectionDialog(session_path, recovery_path, previous_path, self)
            dialog.file_selected.connect(self.load_session_file)
            dialog.exec_()

        elif len(copied_files) == 1:
            file_to_load = list(copied_files.values())[0]
            self.load_session_file(file_to_load)
            

    def export_bookmarks(self):
        # Create window list - fallback if window_data doesn't exist
        window_list = []
        if hasattr(self, 'window_data') and self.window_data:
            window_list = [w.get("title", f"Window {i+1}") for i, w in enumerate(self.window_data)]
        
        dlg = ExportBookmarksDialog(self, window_list=window_list)
        
        # Debug: Print session tabs with favicons (optional, for debugging)
        for t in self.session_tabs:
            if t.get("favicon") is not None:
                print("SessionTab:", t["title"], t["favicon"][:40], t.get("uuid"))
        
        # Traverse the session widget tree to collect data
        for i in range(self.ccw.session_widget.topLevelItemCount()):
            win = self.ccw.session_widget.topLevelItem(i)
            for j in range(win.childCount()):
                group = win.child(j)
                for k in range(group.childCount()):
                    tabitem = group.child(k)
                    data = tabitem.data(0, Qt.UserRole)
        
        if dlg.exec() == QDialog.Accepted:
            opts = dlg.get_export_options()
            exporter = BookmarkExporter(
                self.ccw.session_widget,
                self.window_data, 
                COLORS, 
                assets_path="assets/icons",
                favicon_cache_path=self.cache_dir_favicon
            )
            exporter.export(
                filepath=opts["filepath"],
                variant=opts["variant"],
                groups_as_folders=opts["groups_as_folders"],
                selected_windows=opts["windows"]
            )

    def update_data_from_ui(self):
        # Ignoriere Updates während die UI Daten lädt
        if hasattr(self, 'not_the_human') and self.not_the_human:
            return
            
        current_item = self.ccw.session_widget.currentItem()
        if not current_item: return

        tab_data = current_item.data(0, Qt.UserRole)
        if not tab_data or "uuid" not in tab_data: return

        new_title = self.rcw.title_edit.text()
        new_url = self.rcw.url_edit.text()
        new_group_display_name = self.rcw.group_combo.currentText()

        old_title = tab_data.get('title', '')
        old_url = tab_data.get('url', '')
        old_group_name = tab_data.get('group_name', 'Ungrouped')

        # The display name is now clean (no indentation to remove)
        new_group_name = new_group_display_name

        title_changed = new_title != old_title
        url_changed = new_url != old_url
        group_changed = new_group_name != old_group_name

        if not (title_changed or url_changed or group_changed):
            return 
        
        enriched_tab = next((t for t in self.session_tabs if t['uuid'] == tab_data['uuid']), None)

        if not enriched_tab: return
        
        try:
            if title_changed:
                enriched_tab['title'] = new_title
                self.status_bar.show_message(tr("Tab title updated.", "main"), message_type="success")
            if url_changed:
                enriched_tab['url'] = new_url
                self.status_bar.show_message(tr("Tab URL updated.", "main"), message_type="success")
            if group_changed:
                enriched_tab['group_name'] = new_group_name
                new_group_id = None
                # Check if moving to ungrouped (using proper text comparison)
                ungrouped_text = tr("Ungrouped", "main")
                if new_group_name != ungrouped_text and new_group_name.strip() != "":
                    group_info = next((g for g in self.group_list if g['name'] == new_group_name), None)
                    if group_info:
                        new_group_id = group_info['id']
                
                enriched_tab['group_id'] = new_group_id
                self.status_bar.show_message(tr("Tab group updated.", "main"), message_type="success")
        except Exception as e:
            self.logger.error(f"{tr('Error updating tab data', 'error')}, URL: '{old_url}': {e} |#| ({type(e).__name__})", exc_info=True)
            self.status_bar.show_message(tr('Error updating tab data', 'error'), message_type="error")
            return

        raw_tab = enriched_tab.get("raw_tab")
        try:
            if raw_tab:
                if title_changed or url_changed:
                    if raw_tab.get("entries"):
                        raw_tab["entries"][-1]["title"] = new_title
                        raw_tab["entries"][-1]["url"] = new_url
                if group_changed:
                    # Properly handle groupId removal for ungrouped tabs
                    if enriched_tab.get('group_id') is None:
                        # Remove groupId completely when moving to ungrouped
                        raw_tab.pop('groupId', None)
                        self.logger.info("Removed groupId from raw_tab (moved to ungrouped)")
                    else:
                        raw_tab["groupId"] = enriched_tab.get('group_id')
                        self.logger.info(f"Set groupId in raw_tab to: {enriched_tab.get('group_id')}")
            
            current_item.setData(0, Qt.UserRole, enriched_tab)
            if title_changed:
                current_item.setText(0, new_title)

            if group_changed:
                self._move_tab_to_new_group(current_item, new_group_name, enriched_tab, raw_tab)
        except Exception as e:
            self.logger.error(f"{tr('Error updating Json item data', 'error')}, URL: '{old_url}': {e} |#| ({type(e).__name__})", exc_info=True)
            self.status_bar.show_message(tr('Error updating Json item data', 'error'), message_type="error")
            return

        self.lcw.save_btn.setEnabled(True)




    def save_session_changes(self):
        return self.session_helper.save_session_changes(
            self.current_file_path, 
            self.session_tabs, 
            self
        )

    def _move_tab_to_new_group(self, item, new_group_name, enriched_tab=None, raw_tab=None):
        result = self.session_helper.move_tab_to_new_group(
            item, new_group_name, enriched_tab, raw_tab,
            self.ccw.session_widget, self.group_to_window_map, self.group_list
        )
        
        if result:
            if result.get('window_move_completed'):
                self.logger.info("Cross-window tab move completed successfully")
            elif result.get('visual_move_completed'):
                # Update group labels
                self._update_group_label(result['old_parent'], result['old_count'])
                self._update_group_label(result['new_parent'], result['new_count'])
    
    def _get_window_id_from_tree_item(self, item):
        """Get window ID by traversing up the tree structure to find the window"""
        return self.session_helper.get_window_id_from_tree_item(item, self.ccw.session_widget)

    def _move_tab_between_windows(self, raw_tab, old_window_id, new_window_id, new_group_id):
        """Move a tab between windows in the raw JSON structure"""
        return self.session_helper.move_tab_between_windows(
            raw_tab, old_window_id, new_window_id, new_group_id
        )

    def _get_group_id_for_window(self, new_group_id, target_window_id):
        """Get the appropriate group ID for the target window"""
        return self.session_helper.get_group_id_for_window(new_group_id, target_window_id)

    def replace_session(self):
        return self.session_helper.replace_session(
            self.current_file_path,
            self
        )
    
    def _update_group_label(self, group_item, count):
        gname = ""
        data = group_item.data(0, Qt.UserRole)
        if data and data.get("type") == "group":
            gname = data.get("group_name", group_item.text(0))
            group_item.setText(0, f"{gname} ({count} {'Tab' if count==1 else 'Tabs'})")
            self.ccw.session_widget.viewport().update()
        if not gname:
            gname = group_item.text(0).split("(")[0].strip()
            group_item.setText(0, f"{gname} ({count} {'Tab' if count==1 else 'Tabs'})")

    

    def open_xpath_editor(self):
        #info = self.main_window.current_tab_info
        #if not info:
        #    pass

        #domain = info.get("domain", "")
        #url = info.get("url", "")
        #url_part = self.main_window.extract_url_contains(url)
        #url_contains_options = self.db.get_url_contains_for_domain(domain)

        from app.ui.dialogs.xpath_rule_editor import XPathRuleEditorDialog
        dialog = XPathRuleEditorDialog(
            db_handler=self.db,
            settings=self.settings,
            parent=self
        )
        dialog.exec()

    def _on_scrape_current_tab_clicked(self):
        """
        Handler for the scrape current tab button click.
        """
        try:
            selected = self.ccw.session_widget.selectedItems()
            if not selected:
                self.status_bar.show_message(tr("No tab selected.", "main"), message_type="warning")
                return
            
            item = selected[0]
            item_data = item.data(0, Qt.UserRole)
            if not isinstance(item_data, dict) or item_data.get('type') in ('group', 'window'):
                self.status_bar.show_message(tr("Please select a tab.", "main"), message_type="warning")
                return

            url = item_data.get('url', '')
            url_hash = item_data.get('url_hash')

            if not url or not url_hash:
                self.status_bar.show_message(tr("Tab URL missing.", "error"), message_type="error")
                return

            parsed = urlparse(url)
            # Domain normalisieren
            domain_raw = (parsed.hostname or parsed.netloc or "").lower()
            if not domain_raw:
                self.status_bar.show_message(tr("Could not determine domain.", "error"), message_type="error")
                return
            domain_norm = domain_raw[4:] if domain_raw.startswith("www.") else domain_raw

            # 1) Versuch mit normalisierter Domain
            url_contains = self.db.find_matching_url_part(domain_norm, url) or ""
            rules = self.db.get_xpath_rules(domain_norm, url_contains)

            # 2) Fallback: alternative Domain-Variante (mit/ohne www.)
            if not rules:
                alt_domain = ("www." + domain_norm) if not domain_raw.startswith("www.") else domain_norm[4:]
                url_contains_alt = self.db.find_matching_url_part(alt_domain, url) or ""
                rules = self.db.get_xpath_rules(alt_domain, url_contains_alt)
                if rules:
                    domain_norm = alt_domain
                    url_contains = url_contains_alt

            if not rules:
                self.status_bar.show_message(
                    tr("No XPath rules found for this domain/path.", "main"),
                    message_type="warning"
                )
                return

            # Store rules for data processing
            self.current_xpath_rules = rules

            engine = (self.settings.get("Plugins/scraping_engine", "requests") or "requests").lower()
            if engine == "playwright":
                self.start_xpath_extraction_playwright(url, rules, url_hash)
                self.status_bar.show_message(tr("Started Playwright extraction…", "main"))
            else:
                self.start_xpath_extraction_requests(url, rules, url_hash)
                self.status_bar.show_message(tr("Started Requests extraction…", "main"))

        except Exception as e:
            self.logger.error(f"{tr('Failed to start scraping', 'error')}: {e} |#| ({type(e).__name__})", exc_info=True)
            self.status_bar.show_message(tr("Failed to start scraping.", "error"), message_type="error")

    def _load_and_display_image(self, url_hash):
        """Load and display image from cache if available, based on url_hash."""
        if not url_hash:
            self.rcw.image_frame.setVisible(False)
            return
        
        # Get image cache directory from settings
        image_cache_dir = self.settings._settings.value("image_cache_dir", "user_data/img", type=str)
        image_path = os.path.join(image_cache_dir, f"{url_hash}.jpg")
        
        if os.path.exists(image_path):
            try:
                pixmap = QPixmap(image_path)
                if not pixmap.isNull():
                    # Scale image to fit width (350px) with smooth transformation
                    scaled_pixmap = pixmap.scaledToWidth(350, Qt.SmoothTransformation)
                    self.rcw.image_label.setPixmap(scaled_pixmap)
                    self.rcw.image_label_status.setText("")  # Clear any status text
                    self.rcw.image_frame.setVisible(True)
                else:
                    self.logger.warning(f"Invalid image file: {image_path}")
                    self._clear_image_display()
            except Exception as e:
                self.logger.error(f"Failed to load image {image_path}: {e} |#| ({type(e).__name__})", exc_info=True)
                self._clear_image_display()
        else:
            self._clear_image_display()
    
    def _clear_image_display(self):
        """Helper to clear image display and hide frame."""
        self.rcw.image_label.clear()
        self.rcw.image_label_status.setText(tr("No image available", "main"))
        self.rcw.image_frame.setVisible(False)

    def start_xpath_extraction_requests(self, url, rules, url_hash):
        worker = XPathWorkerRequests(self.db, self.settings, url, rules, url_hash)
        # Wrap signals so we can cleanup the worker after finish/error
        worker.extraction_done.connect(lambda data, w=worker: self._on_worker_extraction_done(w, data))
        worker.error_occurred.connect(lambda err, w=worker: self._on_worker_extraction_error(w, err))
        # Also cleanup on finished as safety
        worker.finished.connect(lambda w=worker: self._cleanup_worker(w))
        self._register_worker(worker)
        worker.start()

    def start_xpath_extraction_playwright(self, url, rules, url_hash):
        worker = XPathWorkerPlaywright(self.db, self.settings, url, rules, url_hash)
        worker.extraction_done.connect(lambda data, w=worker: self._on_worker_extraction_done(w, data))
        worker.error_occurred.connect(lambda err, w=worker: self._on_worker_extraction_error(w, err))
        # Only connect image_ready if the signal exists
        if hasattr(worker, 'image_ready'):
            worker.image_ready.connect(lambda img_bytes, uh, w=worker: self.on_image_ready(img_bytes, uh))
        # Don't cleanup on extraction_done - let images finish first
        worker.finished.connect(lambda w=worker: self._cleanup_worker(w))
        self._register_worker(worker)
        worker.start()

    def _register_worker(self, worker: QThread):
        """Keep a strong reference and wire a finalizer."""
        try:
            self._workers.add(worker)
            self.logger.debug(f"Registered worker #{id(worker)}. Active: {len(self._workers)}")
        except Exception as e:
            self.logger.warning(f"Failed to register worker: {e} |#| ({type(e).__name__})", exc_info=True)

    def _cleanup_worker(self, worker: QThread):
        """Safely stop and release a worker if still present."""
        if worker not in self._workers:
            return
        try:
            # If still running, try to stop gracefully
            if hasattr(worker, "isRunning") and worker.isRunning():
                try:
                    if hasattr(worker, "requestInterruption"):
                        worker.requestInterruption()
                    worker.quit()
                    worker.wait(5000)
                except Exception:
                    pass
            worker.deleteLater()
        except Exception as e:
            self.logger.warning(f"Worker cleanup failed: {e} |#| ({type(e).__name__})", exc_info=True)
        finally:
            self._workers.discard(worker)
            self.logger.debug(f"Cleaned up worker #{id(worker)}. Active: {len(self._workers)}")

    def _on_worker_extraction_done(self, worker, data):
        """Forward to UI handler but don't cleanup the worker yet."""
        try:
            self.logger.info(f"{tr("Extraction done", "worker")}: {data}")
            self.status_bar.show_message(tr("Text extraction completed", "worker"), message_type="info")
            

            if isinstance(data, dict) and data:
                self.on_data_extracted(data, self.current_url_hash)
                    
        except Exception as e:
            self.logger.error(f"Failed to process extracted data: {e} |#| ({type(e).__name__})", exc_info=True)
            self.status_bar.show_message(tr("Failed to process extracted data", "error"), message_type="error")


    def _on_worker_extraction_error(self, worker, error):
        """Forward to UI handler and cleanup the worker."""
        try:
            self.status_bar.show_message(error, message_type="error")
            self.logger.info(f"Extraction error: {error}")
        finally:
            self._cleanup_worker(worker)

    def open_link_in_browser(self, url):
        """Open URL in default browser"""
        try:
            webbrowser.open(url)
        except Exception as e:
            self.logger.error(f"Failed to open URL in browser: {e} |#| ({type(e).__name__})", exc_info=True)
            self.status_bar.show_message(tr("Failed to open URL in browser", "error"), message_type="error")

    @Slot(dict, str)
    def on_data_extracted(self, data, url_hash=""):
        """
        Process extracted data from XPath workers and save to database.
        Updates the UI with the newly extracted data.
        """
        try:
            # Fallback to current_hash if url_hash is empty
            if not url_hash:
                url_hash = getattr(self, 'current_url_hash', '')
            
            if not url_hash or not hasattr(self, 'current_session_id'):
                self.logger.warning("Cannot process extracted data: missing session context")
                return

            # Clear existing display
            if hasattr(self, 'data_renderer'):
                self.data_renderer._clear_data_container()

            # Get current XPath rules with proper field names
            rules_sorted = []
            if hasattr(self, 'current_xpath_rules'):
                rules_sorted = sorted(
                    [r for r in self.current_xpath_rules if isinstance(r, dict)],
                    key=lambda r: r.get("priority", 99)
                )
            
            # Create mapping from rule name to rule info (using 'name' field)
            name_to_ruleinfo = {r["name"]: (r["id"], r.get("is_filter", False)) for r in rules_sorted}

            # Get or create tab ID
            tab_id = self.db.get_tab_id(self.current_session_id, url_hash)
            if not tab_id:
                current_url = getattr(self, 'current_url', '')
                if current_url:
                    tab_id = self.db.write_tab_id(self.current_session_id, url_hash, current_url)
                else:
                    self.logger.warning("Cannot save extracted data: missing current URL")
                    return

            # Save extracted data to database
            saved_count = 0
            for name, entry in data.items():
                rule_id, _ = name_to_ruleinfo.get(name, (None, None))
                if not rule_id:
                    self.logger.debug(f"No rule found for extracted data: {name}")
                    continue

                # Handle different data formats from workers
                if isinstance(entry, dict):
                    # Format: {"values": [...], "is_filter": bool, "priority": int}
                    values = entry.get("values", [])
                elif isinstance(entry, list):
                    # Format: [value1, value2, ...]
                    values = entry
                else:
                    # Format: single value
                    values = [entry] if entry is not None else []

                for val in values:
                    try:
                        self.db.save_extracted_data(
                            tab_id=tab_id,
                            rule_id=rule_id,
                            value=str(val),
                            extracted_at=datetime.utcnow().isoformat()
                        )
                        saved_count += 1
                    except Exception as e:
                        self.logger.error(f"Failed to save extracted value: {e} |#| ({type(e).__name__})", exc_info=True)

            self.logger.info(f"Saved {saved_count} extracted data entries")

            # Refresh the display with updated data
            if hasattr(self, 'data_renderer') and hasattr(self, 'current_url'):
                stored_data = self.db.load_extracted_data_for_url(self.current_url)
                self.data_renderer.render_extracted_data(stored_data)
                
            self.status_bar.show_message(
                tr("Extracted and saved {0} data entries", "worker", saved_count), 
                message_type="success"
            )

            # Automatically load and display image after extraction
            self._load_and_display_image(url_hash or getattr(self, 'current_url_hash', ''))

        except Exception as e:
            self.logger.error(f"Failed to process extracted data: {e} |#| ({type(e).__name__})", exc_info=True)
            self.status_bar.show_message(tr("Failed to process extracted data", "error"), message_type="error")

    @Slot(bytes, str)
    def on_image_ready(self, image_bytes, url_hash):
        """Handle image bytes from worker, save to cache and display."""
        if not image_bytes or not url_hash:
            return
        
        try:
            # Get image cache directory
            image_cache_dir = self.settings._settings.value("image_cache_dir", "user_data/img", type=str)
            os.makedirs(image_cache_dir, exist_ok=True)
            image_path = os.path.join(image_cache_dir, f"{url_hash}.jpg")
            
            # Save bytes to file
            with open(image_path, 'wb') as f:
                f.write(image_bytes)
            
            self.logger.info(f"Saved image to {image_path}")
            self.status_bar.show_message(tr("Image downloaded and saved", "worker"), message_type="success")
            
            # Load and display the image
            self._load_and_display_image(url_hash)
            
        except Exception as e:
            self.logger.error(f"Failed to save/display image: {e} |#| ({type(e).__name__})", exc_info=True)

    def _on_load_images_clicked(self):
        """
        Handler for the load images button click.
        Downloads images based on extracted data from image XPath rules.
        Falls keine extrahierten Daten vorhanden sind, werden die Regeln direkt angewandt.
        """
        try:
            # Check if we have a current URL and URL hash
            if not hasattr(self, 'current_url') or not self.current_url:
                self.status_bar.show_message(tr("No tab selected.", "main"), message_type="warning")
                return
            
            if not hasattr(self, 'current_url_hash') or not self.current_url_hash:
                self.status_bar.show_message(tr("No URL hash available.", "error"), message_type="error")
                return

            # Get XPath rules for the current URL to identify image rules
            parsed = urlparse(self.current_url)
            domain_raw = (parsed.hostname or parsed.netloc or "").lower()
            if not domain_raw:
                self.status_bar.show_message(tr("Could not determine domain.", "error"), message_type="error")
                return
            domain_norm = domain_raw[4:] if domain_raw.startswith("www.") else domain_raw

            # Get rules (same logic as scraping)
            url_contains = self.db.find_matching_url_part(domain_norm, self.current_url) or ""
            rules = self.db.get_xpath_rules(domain_norm, url_contains)

            # Fallback: alternative domain variant
            if not rules:
                alt_domain = ("www." + domain_norm) if not domain_raw.startswith("www.") else domain_norm[4:]
                url_contains_alt = self.db.find_matching_url_part(alt_domain, self.current_url) or ""
                rules = self.db.get_xpath_rules(alt_domain, url_contains_alt)

            if not rules:
                self.status_bar.show_message(tr("No XPath rules found for this domain.", "main"), message_type="warning")
                return

            # Filter for image rules only
            image_rules = [rule for rule in rules if rule.get('is_image', False)]
            if not image_rules:
                self.status_bar.show_message(tr("No image rules found for this domain.", "main"), message_type="warning")
                return

            # First try: Get tab_id and look for existing extracted data
            tab_id = None
            if hasattr(self, 'current_session_id') and self.current_session_id:
                tab_id = self.db.get_tab_id(self.current_session_id, self.current_url_hash)

            # Collect image URLs from stored extracted data (if available)
            image_urls = []
            if tab_id:
                for rule in image_rules:
                    rule_id = rule.get('id')
                    if rule_id:
                        # Get extracted data for this specific image rule
                        extracted_values = self.db.get_extracted_data_for_rule(tab_id, rule_id)
                        for value in extracted_values:
                            if value and isinstance(value, str):
                                image_urls.append(value)
                                self.logger.debug(f"Found image URL from existing data, rule '{rule.get('name')}': {value}")

            # If no extracted data found, apply XPath rules directly as fallback
            if not image_urls:
                self.logger.info("No existing extracted data found, applying XPath rules directly")
                self.status_bar.show_message(tr("No extracted data found. Applying image rules directly...", "main"), message_type="info")
                
                # Start extraction with image-only rules
                engine = (self.settings.get("Plugins/scraping_engine", "requests") or "requests").lower()
                if engine == "playwright":
                    self._start_image_only_extraction_playwright(self.current_url, image_rules, self.current_url_hash)
                else:
                    self._start_image_only_extraction_requests(self.current_url, image_rules, self.current_url_hash)
                return

            # Remove duplicates while preserving order
            unique_urls = []
            seen = set()
            for url in image_urls:
                if url not in seen:
                    unique_urls.append(url)
                    seen.add(url)

            if not unique_urls:
                self.status_bar.show_message(tr("No unique image URLs found.", "main"), message_type="warning")
                return

            self.logger.info(f"Found {len(unique_urls)} unique image URLs from existing data")
            self.status_bar.show_message(tr("Starting download of {0} images from existing data...", "main", len(unique_urls)), message_type="info")

            # Start image downloads
            self._start_image_downloads(unique_urls, self.current_url_hash)

        except Exception as e:
            self.logger.error(f"{tr('Failed to start image downloads', 'error')}: {e} |#| ({type(e).__name__})", exc_info=True)
            self.status_bar.show_message(tr("Failed to start image downloads.", "error"), message_type="error")

    def _start_image_only_extraction_playwright(self, url, image_rules, url_hash):
        """Start Playwright extraction with image-only rules and automatic download."""
        worker = XPathWorkerPlaywright(self.db, self.settings, url, image_rules, url_hash)
        worker.extraction_done.connect(lambda data, w=worker: self._on_image_extraction_done(w, data, url_hash))
        worker.error_occurred.connect(lambda err, w=worker: self._on_worker_extraction_error(w, err))
        # Connect image_ready for direct downloads during extraction
        if hasattr(worker, 'image_ready'):
            worker.image_ready.connect(lambda img_bytes, uh, w=worker: self.on_image_ready(img_bytes, uh))
        worker.finished.connect(lambda w=worker: self._cleanup_worker(w))
        self._register_worker(worker)
        worker.start()

    def _start_image_only_extraction_requests(self, url, image_rules, url_hash):
        """Start Requests extraction with image-only rules and automatic download."""
        worker = XPathWorkerRequests(self.db, self.settings, url, image_rules, url_hash)
        worker.extraction_done.connect(lambda data, w=worker: self._on_image_extraction_done(w, data, url_hash))
        worker.error_occurred.connect(lambda err, w=worker: self._on_worker_extraction_error(w, err))
        worker.finished.connect(lambda w=worker: self._cleanup_worker(w))
        self._register_worker(worker)
        worker.start()

    def _on_image_extraction_done(self, worker, data, url_hash):
        """Handle completion of image-only extraction and start downloads."""
        try:
            self.logger.info(f"Image-only extraction completed: {len(data)} rules processed")
            
            # Collect image URLs from extraction results
            image_urls = []
            for rule_name, entry in data.items():
                if isinstance(entry, dict):
                    values = entry.get("values", [])
                elif isinstance(entry, list):
                    values = entry
                else:
                    values = [entry] if entry is not None else []
                
                for value in values:
                    if value and isinstance(value, str):
                        image_urls.append(value)
                        self.logger.debug(f"Found image URL from extraction '{rule_name}': {value}")

            if not image_urls:
                self.status_bar.show_message(tr("No image URLs found in extraction results.", "main"), message_type="warning")
                return

            # Remove duplicates while preserving order
            unique_urls = []
            seen = set()
            for url in image_urls:
                if url not in seen:
                    unique_urls.append(url)
                    seen.add(url)

            if unique_urls:
                self.logger.info(f"Starting download of {len(unique_urls)} images from fresh extraction")
                self.status_bar.show_message(tr("Starting download of {0} images from extraction...", "main", len(unique_urls)), message_type="info")
                self._start_image_downloads(unique_urls, url_hash)
            else:
                               self.status_bar.show_message(tr("No unique image URLs found in extraction.", "main"), message_type="warning")



        except Exception as e:
            self.logger.error(f"Failed to process image extraction results: {e} |#| ({type(e).__name__})", exc_info=True)
            self.status_bar.show_message(tr("Failed to process image extraction results.", "error"), message_type="error")


    def open_title_cleaner_dialog(self):
        current_tab = self.ccw.session_widget.currentItem()
        current_tab_id = None
        if current_tab:
            data = current_tab.data(0, Qt.UserRole)
            if data:
                current_tab_id = data.get("uuid")
                

        self.ccw.session_widget.setCurrentItem(None)
        
        dialog = TitleCleanerDialog(app_settings=self.settings, parent=self)
        if dialog.exec() == QDialog.Accepted:
            self.cleaner_patterns = [p.strip() for p in dialog.load_patterns() if p and p.strip()]
            self.apply_title_cleaning_to_session_tabs()


            self.populate_group_and_tabs(self.session_tabs, self.group_list)
        
        if current_tab_id:
            item_to_select = self._find_tree_item_by_uuid(data.get("uuid"))
            if item_to_select:
                self.ccw.session_widget.setCurrentItem(item_to_select)

    def apply_title_cleaning_to_session_tabs(self):
        for i, tab in enumerate(self.session_tabs):
            original_title = tab.get("title", "")
            if "_original_title" not in tab:
                tab["_original_title"] = original_title

            cleaned_title = self.strip_title_with_patterns(tab["_original_title"])
            tab["title"] = cleaned_title


    def strip_title_with_patterns(self, title: str) -> str:
        patterns = [p.strip() for p in (self.cleaner_patterns or []) if p and p.strip()]
        out = title

        for idx, p in enumerate(patterns):
            before = out
            out = out.replace(p, "")

        out = out.replace("\u00A0", " ")
        out = re.sub(r"[ \t]{2,}", " ", out)
        out = re.sub(r"\s*\|\s*\|\s*", "|", out)
        out = re.sub(r"\s*\|\s*$", "", out)
        out = re.sub(r"^\s*\|\s*", "", out)
        out = out.strip()
        return out

    def _find_tree_item_by_uuid(self, uuid):
        iterator = QTreeWidgetItemIterator(self.ccw.session_widget)
        while iterator.value():
            item = iterator.value()
            item_data = item.data(0, Qt.UserRole)
            if item_data and isinstance(item_data, dict) and item_data.get("uuid") == uuid:
                return item
            iterator += 1
        return None
    

    def open_group_editor(self):
        dialog = GroupEditor(
            all_groups=self.group_list.copy(),
            parent=self
        )
        dialog.changes_ready.connect(self.on_group_changes_ready)
        dialog.exec()

    def on_group_changes_ready(self, changes):
        if not changes:
            return

        for change in changes:
            group_id = change['group_id']
            field = change['field']
            new_value = change['new_value']
            
            for window in self.session_loader.json_data.get("windows", []):
                for group_data in window.get("groups", []):
                    if group_data.get("id") == group_id:
                        group_data[field] = new_value  
            
            for group in self.group_list:
                if group['id'] == group_id:
                    group[field] = new_value
            
            if field == 'name':
                self.session_groups[group_id] = new_value
            elif field == 'color':
                self.group_id_to_color[group_id] = new_value
        
        self._ui_update_group_combo()
        self.populate_group_and_tabs(self.session_tabs, self.group_list)

    def open_settings_dialog(self):
        from app.ui.dialogs.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self.settings, self)
        dlg.exec()