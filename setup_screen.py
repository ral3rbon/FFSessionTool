import sys
import subprocess
import importlib
import os
from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QScrollArea, QWidget, QFrame, QProgressBar, QTextEdit, QTabWidget,
    QFormLayout, QLineEdit, QComboBox, QSpinBox, QGroupBox, QMessageBox,
    QSizePolicy, QFileDialog
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QPixmap, QIcon
from app.ui.helpers.ui_icon_loader import load_icon
from app.utils.ui_translator import tr
from app.ui.helpers.ui_themes import theme_manager
from app.utils import Logger


class PackageInstaller(QThread):
    """Thread for installing packages without blocking the UI"""
    progress_updated = Signal(str)
    installation_finished = Signal(bool, str)

    def __init__(self, command):
        super().__init__()
        self.command = command

    def run(self):
        try:
            self.progress_updated.emit(f"Running {self.command}...")
            result = subprocess.run(
                self.command,
                capture_output=True,
                text=True,
                shell=isinstance(self.command, str)
            )

            if result.returncode != 0:
                self.installation_finished.emit(False, f"Failed to execute {self.command}: {result.stderr}")
                return

            self.installation_finished.emit(True, f"Successfully executed {self.command}!")

        except Exception as e:
            self.installation_finished.emit(False, f"Execution error: {str(e)}")


