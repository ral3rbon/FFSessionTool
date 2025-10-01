# export_bookmarks.py
import os
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, QCheckBox,
    QLabel, QFileDialog, QDialogButtonBox, QFormLayout, QComboBox, QListWidget, QListWidgetItem
)
from PySide6.QtCore import Qt
from app.utils import tr


class ExportBookmarksDialog(QDialog):
    def __init__(self, parent=None, window_list=None):
        super().__init__(parent)
        self.setWindowTitle(tr("Export Bookmarks", "Bookmarks"))
        self.setMinimumWidth(450)
        layout = QVBoxLayout(self)

        # File selection + browse
        form = QFormLayout()
        self.filename_edit = QLineEdit(self)
        self.filename_edit.setText("bookmarks.html")
        browse_btn = QPushButton("Browse")
        browse_btn.clicked.connect(self.on_browse)
        file_box = QHBoxLayout()
        file_box.addWidget(self.filename_edit)
        file_box.addWidget(browse_btn)
        form.addRow(QLabel(tr("Save Bookmarks as", "Bookmarks")), file_box)

        # Variant selection (Browser/Pretty)
        self.variant_combo = QComboBox()
        self.variant_combo.addItems(["Browser Compatible", "Pretty (embedded Favicons)"])
        form.addRow(QLabel("Export Type:"), self.variant_combo)

        # Checkbox for group as folders
        self.group_as_folder_cb = QCheckBox(tr("Use Groups as Folders", "Bookmarks"))
        self.group_as_folder_cb.setChecked(True)
        form.addRow(self.group_as_folder_cb)

        # Window selection (only if multiple windows exist)
        self.window_list_widget = None
        if window_list and len(window_list) > 1:
            self.window_list_widget = QListWidget()
            self.window_list_widget.setSelectionMode(QListWidget.MultiSelection)
            for idx, win_name in enumerate(window_list):
                item = QListWidgetItem(f"Window {idx+1}: {win_name}")
                item.setData(Qt.UserRole, idx)
                item.setSelected(True)  # Default: all selected
                self.window_list_widget.addItem(item)
            form.addRow(QLabel(tr("Select Window(s) to export", "Bookmarks")), self.window_list_widget)

        layout.addLayout(form)
        layout.addSpacing(10)
        
        # Error message label (initially hidden)
        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: red; font-weight: bold; padding: 5px;")
        self.error_label.setAlignment(Qt.AlignCenter)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        
        layout.addStretch(1)

        # Standard Ok/Cancel
        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.validate_and_accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def on_browse(self):
        fname, _ = QFileDialog.getSaveFileName(
            self,
            tr("Save Bookmarks as", "Bookmarks"),
            self.filename_edit.text(),
            "HTML Files (*.html)"
        )
        if fname:
            self.filename_edit.setText(fname)

    def validate_and_accept(self):
        """Validate user input before accepting the dialog."""
        # Clear any previous error message
        self.error_label.hide()
        
        # Check if filename is provided
        if not self.filename_edit.text().strip():
            self.show_error(tr("Please specify a filename", "Bookmarks"))
            return
        
        # Check if at least one window is selected (when multi-window)
        if self.window_list_widget:
            selected_items = self.window_list_widget.selectedItems()
            if not selected_items:
                self.show_error(f"{tr('No Window Selected', 'Bookmarks')} - {tr('Please select at least one window to export', 'Bookmarks')}")
                return
        
        # All validations passed
        self.accept()
    
    def show_error(self, message):
        """Display error message to user."""
        self.error_label.setText(message)
        self.error_label.show()

    def get_export_options(self):
        selected_windows = None
        if self.window_list_widget:
            selected_windows = [
                item.data(Qt.UserRole)
                for item in self.window_list_widget.selectedItems()
            ]

        return {
            "filepath": self.filename_edit.text(),
            "variant": self.variant_combo.currentIndex(),  # 0=Browser, 1=Pretty
            "groups_as_folders": self.group_as_folder_cb.isChecked(),
            "windows": selected_windows,  # None = all, List = selection
        }
