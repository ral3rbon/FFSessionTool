from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QLabel, QLineEdit, QComboBox,
    QPushButton, QSpinBox, QToolButton, QWidget, QScrollArea, QSizePolicy, QTextEdit, QTabWidget
)
from PySide6.QtCore import Qt
from app.utils.ui_translator import tr
from app.ui.helpers.ui_icon_loader import load_icon
from app.src.settings import AppSettings

from app.ui.dialogs.about_dialog import AboutDialog

class SettingsDialog(QDialog):
    def __init__(self, app_settings: AppSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Settings", "dialog"))
        self.setMinimumWidth(500)
        self.settings = app_settings
        self._toggles = {}
        self._inputs = {}
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        scroll.setWidget(container)
        form_layout = QVBoxLayout(container)
        form_layout.setAlignment(Qt.AlignTop)

        # --- Kategorien definieren ---
        categories = [
            ("General", [
                ("language", tr("Language", "settings"), "str"),
                ("theme", tr("Theme", "settings"), "str"),
                ("your_timezone", tr("Timezone", "settings"), "int"),
            ]),
            ("Paths", [
                ("image_cache_dir", tr("Image Cache Directory", "settings"), "str"),
                ("favicon_cache_dir", tr("Favicon Cache Directory", "settings"), "str"),
            ]),
            ("Plugins", [
                ("Plugins/xpath_enabled", tr("Enable XPath Plugin", "settings"), "bool"),
                ("Plugins/scraping_engine", tr("Scraping Engine", "settings"), "str"),
            ]),
            ("Browser Agent", [
                ("browser_agent/User-Agent", "User-Agent", "str"),
                ("browser_agent/Accept", "Accept", "str"),
                ("browser_agent/Accept-Language", "Accept-Language", "str"),
                ("browser_agent/Accept-Encoding", "Accept-Encoding", "str"),
                ("browser_agent/Connection", "Connection", "str"),
                ("browser_agent/Upgrade-Insecure-Requests", "Upgrade-Insecure-Requests", "str"),
                ("browser_agent/Sec-Fetch-Dest", "Sec-Fetch-Dest", "str"),
                ("browser_agent/Sec-Fetch-Mode", "Sec-Fetch-Mode", "str"),
                ("browser_agent/Sec-Fetch-Site", "Sec-Fetch-Site", "str"),
                ("browser_agent/Sec-Fetch-User", "Sec-Fetch-User", "str"),
            ]),
        ]

        # --- read defined values "categories" and build UI---
        for cat_name, fields in categories:
            group = QGroupBox(tr(cat_name, "settings"))
            group_layout = QFormLayout(group)
            for key, label, typ in fields:
                val = self.settings.get(key)
                if typ == "bool":
                    toggle = QToolButton()
                    toggle.setCheckable(True)
                    toggle.setChecked(bool(val))
                    toggle.setAutoRaise(True)
                    toggle.setStyleSheet("QToolButton { border: none; background: transparent; }")
                    self._set_toggle_icon(toggle, bool(val))
                    toggle.toggled.connect(lambda checked, k=key, btn=toggle: self._on_toggle(k, checked, btn))
                    group_layout.addRow(label, toggle)
                    self._toggles[key] = toggle
                elif typ == "int":
                    spin = QSpinBox()
                    spin.setMinimum(-12)
                    spin.setMaximum(14)
                    spin.setValue(int(val))
                    spin.valueChanged.connect(lambda v, k=key: self.settings.set(k, v))
                    group_layout.addRow(label, spin)
                    self._inputs[key] = spin
                elif typ == "str":
                    # Use Combobox for known fields
                    if key == "language":
                        combo = QComboBox()
                        combo.addItems(["auto", "en", "de"])
                        combo.setCurrentText(str(val))
                        combo.currentTextChanged.connect(lambda v, k=key: self.settings.set(k, v))
                        group_layout.addRow(label, combo)
                        self._inputs[key] = combo
                    elif key == "theme":
                        combo = QComboBox()
                        combo.addItems(["auto", "light", "dark"])
                        combo.setCurrentText(str(val))
                        combo.currentTextChanged.connect(lambda v, k=key: self.settings.set(k, v))
                        group_layout.addRow(label, combo)
                        self._inputs[key] = combo
                    elif key == "Plugins/scraping_engine":
                        combo = QComboBox()
                        combo.addItems(["requests", "playwright"])
                        combo.setCurrentText(str(val))
                        combo.currentTextChanged.connect(lambda v, k=key: self.settings.set(k, v))
                        group_layout.addRow(label, combo)
                        self._inputs[key] = combo
                    else:
                        line = QLineEdit(str(val))
                        line.editingFinished.connect(lambda k=key, l=line: self.settings.set(k, l.text()))
                        group_layout.addRow(label, line)
                        self._inputs[key] = line
            form_layout.addWidget(group)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        
        # About button on the left
        about_btn = QPushButton(tr("About", "settings"))
        about_btn.setIcon(load_icon("info-circle"))
        about_btn.clicked.connect(self._show_about)
        btn_row.addWidget(about_btn)
        
        btn_row.addStretch(1)
        
        save_btn = QPushButton(tr("Save", "settings"))
        save_btn.setIcon(load_icon("device-floppy"))
        save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(save_btn)
        close_btn = QPushButton(tr("Close", "settings"))
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)


        layout.addWidget(scroll)
        layout.addLayout(btn_row)

    def _set_toggle_icon(self, btn: QToolButton, checked: bool):
        if checked:
            btn.setIcon(load_icon("toggle-right", "#2ecc71", size=20))
        else:
            btn.setIcon(load_icon("toggle-left", None, size=20))

    def _on_toggle(self, key, checked, btn):
        self.settings.set(key, checked)
        self._set_toggle_icon(btn, checked)

    def _on_save(self):
        self.settings.sync()
        self.accept()

    def _show_about(self):
        """Show the about dialog with license information"""
        about_dialog = AboutDialog(self)
        about_dialog.exec()
