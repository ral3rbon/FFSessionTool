# statusbar.py
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt, Signal
from typing import List, Union, Callable, Optional
from app.ui.helpers.ui_icon_loader import load_icon
from app.ui.helpers.ui_themes import theme_manager

class StatusButton:
    """Klasse für Button-Definitionen"""
    def __init__(self, text: str, callback: Callable = None, action_type: str = None, action_data: str = None, icon: str = None):
        self.icon = icon
        self.text = text
        self.callback = callback
        self.action_type = action_type
        self.action_data = action_data
        
        # Wenn callback nicht gesetzt ist, aber action_type, dann Standard-Callback verwenden
        if self.callback is None and self.action_type:
            self.callback = lambda: None  # Wird später durch StatusBar ersetzt

class StatusBar(QWidget):
    link_activated = Signal(str)  # Signal für Link-Klicks
    button_clicked = Signal(str, str)  # Signal für Button-Klicks (action_type, action_data)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        theme_manager.theme_changed.connect(self.on_theme_changed)

    def addBt(text: str, callback: Callable = None, switch_tab: str = None, action: str = None, icon: str = None) -> StatusButton:
        """Hilfsfunktion zum Erstellen von StatusButton-Objekten"""
        if switch_tab:
            return StatusButton(icon=icon, text=text, action_type="switch_tab", action_data=switch_tab)
        elif action:
            return StatusButton(icon=icon, text=text, action_type="action", action_data=action)
        else:
            return StatusButton(icon=icon, text=text, callback=callback)

    def setup_ui(self):
        # Hauptlayout
        layout = QVBoxLayout(self)
        self.setLayout(layout)
        
        # Container für den gesamten Inhalt
        self.content_widget = QWidget()
        self.content_layout = QHBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(5, 5, 5, 5)
        
        # Label für Text/Links (wird bei Bedarf erstellt)
        self.status_label = None
        
        # Liste der Button-Widgets (wird bei Bedarf erstellt)
        self.buttons = []
        
        layout.addWidget(self.content_widget)

    def clear_content(self):
        """Löscht alle Inhalte"""
        # Alle Widgets aus dem Layout entfernen
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        # Referenzen zurücksetzen
        self.status_label = None
        self.buttons.clear()
    
    def create_label_if_needed(self):
        """Erstellt das Label wenn es noch nicht existiert"""
        if self.status_label is None:
            self.status_label = QLabel()
            self.status_label.setWordWrap(True)
            self.status_label.setMinimumHeight(20)
            self.status_label.setOpenExternalLinks(False)
            self.status_label.setTextFormat(Qt.RichText)
            self.status_label.linkActivated.connect(self.on_link_activated)
            self.content_layout.addWidget(self.status_label)
    
    def on_link_activated(self, link):
        """Wird aufgerufen, wenn ein Link im Label angeklickt wird"""
        self.link_activated.emit(link)
    
    def on_button_clicked(self, button: StatusButton):
        """Wird aufgerufen, wenn ein Button geklickt wird"""
        if button.callback:
            button.callback()
        
        if button.action_type:
            self.button_clicked.emit(button.action_type, button.action_data or "")
    
    def apply_message_style(self, message_type: str):
            """
            FINALE Version - überschreibt Palette GARANTIERT.
            """
            self.current_message_type = message_type
            
            # Palette-unabhängige Farben holen
            colors = theme_manager.get_status_colors(message_type)
            # Widget von Palette isolieren
            self.content_widget.setAutoFillBackground(False)
            
            # Base-Stil
            base_stylesheet = "padding: 2px; border: 0.5px solid #ccc; font-size: 10px; border-radius: 3px;"
            
            # Komplettes StyleSheet das Palette ignoriert
            stylesheet = f"""
                QWidget#content_widget {{
                    {base_stylesheet}
                    background-color: {colors['bg']};
                    color: {colors['color']};
                }}
                QWidget#content_widget QLabel {{
                    background-color: transparent;
                    color: {colors['color']};
                    border: none;
                    padding: 0px;
                }}
                QWidget#content_widget QPushButton {{
                    background-color: black;
                    font-weight: bold; 
                    color: White;
                }}
            """
            
            self.content_widget.setStyleSheet(stylesheet)
            self.content_widget.setObjectName("content_widget")
            
            # Button-Stil für alle Buttons anwenden
            # button_style = self.get_button_style(message_type)
            # for button in getattr(self, 'buttons', []):
            #     button.setStyleSheet(button_style)
        
    def on_theme_changed(self, is_dark: bool):
        """Wird bei Theme-Änderung aufgerufen."""
        self.apply_message_style(self.current_message_type)
    
    def get_button_style(self, message_type: str) -> str:
        """Ihre bestehende get_button_style Methode bleibt unverändert"""
        colors = theme_manager.get_status_colors(message_type)
        return f"""
            QPushButton {{
                background-color: rgba(255,255,255,0.1);
                color: {colors['color']};
                border: 1px solid rgba(255,255,255,0.3);
                border-radius: 2px;
                padding: 2px 6px;
                font-size: 9px;
            }}
            QPushButton:hover {{
                background-color: rgba(255,255,255,0.2);
            }}
        """

    # def apply_message_style(self, message_type: str):
    #     """Wendet den Stil basierend auf dem Message-Typ an"""

    #     base_stylesheet = "padding: 2px; border: 0.5px solid #ccc; font-size: 10px; border-radius: 3px;"

    #     style_map = {
    #         "success": "color: green!important; background-color: #f0fff0 !important;",# padding: 5px; border: 1px solid #cfc;",
    #         "error": "color: red; background-color: #fff0f0;", #padding: 5px; border: 1px solid #fcc;",
    #         "warning": "color: white!important; background-color: #E4A11B !important;", #padding: 5px; border: 1px solid #fcc;",
    #         "process": "color: white; background-color: #E4A11B; font-weight: bold;", #padding: 5px; border: 1px solid #fcc;",
    #         "info": "color: black; background-color: #f0f0f0;" #padding: 5px; border: 1px solid #ccc;"
    #     }
        
    #     #style = style_map.get(message_type, style_map["info"])
    #     #self.content_widget.setStyleSheet(f"QWidget {{ {base_stylesheet} {style} }}")
        
    #     container_style = style_map.get(message_type, style_map["info"])
    #     self.content_widget.setStyleSheet(f"""
    #         QWidget#content_widget {{ {base_stylesheet} {container_style} }}
    #         QPushButton {{ 
    #         }}
    #     """)

    #     self.content_widget.setObjectName("content_widget")

        
    #     # Button-Stil anpassen basierend auf Message-Typ
    #     # button_style = self.get_button_style(message_type)
    #     # for button in self.buttons:
    #     #     button.setStyleSheet(button_style)
    
    # def get_button_style(self, message_type: str) -> str:
    #     """Gibt den Button-Stil basierend auf dem Message-Typ zurück"""
    #     base_style = """
    #         QPushButton {
    #             font-weight: bold;
    #         }
    #         QPushButton:hover {
    #             opacity: 0.8;
    #         }
    #     """
    #     
        
        # if message_type == "success":
        #     return base_style + """
        #         QPushButton {
        #             background-color: #28a745;
        #             color: white;
        #             border-color: #1e7e34;
        #         }
        #     """
        # elif message_type == "error":
        #     return base_style + """
        #         QPushButton {
        #             background-color: #dc3545;
        #             color: white;
        #             border-color: #bd2130;
        #         }
        #     """
        # elif message_type == "warning":
        #     return base_style + """
        #         QPushButton {
        #             background-color: #ffc107;
        #             color: black;
        #             border-color: #d39e00;
        #         }
        #     """
        # else:  # info
        #     return base_style + """
        #         QPushButton {
        #             background-color: #007bff;
        #             color: white;
        #             border-color: #0056b3;
        #         }
        #     """
        return base_style

    def show_message(self, message: Union[str, List], message_type: str = "info"):
        """
        Zeigt eine Statusmeldung an
        
        Args:
            message: Entweder ein String oder eine Liste mit [text, button1, button2, ...]
            message_type: Typ der Nachricht ("info", "success", "error", "warning")
        """
        # Alten Inhalt löschen
        self.clear_content()
        
        if isinstance(message, str):
            # Einfache Textnachricht
            self.create_label_if_needed()
            self.status_label.setText(message)
        
        elif isinstance(message, list) and len(message) > 0:
            # Nachricht mit Text und möglicherweise Buttons
            text = message[0] if message else ""
            buttons = message[1:] if len(message) > 1 else []
            
            # Text-Label erstellen wenn Text vorhanden
            if text:
                self.create_label_if_needed()
                self.status_label.setText(text)
            
            # Buttons erstellen
            for button_def in buttons:
                if isinstance(button_def, StatusButton):
                    btn = QPushButton(button_def.text)
                    if button_def.icon is not None:
                        btn.setIcon(button_def.icon)
                    btn.clicked.connect(lambda checked=False, b=button_def: self.on_button_clicked(b))
                    self.buttons.append(btn)
                    self.content_layout.addWidget(btn)
        
        # Stil anwenden
        self.apply_message_style(message_type)