from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFrame, QLineEdit, QLabel, QTreeWidget, QPushButton
)
from app.ui.helpers import load_icon, colored_svg_icon
from app.utils.ui_translator import tr

class CenterColumnWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        self.ccf_layout = QVBoxLayout(self)  # "center layout"
        self.ccf_layout.setContentsMargins(0, 0, 0, 0)
        self.ccf_layout.setSpacing(0)

        filter_container = QWidget()
        filter_layout = QHBoxLayout(filter_container)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText(tr("Filter Tabs (Title, URL or url_hash)...", "main"))
        self.filter_input.setClearButtonEnabled(True)
        self.filter_input.addAction(load_icon("filter"), QLineEdit.LeadingPosition)
        self.active_filter_label = QLabel("")  # Shows the active filter when applied
        self.active_filter_label.setVisible(False)  # Hidden at start
        filter_layout.addWidget(self.filter_input, 1)
        filter_layout.addWidget(self.active_filter_label, 0)
        self.ccf_layout.addWidget(filter_container)

        self.scc = QWidget()  # Session Content Container
        self.scc_layout = QVBoxLayout(self.scc)
        self.scc_layout.setContentsMargins(0, 0, 0, 0)
        self.scc_layout.setSpacing(0)

        self.session_widget = QTreeWidget()
        self.session_widget.setHeaderLabel(tr("Session Tabs", "main"))
        self.session_widget.setExpandsOnDoubleClick(True)
        self.session_widget.setUniformRowHeights(True)

        self.show_closed_tabs_btn = QPushButton(icon=load_icon("history"), text=tr("Show Closed Tabs", "main"))
        self.show_closed_tabs_btn.setCheckable(True)
        self.show_closed_tabs_btn.setChecked(False)
        self.show_closed_tabs_btn.setToolTip(tr("Show/Hide Closed Tabs from the Session", "main"))

        self.closed_session_widget = QTreeWidget()
        self.closed_session_widget.setHeaderLabel(tr("Closed Tabs / Saved Groups", "main"))
        self.closed_session_widget.setVisible(False)

        self.scc_layout.addWidget(self.session_widget, 1)
        self.scc_layout.addWidget(self.show_closed_tabs_btn, 0)
        self.scc_layout.addWidget(self.closed_session_widget, 1)
        self.ccf_layout.addWidget(self.scc, 1)

        self.active_filter_label.setStyleSheet("""
            border: 1px solid #3a87ad; 
            border-radius: 12px; 
            background-color: #3a87ad; 
            color: white; 
            padding: 2px 8px; 
            font-size: 10px;"""
        )
