##*** dialog/list_profiles.py
import os
import glob
from datetime import datetime
from functools import partial

# Imports for PySide6
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QScrollArea, QLabel, QGridLayout,
    QPushButton, QHBoxLayout, QFrame, QWidget, QMessageBox
)
from PySide6.QtGui import QIcon
from PySide6.QtCore import Qt, QSize, Signal
from app.utils import tr, format_size
class ProfileWidget(QFrame):
    clicked = Signal(object)

    def __init__(self, profile_path, parent=None):
        super().__init__(parent)
        self.profile_path = profile_path
        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Raised)
        self.setLineWidth(1)
        self.setMidLineWidth(1)
        self.setContentsMargins(5, 5, 5, 5)
        self.setCursor(Qt.PointingHandCursor)

        self.layout = QHBoxLayout(self)
        self.layout.setSpacing(10)
        
        self.icon_name_widget = QWidget()
        self.icon_name_widget.setFixedWidth(150)
        icon_name_layout = QVBoxLayout(self.icon_name_widget)
        icon_name_layout.setContentsMargins(0, 0, 0, 0)
        
        self.icon_label = QLabel()
        self.icon_label.setPixmap(QIcon("assets/icons/user-square-rounded.svg").pixmap(QSize(100, 100)))
        self.icon_label.setAlignment(Qt.AlignCenter)
        icon_name_layout.addWidget(self.icon_label)
        
        self.profile_name_label = QLabel(os.path.basename(self.profile_path))
        self.profile_name_label.setAlignment(Qt.AlignCenter)
        self.profile_name_label.setWordWrap(True)
        self.profile_name_label.setStyleSheet("font-weight: bold;")
        icon_name_layout.addWidget(self.profile_name_label, alignment=Qt.AlignHCenter)

        self.layout.addWidget(self.icon_name_widget)
        
        self.info_grid_layout = QGridLayout()
        self.info_grid_layout.setHorizontalSpacing(20)
        self.info_grid_layout.setVerticalSpacing(5)
        self.layout.addLayout(self.info_grid_layout)
        
        row = 0
        self.session_path = os.path.join(self.profile_path, 'sessionstore.jsonlz4')
        self.session_exists = os.path.exists(self.session_path)

        self.info_grid_layout.addWidget(QLabel("<b>Sessionstore:</b>"), row, 0)
        
        if self.session_exists:
            session_size = os.path.getsize(self.session_path)
            session_modified_timestamp = os.path.getmtime(self.session_path)
            session_modified_date = datetime.fromtimestamp(session_modified_timestamp).strftime('%d.%m.%Y %H:%M')
            
            session_info_layout = QVBoxLayout()
            session_info_layout.setSpacing(0)
            session_info_layout.addWidget(QLabel(f"{tr('Last modified', 'load_profile')}: {session_modified_date}"))
            session_info_layout.addWidget(QLabel(f"{tr('Size', 'load_profile')}: {format_size(session_size)}"))
            self.info_grid_layout.addLayout(session_info_layout, row, 1)
        else:
            self.info_grid_layout.addWidget(QLabel(tr("File not Found.", "load_profile")), row, 1)

        row += 1
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        self.info_grid_layout.addWidget(line, row, 0, 1, 2)

        row += 1
        self.recovery_path = os.path.join(self.profile_path, 'sessionstore-backups', 'recovery.jsonlz4')
        self.recovery_exists = os.path.exists(self.recovery_path)
        
        self.info_grid_layout.addWidget(QLabel("<b>Recovery:</b>"), row, 0)
        
        if self.recovery_exists:
            recovery_size = os.path.getsize(self.recovery_path)
            recovery_modified_timestamp = os.path.getmtime(self.recovery_path)
            recovery_modified_date = datetime.fromtimestamp(recovery_modified_timestamp).strftime('%d.%m.%Y %H:%M')
            
            recovery_info_layout = QVBoxLayout()
            recovery_info_layout.setSpacing(0)
            recovery_info_layout.addWidget(QLabel(f"{tr('Last modified', 'load_profile')}: {recovery_modified_date}"))
            recovery_info_layout.addWidget(QLabel(f"{tr('Size', 'load_profile')}: {format_size(recovery_size)}"))
            self.info_grid_layout.addLayout(recovery_info_layout, row, 1)
        else:
            self.info_grid_layout.addWidget(QLabel(tr("File not Found.", "load_profile")), row, 1)
        
        row += 1
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        self.info_grid_layout.addWidget(line, row, 0, 1, 2)

        row += 1
        self.previous_path = os.path.join(self.profile_path, 'sessionstore-backups', 'previous.jsonlz4')
        self.previous_exists = os.path.exists(self.previous_path)
        
        self.info_grid_layout.addWidget(QLabel("<b>Previous:</b>"), row, 0)
        
        if self.previous_exists:
            previous_size = os.path.getsize(self.previous_path)
            previous_modified_timestamp = os.path.getmtime(self.previous_path)
            previous_modified_date = datetime.fromtimestamp(previous_modified_timestamp).strftime('%d.%m.%Y %H:%M')
            
            previous_info_layout = QVBoxLayout()
            previous_info_layout.setSpacing(0)
            previous_info_layout.addWidget(QLabel(f"{tr('Last modified', 'load_profile')}: {previous_modified_date}"))
            previous_info_layout.addWidget(QLabel(f"{tr('Size', 'load_profile')}: {format_size(previous_size)}"))
            self.info_grid_layout.addLayout(previous_info_layout, row, 1)
        else:
            self.info_grid_layout.addWidget(QLabel(tr("File not Found.", "load_profile")), row, 1)

        if not self.session_exists and not self.previous_exists:
            self.setEnabled(False)
            
    def get_paths(self):
        paths_to_copy = []
        if self.session_exists:
            paths_to_copy.append(self.session_path)
        if self.recovery_exists:
            paths_to_copy.append(self.recovery_path)
        if self.previous_exists:
            paths_to_copy.append(self.previous_path)
        return paths_to_copy

    def mousePressEvent(self, event):
        self.clicked.emit(self)

