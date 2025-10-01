# themes.py
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor, QPalette
from PySide6.QtCore import QObject, Signal, QTimer
from typing import Dict, Optional

class ThemeManager(QObject):
    """
    Manages the application's theme (light/dark mode).
    """
    
    # Signal wird ausgelöst wenn sich das Theme ändert
    theme_changed = Signal(bool)  # True = Dark Mode, False = Light Mode
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ThemeManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        self._initialized = True
        self._current_theme = None
        self._observers = []
        self._auto_mode = False
        
        # Timer für automatische Theme-Erkennung
        self._theme_check_timer = QTimer()
        self._theme_check_timer.timeout.connect(self._check_theme_change)
        self._theme_check_timer.setInterval(1000)  # Prüfe jede Sekunde
        
        # Theme-spezifische Farben für EIGENE Widgets (nicht Qt-Standard-Widgets)
        self.light_colors = {
            "text": QColor(0, 0, 0),
            "background": QColor(240, 240, 240),
            "icon": QColor(0, 0, 0),
            "accent": QColor(9, 86, 198),
            "border": QColor(200, 200, 200),
            "hover": QColor(240, 240, 240),
        }
        
        self.dark_colors = {
            "text": QColor(255, 255, 255),
            "background": QColor(53, 53, 53),
            "icon": QColor(255, 255, 255),
            "accent": QColor(100, 149, 237),
            "border": QColor(80, 80, 80),
            "hover": QColor(70, 70, 70),
        }
    
    def is_dark_mode(self) -> bool:
        """
        Erkennt automatisch ob Dark Mode aktiv ist.
        """
        app = QApplication.instance()
        if app is None:
            return False
        
        palette = app.palette()
        bg_color = palette.color(palette.ColorRole.Window)
        brightness = (bg_color.red() + bg_color.green() + bg_color.blue()) / 3
        
        is_dark = brightness < 128
        
        # Theme-Change Detection
        if self._current_theme != is_dark:
            old_theme = self._current_theme
            self._current_theme = is_dark
            if old_theme is not None:  # Nicht beim ersten Aufruf
                self.theme_changed.emit(is_dark)
        
        return is_dark
    
    def get_color(self, color_name: str) -> QColor:
        """
        Gibt die passende Farbe für das aktuelle Theme zurück.
        
        :param color_name: Farbname (z.B. 'text', 'background', 'icon')
        :return: QColor für das aktuelle Theme
        """
        colors = self.dark_colors if self.is_dark_mode() else self.light_colors
        
        if color_name not in colors:
            available = list(colors.keys())
            raise ValueError(f"Theme-Farbe '{color_name}' nicht gefunden. Verfügbar: {available}")
        
        return colors[color_name]
    
    def get_color_hex(self, color_name: str) -> str:
        """
        Gibt die passende Farbe als Hex-String zurück.
        """
        return self.get_color(color_name).name()
    
    def get_icon_color(self) -> str:
        """
        Gibt die Standard-Icon-Farbe für das aktuelle Theme zurück.
        """
        return self.get_color_hex("icon")
    
    def register_observer(self, callback):
        """
        Registriert einen Observer für Theme-Änderungen.
        
        :param callback: Funktion die bei Theme-Änderung aufgerufen wird (bekommt is_dark_mode als Parameter)
        """
        self._observers.append(callback)
        self.theme_changed.connect(callback)
    
    def apply_fusion_dark_theme(self):
        """
        Wendet ein korrekt konfiguriertes Fusion-Theme an.
        Löst das Problem mit Input-Feldern und Checkboxen.
        """
        app = QApplication.instance()
        if app is None:
            return
        
        app.setStyle("Fusion")
        
        if self.is_dark_mode():
            self._apply_dark_palette()
        else:
            self._apply_light_palette()
    
    def apply_theme_by_preference(self, theme_preference="auto"):
        """
        Wendet das Theme basierend auf der Benutzereinstellung an.
        
        :param theme_preference: "auto", "dark", oder "light"
        """
        app = QApplication.instance()
        if app is None:
            return
        
        app.setStyle("Fusion")
        
        # Stoppe Timer wenn nicht auto
        if theme_preference != "auto":
            self._theme_check_timer.stop()
            self._auto_mode = False
        else:
            self._auto_mode = True
            self._theme_check_timer.start()
        
        if theme_preference == "dark":
            self._apply_dark_palette()
            self._current_theme = True
        elif theme_preference == "light":
            self._apply_light_palette()
            self._current_theme = False
        else:  # auto
            if self.is_dark_mode():
                self._apply_dark_palette()
            else:
                self._apply_light_palette()
            
    def _apply_light_palette(self):
        """Wendet Light-Palette mit korrekten ColorRoles an."""
        app = QApplication.instance()
        palette = QPalette()
        
        # Fenster-Hintergrund (Ihr angepasstes Grau)
        palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
        
        # Input-Felder - WEISS (löst das "deaktiviert"-Problem)
        palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(245, 245, 245))
        palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
        
        # Buttons
        palette.setColor(QPalette.ColorRole.Button, QColor(225, 225, 225))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
        
        # Tooltips
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(255, 255, 220))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(0, 0, 0))
        
        # Auswahl/Highlight
        palette.setColor(QPalette.ColorRole.Highlight, QColor(48, 140, 198))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
        
        # Links
        palette.setColor(QPalette.ColorRole.Link, QColor(0, 0, 255))
        palette.setColor(QPalette.ColorRole.LinkVisited, QColor(128, 0, 128))
        
        # Deaktivierte Elemente
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(120, 120, 120))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(120, 120, 120))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(120, 120, 120))
        
        app.setPalette(palette)
    
    def _apply_dark_palette(self):
        """Wendet Dark-Palette mit korrekten ColorRoles an."""
        app = QApplication.instance()
        palette = QPalette()
        
        app.setStyleSheet("""
            QToolTip {
                background-color: #2d2d2d;
                color: #e0e0e0;
                border: 1px solid #444444;
                padding: 3px;
                font-size: 12px;
            }
        """)

        # Fenster-Hintergrund
        palette.setColor(QPalette.ColorRole.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(255, 255, 255))
        
        # Input-Felder - DUNKEL aber kontrastreich
        palette.setColor(QPalette.ColorRole.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.Text, QColor(255, 255, 255))
        
        # Buttons
        palette.setColor(QPalette.ColorRole.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(255, 255, 255))
        
        # Tooltips
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(0, 0, 0))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(255, 255, 255))
        
        # Auswahl/Highlight
        palette.setColor(QPalette.ColorRole.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(0, 0, 0))
        
        # Links
        palette.setColor(QPalette.ColorRole.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.ColorRole.LinkVisited, QColor(128, 100, 200))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(255, 0, 0))
        
        # Deaktivierte Elemente
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor(127, 127, 127))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(127, 127, 127))
        palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(127, 127, 127))
        
        app.setPalette(palette)
    
    def get_status_colors(self, message_type: str) -> dict:
        """
        Spezielle Farben für StatusBar-Messages die palette-unabhängig sind.
        
        :param message_type: "success", "error", "warning", "info", "process"
        :return: {"color": hex_color, "bg": hex_color}
        """
        is_dark = self.is_dark_mode()
        
        if is_dark:
            color_map = {
                "success": {"color": "#FFFFFF", "bg": "#2D5A2D"},
                "error": {"color": "#FFFFFF", "bg": "#5A2D2D"},
                "warning": {"color": "#000000", "bg": "#E4A11B"},
                "process": {"color": "#000000", "bg": "#E4A11B"},
                "info": {"color": "#FFFFFF", "bg": "#2D2D5A"}
            }
        else:
            color_map = {
                "success": {"color": "#0F5132", "bg": "#D1E7DD"},
                "error": {"color": "#721C24", "bg": "#F8D7DA"},
                "warning": {"color": "#664D03", "bg": "#FFF3CD"},
                "process": {"color": "#664D03", "bg": "#FFF3CD"},
                "info": {"color": "#055160", "bg": "#D1ECF1"}
            }
        
        return color_map.get(message_type, color_map["info"])
    
    def _check_theme_change(self):
        """
        Prüft regelmäßig ob sich das System-Theme geändert hat (nur im auto-Modus).
        """
        if not self._auto_mode:
            return
            
        # Rufe is_dark_mode auf, um Theme-Change-Detection zu triggern
        current_is_dark = self.is_dark_mode()
        
        # Wenn sich das Theme geändert hat, wende das entsprechende Palette an
        if self._current_theme != current_is_dark:
            if current_is_dark:
                self._apply_dark_palette()
            else:
                self._apply_light_palette()

# Globale Instanz erstellen
theme_manager = ThemeManager()

# Convenience-Funktionen für einfachen Zugriff - EXAKT wie vorher
def is_dark_mode() -> bool:
    """Globale Funktion für Dark Mode Detection."""
    return theme_manager.is_dark_mode()

def get_theme_color(color_name: str) -> QColor:
    """Globale Funktion um Theme-Farben zu holen."""
    return theme_manager.get_color(color_name)

def get_theme_color_hex(color_name: str) -> str:
    """Globale Funktion um Theme-Farben als Hex zu holen."""
    return theme_manager.get_color_hex(color_name)

def get_icon_color() -> str:
    """Globale Funktion für Standard-Icon-Farbe."""
    return theme_manager.get_icon_color()