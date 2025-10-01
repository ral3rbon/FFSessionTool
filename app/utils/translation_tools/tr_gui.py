#!/usr/bin/env python3
"""
Translation Manager GUI for JsonLz4Tool

GUI-Version des Translation Managers mit allen Funktionen:
- Dropbox für Sprachauswahl mit + Button für neue Sprachen
- Tabelle mit Original, Übersetzung und Vorkommen
- Update und Speicher Buttons
- Kategorien-basierte Anzeige
- Google Translate Integration mit Nutzererlaubnis
"""

import os
import sys
import re
import json
import requests
from pathlib import Path
from typing import Dict, List, Set, Tuple
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QComboBox, 
    QLabel, QInputDialog, QMessageBox, QHeaderView, QProgressDialog,
    QSplitter, QFrame, QCheckBox, QTextEdit, QDialog, QDialogButtonBox,
    QGroupBox, QSpinBox
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer, QSettings
from PySide6.QtGui import QFont, QColor, QAction

# Import der bestehenden Module
#sys.path.append(os.path.join(os.path.dirname(__file__), 'app', 'utils'))
try:
    from app.utils.ui_translator import CategorizedTranslator
except ImportError:
    print("Warning: Could not import CategorizedTranslator")
    CategorizedTranslator = None

try:
    from googletrans import Translator
    GOOGLE_TRANSLATE_AVAILABLE = True
except ImportError:
    GOOGLE_TRANSLATE_AVAILABLE = False
    print("Warning: googletrans not installed. Install with: pip install googletrans==4.0.0rc1")

class StringExtractorThread(QThread):
    """Thread for extracting the Strings from the Sourcecode"""
    progress = Signal(int)
    finished_extraction = Signal(dict, dict)  # strings_by_category, line_numbers
    
    def __init__(self):
        super().__init__()
        project_root = os.path.dirname(__file__) + "/../../.."
        self.project_root = Path(project_root)
        print(self.project_root)
        self.app_dir = self.project_root / "app"
    
    def run(self):
        """Extrahiere Strings aus dem Quellcode"""
        strings_by_category = {}
        line_numbers = {}  # key -> [(file, line_num), ...]
        
        tr_pattern_with_category = re.compile(
            r'tr\s*\(\s*["\']([^"\']+)["\']\s*,\s*["\']([^"\']+)["\']\s*[,\)]', 
            re.MULTILINE
        )
        tr_pattern_simple = re.compile(
            r'tr\s*\(\s*["\']([^"\']+)["\']\s*[,\)]', 
            re.MULTILINE
        )
        
        py_files = list(self.app_dir.rglob("*.py"))
        total_files = len(py_files)
        
        for i, py_file in enumerate(py_files):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                
                # Suche nach tr() Aufrufen mit Kategorie
                for match in tr_pattern_with_category.finditer(content):
                    text = match.group(1)
                    category = match.group(2)
                    
                    if category not in strings_by_category:
                        strings_by_category[category] = set()
                    strings_by_category[category].add(text)
                    
                    # Finde Zeilennummer
                    line_num = content[:match.start()].count('\n') + 1
                    if text not in line_numbers:
                        line_numbers[text] = []
                    line_numbers[text].append((py_file.name, line_num))
                
                # Suche nach tr() Aufrufen ohne Kategorie
                content_without_category_matches = content
                for match in reversed(list(tr_pattern_with_category.finditer(content))):
                    content_without_category_matches = (
                        content_without_category_matches[:match.start()] + 
                        content_without_category_matches[match.end():]
                    )
                
                for match in tr_pattern_simple.finditer(content_without_category_matches):
                    text = match.group(1)
                    
                    if "General" not in strings_by_category:
                        strings_by_category["General"] = set()
                    strings_by_category["General"].add(text)
                    
                    # Finde Zeilennummer im ursprünglichen Content
                    original_matches = list(tr_pattern_simple.finditer(content))
                    for orig_match in original_matches:
                        if orig_match.group(1) == text:
                            line_num = content[:orig_match.start()].count('\n') + 1
                            if text not in line_numbers:
                                line_numbers[text] = []
                            line_numbers[text].append((py_file.name, line_num))
                            break
            
            except Exception as e:
                print(f"Error reading {py_file}: {e}")
            
            # Progress update
            progress_value = int((i + 1) / total_files * 100)
            self.progress.emit(progress_value)
        
        # Konvertiere sets zu lists für JSON serialization
        for category in strings_by_category:
            strings_by_category[category] = list(strings_by_category[category])
        
        self.finished_extraction.emit(strings_by_category, line_numbers)
    