class FFProfileSelectionDialog(QDialog):
    def __init__(self, profiles, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Select Firefox Profile", "load_profile"))
        self.selected_paths = []
        
        self.main_layout = QVBoxLayout(self)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.content_widget = QWidget()
        self.scroll_layout = QVBoxLayout(self.content_widget)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        
        self.profile_widgets = []
        for profile_path in profiles:
            widget = ProfileWidget(profile_path)
            
            profile_name = os.path.basename(profile_path)
            if profile_name.endswith('.default'):
                if widget.session_exists or widget.recovery_exists or widget.previous_exists:
                    self.scroll_layout.addWidget(widget)
                    self.profile_widgets.append(widget)
                    widget.clicked.connect(self.handle_selection)
            else:
                self.scroll_layout.addWidget(widget)
                self.profile_widgets.append(widget)
                widget.clicked.connect(self.handle_selection)

        self.scroll_area.setWidget(self.content_widget)
        self.main_layout.addWidget(self.scroll_area)
        
        self.info_label = QLabel(tr("Choose a profile to copy session files from.", "load_profile"))
        self.main_layout.addWidget(self.info_label)
        self.adjustSize()

    def handle_selection(self, profile_widget):
        self.selected_paths = profile_widget.get_paths()
        if self.selected_paths:
            self.accept()
        else:
            QMessageBox.warning(self, tr("No Files", "load_profile"), tr("No files found to process in this profile.", "load_profile"))

class FileSelectionDialog(QDialog):
    file_selected = Signal(str)

    def __init__(self, session_path, recovery_path, previous_path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Select Session File to Open", "select_file_dialog"))
        self.setModal(True)
        
        self.session_path = session_path
        self.recovery_path = recovery_path
        self.previous_path = previous_path
        
        main_layout = QVBoxLayout(self)
        
        info_label = QLabel(tr("Select which session file to open:", "select_file_dialog"))
        info_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(info_label)
        
        self.session_button = QPushButton("Sessionstore")
        self.session_button.setCursor(Qt.PointingHandCursor)
        self.session_button.clicked.connect(lambda: self.select_file(self.session_path))
        main_layout.addWidget(self.session_button)
        
        self.recovery_button = QPushButton("Recovery")
        self.recovery_button.setCursor(Qt.PointingHandCursor)
        self.recovery_button.clicked.connect(lambda: self.select_file(self.recovery_path))
        main_layout.addWidget(self.recovery_button)
        
        self.previous_button = QPushButton("Previous")
        self.previous_button.setCursor(Qt.PointingHandCursor)
        self.previous_button.clicked.connect(lambda: self.select_file(self.previous_path))
        main_layout.addWidget(self.previous_button)


        self._update_ui()

    def _update_ui(self):
        if self.session_path and os.path.exists(self.session_path):
            size = os.path.getsize(self.session_path)
            mod_time = datetime.fromtimestamp(os.path.getmtime(self.session_path)).strftime('%d.%m.%Y %H:%M')
            self.session_button.setText(f"Sessionstore\n{tr('Last modified', 'select_file_dialog')}: {mod_time}\n{tr('Size', 'select_file_dialog')}: {format_size(size)}")
        else:
            self.session_button.hide()

        if self.recovery_path and os.path.exists(self.recovery_path):
            size = os.path.getsize(self.recovery_path)
            mod_time = datetime.fromtimestamp(os.path.getmtime(self.recovery_path)).strftime('%d.%m.%Y %H:%M')
            self.recovery_button.setText(f"Recovery\n{tr('Last modified', 'select_file_dialog')}: {mod_time}\n{tr('Size', 'select_file_dialog')}: {format_size(size)}")
        else:
            self.recovery_button.hide()
        
        if self.previous_path and os.path.exists(self.previous_path):
            size = os.path.getsize(self.previous_path)
            mod_time = datetime.fromtimestamp(os.path.getmtime(self.previous_path)).strftime('%d.%m.%Y %H:%M')
            self.previous_button.setText(f"Previous\n{tr('Last modified', 'select_file_dialog')}: {mod_time}\n{tr('Size', 'select_file_dialog')}: {format_size(size)}")
        else:
            self.previous_button.hide()
        
    def select_file(self, file_path):
        self.file_selected.emit(file_path)
        self.accept()