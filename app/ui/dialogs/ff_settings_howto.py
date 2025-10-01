import os
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QScrollArea, QWidget, QFrame, QSizePolicy
)
from app.utils.ui_translator import tr

class FirefoxConfigDialog(QDialog):
    """Dialog to guide user through Firefox startup configuration"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Firefox Startup Configuration", "ReplaceSession"))
        self.setModal(True)
        self.resize(600, 500)
        self.result_value = None
        


        self.setup_ui()
    
    def setup_ui(self):
        """Setup the dialog UI with message and screenshot"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        message = f"{tr('Firefox is not configured to restore the previous session on startup', 'ReplaceSession')}!\n\n"
        message += f"{tr('To work properly, Firefox needs to be set to restore the previous session on startup.', 'ReplaceSession')}"

        # Message section
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        message_label.setStyleSheet("""
            QLabel {
                font-size: 12px;
                padding: 10px;
                background-color: #f0f0f0;
                border-radius: 5px;
                border: 1px solid #ccc;
            }
        """)
        layout.addWidget(message_label)
        
        # Instructions section
        instructions_label = QLabel(tr("Please follow these steps:", "ReplaceSession"))
        instructions_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(instructions_label)
        
        # Steps section
        steps_widget = self.create_steps_widget()
        layout.addWidget(steps_widget)
        
        # Screenshot section
        screenshot_frame = self.create_screenshot_section()
        layout.addWidget(screenshot_frame)
        
        # Warning section
        warning_label = QLabel(tr("After changing the settings, close Firefox entirely! And THEN click on 'Done!'", "ReplaceSession"))
        warning_label.setStyleSheet("""
            QLabel {
                color: #d32f2f;
                font-weight: bold;
                font-size: 12px;
                padding: 8px;
                background-color: #ffebee;
                border-radius: 5px;
                border: 1px solid #ffcdd2;
            }
        """)
        warning_label.setWordWrap(True)
        layout.addWidget(warning_label)
        
        # Button section
        button_layout = self.create_button_section()
        layout.addLayout(button_layout)
    
    def create_steps_widget(self):
        """Create widget with step-by-step instructions"""
        steps_frame = QFrame()
        steps_frame.setFrameStyle(QFrame.Box)
        steps_frame.setStyleSheet("""
            QFrame {
                background-color: #fafafa;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 5px;
            }
        """)
        
        steps_layout = QVBoxLayout(steps_frame)
        
        steps = [
            tr("1. Open Firefox and go to Settings (about:preferences)", "ReplaceSession"),
            tr("2. Navigate to 'General' → 'Startup'", "ReplaceSession"),
            tr("3. Select 'Open previous windows and tabs'", "ReplaceSession"),
            tr("4. Close Firefox completely", "ReplaceSession")
        ]
        
        for step in steps:
            step_label = QLabel(f"• {step}")
            step_label.setStyleSheet("font-size: 11px; padding: 2px;")
            step_label.setWordWrap(True)
            steps_layout.addWidget(step_label)
        
        return steps_frame
    
    def create_screenshot_section(self):
        """Create scrollable screenshot section"""
        # Main frame for screenshot
        screenshot_frame = QFrame()
        screenshot_frame.setFrameStyle(QFrame.Box)
        screenshot_frame.setFixedHeight(260)
        screenshot_frame.setStyleSheet("border: 1px solid #ccc;")
        
        # Layout for the frame
        frame_layout = QVBoxLayout(screenshot_frame)
        frame_layout.setContentsMargins(5, 5, 5, 5)
        
        # Title for screenshot
        screenshot_title = QLabel(tr("Firefox Settings Screenshot:", "ReplaceSession"))
        screenshot_title.setStyleSheet("font-weight: bold; font-size: 11px;")
        frame_layout.addWidget(screenshot_title)
        
        # Scroll area for screenshot
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setMaximumHeight(250)
        
        # Screenshot label
        screenshot_label = QLabel()
        screenshot_label.setAlignment(Qt.AlignCenter)
        screenshot_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Try to load screenshot
        screenshot_path = self.get_screenshot_path()
        if os.path.exists(screenshot_path):
            pixmap = QPixmap(screenshot_path)
            if not pixmap.isNull():
                # Scale pixmap to reasonable size while maintaining aspect ratio
                scaled_pixmap = pixmap.scaled(600, 200, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                screenshot_label.setPixmap(scaled_pixmap)
            else:
                screenshot_label.setText(tr("Screenshot could not be loaded", "ReplaceSession"))
                screenshot_label.setStyleSheet("color: #666; font-style: italic;")
        else:
            screenshot_label.setText(tr("Screenshot not available", "ReplaceSession"))
            screenshot_label.setStyleSheet("color: #666; font-style: italic;")
        
        scroll_area.setWidget(screenshot_label)
        frame_layout.addWidget(scroll_area)
        
        return screenshot_frame
    
    def get_screenshot_path(self):
        """Get path to Firefox settings screenshot"""
        # TODO: OR at least think about it... -> adding multilanguage support for screenshots?
        screen_path = "assets/screenshots/ff_startup_setting.png"

        if os.path.exists(screen_path):
            return screen_path

        return None
        
    
    def create_button_section(self):
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        # Done button
        done_button = QPushButton(tr("Done!", "ReplaceSession"))
        done_button.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: white;
                font-weight: bold;
            }
        """)
        done_button.clicked.connect(self.accept_configuration)
                
        # Cancel button
        cancel_button = QPushButton(tr("Cancel", "ReplaceSession"))

        cancel_button.clicked.connect(self.reject)
        
        button_layout.addWidget(done_button)
        button_layout.addWidget(cancel_button)
        
        return button_layout
    
    def accept_configuration(self):
        """User confirmed configuration is done"""
        self.result_value = "configured"
        self.accept()
    
    def reject_configuration(self):
        """User wants to skip configuration"""
        self.result_value = "skip"
        self.accept()
    
    def get_user_choice(self):
        """Get the user's choice after dialog closes"""
        return self.result_value