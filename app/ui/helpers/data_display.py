from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, 
    QSizePolicy, QMessageBox, QInputDialog
)
from app.ui.helpers import FlowLayout
from app.utils.ui_translator import tr

class ExtractedDataRenderer:
    def __init__(self, right_column_widget, db_handler, logger):
        self.right_column = right_column_widget
        self.db = db_handler
        self.logger = logger
        self.current_session_id = None
        self.current_url = None
        self.current_hash = None
        self.xpath_rules = []

    def set_current_context(self, session_id, url, url_hash, xpath_rules):
        """Set the current context for data operations"""
        self.current_session_id = session_id
        self.current_url = url
        self.current_hash = url_hash
        self.xpath_rules = xpath_rules

    def render_extracted_data(self, data_entries):
        """Render extracted data in the right column's data container"""
        # Clear existing content
        self._clear_data_container()
        
        if not data_entries:
            no_data_label = QLabel(tr("No extracted data available.", "Addon_Xpath"))
            no_data_label.setStyleSheet("color: grey; font-style: italic;")
            no_data_label.setAlignment(Qt.AlignCenter)
            self.right_column.its_data_layout.addWidget(no_data_label)
            return
        
        # Get the data layout from right column
        data_layout = self.right_column.its_data_layout

        # Create header
        header = QWidget()
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(10)
        
        lbl_label = QLabel(tr("Label Title", "Addon_Xpath"))
        lbl_label.setMaximumWidth(120)
        lbl_label.setStyleSheet("font-weight: bold; color: #000;")
        
        lbl_value = QLabel(tr("Value Content", "Addon_Xpath"))
        lbl_value.setWordWrap(True)
        lbl_value.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        lbl_value.setMaximumWidth(150)
        lbl_value.setStyleSheet("font-weight: bold; color: #000;")
        
        header_layout.addWidget(lbl_label)
        header_layout.addWidget(lbl_value, stretch=1)
        header.setStyleSheet("background:#e9e9ef; border-bottom:1px solid #bdc")
        data_layout.addWidget(header)

        # Calculate max label width - use 'name' field instead of 'label'
        max_label_width = max(
            self.right_column.fontMetrics().horizontalAdvance(e.get('name', '')) 
            for e in data_entries if e.get('name')
        ) + 10 if data_entries else 120

        # Render data entries
        for entry in data_entries:
            if entry.get("priority", 0) == 0:
                continue

            row_widget = QWidget()
            row_layout = QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 4, 0, 4)
            row_layout.setSpacing(10)

            # Use 'name' field instead of 'label'
            label_text = entry.get('name', 'Unknown')
            label_widget = QLabel(label_text)
            label_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
            label_widget.setFixedWidth(max_label_width)
            label_widget.setStyleSheet("font-weight: bold; font-size: 11pt;")
            label_widget.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            row_layout.addWidget(label_widget)

            # Use 'is_filter' to determine display type
            if entry.get('is_filter', False):
                value_widget = self.make_chip_container(label_text, entry.get("values", []))
            else:
                values = entry.get("values", [])
                value_widget = QLabel(", ".join(str(v) for v in values))
                value_widget.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                value_widget.setWordWrap(True)
                value_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                # Use scroll area viewport width from right column
                scroll_width = self.right_column.its_tags_scroll.viewport().width()
                value_widget.setMaximumWidth(scroll_width - max_label_width - 30)

            row_layout.addWidget(value_widget, stretch=1, alignment=Qt.AlignVCenter)

            # Create separator line
            line = QFrame()
            line.setFrameShape(QFrame.HLine)
            line.setFrameShadow(QFrame.Sunken)
            line.setStyleSheet("color: #c7d4e0;")
            
            vbox = QVBoxLayout()
            vbox.setContentsMargins(0, 0, 0, 0)
            vbox.setSpacing(0)
            vbox.addWidget(row_widget)
            vbox.addWidget(line)
            
            zeilen_container = QWidget()
            zeilen_container.setLayout(vbox)
            data_layout.addWidget(zeilen_container)

        data_layout.addStretch()

    def make_chip_container(self, name, values):
        """Create a container with chip-style buttons for filter values"""
        chip_container = QWidget()
        chip_layout = FlowLayout(chip_container, spacing=4)

        for val in values:
            btn = QPushButton(str(val))
            btn.setStyleSheet("""
                QPushButton {
                    border: 1px solid #579;
                    border-radius: 20px;
                    background-color: #29304e;
                    padding: 2px 5px;
                    font-size: 10pt;
                    color: white;
                }
                QPushButton:hover {
                    background-color: #483d8b;
                }
            """)
            btn.setCursor(Qt.PointingHandCursor)
            
            # Connect the button click to the filter method
            btn.clicked.connect(
                lambda _, value=str(val).strip().lower(), button=btn: 
                self._apply_chip_filter(value, button)
            )

            chip_layout.addWidget(btn)
        
        # Add custom tag button
        add_tag_btn = QPushButton(f"+ {tr('Add Tag', 'Addon_Xpath')}")
        add_tag_btn.setToolTip(tr("Manually add a new tag", "Addon_Xpath"))
        add_tag_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #579;
                border-radius: 20px;
                background-color: #4CAF50;
                color: white;
                padding: 2px 5px;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        add_tag_btn.setCursor(Qt.PointingHandCursor)
        add_tag_btn.clicked.connect(lambda: self.add_custom_tag(name))
        chip_layout.addWidget(add_tag_btn)

        return chip_container

    def add_custom_tag(self, label_name):
        """Add a custom tag for the given label"""
        # Find the rule_id for the given label_name - use 'name' field
        rule_id = None
        for r in self.xpath_rules:
            if r.get('name') == label_name:
                rule_id = r.get('id')
                break
        
        if not rule_id:
            QMessageBox.warning(self.right_column, tr("Error", "error"), 
                              tr("Could not find rule ID for label: {0}", "error", label_name))
            return

        # Open dialog to get new tag value
        new_tag, ok = QInputDialog.getText(
            self.right_column, 
            tr("Add custom tag", "Addon_Xpath"), 
            tr("Enter the new tag value:", "Addon_Xpath")
        )

        if ok and new_tag:
            # Check if session and tab ID exist
            if not self.current_session_id or not self.current_url:
                QMessageBox.warning(self.right_column, tr("Error", "error"), 
                                  tr("No active session or URL found.", "error"))
                return

            tab_id = self.db.get_tab_id_by_url(self.current_url)
            if not tab_id:
                QMessageBox.warning(self.right_column, tr("Error", "error"), 
                                  tr("Could not find tab ID for the current URL.", "error"))
                return
            
            # Save the new tag to database
            try:
                self.db.save_extracted_data(
                    tab_id=tab_id,
                    rule_id=rule_id,
                    value=new_tag.strip(),
                )
                QMessageBox.information(self.right_column, tr("Success", "success"), 
                                      tr("New tag has been saved.", "success"))
                # Refresh the display
                if hasattr(self, '_refresh_callback') and self._refresh_callback:
                    self._refresh_callback(url_hash=self.current_hash)
            except Exception as e:
                self.logger.error(f"Failed to save custom tag: {e} |#| ({type(e).__name__})", exc_info=True)
                QMessageBox.critical(self.right_column, tr("Database Error", "error"), 
                                   tr("Failed to save tag to database: {0}", "error", str(e)))

    def _clear_data_container(self):
        """Clear all widgets from the data container"""
        while self.right_column.its_data_layout.count():
            item = self.right_column.its_data_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _apply_chip_filter(self, value, button):
        """Apply filter based on chip value"""
        if hasattr(self, '_filter_callback') and self._filter_callback:
            self._filter_callback(value, button)
        else:
            self.logger.info(f"Filter requested for value: {value}")
        
    def set_refresh_callback(self, callback):
        """Set callback function for refreshing data display"""
        self._refresh_callback = callback

    def set_filter_callback(self, callback):
        """Set callback function for applying chip filters"""
        self._filter_callback = callback