class StartupScreen(QDialog):
    """
    Startup screen that checks for required packages and allows initial configuration
    """

    def __init__(self, settings, translator, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.translator = translator
        self.logger = Logger.get_logger("StartupScreen")
        
        # Definiere Pakete mit Kategorien (required/xpath/optional)
        self.package_definitions = [
            ("PySide6", "PySide6", "Qt6 Python bindings for GUI", "required"),
            ("lz4", "lz4", "LZ4 compression library for Firefox session files", "required"),
            ("requests", "requests", "HTTP library for web requests", "xpath"),
            ("lxml", "lxml", "XML/HTML parsing library", "xpath"),
            ("playwright", "playwright", "Web automation library for data extraction", "xpath"),
            ("googletrans", "googletrans==4.0.0-rc1", "Google Translate API client - Honestly, dont use it. The Translations are Terrible", "optional"),
            ("shiboken6", "shiboken6", "Qt6 Python bindings support", "optional"),
        ]

        self.package_status = {}
        self.package_checkboxes = {}  # Store checkboxes for optional packages
        self.missing_packages = []
        self.selected_packages = []  # User selected packages to install
        self.playwright_browsers_missing = False

        self.setWindowTitle(tr("FFSessionTool - Startup Configuration", "Startup"))
        self.setModal(True)
        self.resize(850, 900)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._init_ui()
        self._check_packages()
        self._load_current_settings()

    def _init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        layout.setObjectName("main_layout")

        # Header
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background-color: #2c3e50;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        header_layout = QVBoxLayout(header_frame)
        header_layout.setObjectName("header_layout")

        title_label = QLabel("Firefox Session Tool")
        title_label.setStyleSheet("color: white; font-size: 24px; font-weight: bold;")
        title_label.setAlignment(Qt.AlignCenter)

        subtitle_label = QLabel(tr("Initial Setup and Configuration", "Startup"))
        subtitle_label.setStyleSheet("color: #ecf0f1; font-size: 14px;")
        subtitle_label.setAlignment(Qt.AlignCenter)

        header_layout.addWidget(title_label)
        header_layout.addWidget(subtitle_label)
        layout.addWidget(header_frame)

        # Tab widget for different sections
        self.tab_widget = QTabWidget()
        self.tab_widget.setObjectName("tab_widget")

        # Package Check Tab
        self.package_tab = self._create_package_tab()
        self.tab_widget.addTab(self.package_tab, tr("Package Dependencies", "Startup"))

        # Settings Tab
        self.settings_tab = self._create_settings_tab()
        self.tab_widget.addTab(self.settings_tab, tr("Settings", "Startup"))

        layout.addWidget(self.tab_widget)

        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.setObjectName("button_layout")

        # Install selected packages button (only visible on package tab)
        self.install_selected_button = QPushButton(tr("Install Selected Packages", "Startup"))
        self.install_selected_button.setIcon(load_icon("download"))
        self.install_selected_button.clicked.connect(self._install_selected_packages)
        self.install_selected_button.setEnabled(False)

        # Playwright browsers button (only visible on package tab)
        self.playwright_install_button = QPushButton(tr("Install Playwright Browsers", "Startup"))
        self.playwright_install_button.setIcon(load_icon("download"))
        self.playwright_install_button.clicked.connect(self._install_playwright_browsers)
        self.playwright_install_button.setEnabled(False)

        # Select/Deselect all buttons for optional packages (only visible on package tab)
        self.select_all_button = QPushButton(tr("Select All Optional", "Startup"))
        self.select_all_button.setIcon(load_icon("check"))
        self.select_all_button.clicked.connect(self._select_all_optional)
        
        self.deselect_all_button = QPushButton(tr("Deselect All", "Startup"))
        self.deselect_all_button.setIcon(load_icon("x"))
        self.deselect_all_button.clicked.connect(self._deselect_all_optional)

        # Navigation buttons
        self.next_button = QPushButton(tr("Next Page", "Startup"))
        self.next_button.setIcon(load_icon("arrow-badge-right"))
        self.next_button.clicked.connect(self._next_page)

        self.previous_button = QPushButton(tr("Previous Page", "Startup"))
        self.previous_button.setIcon(load_icon("arrow-badge-left"))
        self.previous_button.clicked.connect(self._previous_page)
        self.previous_button.setVisible(False)  # Hidden on first tab

        self.continue_button = QPushButton(tr("Continue to Application", "Startup"))
        self.continue_button.setIcon(load_icon("player-play"))
        self.continue_button.clicked.connect(self._continue_to_app)
        self.continue_button.setVisible(False)  # Only visible on settings tab

        self.exit_button = QPushButton(tr("Exit", "Startup"))
        self.exit_button.setIcon(load_icon("x"))
        self.exit_button.clicked.connect(self.reject)

        button_layout.addWidget(self.select_all_button)
        button_layout.addWidget(self.deselect_all_button)
        button_layout.addWidget(self.install_selected_button)
        button_layout.addWidget(self.playwright_install_button)
        button_layout.addStretch()
        button_layout.addWidget(self.exit_button)
        button_layout.addWidget(self.previous_button)
        button_layout.addWidget(self.next_button)
        button_layout.addWidget(self.continue_button)

        layout.addLayout(button_layout)

        # Connect tab changed signal to update button visibility
        self.tab_widget.currentChanged.connect(self._on_tab_changed)

    def _create_package_tab(self):
        """Create the package checking tab"""
        tab = QWidget()
        tab.setObjectName("tab _create_package_tab")
        layout = QVBoxLayout(tab)

        # Info container with better explanation
        info_container = QWidget()
        info_layout = QVBoxLayout(info_container)
        
        main_info = QLabel(tr("Package Dependencies Overview", "Startup"))
        main_info.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50;")
        
        detail_info = QLabel(F"{tr('Required packages are essential for basic functionality.', 'Startup')} {tr('XPath packages enable web scraping features.', 'Startup')}")
        detail_info.setWordWrap(True)
        detail_info.setStyleSheet("color: #7f8c8d; font-style: italic; margin-bottom: 10px;")
        
        info_layout.addWidget(main_info)
        info_layout.addWidget(detail_info)
        layout.addWidget(info_container)

        # Scroll area for package list
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.package_container = QWidget()
        self.package_layout = QVBoxLayout(self.package_container)
        self.package_layout.setSpacing(8)

        scroll_area.setWidget(self.package_container)
        layout.addWidget(scroll_area)

        # Progress bar for installation
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status label
        stat_container = QWidget()
        stat_layout = QHBoxLayout(stat_container)
        self.status_label = QLabel("")
        self.status_label_icon_l = QLabel()

        stat_layout.addWidget(self.status_label_icon_l, 0)
        stat_layout.addWidget(self.status_label, 1)

        layout.addWidget(stat_container)
        return tab

    def _create_settings_tab(self):
        """Create the initial settings tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Info message
        info_label = QLabel(tr("Configure application settings before starting. You can modify these later in the application preferences.", "Startup"))
        info_label.setWordWrap(True)
        info_label.setStyleSheet("color: #7f8c8d; font-style: italic; margin-bottom: 15px; padding: 10px; background-color: #ecf0f1; border-radius: 4px;")
        layout.addWidget(info_label)

        # Scroll area for settings
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        settings_widget = QWidget()
        settings_layout = QVBoxLayout(settings_widget)

        # General Settings Group
        general_group = QGroupBox(tr("General Settings", "Startup"))
        general_layout = QFormLayout(general_group)

        # Language selection
        self.language_combo = QComboBox()
        self.language_combo.addItems(["auto", "en", "de"])
        general_layout.addRow(tr("Language:", "Startup"), self.language_combo)

        # Timezone
        self.timezone_spin = QSpinBox()
        self.timezone_spin.setRange(-12, 12)
        self.timezone_spin.setValue(2)
        self.timezone_spin.setSuffix(" hours")
        general_layout.addRow(tr("UTC Timezone:", "Startup"), self.timezone_spin)

        settings_layout.addWidget(general_group)

        # Paths Group
        paths_group = QGroupBox(tr("Directory Settings", "Startup"))
        paths_layout = QFormLayout(paths_group)

        # Image cache directory with browse button
        image_cache_layout = QHBoxLayout()
        self.image_cache_edit = QLineEdit("user_data/img")
        image_cache_browse_btn = QPushButton("...")
        image_cache_browse_btn.setFixedWidth(30)
        image_cache_browse_btn.setToolTip(tr("Browse for directory", "Startup"))
        image_cache_browse_btn.clicked.connect(lambda: self._browse_directory(self.image_cache_edit))
        image_cache_layout.addWidget(self.image_cache_edit)
        image_cache_layout.addWidget(image_cache_browse_btn)
        image_cache_widget = QWidget()
        image_cache_widget.setLayout(image_cache_layout)
        paths_layout.addRow(tr("Image cache directory:", "Startup"), image_cache_widget)

        # Favicon cache directory with browse button
        favicon_cache_layout = QHBoxLayout()
        self.favicon_cache_edit = QLineEdit("user_data/favicons")
        favicon_cache_browse_btn = QPushButton("...")
        favicon_cache_browse_btn.setFixedWidth(30)
        favicon_cache_browse_btn.setToolTip(tr("Browse for directory", "Startup"))
        favicon_cache_browse_btn.clicked.connect(lambda: self._browse_directory(self.favicon_cache_edit))
        favicon_cache_layout.addWidget(self.favicon_cache_edit)
        favicon_cache_layout.addWidget(favicon_cache_browse_btn)
        favicon_cache_widget = QWidget()
        favicon_cache_widget.setLayout(favicon_cache_layout)
        paths_layout.addRow(tr("Favicon cache directory:", "Startup"), favicon_cache_widget)


        settings_layout.addWidget(paths_group)

        # Scraping Settings Group
        scraping_group = QGroupBox(tr("Web Scraping Settings", "Startup"))
        scraping_layout = QFormLayout(scraping_group)

        self.scraping_engine_combo = QComboBox()
        self.scraping_engine_combo.addItems(["playwright", "requests"])
        scraping_layout.addRow(tr("Scraping engine:", "Startup"), self.scraping_engine_combo)

        self.hide_xpath_checkbox = QCheckBox(tr("Hide XPath/Scraping buttons", "Startup"))
        scraping_layout.addRow("", self.hide_xpath_checkbox)

        settings_layout.addWidget(scraping_group)

        # Interface Settings Group
        interface_group = QGroupBox(tr("Interface Settings", "Startup"))
        interface_layout = QFormLayout(interface_group)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["auto", "dark", "light"])
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        interface_layout.addRow(tr("Theme:", "Startup"), self.theme_combo)

        settings_layout.addWidget(interface_group)

        settings_layout.addStretch()
        scroll_area.setWidget(settings_widget)
        layout.addWidget(scroll_area)

        # Auto-save settings button (optional)
        save_info = QLabel(tr("Settings will be automatically saved when you continue to the application.", "Startup"))
        save_info.setStyleSheet("color: #27ae60; font-style: italic; padding: 5px;")
        save_info.setAlignment(Qt.AlignCenter)
        layout.addWidget(save_info)

        return tab

    def _on_tab_changed(self, index):
        """Handle tab changes to show/hide appropriate buttons"""
        is_package_tab = (index == 0)
        is_settings_tab = (index == 1)

        # Show/hide package-related buttons
        self.install_selected_button.setVisible(is_package_tab)
        self.playwright_install_button.setVisible(is_package_tab)
        self.select_all_button.setVisible(is_package_tab)
        self.deselect_all_button.setVisible(is_package_tab)

        # Show/hide navigation buttons
        self.previous_button.setVisible(is_settings_tab)
        self.next_button.setVisible(is_package_tab)
        self.continue_button.setVisible(is_settings_tab)

    def _next_page(self):
        """Go to next tab (settings)"""
        current_index = self.tab_widget.currentIndex()
        if current_index < self.tab_widget.count() - 1:
            self.tab_widget.setCurrentIndex(current_index + 1)

    def _previous_page(self):
        """Go to previous tab (packages)"""
        current_index = self.tab_widget.currentIndex()
        if current_index > 0:
            self.tab_widget.setCurrentIndex(current_index - 1)

    def _check_packages(self):
        """Check which packages are installed and create UI"""
        self.package_status.clear()
        self.missing_packages.clear()
        self.package_checkboxes.clear()

        # Clear existing widgets
        for i in reversed(range(self.package_layout.count())):
            child = self.package_layout.itemAt(i).widget()
            if child:
                child.setParent(None)

        required_missing = 0
        xpath_missing = 0
        optional_missing = 0

        # Group packages by category
        categories = {
            'required': [],
            'xpath': [],
            'optional': []
        }

        for import_name, pip_name, description, category in self.package_definitions:
            is_available = self._check_package_availability(import_name)
            self.package_status[pip_name] = is_available
            
            categories[category].append((import_name, pip_name, description, is_available))
            
            if not is_available:
                self.missing_packages.append(pip_name)
                if category == 'required':
                    required_missing += 1
                elif category == 'xpath':
                    xpath_missing += 1
                else:
                    optional_missing += 1

        # Create package sections
        self._create_package_section("Required Packages", categories['required'], 
                                   "These packages are essential for basic functionality.", 
                                   "#e74c3c", True)
                                   
        self._create_package_section("XPath/Scraping Packages", categories['xpath'],
                                   "These packages enable web scraping and data extraction features.",
                                   "#f39c12", False)
                                   
        self._create_package_section("Optional Packages", categories['optional'],
                                   "These packages provide additional convenience features.",
                                   "#27ae60", False)

        # Update status and buttons
        self._update_installation_status(required_missing, xpath_missing, optional_missing)
        self._add_special_checks()

    def _create_package_section(self, title, packages, description, color, is_required):
        """Create a section for a package category"""
        # Section header
        section_frame = QFrame()
        section_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {color};
                border-radius: 6px;
                padding: 6px;
                margin: 2px 0px;
            }}
        """)
        
        header_layout = QVBoxLayout(section_frame)
        title_label = QLabel(f"<b>{title}</b>")
        title_label.setStyleSheet("color: white; font-size: 13px;")
        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: white; font-size: 11px;")
        desc_label.setWordWrap(True)
        
        header_layout.addWidget(title_label)
        header_layout.addWidget(desc_label)
        self.package_layout.addWidget(section_frame)

        # Package widgets
        for import_name, pip_name, package_desc, is_available in packages:
            package_widget = self._create_package_widget(
                pip_name, package_desc, is_available, is_required
            )
            self.package_layout.addWidget(package_widget)

    def _create_package_widget(self, package_name, description, is_available, is_required):
        """Create a widget showing package status with optional checkbox"""
        widget = QFrame()
        widget.setFrameStyle(QFrame.Box)
        widget.setStyleSheet("""
            QFrame {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                padding: 10px;
                margin: 2px;
                background-color: #ffffff;
            }
        """)

        layout = QHBoxLayout(widget)

        # Status icon
        status_label = QLabel()
        if is_available:
            status_icon = load_icon("checkbox", "green", 24)
            status_label.setPixmap(status_icon.pixmap(24, 24))
        else:
            status_icon = load_icon("cancel", "red", 24) if is_required else load_icon("exclamation-circle", "orange", 24)
            status_label.setPixmap(status_icon.pixmap(24, 24))

        # Package info
        info_widget = QWidget()
        info_layout = QVBoxLayout(info_widget)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(2)
        
        name_label = QLabel(f"<b>{package_name}</b>")
        name_label.setStyleSheet("font-size: 12px;")
        
        desc_label = QLabel(description)
        desc_label.setStyleSheet("font-size: 11px; color: #7f8c8d;")
        desc_label.setWordWrap(True)
        
        info_layout.addWidget(name_label)
        info_layout.addWidget(desc_label)

        # Checkbox for selection (only for non-required missing packages)
        selection_widget = QWidget()
        selection_widget.setFixedWidth(80)
        selection_layout = QVBoxLayout(selection_widget)
        selection_layout.setContentsMargins(0, 0, 0, 0)
        
        if not is_available:
            if is_required:
                required_label = QLabel("REQUIRED")
                required_label.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 10px;")
                required_label.setAlignment(Qt.AlignCenter)
                selection_layout.addWidget(required_label)
            else:
                checkbox = QCheckBox("Install")
                checkbox.setStyleSheet("font-size: 11px;")
                checkbox.setChecked(False)  # Default: optional packages selected
                checkbox.toggled.connect(self._on_package_selection_changed)
                self.package_checkboxes[package_name] = checkbox
                selection_layout.addWidget(checkbox)
        else:
            installed_label = QLabel("INSTALLED")
            installed_label.setStyleSheet("color: #27ae60; font-weight: bold; font-size: 10px;")
            installed_label.setAlignment(Qt.AlignCenter)
            selection_layout.addWidget(installed_label)

        layout.addWidget(status_label)
        layout.addWidget(info_widget, 1)
        layout.addWidget(selection_widget)

        return widget

    def _update_installation_status(self, required_missing, xpath_missing, optional_missing):
        """Update the status label and installation buttons"""
        total_missing = required_missing + xpath_missing + optional_missing
        
        if total_missing == 0:
            self.status_label_icon = load_icon("checkbox", "green", 20)
            self.status_label_icon_l.setPixmap(self.status_label_icon.pixmap(20, 20))
            self.status_label.setText(tr('All packages are installed!', 'Startup'))
            self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            self.install_selected_button.setEnabled(False)
            self.select_all_button.setEnabled(False)
            self.deselect_all_button.setEnabled(False)
        elif required_missing > 0:
            self.status_label_icon = load_icon("cancel", "red", 20)
            self.status_label_icon_l.setPixmap(self.status_label_icon.pixmap(20, 20))
            self.status_label.setText(tr('Critical packages missing! Application cannot start without required packages.', 'Startup'))
            self.status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
            self.install_selected_button.setEnabled(True)
            self.select_all_button.setEnabled(True)
            self.deselect_all_button.setEnabled(True)
        else:
            self.status_label_icon = load_icon("exclamation-circle", "orange", 20)
            self.status_label_icon_l.setPixmap(self.status_label_icon.pixmap(20, 20))
            optional_count = xpath_missing + optional_missing
            self.status_label.setText(tr('{0} optional package(s) available for installation.', 'Startup').format(optional_count))
            self.status_label.setStyleSheet("color: #f39c12; font-weight: bold;")
            self.install_selected_button.setEnabled(True)
            self.select_all_button.setEnabled(True)
            self.deselect_all_button.setEnabled(True)

    def _on_package_selection_changed(self):
        """Handle checkbox state changes"""
        self._update_selected_packages()
        self._update_install_button_state()

    def _update_selected_packages(self):
        """Update the list of selected packages for installation"""
        self.selected_packages.clear()
        
        # Always include required missing packages
        for import_name, pip_name, description, category in self.package_definitions:
            if category == "required" and not self.package_status.get(pip_name, False):
                self.selected_packages.append(pip_name)
        
        # Add optional packages that are checked
        for package_name, checkbox in self.package_checkboxes.items():
            if checkbox.isChecked():
                self.selected_packages.append(package_name)

    def _update_install_button_state(self):
        """Update install button text and state"""
        self._update_selected_packages()
        count = len(self.selected_packages)
        
        if count == 0:
            self.install_selected_button.setText(tr("No packages selected", "Startup"))
            self.install_selected_button.setEnabled(False)
        else:
            self.install_selected_button.setText(tr("Install {0} Selected Package(s)", "Startup").format(count))
            self.install_selected_button.setEnabled(True)

    def _select_all_optional(self):
        """Select all optional packages"""
        for checkbox in self.package_checkboxes.values():
            checkbox.setChecked(True)

    def _deselect_all_optional(self):
        """Deselect all optional packages"""
        for checkbox in self.package_checkboxes.values():
            checkbox.setChecked(False)

    def _install_selected_packages(self):
        """Install selected packages"""
        self._update_selected_packages()
        
        if not self.selected_packages:
            QMessageBox.information(self, tr("No Selection", "Startup"), 
                                  tr("Please select at least one package to install.", "Startup"))
            return

        self.install_selected_button.setEnabled(False)
        self.playwright_install_button.setEnabled(False)
        self.select_all_button.setEnabled(False)
        self.deselect_all_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress

        command = [sys.executable, "-m", "pip", "install"] + self.selected_packages
        self.logger.info(f"Installing packages: {self.selected_packages}")

        self.installer = PackageInstaller(command)
        self.installer.progress_updated.connect(self._on_installation_progress)
        self.installer.installation_finished.connect(self._on_installation_finished)
        self.installer.start()

    def _check_package_availability(self, package_name):
        """Check if a package is available for import"""
        try:
            importlib.import_module(package_name)
            return True
        except ImportError:
            return False

    def _add_special_checks(self):
        """Add special checks for system requirements"""
        if "playwright" in [pkg for _, pkg, _, _ in self.package_definitions]:
            self.playwright_browsers_missing = not self._check_playwright_browsers()
            browser_widget = self._create_special_check_widget(
                tr("Playwright Browsers", "Startup"),
                tr("Required for web scraping functionality", "Startup"),
                not self.playwright_browsers_missing
            )
            self.package_layout.addWidget(browser_widget)
            self.playwright_install_button.setEnabled(self.playwright_browsers_missing)
        # Check for write permissions in assets directory
        assets_writable = self._check_assets_directory()
        assets_widget = self._create_special_check_widget(
            tr("Assets Directory", "Startup"),
            tr("Write permissions for cache and config files", "Startup"),
            assets_writable
        )
        self.package_layout.addWidget(assets_widget)

    def _check_playwright_browsers(self):
        """Check if Playwright browsers are installed"""
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                # Try to get browser, this will fail if not installed
                try:
                    browser = p.chromium.launch(headless=True)
                    browser.close()
                    return True
                except Exception:
                    return False
        except ImportError:
            return False

    def _check_assets_directory(self):
        """Check if assets directory exists and is writable"""

        self.user_dir = Path("user_data")
        try:
            (self.user_dir / "cache").mkdir(exist_ok=True)
            (self.user_dir / "config").mkdir(exist_ok=True)

            # Test write permissions
            test_file = self.user_dir / "test_write.tmp"
            test_file.write_text("test")
            test_file.unlink()
            return True
        except Exception as e:
            print(e)
            return False

    def _create_special_check_widget(self, name, description, is_available):
        """Create a widget for special system checks"""
        widget = QFrame()
        widget.setFrameStyle(QFrame.Box)
        widget.setStyleSheet("""
            QFrame {
                border: 1px solid #bdc3c7;
                border-radius: 4px;
                padding: 8px;
                margin: 2px;
                background-color: #f8f9fa;
            }
        """)

        layout = QVBoxLayout(widget)

        # Header layout
        header_layout = QHBoxLayout()

        # Status icon

        install_status_label = QLabel()
        install_status_icon = load_icon("checkbox", "green", 20) if is_available else load_icon("exclamation-circle", "yellow", 20)
        install_status_label.setPixmap(install_status_icon.pixmap(20, 20))



        # Name and description
        name_label = QLabel(f"<b>{name}</b>")
        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: #7f8c8d;")

        header_layout.addWidget(install_status_label)
        header_layout.addWidget(name_label)
        header_layout.addWidget(desc_label, 1)

        layout.addLayout(header_layout)

        return widget

    def _install_missing_packages(self):
        """Install missing packages"""
        if not self.missing_packages:
            return

        self.install_selected_button.setEnabled(False)
        self.playwright_install_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress

        command = [sys.executable, "-m", "pip", "install"] + self.missing_packages

        self.installer = PackageInstaller(command)
        self.installer.progress_updated.connect(self._on_installation_progress)
        self.installer.installation_finished.connect(self._on_installation_finished)
        self.installer.start()

    def _install_playwright_browsers(self):
        """Install Playwright browsers"""
        self.install_selected_button.setEnabled(False)
        self.playwright_install_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress

        command = [sys.executable, "-m", "playwright", "install"]

        self.installer = PackageInstaller(command)
        self.installer.progress_updated.connect(self._on_installation_progress)
        self.installer.installation_finished.connect(self._on_playwright_installation_finished)
        self.installer.start()

    def _on_installation_progress(self, message):
        """Handle installation progress updates"""
        self.status_label.setText(message)
        self.status_label.setStyleSheet("color: #3498db; font-weight: bold;")

    def _on_installation_finished(self, success, message):
        """Handle package installation completion"""
        self.progress_bar.setVisible(False)
        self.select_all_button.setEnabled(True)
        self.deselect_all_button.setEnabled(True)

        if success:
            self.status_label.setText(message)
            self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")
            self.logger.info(f"Package installation successful: {message}")

            # Recheck packages after installation
            QTimer.singleShot(1000, self._check_packages)
        else:
            self.status_label.setText(message)
            self.status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")
            self.logger.error(f"Package installation failed: {message}")

            # Re-enable buttons even on failure
            self.install_selected_button.setEnabled(True)
            self.playwright_install_button.setEnabled(self.playwright_browsers_missing)

            QMessageBox.critical(self, tr("Installation Error", "Startup"), message)

    def _on_playwright_installation_finished(self, success, message):
        """Handle Playwright browser installation completion"""
        self.progress_bar.setVisible(False)
        self.install_selected_button.setEnabled(bool(self.missing_packages))
        self.playwright_install_button.setEnabled(not success)

        if success:
            self.status_label.setText(message)
            self.status_label.setStyleSheet("color: #27ae60; font-weight: bold;")

            # Recheck packages after installation
            QTimer.singleShot(1000, self._check_packages)
        else:
            self.status_label.setText(message)
            self.status_label.setStyleSheet("color: #e74c3c; font-weight: bold;")

            QMessageBox.critical(self, tr("Installation Error", "Startup"), message)

    def _load_current_settings(self):
        """Load current settings into the form"""
        # Language
        language = self.settings.get("language", "auto")
        index = self.language_combo.findText(language)
        if index >= 0:
            self.language_combo.setCurrentIndex(index)

        # Timezone
        timezone = self.settings.get("your_timezone", 2, int)
        self.timezone_spin.setValue(timezone)

        # Paths
        self.image_cache_edit.setText(self.settings.get("image_cache_dir", "user_data/img"))
        self.favicon_cache_edit.setText(self.settings.get("favicon_cache_dir", "user_data/favicons"))

        # Scraping
        scraping_engine = self.settings.get("Plugins/scraping_engine", "playwright")
        index = self.scraping_engine_combo.findText(scraping_engine)
        if index >= 0:
            self.scraping_engine_combo.setCurrentIndex(index)

        self.hide_xpath_checkbox.setChecked(self.settings.get("hide_xpath_buttons", False, bool))

        # Theme
        theme = self.settings.get("theme", "auto")
        index = self.theme_combo.findText(theme)
        if index >= 0:
            self.theme_combo.setCurrentIndex(index)

    def _save_settings(self):
        """Save settings from the form"""
        # Language
        self.settings.set("language", self.language_combo.currentText())

        # Timezone
        self.settings.set("your_timezone", self.timezone_spin.value())

        # Paths
        self.settings.set("image_cache_dir", self.image_cache_edit.text())
        self.settings.set("favicon_cache_dir", self.favicon_cache_edit.text())

        # Scraping
        self.settings.set("Plugins/scraping_engine", self.scraping_engine_combo.currentText())
        self.settings.set("hide_xpath_buttons", self.hide_xpath_checkbox.isChecked())

        # Theme
        self.settings.set("theme", self.theme_combo.currentText())

        # Mark that initial setup is complete
        self.settings.set("initial_setup_complete", True)

        # Sync settings
        self.settings.sync()

        # Create directories if they don't exist
        self._create_directories()

        QMessageBox.information(self, tr("Settings Saved", "Startup"),
                                tr("Settings have been saved successfully!", "Startup"))

    def _browse_directory(self, line_edit):
        """
        Open a directory browser dialog and set the selected path to the line edit.
        """
        current_path = line_edit.text()

        # If current path is relative, make it absolute for the dialog
        if not os.path.isabs(current_path):
            current_path = os.path.abspath(current_path)

        # Ensure the directory exists for the dialog to start from
        if not os.path.exists(current_path):
            # Try parent directory
            parent_dir = os.path.dirname(current_path)
            if os.path.exists(parent_dir):
                current_path = parent_dir
            else:
                # Fall back to current working directory
                current_path = os.getcwd()

        selected_dir = QFileDialog.getExistingDirectory(
            self,
            tr("Select Directory", "Startup"),
            current_path,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if selected_dir:
            # Convert to relative path if it's within the current working directory
            try:
                cwd = os.getcwd()
                if selected_dir.startswith(cwd):
                    relative_path = os.path.relpath(selected_dir, cwd)
                    # Use forward slashes for consistency across platforms
                    relative_path = relative_path.replace(os.sep, '/')
                    line_edit.setText(relative_path)
                else:
                    # Use absolute path with forward slashes
                    absolute_path = selected_dir.replace(os.sep, '/')
                    line_edit.setText(absolute_path)
            except (ValueError, OSError):
                # Fallback to absolute path if relative path calculation fails
                absolute_path = selected_dir.replace(os.sep, '/')
                line_edit.setText(absolute_path)

    def _browse_file(self, line_edit):
        """
        Open a file browser dialog and set the selected path to the line edit.
        """
        current_path = line_edit.text()

        # If current path is relative, make it absolute for the dialog
        if not os.path.isabs(current_path):
            current_path = os.path.abspath(current_path)

        # Get directory for the dialog to start from
        if os.path.isfile(current_path):
            start_dir = os.path.dirname(current_path)
            filename = os.path.basename(current_path)
        else:
            start_dir = os.path.dirname(current_path)
            filename = os.path.basename(current_path)

            # If directory doesn't exist, try parent or fall back to cwd
            if not os.path.exists(start_dir):
                parent_dir = os.path.dirname(start_dir)
                if os.path.exists(parent_dir):
                    start_dir = parent_dir
                else:
                    start_dir = os.getcwd()

        selected_file, _ = QFileDialog.getSaveFileName(
            self,
            tr("Select Log File", "Startup"),
            os.path.join(start_dir, filename),
            tr("Log Files (*.log *.txt);;All Files (*)", "Startup")
        )

        if selected_file:
            # Convert to relative path if it's within the current working directory
            try:
                cwd = os.getcwd()
                if selected_file.startswith(cwd):
                    relative_path = os.path.relpath(selected_file, cwd)
                    # Use forward slashes for consistency across platforms
                    relative_path = relative_path.replace(os.sep, '/')
                    line_edit.setText(relative_path)
                else:
                    # Use absolute path with forward slashes
                    absolute_path = selected_file.replace(os.sep, '/')
                    line_edit.setText(absolute_path)
            except (ValueError, OSError):
                # Fallback to absolute path if relative path calculation fails
                absolute_path = selected_file.replace(os.sep, '/')
                line_edit.setText(absolute_path)

    def _on_theme_changed(self, theme_preference):
        """Apply theme immediately when changed in the startup screen"""
        theme_manager.apply_theme_by_preference(theme_preference)

    def _create_directories(self):
        """Create necessary directories"""
        directories = [
            self.image_cache_edit.text(),
            self.favicon_cache_edit.text(),
            self.user_dir / "cache",
            self.user_dir / "config"
        ]

        for directory in directories:
            try:
                Path(directory).mkdir(parents=True, exist_ok=True)
            except Exception as e:
                QMessageBox.warning(self, tr("Directory Error", "Startup"),
                                    f"Could not create directory {directory}: {e}")

    def _continue_to_app(self):
        """Continue to the main application"""
        # Check if critical packages are available
        critical_missing = []
        for import_name, pip_name, _, category in self.package_definitions:
            if category == "required" and not self._check_package_availability(import_name):
                critical_missing.append(pip_name)

        if critical_missing:
            # Switch back to package tab to show the issue
            self.tab_widget.setCurrentIndex(0)
            QMessageBox.critical(
                self,
                tr("Critical Dependencies Missing", "Startup"),
                f"{tr('The following critical packages are required:', 'Startup')} {', '.join(critical_missing)}\n\n"
                f"{tr('Please install them on the Package Dependencies tab before continuing.', 'Startup')}",
            )
            return

        # Warn about missing optional packages
        optional_missing = []
        for import_name, pip_name, _, category in self.package_definitions:
            if category in ["xpath", "optional"] and not self._check_package_availability(import_name):
                optional_missing.append(pip_name)
        
        if optional_missing:
            reply = QMessageBox.question(
                self,
                tr("Optional Dependencies", "Startup"),
                f"{tr('The following optional packages are missing:', 'Startup')} {', '.join(optional_missing)}\n\n"
                f"{tr('Some features may be unavailable. Continue anyway?', 'Startup')}",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes
            )

            if reply == QMessageBox.No:
                # Switch back to package tab
                self.tab_widget.setCurrentIndex(0)
                return

        # Save current settings before continuing
        self._save_settings()
        self.accept()

    def should_show_startup_screen(self):
        """Check if startup screen should be shown"""
        # Show if initial setup is not complete
        if not self.settings.get("initial_setup_complete", False, bool):
            return True

        # Show if critical packages are missing - korrigiere hier auch
        for import_name, _, _, category in self.package_definitions:
            if category == "required" and not self._check_package_availability(import_name):
                return True

        return False