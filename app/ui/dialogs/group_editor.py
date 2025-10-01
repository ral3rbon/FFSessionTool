from functools import partial
import pprint
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QCheckBox,
    QHeaderView, QMessageBox, QComboBox
)
from PySide6.QtGui import QIcon, QColor, QPixmap, QPainter
from PySide6.QtCore import Qt, Signal
from PySide6.QtSvg import QSvgRenderer
from app.ui.helpers import COLORS, colored_svg_icon
from app.utils import tr

class GroupEditor(QDialog):
    changes_ready = Signal(list)

    def __init__(self, all_groups: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Manage Groups")
        self.resize(800, 500)
        self.original_groups = all_groups  # Store original groups
        self.changes = []  # Changes tracken
        
        self.svg_path = "assets/icons/folder.svg"
        self.setup_ui()
        self.load_data(all_groups)

    def setup_ui(self):
        layout = QVBoxLayout()

        # Info Label
        info_label = QLabel("Änderungen werden sofort übernommen und in der Liste angezeigt.")
        info_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(info_label)

        # Tabelle
        self.group_table = QTableWidget(0, 4) 
        self.group_table.setHorizontalHeaderLabels(["Color", "Name", "ID", "Collapsed"])
        header = self.group_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.group_table.setColumnHidden(2, True)

        
        # Enable inline editing for names
        self.group_table.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.EditKeyPressed)
        layout.addWidget(self.group_table)

        # Buttons
        button_layout = QHBoxLayout()
        self.apply_button = QPushButton("Apply Changes")
        self.apply_button.clicked.connect(self.apply_changes)
        self.cancel_button = QPushButton("Close")
        self.cancel_button.clicked.connect(self.accept)
        
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.apply_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def load_data(self, all_groups):
        """Lädt Daten in die Tabelle"""
        self.group_table.setRowCount(len(all_groups))
        
        # Temporarily disable signal during loading
        try:
            self.group_table.cellChanged.disconnect(self.on_cell_changed)
        except:
            pass

        for row, group in enumerate(all_groups):
            # Farbauswahl-Combobox
            color_combo = QComboBox()
            for color_name, color in COLORS.items():
                icon = colored_svg_icon(self.svg_path, color, size=16)
                color_combo.addItem(icon, color_name)
            color_combo.setCurrentText(group['color'])
            color_combo.currentIndexChanged.connect(
                lambda _, r=row, c=color_combo: self.on_color_changed(r, c.currentText())
            )
            self.group_table.setCellWidget(row, 0, color_combo)

            # Name-Spalte
            name_item = QTableWidgetItem(group['name'])
            current_color = COLORS.get(group['color'], "#000000")
        
            self.group_table.setItem(row, 1, name_item)

            # ID (display only)
            id_item = QTableWidgetItem(group['id'])
            id_item.setFlags(Qt.ItemIsEnabled)
            self.group_table.setItem(row, 2, id_item)

            # Collapsed Checkbox
            collapsed_checkbox = QCheckBox()
            collapsed_checkbox.setChecked(group.get('collapsed', False))
            collapsed_checkbox.setStyleSheet("QCheckBox { margin: 0 auto;}")
            collapsed_checkbox.stateChanged.connect(
                partial(self.on_collapsed_changed, row)
            )
            self.group_table.setCellWidget(row, 3, collapsed_checkbox)

        # CellChanged Signal wieder verbinden
        self.group_table.cellChanged.connect(self.on_cell_changed)

    def on_cell_changed(self, row, column):
        """Wird aufgerufen wenn eine Zelle geändert wird"""
        if column != 1:  # Only name column interests us
            return
            
        new_name = self.group_table.item(row, 1).text()
        group_id = self.group_table.item(row, 2).text()
        
        # Original Namen finden
        original_group = next((g for g in self.original_groups if g['id'] == group_id), None)
        if not original_group or original_group['name'] == new_name:
            return
            
        # Track change
        self.track_change(group_id, 'name', new_name)

    def on_color_changed(self, row, new_color):
        """Wird aufgerufen wenn Farbe geändert wird"""
        group_id = self.group_table.item(row, 2).text()
        
        # Find original color
        original_group = next((g for g in self.original_groups if g['id'] == group_id), None)
        if not original_group or original_group['color'] == new_color:
            return
            
        # Icon aktualisieren
        name_item = self.group_table.item(row, 1)
        if name_item:
            color_hex = COLORS.get(new_color, "#000000")
            name_item.setIcon(colored_svg_icon(self.svg_path, color_hex, size=16))
        
        # Track change
        self.track_change(group_id, 'color', new_color)

    def on_collapsed_changed(self, row, state):
        """Wird aufgerufen wenn Collapsed geändert wird"""
        collapsed = bool(state)
        print(f"Row {row}, collapsed={collapsed}")
        print(collapsed)
        group_id = self.group_table.item(row, 2).text()
        self.track_change(group_id, 'collapsed', collapsed)

    def track_change(self, group_id, field, new_value):
        """Trackt Änderungen an Gruppen"""
        # Find ursprünglichen Wert
        original_group = next((g for g in self.original_groups if g['id'] == group_id), None)
        if not original_group:
            return
            
        old_value = original_group.get(field)
        if old_value == new_value:
            # Remove vorhandene Änderung falls Wert zurückgesetzt wurde
            self.changes = [c for c in self.changes if not (c['group_id'] == group_id and c['field'] == field)]
            return
            
        # Remove vorhandene Änderungen für diese Gruppe+Field
        self.changes = [c for c in self.changes if not (c['group_id'] == group_id and c['field'] == field)]
        
        # Add neue Änderung hinzu
        self.changes.append({
            'group_id': group_id,
            'field': field,
            'old_value': old_value,
            'new_value': new_value
        })

    def apply_changes(self):
        """Übernimmt die Änderungen und sendet sie"""
        if not self.changes:
            self.accept()
            return
            
        # Only send actual changes
        actual_changes = []
        for change in self.changes:
            group_id = change['group_id']
            field = change['field']
            new_value = change['new_value']
            
            original_group = next((g for g in self.original_groups if g['id'] == group_id), None)
            if original_group and original_group.get(field) != new_value:
                actual_changes.append(change)
    
        if actual_changes:
            self.changes_ready.emit(actual_changes)
        self.accept()