class GoogleTranslateConsentDialog(QDialog):
    """Dialog for Google Translate consent and settings"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Google Translate Settings")
        self.setModal(True)
        self.resize(500, 400)
        
        layout = QVBoxLayout(self)
        
        # Warning text
        warning_label = QLabel(
            "<b>Google Translate Integration</b><br><br>"
            "This feature uses Google Translate to automatically translate text. "
            "Please be aware of the following:<br><br>"
            "• Translations may not be accurate and require proofreading<br>"
            "• Special characters like '\\n' may be incorrectly spaced<br>"
            "• Your text will be sent to Google's servers<br>"
            "• Usage may be subject to Google's rate limits<br><br>"
            "Do you want to enable Google Translate integration?"
        )
        warning_label.setWordWrap(True)
        layout.addWidget(warning_label)
        
        # Settings group
        settings_group = QGroupBox("Translation Settings")
        settings_layout = QVBoxLayout(settings_group)
        
        # Auto-translate delay
        delay_layout = QHBoxLayout()
        delay_layout.addWidget(QLabel("Delay between translations (ms):"))
        self.delay_spinbox = QSpinBox()
        self.delay_spinbox.setRange(100, 5000)
        self.delay_spinbox.setValue(500)
        self.delay_spinbox.setSuffix(" ms")
        delay_layout.addWidget(self.delay_spinbox)
        delay_layout.addStretch()
        settings_layout.addLayout(delay_layout)
        
        # Confirmation for batch translate
        self.batch_confirm_checkbox = QCheckBox("Always ask before batch translation")
        self.batch_confirm_checkbox.setChecked(True)
        settings_layout.addWidget(self.batch_confirm_checkbox)
        
        layout.addWidget(settings_group)
        
        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
    
    def get_settings(self):
        return {
            'delay': self.delay_spinbox.value(),
            'batch_confirm': self.batch_confirm_checkbox.isChecked()
        }

class TranslationManagerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.project_root = Path("../../..")
        self.translations_dir = self.project_root / "assets" / "lang"
        self.app_dir = self.project_root / "app"
        
        # Settings with grouped keys
        self.settings = QSettings("JsonLz4Tool", "TranslationManager")
        self.google_translate_enabled = self.settings.value("translation_manager/google_translate_enabled", False, bool)
        self.translation_delay = self.settings.value("translation_manager/translation_delay", 500, int)
        self.batch_confirm = self.settings.value("translation_manager/batch_confirm", True, bool)
        
        self.strings_by_category = {}
        self.line_numbers = {}
        self.current_translations = {}
        
        self.setWindowTitle("Translation Manager - JsonLz4Tool")
        self.setGeometry(100, 100, 1400, 900)
        self.setup_ui()
        self.create_menu_bar()
        self.load_available_languages()
        
        self.extractor_thread = None
        self.translation_timer = QTimer()
        self.translation_timer.setSingleShot(True)
        self.pending_translations = []

        # Language Code Mapping for GoogleTranslate
        self.lang_code_mapping = {
            "en": "en",  # english
            "de": "de",  # german
            "fr": "fr",  # french
            "es": "es",  # spanish
            "it": "it",  # italian
            "pt": "pt",  # portuguese
            "ru": "ru",  # russian
            "ja": "ja",  # japanese
            "ko": "ko",  # korean
            "zh": "zh",  # chinese
            "ar": "ar",  # arabic
            "hi": "hi",  # hindi
            "tr": "tr",  # turkish
            "pl": "pl",  # polish
            "nl": "nl",  # dutch
            "sv": "sv",  # swedish
            "da": "da",  # danish
            "no": "no",  # norwegian
            "fi": "fi",  # finnish
            "cs": "cs",  # czech
            "hu": "hu",  # hungarian
            "ro": "ro",  # romanian
            "bg": "bg",  # bulgarian
            "hr": "hr",  # croatian
            "sk": "sk",  # slovak
            "sl": "sl",  # slovenian
            "et": "et",  # estonian
            "lv": "lv",  # latvian
            "lt": "lt",  # lithuanian
            "mt": "mt",  # maltese
            "el": "el",  # greek
            "cy": "cy",  # welsh
            "ga": "ga",  # irish
            "is": "is",  # icelandic
            "mk": "mk",  # macedonian
            "sq": "sq",  # alabanian
        }

        if GOOGLE_TRANSLATE_AVAILABLE:
            self.translator = Translator()
        else:
            self.translator = None
    
    def create_menu_bar(self):
        """Create menu bar with additional options"""
        menubar = self.menuBar()
        
        # Settings menu
        settings_menu = menubar.addMenu("Settings")
        
        translate_action = QAction("Google Translate Settings...", self)
        translate_action.triggered.connect(self.show_google_translate_settings)
        settings_menu.addAction(translate_action)
        
        settings_menu.addSeparator()
        
        reset_action = QAction("Reset All Settings", self)
        reset_action.triggered.connect(self.reset_settings)
        settings_menu.addAction(reset_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        
        about_action = QAction("About Translation Keys", self)
        about_action.triggered.connect(self.show_translation_help)
        help_menu.addAction(about_action)
    
    def show_google_translate_settings(self):
        """Show Google Translate consent and settings dialog"""
        if not GOOGLE_TRANSLATE_AVAILABLE:
            QMessageBox.warning(
                self, 
                "Google Translate Not Available", 
                "Google Translate is not available.\n\n"
                "Please install googletrans:\n"
                "pip install googletrans==4.0.0rc1"
            )
            return
            
        dialog = GoogleTranslateConsentDialog(self)
        dialog.delay_spinbox.setValue(self.translation_delay)
        dialog.batch_confirm_checkbox.setChecked(self.batch_confirm)
        
        if dialog.exec() == QDialog.Accepted:
            self.google_translate_enabled = True
            settings = dialog.get_settings()
            self.translation_delay = settings['delay']
            self.batch_confirm = settings['batch_confirm']
            
            # Save settings with grouped keys
            self.settings.setValue("translation_manager/google_translate_enabled", True)
            self.settings.setValue("translation_manager/translation_delay", self.translation_delay)
            self.settings.setValue("translation_manager/batch_confirm", self.batch_confirm)
            
            self.status_label.setText("Google Translate enabled - 🌐 buttons are now active")
            self.populate_table()  # Refresh to show translate buttons
        else:
            # User can also disable it here
            if self.google_translate_enabled:
                reply = QMessageBox.question(
                    self, "Disable Google Translate", 
                    "Do you want to disable Google Translate?",
                    QMessageBox.Yes | QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    self.google_translate_enabled = False
                    self.settings.setValue("translation_manager/google_translate_enabled", False)
                    self.status_label.setText("Google Translate disabled")
                    self.populate_table()  # Refresh to show locked buttons
    
    def reset_settings(self):
        """Reset all settings to default"""
        reply = QMessageBox.question(
            self, "Reset Settings", 
            "Are you sure you want to reset all settings to default?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.settings.clear()
            self.google_translate_enabled = False
            self.translation_delay = 500
            self.batch_confirm = True
            self.status_label.setText("Settings reset to default")
            self.populate_table()
    
    def show_translation_help(self):
        """Show help dialog about special characters"""
        help_text = """
