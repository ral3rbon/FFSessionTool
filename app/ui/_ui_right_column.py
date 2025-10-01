from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLineEdit, QLabel, QComboBox, QPushButton,
    QFormLayout, QTabWidget, QScrollArea, QSizePolicy, QSpacerItem, QTextEdit, QPlainTextEdit
)
from app.ui.helpers import load_icon, FlowLayout
from app.utils.ui_translator import tr
import json

class RightColumnWidget(QWidget):
    debug_json_saved = Signal(dict)  # Signal für gespeicherte Änderungen

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(400)
        self._init_ui()

    def _init_ui(self):
        self.rcf_layout = QVBoxLayout(self)
        self.rcf_layout.setContentsMargins(0, 0, 0, 0)
        self.rcf_layout.setSpacing(0)

        self.rc_form = QWidget()
        self.rc_form_layout = QFormLayout(self.rc_form)

        self.title_edit = QLineEdit()
        self.btn_update_title = QPushButton(icon=load_icon("refresh"), text="")
        self.btn_update_title.setCursor(Qt.PointingHandCursor)
        self.btn_update_title.setToolTip(tr("Update Title via 'request'", "right_column_tooltip"))

        self.url_edit = QLineEdit()
        self.group_combo = QComboBox()
        self.group_combo.setEditable(True)
        self.last_accessed_label = QLabel("")
        self.last_accessed_label.setStyleSheet("color: gray; font-style: italic;")
        self.closed_at_label = QLabel("")
        self.closed_at_label.setStyleSheet("color: red; font-style: italic;")
        
        # Referenz auf das Label für das "Closed at:" Field speichern
        self.closed_at_label_text = None

        title_input_btn = QHBoxLayout()
        title_input_btn.addWidget(self.title_edit, 1)
        title_input_btn.addWidget(self.btn_update_title, 0)
        title_input_btn.setContentsMargins(0, 0, 0, 0)

        self.rc_form_layout.addRow(tr("Title:", "main"), title_input_btn)
        self.rc_form_layout.addRow(tr("URL:", "main"), self.url_edit)
        self.rc_form_layout.addRow(tr("Group:", "main"), self.group_combo)
        self.rc_form_layout.addRow(tr("Last Accessed:", "main"), self.last_accessed_label)
        
        # "Closed at" Zeile - wird initial versteckt
        self.closed_at_row_index = self.rc_form_layout.rowCount()
        self.rc_form_layout.addRow(tr("Closed at:", "main"), self.closed_at_label)
        
        # Speichere Referenz auf das Label-Widget für "Closed at:"
        self.closed_at_label_text = self.rc_form_layout.itemAt(self.closed_at_row_index, QFormLayout.LabelRole).widget()
        
        # Initial verstecken
        self.set_closed_at_visible(False)

        self.btn_delete = QPushButton(icon=load_icon("trash"), text=tr("Delete Selected Tab", "main"))
        self.btn_delete.setToolTip(tr("coming soon..."))
        #self.btn_delete.setToolTip(tr("Delete the selected Tab or Group from the Session", "main"))
        self.btn_delete.setEnabled(False)  # Disabled until a tab/group is selected


        # Avoiding the word "Tab" (because of potential confusion with browser tabs)
        self.infotainmentsystem = QTabWidget()
        self.infotainmentsystem.setContentsMargins(0, 0, 0, 0)

        self.its_tags = QWidget()
        self.its_tags_layout = QVBoxLayout(self.its_tags)
        self.its_tags_layout.setContentsMargins(0, 0, 0, 0)

        self.its_tags_scroll = QScrollArea()
        self.its_tags_scroll.setWidgetResizable(True)
        self.its_tags_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.its_tags_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.its_data_container = QWidget()
        self.its_data_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)
        self.its_data_layout = QVBoxLayout()
        self.its_data_container.setLayout(self.its_data_layout)
        self.its_tags_scroll.setWidget(self.its_data_container)
        self.its_tags_layout.addWidget(self.its_tags_scroll)
        self.its_status_lbl = QLabel("")
        self.its_tags_layout.addWidget(self.its_status_lbl)

        ###### Buttons XPath Addon ######
        self.xpath_buttons_container = QWidget()
        self.xpath_buttons_layout = QVBoxLayout(self.xpath_buttons_container)
        self.xpath_buttons_layout.setContentsMargins(0, 0, 0, 5)
        self.xpath_buttons_layout.setSpacing(5)

        self.xph_scrape_url_btn = QPushButton(icon=load_icon("magnet-with-tag"), text=tr("Scrape URL", "xpath_addon"))  # Single Tab
        self.xph_scrape_group_btn = QPushButton(icon=load_icon("magnet-with-tag"), text=tr("Scrape Group", "xpath_addon"))  # All tabs in group
        self.xph_scrape_window_btn = QPushButton(icon=load_icon("magnet-with-tag"), text=tr("Scrape Window", "xpath_addon"))  # All tabs in window
        

        self.xpath_buttons_layout.addWidget(self.xph_scrape_url_btn)
        self.xpath_buttons_layout.addWidget(self.xph_scrape_group_btn)
        self.xpath_buttons_layout.addWidget(self.xph_scrape_window_btn)

        self.its_tags_layout.addWidget(self.xpath_buttons_container)

        ###### History of the selected Tab ######
        self.its_his = QWidget()
        self.its_his_layout = QVBoxLayout(self.its_his)
        self.its_his_layout.setContentsMargins(0, 0, 0, 0)
        self.its_his_layout.setAlignment(Qt.AlignTop)

        self.its_his_info = QWidget()
        self.its_his_info_layout = QHBoxLayout(self.its_his_info)
        self.its_his_info_layout.setContentsMargins(0, 0, 0, 0)
        self.its_his_info_layout.setAlignment(Qt.AlignCenter)

        self.its_his_info_lbl = QLabel(f"{tr('Show the browsing history of the selected tab.', 'history_addon')}\n{tr('... but i will try to find the Origin if any', 'history_addon')}")
        self.its_his_info_lbl.setToolTip(tr('... but it will try to find the Origin if any', 'history_addon'))
        self.its_his_info_lbl.setStyleSheet("color: gray; font-style: italic; font-size: 10px;")
        self.its_his_info_layout.addWidget(self.its_his_info_lbl, alignment=Qt.AlignCenter)
        self.its_his_layout.addWidget(self.its_his_info)

        self.its_his_scroll = QScrollArea()
        self.its_his_scroll.setWidgetResizable(True)
        self.its_his_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.its_his_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.its_his_container = QWidget()
        self.its_his_container_layout = QVBoxLayout(self.its_his_container)
        self.its_his_container_layout.setContentsMargins(10, 10, 10, 10)
        self.its_his_container_layout.setAlignment(Qt.AlignTop)
        self.its_his_container_layout.setSpacing(15)
        self.its_his_scroll.setWidget(self.its_his_container)
        self.its_his_layout.addWidget(self.its_his_scroll)

        ##### Show Json Data for Debugging and manipulation #####
        self.its_debug = QWidget()
        self.its_debug_layout = QVBoxLayout(self.its_debug)
        self.its_debug_layout.setContentsMargins(0, 0, 0, 0)
        self.its_debug_layout.setAlignment(Qt.AlignTop)
        
        self.its_debug_lbl = QLabel(f"{tr('Show the raw JSON data of the selected tab/group/window.', 'debug_addon')}\n{tr('Useful for debugging or manual manipulation.', 'debug_addon')}")
        self.its_debug_lbl.setToolTip(tr("... but be careful when editing the JSON directly!", "debug_addon"))
        self.its_debug_lbl.setStyleSheet("color: gray; font-style: italic; font-size: 10px;")
        self.its_debug_layout.addWidget(self.its_debug_lbl, alignment=Qt.AlignCenter)
        
        self.its_debug_scroll = QScrollArea()
        self.its_debug_scroll.setWidgetResizable(True)
        self.its_debug_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.its_debug_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        self.its_debug_container = QWidget()
        self.its_debug_container_layout = QFormLayout(self.its_debug_container)
        self.its_debug_container_layout.setContentsMargins(10, 10, 10, 10)
        self.its_debug_container_layout.setVerticalSpacing(8)
        self.its_debug_container_layout.setHorizontalSpacing(10)
        
        self.its_debug_scroll.setWidget(self.its_debug_container)
        self.its_debug_layout.addWidget(self.its_debug_scroll)

        self.debug_save_btn = QPushButton(tr("Save JSON Changes", "debug_addon"))
        self.debug_save_btn.setToolTip(tr("Save changes made in the debug fields back to the JSON object.", "debug_addon"))
        self.debug_save_btn.clicked.connect(self._on_debug_save_clicked)
        self.its_debug_layout.addWidget(self.debug_save_btn, alignment=Qt.AlignRight)


        self.infotainmentsystem.addTab(self.its_his, tr("History", "main"))
        self.infotainmentsystem.addTab(self.its_tags, tr("Tags", "main"))
        self.infotainmentsystem.addTab(self.its_debug, tr("Debug", "main"))
        
        # Connect tab change signal to handle image frame visibility
        self.infotainmentsystem.currentChanged.connect(self._on_tab_changed)

        self.image_frame = QFrame()
        self.image_layout = QVBoxLayout(self.image_frame)
        self.image_layout.setContentsMargins(5, 5, 5, 5)
        self.image_layout.setSpacing(5)
        
        self.image_label_status = QLabel()
        self.image_label_status.setAlignment(Qt.AlignCenter)
        self.image_label_status.setStyleSheet("QLabel { color: grey; font-style: italic; font-size: 10px}")
        
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setScaledContents(True)
        self.image_layout.addWidget(self.image_label_status)
        self.image_layout.addWidget(self.image_label, alignment=Qt.AlignCenter)
        self.load_image_button = QPushButton(tr("Load Images", "xpath_addon"))
        self.load_image_button.setContentsMargins(5, 5, 5, 5)

           
        self.rcf_layout.addWidget(self.rc_form, 0)
        self.rcf_layout.addWidget(self.btn_delete, 0)
        self.rcf_layout.addItem(QSpacerItem(20, 10, QSizePolicy.Fixed))
        self.rcf_layout.addWidget(self.infotainmentsystem, 1)
        self.rcf_layout.addWidget(self.image_frame, 0)
        self.rcf_layout.addWidget(self.load_image_button)


        self.xpath_buttons_container.setVisible(False)
        self.image_frame.setVisible(False)


    def set_closed_at_visible(self, visible):
        """Zeigt oder versteckt die 'Closed at:' Zeile im FormLayout"""
        if self.closed_at_label_text:
            self.closed_at_label_text.setVisible(visible)
        self.closed_at_label.setVisible(visible)
    
    def show_closed_tab_info(self):
        """Zeigt Informationen für geschlossene Tabs an"""
        self.set_closed_at_visible(True)
    
    def show_active_tab_info(self):
        """Zeigt Informationen für aktive Tabs an"""
        self.set_closed_at_visible(False)

    def clear_details(self):
        while self.its_data_layout.count():
            item = self.its_data_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        
        # Reset zur Standard-Ansicht (aktive Tabs)
        self.show_active_tab_info()

    def get_data_renderer(self, db_handler, logger):
        """Create and return an ExtractedDataRenderer instance for this column"""
        from app.ui.helpers.data_display import ExtractedDataRenderer
        return ExtractedDataRenderer(self, db_handler, logger)

    def populate_debug_fields(self, raw_tab_data):
        """Populate the debug tab with input fields for raw_tab JSON data"""
        # Clear existing fields
        self._clear_debug_fields()
        
        self._debug_raw_json_ref = raw_tab_data  # Referenz für Save
        if not raw_tab_data or not isinstance(raw_tab_data, dict):
            no_data_label = QLabel(tr("No debug data available", "debug_addon"))
            no_data_label.setStyleSheet("color: grey; font-style: italic;")
            self.its_debug_container_layout.addRow(no_data_label)
            self.debug_save_btn.setEnabled(False)
            return
        
        self.debug_save_btn.setEnabled(True)
        self.debug_field_widgets = {}
        self._add_json_fields("", raw_tab_data, self.its_debug_container_layout)

    def _clear_debug_fields(self):
        """Clear all debug fields from the container"""
        while self.its_debug_container_layout.count():
            child = self.its_debug_container_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.debug_field_widgets = {}
    
    def _add_json_fields(self, prefix, data, layout, max_depth=3, current_depth=0):
        """Recursively add input fields for JSON data"""
        if current_depth > max_depth:
            return
            
        if isinstance(data, dict):
            for key, value in data.items():
                field_name = f"{prefix}.{key}" if prefix else key
                self._add_field_for_value(field_name, key, value, layout, current_depth)
                
        elif isinstance(data, list):
            for i, value in enumerate(data):
                field_name = f"{prefix}[{i}]" if prefix else f"[{i}]"
                self._add_field_for_value(field_name, f"Item {i}", value, layout, current_depth)
    
    def _add_field_for_value(self, field_name, display_name, value, layout, current_depth):
        """Add appropriate input field based on value type and length"""
        # ---  Add Fields that should only read only---
        readonly_fields = {"lastAccessed", "last_accessed"}
        is_readonly = any(fn in field_name for fn in readonly_fields)


        if isinstance(value, (dict, list)) and current_depth < 3:
            # For nested objects, add a separator label and recurse
            separator = QLabel(f"─── {display_name} ───")
            separator.setStyleSheet("font-weight: bold; color: #666; margin: 5px 0;")
            layout.addRow(separator)
            
            self._add_json_fields(field_name, value, layout, current_depth=current_depth + 1)
        else:
            # Convert value to string for display
            str_value = self._value_to_string(value)
            
            # Check if this is a URL field (special handling)
            is_url_field = 'url' in field_name.lower() or (isinstance(value, str) and value.startswith(('http://', 'https://')))
            
            # Create appropriate input widget
            if is_url_field:
                # Always use LineEdit for URLs, regardless of length
                input_widget = QLineEdit()
                input_widget.setText(str_value)
                input_widget.setToolTip(f"{tr('Field', 'debug_addon')}: {field_name}\n{tr('URL Field', 'debug_addon')}")
                input_widget.setCursorPosition(0)
            elif len(str_value) > 100 or '\n' in str_value:
                input_widget = QPlainTextEdit()
                input_widget.setMaximumHeight(75) 
                input_widget.setPlainText(str_value)
                input_widget.setToolTip(f"{tr('Field', 'debug_addon')}: {field_name}")
                #input_widget.setCursorPosition(0)
            else:
                input_widget = QLineEdit()
                input_widget.setText(str_value)
                input_widget.setToolTip(f"{tr('Field', 'debug_addon')}: {field_name}")
                input_widget.setCursorPosition(0)

            # --- Deaktivate if Readonly ---
            if is_readonly:
                input_widget.setReadOnly(True)
                input_widget.setStyleSheet("background: #eee; color: #888;")


            # Store widget reference
            self.debug_field_widgets[field_name] = input_widget
            
            # Create label with truncated field name and full name in tooltip
            if current_depth == 0:
                label_text = display_name[:20] + "..." if len(display_name) > 20 else display_name
            else:
                truncated_name = display_name[:17] + "..." if len(display_name) > 17 else display_name
                label_text = f"{truncated_name}:"
            
            label = QLabel(label_text)
            label.setToolTip(f"{field_name}")
            
            # Add to layout
            layout.addRow(label, input_widget)
    
    def _value_to_string(self, value):
        """Convert various value types to string representation"""
        if value is None:
            return ""
        elif isinstance(value, bool):
            return "true" if value else "false"
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, str):
            return value
        elif isinstance(value, (dict, list)):
            try:
                return json.dumps(value, indent=2, ensure_ascii=False)
            except Exception:
                return str(value)
        else:
            return str(value)
    
    def get_debug_field_values(self):
        """Get current values from all debug fields"""
        values = {}
        for field_name, widget in self.debug_field_widgets.items():
            if isinstance(widget, QLineEdit):
                values[field_name] = widget.text()
            elif isinstance(widget, QPlainTextEdit):
                values[field_name] = widget.toPlainText()
        return values

    def _on_tab_changed(self, index):
        """Handle tab changes to show/hide the image frame based on selected tab."""
        tab_text = self.infotainmentsystem.tabText(index)
        if tab_text == tr("Debug", "main"):
            self.image_frame.setVisible(False)
            self.load_image_button.setVisible(False)
        else:
            # Show image frame for other tabs (History, Tags), but respect other visibility logic
            self.image_frame.setVisible(True)
            self.load_image_button.setVisible(True)

    def _on_debug_save_clicked(self):
        """Save Changes back to JSON"""
        if not hasattr(self, "_debug_raw_json_ref") or not isinstance(self._debug_raw_json_ref, dict):
            return
        values = self.get_debug_field_values()
        # Write values back to JSON (only editable fields)
        for field_name, val in values.items():
            # Don't overwrite read-only fields
            if any(fn in field_name for fn in ("lastAccessed", "last_accessed")):
                continue
            self._set_json_value_by_path(self._debug_raw_json_ref, field_name, val)
        # emit Signal to refresh (not implemented yet)
        self.debug_json_saved.emit(self._debug_raw_json_ref)

    def _set_json_value_by_path(self, json_obj, path, value):
        """Set Json Data helper using a path like 'a.b[0].c'"""
        import re
        parts = re.split(r'\.(?![^\[]*\])', path)
        obj = json_obj
        for i, part in enumerate(parts):
            
            if "[" in part and "]" in part:
                key, idx = re.match(r"([^\[]+)\[(\d+)\]", part).groups()
                idx = int(idx)
                if key:
                    obj = obj.get(key, [])
                if i == len(parts) - 1:
                    if isinstance(obj, list) and 0 <= idx < len(obj):
                        obj[idx] = value
                else:
                    if isinstance(obj, list) and 0 <= idx < len(obj):
                        obj = obj[idx]
                    else:
                        return
            else:
                if i == len(parts) - 1:
                    if isinstance(obj, dict):
                        obj[part] = value
                else:
                    obj = obj.get(part, {})