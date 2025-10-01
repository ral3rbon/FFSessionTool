import os
from datetime import datetime
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget, QListWidgetItem, QLabel, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, Signal
from app.ui.helpers.ui_icon_loader import load_icon
from app.utils.ui_translator import tr
from app.utils import Logger, format_size

class OpenRecentProjectFileDialog(QDialog):
    file_selected = Signal(str)

    def __init__(self, recent_files, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Open Recent Project File", "recent_files_dialog"))
        self.setModal(True)

        self.logger = Logger.get_logger("OpenRecentFiles")

        self.current_profile = None
        self.recent_files = recent_files

        self._init_ui()
        
        self.session_path = None
        self.recovery_path = None
        self.previous_path = None

    def _init_ui(self):
        rf_dialog_layout = QHBoxLayout(self)

        rf_files_layout = QVBoxLayout()
        info_label = QLabel(tr("Last imported sessions:", "recent_files_dialog"))

        self.recent_list = QListWidget()
        self.recent_list.setTextElideMode(Qt.ElideMiddle)
        self.recent_list.setWordWrap(True)
        self.recent_list.currentItemChanged.connect(self._on_recent_file_selected)

        rf_files_layout.addWidget(info_label)
        rf_files_layout.addWidget(self.recent_list, 0)

        self._populate_recent_files(self.recent_files)
        rf_dialog_layout.addLayout(rf_files_layout, stretch=2)

        # == Right side: Buttons ==
        rf_btn_layout = QVBoxLayout()
        rf_btn_layout.setContentsMargins(0, info_label.sizeHint().height(), 0, 0)

        self.session_btn = QPushButton("Sessionstore")
        self.session_btn.clicked.connect(lambda: self._select_file(self.session_path))
        self.recovery_btn = QPushButton("Recovery")
        self.recovery_btn.clicked.connect(lambda: self._select_file(self.recovery_path))
        self.previous_btn = QPushButton("Previous")
        self.previous_btn.clicked.connect(lambda: self._select_file(self.previous_path))

        self.sf_import_btn = QPushButton(tr("Import single *.JsonLz4 File...", "recent_files_dialog"))
        self.sf_import_btn.clicked.connect(self._import_single_file)
        self.sf_import_btn.setToolTip(tr("... outside of the profile location", "recent_files_dialog"))

        rf_btn_layout.addWidget(self.session_btn)
        rf_btn_layout.addWidget(self.recovery_btn)
        rf_btn_layout.addWidget(self.previous_btn)
        rf_btn_layout.addWidget(self.sf_import_btn)
        rf_dialog_layout.addLayout(rf_btn_layout, stretch=1)

    def _populate_recent_files(self, recent_files):
        if not recent_files:
            return

        if isinstance(recent_files, str):
            recent_files = [recent_files]

        for path in recent_files:
            
            display_name = self.get_profile_display_name(path)
            item = QListWidgetItem(display_name)
            item.setToolTip(path)
            item.setData(Qt.UserRole, path)
            item.setText(display_name)
            self.recent_list.addItem(item)
    
    def get_profile_display_name(self, path):
        if not os.path.isdir(path):
            return os.path.basename(path)
        
        profile_txt = os.path.join(path, "profile.txt")
        if os.path.exists(profile_txt):
            try:
                with open(profile_txt, "r", encoding="utf-8") as f:
                    content = f.read().strip()

                if "|" in content:
                    profile, date = content.split("|", 1)
                    if "." in profile:
                        profile = profile.rsplit(".", 1)[1]
                    return f"{profile} ({date})"
                    
                elif "." in content:
                    return content.rsplit(".", 1)[1]
                return content
            except Exception as e:
                self.logger.error(f"{tr('Failed to read profile information', 'recent_files_dialog')}: {e} |#| ({type(e).__name__})", exc_info=True)
                raise ValueError(tr('Failed to read profile information.', 'recent_files_dialog')) from e
    
        return os.path.basename(path)
    
    def _on_recent_file_selected(self, current, previous):
        if not current:
            return
        path = current.data(Qt.UserRole)
        self.current_profile = path
        self.session_path = os.path.join(path, "sessionstore.jsonlz4")
        self.recovery_path = os.path.join(path, "recovery.jsonlz4")
        self.previous_path = os.path.join(path, "previous.jsonlz4")

        self._update_ui()

    def _update_ui(self):
        if self.session_path and os.path.exists(self.session_path):
            size = os.path.getsize(self.session_path)
            mod_time = datetime.fromtimestamp(os.path.getmtime(self.session_path)).strftime('%d.%m.%Y %H:%M')
            self.session_btn.setText(
                f"Sessionstore\n{mod_time}\n{format_size(size)}"
            )
            self.session_btn.setEnabled(True)
        else:
            self.session_btn.setText(f"Sessionstore ({tr('not found', 'recent_files_dialog')})")
            self.session_btn.setEnabled(False)


        if self.recovery_path and os.path.exists(self.recovery_path):
            size = os.path.getsize(self.recovery_path)
            mod_time = datetime.fromtimestamp(os.path.getmtime(self.recovery_path)).strftime('%d.%m.%Y %H:%M')
            self.recovery_btn.setText(
                f"Recovery\n{mod_time}\n{format_size(size)}"
            )
            self.recovery_btn.setEnabled(True)
        else:
            self.recovery_btn.setText(f"Recovery ({tr('not found', 'recent_files_dialog')})")
            self.recovery_btn.setEnabled(False)

        if self.previous_path and os.path.exists(self.previous_path):
            size = os.path.getsize(self.previous_path)
            mod_time = datetime.fromtimestamp(os.path.getmtime(self.previous_path)).strftime('%d.%m.%Y %H:%M')
            self.previous_btn.setText(
                f"Previous\n{mod_time}\n{format_size(size)}"
            )
            self.previous_btn.setEnabled(True)
        else:
            self.previous_btn.setText(f"Previous ({tr('not found', 'recent_files_dialog')})")
            self.previous_btn.setEnabled(False)

    def _import_single_file(self):
        single_path, _ = QFileDialog.getOpenFileName(
            self,
            tr("Select Single JsonLz4 File", "recent_files_dialog"),
            "",
            "JsonLz4 Files (*.jsonlz4);;All Files (*)"
        )
        if single_path:
            self._select_file(single_path)

    def _select_file(self, path):
        if path and os.path.exists(path):
            self.logger.info(f"{tr('Selected file', 'recent_files_dialog')}: {path}")
            self.file_selected.emit(path)
            self.accept()
        else:
            self.logger.warning(f"{tr('File not found', 'recent_files_dialog')}: {path}")
            QMessageBox.warning(self, tr("File not found", "recent_files_dialog"),
                                tr("The selected file does not exist.", "recent_files_dialog"))