<h3>Translation Help</h3>

<h4>Special Characters:</h4>
<ul>
<li><b>\\n</b> - Line break (no spaces around it!)</li>
<li><b>\\t</b> - Tab character</li>
<li><b>{}</b> - Placeholder for dynamic content (keep unchanged)</li>
<li><b>%s, %d, %f</b> - Format placeholders (keep unchanged)</li>
</ul>

<h4>Best Practices:</h4>
<ul>
<li>Preserve placeholders exactly as they are</li>
<li>Test translations in the actual application</li>
<li>Consider cultural context, not just literal translation</li>
</ul>
        """
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Translation Help")
        msg.setTextFormat(Qt.RichText)
        msg.setText(help_text)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()

    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Header mit Titel
        header_label = QLabel("Translation Manager")
        header_font = QFont()
        header_font.setPointSize(16)
        header_font.setBold(True)
        header_label.setFont(header_font)
        header_label.setAlignment(Qt.AlignCenter)

        # Improved warning text
        header_small = QLabel("Click the Settings button to enable Google Translate. Always proofread automated translations!")
        header_small_font = QFont()
        header_small_font.setPointSize(11)
        header_small.setFont(header_small_font)
        header_small.setAlignment(Qt.AlignCenter)
        header_small.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(header_label)
        layout.addWidget(header_small)

        # Language selection with settings button
        lang_frame = QFrame()
        lang_frame.setFrameStyle(QFrame.Box)
        lang_layout = QHBoxLayout(lang_frame)
        
        lang_layout.addWidget(QLabel("Language:"))
        
        self.language_combo = QComboBox()
        self.language_combo.setMinimumWidth(150)
        self.language_combo.currentTextChanged.connect(self.on_language_changed)
        lang_layout.addWidget(self.language_combo)
        
        self.add_language_btn = QPushButton("+")
        self.add_language_btn.setMaximumWidth(30)
        self.add_language_btn.setToolTip("Add new Language")
        self.add_language_btn.clicked.connect(self.add_new_language)
        lang_layout.addWidget(self.add_language_btn)
        
        # Add Settings button prominently
        self.settings_btn = QPushButton("⚙️ Settings")
        self.settings_btn.setToolTip("Configure Google Translate and other settings")
        self.settings_btn.clicked.connect(self.show_google_translate_settings)
        lang_layout.addWidget(self.settings_btn)
        
        # Add Help button
        self.help_btn = QPushButton("❓ Help")
        self.help_btn.setToolTip("Show translation guidelines and help")
        self.help_btn.clicked.connect(self.show_translation_help)
        lang_layout.addWidget(self.help_btn)
        
        lang_layout.addStretch()
        layout.addWidget(lang_frame)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Original","Auto", "Translation", "Occurs in:"])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.resizeSection(1, 50)  # Fixe Breite für Auto-Translate Button
        
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.itemChanged.connect(self.on_item_changed)
        
        layout.addWidget(self.table)
        
        # Enhanced button layout
        button_layout = QHBoxLayout()
        
        self.update_btn = QPushButton("🔄 Update English Base")
        self.update_btn.setToolTip("Extract all tr() strings from the sourcecode and update the basefile (en).")
        self.update_btn.clicked.connect(self.update_english_base)
        button_layout.addWidget(self.update_btn)
        
        self.missing_btn = QPushButton("🔍 Mark Missing")
        self.missing_btn.setToolTip("Mark missing translations.")
        self.missing_btn.clicked.connect(self.find_missing_translations)
        self.missing_btn.setEnabled(False)
        button_layout.addWidget(self.missing_btn)
        
        # Add statistics label
        self.stats_label = QLabel("Translation Statistics: -")
        button_layout.addWidget(self.stats_label)
        
        button_layout.addStretch()
        
        self.save_btn = QPushButton("💾 Save")
        self.save_btn.setToolTip("Save translation")
        self.save_btn.clicked.connect(self.save_translations)
        self.save_btn.setEnabled(False)
        button_layout.addWidget(self.save_btn)
        
        self.translate_all_btn = QPushButton("🌐 Translate All Missing")
        self.translate_all_btn.setToolTip("Translate all missing strings with Google Translate")
        self.translate_all_btn.clicked.connect(self.translate_all_missing)
        self.translate_all_btn.setEnabled(False)
        button_layout.addWidget(self.translate_all_btn)

        layout.addLayout(button_layout)
        
        # Enhanced status
        self.status_label = QLabel("Ready - Click 'Settings' button to configure Google Translate")
        layout.addWidget(self.status_label)
    
    def load_available_languages(self):
        """Load all json Files to the Combobox"""
        self.language_combo.clear()
        
        languages = []
        if self.translations_dir.exists():
            for file in self.translations_dir.glob("*.json"):
                languages.append(file.stem)
        
        if not languages:
            self.create_empty_translation_file("en")
            languages = ["en"]
        
        languages.sort()
        self.language_combo.addItems(languages)
        
        # Setze Englisch als Standard
        if "en" in languages:
            self.language_combo.setCurrentText("en")
    
    def create_empty_translation_file(self, language_code: str):
        """Create an empty language File with dummy Content"""
        translation_file = self.translations_dir / f"{language_code}.json"
        
        empty_translations = {
            "GUI": {},
            "Labels": {},
            "Actions": {},
            "Messages": {},
            "Bookmarks": {},
            "Translator": {},
            "General": {}
        }
        
        with open(translation_file, 'w', encoding='utf-8') as f:
            json.dump(empty_translations, f, indent=2, ensure_ascii=False, sort_keys=True)

    def update_all_language_files(self, english_translations: Dict):
        """update all language files, with new Strings"""
        updated_count = 0
        
        for lang_file in self.translations_dir.glob("*.json"):
            if lang_file.stem == "en":
                continue 
            
            try:
                with open(lang_file, 'r', encoding='utf-8') as f:
                    existing_translations = json.load(f)
                
                updated_translations = self.merge_translations(english_translations, existing_translations)
                
                with open(lang_file, 'w', encoding='utf-8') as f:
                    json.dump(updated_translations, f, indent=2, ensure_ascii=False, sort_keys=True)
                
                updated_count += 1
            
            except Exception as e:
                self.status_label.setText = f"Error updating {lang_file}: {e}"
                print(f"Error updating {lang_file}: {e}")
        
        if updated_count > 0:
            print(f"{updated_count} language files updated")

    def merge_translations(self, english_base: Dict, existing_translations: Dict) -> Dict:
        """Merge english base with existing Translations"""
        merged = {}
        
        for category, english_strings in english_base.items():
            merged[category] = {}
            existing_category = existing_translations.get(category, {})
            
            for key in english_strings.keys():
                if key in existing_category and existing_category[key].strip():
                    merged[category][key] = existing_category[key]
                else:
                    merged[category][key] = ""
        
        return merged

    def add_new_language(self):
        """Adding new Language"""
        lang_code, ok = QInputDialog.getText(
            self, 
            "New language", 
            "language Codes (ISO 639: de, fr, es ...):"
        )
        
        if ok and lang_code:
            lang_code = lang_code.lower().strip()
            
            translation_file = self.translations_dir / f"{lang_code}.json"
            if translation_file.exists():
                QMessageBox.warning(self, "Error", f"Language '{lang_code}' already exists!")
                return
            
            self.create_language_template(lang_code)
            self.load_available_languages()
            self.language_combo.setCurrentText(lang_code)
            
            self.status_label.setText(f"New language '{lang_code}' created!")
    
    def create_language_template(self, language_code: str):
        english_file = self.translations_dir / "en.json"
        
        if english_file.exists():
            try:
                with open(english_file, 'r', encoding='utf-8') as f:
                    english_translations = json.load(f)
                
                template = {}
                for category, translations in english_translations.items():
                    template[category] = {key: "" for key in translations.keys()}
                
                translation_file = self.translations_dir / f"{language_code}.json"
                with open(translation_file, 'w', encoding='utf-8') as f:
                    json.dump(template, f, indent=2, ensure_ascii=False, sort_keys=True)
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error creating new Language: {e}")
        else:
            self.create_empty_translation_file(language_code)
    
    def on_language_changed(self, language_code: str):
        if not language_code:
            return
        
        self.load_translations_for_language(language_code)
        self.populate_table()

        self.save_btn.setEnabled(language_code != "en")
        self.save_btn.setEnabled(language_code != "en")
        self.missing_btn.setEnabled(language_code != "en")
        self.translate_all_btn.setEnabled(language_code != "en")
    
    def load_translations_for_language(self, language_code: str):
        translation_file = self.translations_dir / f"{language_code}.json"
        
        if translation_file.exists():
            try:
                with open(translation_file, 'r', encoding='utf-8') as f:
                    self.current_translations = json.load(f)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error loading {language_code}.json: {e}")
                self.current_translations = {}
        else:
            self.current_translations = {}
    
    def update_english_base(self):
        if self.extractor_thread and self.extractor_thread.isRunning():
            return
        
        progress = QProgressDialog("Extract Strings from Source...", "Abort", 0, 100, self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        
        self.extractor_thread = StringExtractorThread()
        self.extractor_thread.progress.connect(progress.setValue)
        self.extractor_thread.finished_extraction.connect(self.on_extraction_finished)
        self.extractor_thread.finished.connect(progress.close)
        self.extractor_thread.start()
        
        self.update_btn.setEnabled(False)
    
    def on_extraction_finished(self, strings_by_category: Dict, line_numbers: Dict):
        self.strings_by_category = strings_by_category
        self.line_numbers = line_numbers
        
        english_file = self.translations_dir / "en.json"
        english_translations = {}
        
        for category, strings in strings_by_category.items():
            english_translations[category] = {string: string for string in strings}
        try:
            with open(english_file, 'w', encoding='utf-8') as f:
                json.dump(english_translations, f, indent=2, ensure_ascii=False, sort_keys=True)
            
            if self.language_combo.currentText() == "en":
                self.current_translations = english_translations
                self.populate_table()
            
            self.status_label.setText(f"English Base Updated. {sum(len(strings) for strings in strings_by_category.values())} Strings found.")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error saving english base: {e}")
        
        self.update_btn.setEnabled(True)
    
    def find_missing_translations(self):
        current_lang = self.language_combo.currentText()
        if not current_lang or current_lang == "en":
            return
        
        english_file = self.translations_dir / "en.json"
        if not english_file.exists():
            QMessageBox.warning(self, "Error", "No Base File (en.json) found. Please run 'Update English Base' first.")
            return
        
        try:
            with open(english_file, 'r', encoding='utf-8') as f:
                english_translations = json.load(f)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading english base: {e}")
            return
        
        self.current_translations = self.merge_translations(english_translations, self.current_translations)
        
        missing_count = 0
        total_count = 0
        
        for category, strings in self.current_translations.items():
            for key, translation in strings.items():
                total_count += 1
                if not translation.strip():
                    missing_count += 1

        self.populate_table()
        
        # Status-Update
        if missing_count > 0:
            self.status_label.setText(f"Missing Translation found: {missing_count} out of {total_count} Strings")
        else:
            self.status_label.setText(f"All {total_count} Strings are Translated!")
        
        self.highlight_missing_translations()
    
    def populate_table(self):
        """Fülle Tabelle mit Daten"""
        self.table.setRowCount(0)
        
        current_lang = self.language_combo.currentText()
        if not current_lang or not self.current_translations:
            return

        rows = []
        total_strings = 0
        translated_strings = 0
        
        for category in sorted(self.current_translations.keys()):
            rows.append(("category", f"[{category}]", "", ""))
            
            category_translations = self.current_translations[category]
            for original in sorted(category_translations.keys()):
                translation = category_translations[original]
                total_strings += 1
                if translation.strip():
                    translated_strings += 1
                
                occurrences = ""
                if original in self.line_numbers:
                    file_lines = []
                    for filename, line_num in self.line_numbers[original]:
                        file_lines.append(f"{filename}:{line_num}")
                    occurrences = ", ".join(file_lines)
                
                rows.append(("string", original, translation, occurrences))
        
        # Update statistics
        if current_lang != "en" and total_strings > 0:
            percentage = (translated_strings / total_strings) * 100
            self.stats_label.setText(f"Progress: {translated_strings}/{total_strings} ({percentage:.1f}%)")
        else:
            self.stats_label.setText("Translation Statistics: -")
        
        self.table.setRowCount(len(rows))
        
        for row_idx, (row_type, original, translation, occurrences) in enumerate(rows):
            original_item = QTableWidgetItem(original)
            if row_type == "category":
                original_item.setBackground(QColor(230, 230, 230))
                font = original_item.font()
                font.setBold(True)
                original_item.setFont(font)
            original_item.setFlags(original_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row_idx, 0, original_item)
            
            # Show translate button based on Google Translate status and language
            if row_type == "string" and current_lang != "en":
                if self.google_translate_enabled and GOOGLE_TRANSLATE_AVAILABLE:
                    # Show active translate button
                    translate_btn = QPushButton("🌐")
                    translate_btn.setMaximumWidth(40)
                    translate_btn.setToolTip("Automatic translation with Google Translate")
                    translate_btn.clicked.connect(lambda checked, r=row_idx: self.translate_row(r))
                    self.table.setCellWidget(row_idx, 1, translate_btn)
                else:
                    # Show locked button with tooltip to enable Google Translate
                    disabled_btn = QPushButton("🔒")
                    disabled_btn.setMaximumWidth(40)
                    disabled_btn.setEnabled(False)
                    if not GOOGLE_TRANSLATE_AVAILABLE:
                        disabled_btn.setToolTip("Google Translate not available (googletrans not installed)")
                    else:
                        disabled_btn.setToolTip("Click 'Settings' button to enable Google Translate")
                    self.table.setCellWidget(row_idx, 1, disabled_btn)
            elif row_type == "category":
                # Empty cell for category rows
                empty_item = QTableWidgetItem("")
                empty_item.setBackground(QColor(230, 230, 230))
                empty_item.setFlags(empty_item.flags() & ~Qt.ItemIsEditable)
                self.table.setItem(row_idx, 1, empty_item)

            translation_item = QTableWidgetItem(translation)
            if row_type == "category":
                translation_item.setBackground(QColor(230, 230, 230))
                translation_item.setFlags(translation_item.flags() & ~Qt.ItemIsEditable)
            elif current_lang == "en":
                translation_item.setFlags(translation_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row_idx, 2, translation_item)
            
            occurrences_item = QTableWidgetItem(occurrences)
            if row_type == "category":
                occurrences_item.setBackground(QColor(230, 230, 230))
            occurrences_item.setFlags(occurrences_item.flags() & ~Qt.ItemIsEditable)
            self.table.setItem(row_idx, 3, occurrences_item)
        
        #self.table.resizeRowsToContents()
    
    def highlight_missing_translations(self):
        current_lang = self.language_combo.currentText()
        if current_lang == "en":
            return
        
        for row in range(self.table.rowCount()):
            original_item = self.table.item(row, 0)
            translation_item = self.table.item(row, 2) 
            
            if original_item and original_item.text().startswith("["):
                continue
            if translation_item:

                if not translation_item.text().strip():
                    translation_item.setBackground(QColor(255, 200, 200)) 
                else:
                    translation_item.setBackground(QColor(255, 255, 255))
    
    def on_item_changed(self, item: QTableWidgetItem):
        if item.column() != 2:  
            return
        
        row = item.row()
        original_item = self.table.item(row, 0)
        
        if not original_item or original_item.text().startswith("["):
            return 
        
        original_text = original_item.text()
        new_translation = item.text()
        
        category = None
        for check_row in range(row, -1, -1):
            check_item = self.table.item(check_row, 0)
            if check_item and check_item.text().startswith("[") and check_item.text().endswith("]"):
                category = check_item.text()[1:-1]
                break
        
        if category and category in self.current_translations:
            self.current_translations[category][original_text] = new_translation
            self.status_label.setText("Translation modefied (NOT saved)")
    
    def save_translations(self):
        current_lang = self.language_combo.currentText()
        if not current_lang or current_lang == "en":
            return
        
        translation_file = self.translations_dir / f"{current_lang}.json"
        
        try:
            with open(translation_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_translations, f, indent=2, ensure_ascii=False, sort_keys=True)
            
            self.status_label.setText(f"Translation '{current_lang}' saved")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error while saving: {e}")
    
    def translate_text_with_google(self, text: str, target_lang: str) -> str:
        """translate with google"""
        if not self.google_translate_enabled:
            self.status_label.setText("Google Translate not enabled. Check Settings menu.")
            return text

        if not GOOGLE_TRANSLATE_AVAILABLE or not self.translator:
            self.status_label.setText("Google Translate not available")
            return text
        
        try:
            if target_lang not in self.lang_code_mapping:
                self.status_label.setText(f"Language {target_lang} not supported by Google Translate")
                return text
            
            target_code = self.lang_code_mapping[target_lang]
            
            # Google Translate Aufruf
            result = self.translator.translate(text, src='en', dest=target_code)
            
            if result and result.text:
                translated_text = result.text
                # Basic cleanup for common issues
                translated_text = translated_text.replace(' \\n ', '\\n')
                translated_text = translated_text.replace(' \\n', '\\n')
                translated_text = translated_text.replace('\\n ', '\\n')
                return translated_text
            else:
                return text
            
        except Exception as e:
            self.status_label.setText(f"Google Translate Error: {str(e)[:50]}...")
            return text

    def translate_row(self, row: int):
        current_lang = self.language_combo.currentText()
        if current_lang == "en":
            self.status_label.setText("Englisch File - no translation needed")
            return
        
        original_item = self.table.item(row, 0)
        translation_item = self.table.item(row, 2)
        
        # if not original_item or not translation_item:
        #     self.status_label.setText("Debug: Keine Items gefunden in Zeile " + str(row))
        #     return
        
        original_text = original_item.text()
        if original_text.startswith("["): 
            return
                
        # Zeige Loading-Indikator
        translate_btn = self.table.cellWidget(row, 1)
        if translate_btn:
            translate_btn.setText("⏳")
            translate_btn.setEnabled(False)
        
        # Starte Übersetzung in separatem Thread
        QTimer.singleShot(100, lambda: self.perform_translation(row, original_text, current_lang))

    def perform_translation(self, row: int, original_text: str, target_lang: str):
        self.status_label.setText(f"GT Translating: '{original_text}'...")
        
        translated_text = self.translate_text_with_google(original_text, target_lang)
        
        self.status_label.setText(f"GT Response: '{translated_text}'")
        
        translation_item = self.table.item(row, 2)
        if translation_item and translated_text != original_text:
            translation_item.setText(translated_text)
            
            # Aktualisiere auch das Daten-Model
            self.update_translation_data(original_text, translated_text)
            
        else:
            self.status_label.setText(f"No Changes - Original: '{original_text}', Übersetzt: '{translated_text}'")
        
        # Setze Button zurück
        translate_btn = self.table.cellWidget(row, 1)
        if translate_btn:
            translate_btn.setText("🌐")
            translate_btn.setEnabled(True)

    def update_translation_data(self, original_text: str, translated_text: str):
        for category, translations in self.current_translations.items():
            if original_text in translations:
                self.current_translations[category][original_text] = translated_text
                break

    def translate_all_missing(self):
        current_lang = self.language_combo.currentText()
        if current_lang == "en":
            return
        
        if not self.google_translate_enabled:
            QMessageBox.information(
                self, "Google Translate Disabled", 
                "Please enable Google Translate in the Settings menu first."
            )
            return
        
        missing_rows = []
        for row in range(self.table.rowCount()):
            original_item = self.table.item(row, 0)
            translation_item = self.table.item(row, 2)
            
            if (original_item and translation_item and 
                not original_item.text().startswith("[") and 
                not translation_item.text().strip()):
                missing_rows.append(row)
        
        if not missing_rows:
            QMessageBox.information(self, "Info", "No missing translations found!")
            return
        
        if self.batch_confirm:
            reply = QMessageBox.question(
                self, 
                "Translate All Missing", 
                f"Translate {len(missing_rows)} missing strings with Google Translate?\n\n"
                f"This will take approximately {len(missing_rows) * self.translation_delay / 1000:.1f} seconds.\n"
                f"You can disable this confirmation in Settings.",
                QMessageBox.Yes | QMessageBox.No
            )
            
            if reply != QMessageBox.Yes:
                return
        
        self.batch_translate_rows(missing_rows, current_lang)

    def batch_translate_rows(self, rows: List[int], target_lang: str):
        if not rows:
            return
        
        progress = QProgressDialog("Translating with Google Translate...", "Cancel", 0, len(rows), self)
        progress.setWindowModality(Qt.WindowModal)
        progress.show()
        
        def translate_next(index=0):
            if index >= len(rows) or progress.wasCanceled():
                progress.close()
                self.status_label.setText(f"Batch translation completed: {index}/{len(rows)} translations")
                self.populate_table()  # Refresh statistics
                return
            
            row = rows[index]
            original_item = self.table.item(row, 0)
            
            if original_item:
                original_text = original_item.text()
                translated_text = self.translate_text_with_google(original_text, target_lang)
                
                translation_item = self.table.item(row, 2)
                if translation_item and translated_text != original_text:
                    translation_item.setText(translated_text)
                    self.update_translation_data(original_text, translated_text)
            
            progress.setValue(index + 1)
            QTimer.singleShot(self.translation_delay, lambda: translate_next(index + 1))
        
        translate_next()


def main():
    app = QApplication(sys.argv)
    
    app.setApplicationName("Translation Manager")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("JsonLz4Tool")
    
    window = TranslationManagerGUI()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()