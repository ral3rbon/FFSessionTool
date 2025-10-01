from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QCheckBox, QComboBox, QSizePolicy, QSpacerItem
)
from app.ui.helpers.ui_icon_loader import load_icon
from app.utils.ui_translator import tr

class LeftColumnWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(250)
        self._init_ui()

    def _init_ui(self):
        self.lcw_layout = QVBoxLayout(self)
        self.lcw_layout.setContentsMargins(0,0,0,0)
        self.lcw_layout.setSpacing(0)

        # Session File Actions
        btn_group = QGroupBox("")
        btn_layout = QVBoxLayout(btn_group)

        self.load_btn = QPushButton(icon=load_icon("calendar-code"), text=tr("Load Recent Session", "menu_btn"))
        self.load_btn.setToolTip(tr("Load one of already Imported Sessions.", "menu_tooltip"))
        self.import_btn = QPushButton(icon=load_icon("brand-firefox"),text=tr("Import Current Session", "menu_btn"))
        self.import_btn.setToolTip(tr("Import directly from Firefox Profiles Folder", "menu_tooltip"))
        self.save_btn = QPushButton(icon=load_icon("device-floppy"),text=tr("Save Changes", "menu_btn"))
        self.save_btn.setToolTip(tr("Changes only Saved in the imported '.jsonlz4' File", "menu_tooltip"))
        self.export_btn = QPushButton(icon=load_icon("json"),text=tr("Save as JSON", "menu_btn"))
        self.export_btn.setToolTip(tr("Save current state of the data in decompiled json format", "menu_tooltip"))
        self.replace_btn = QPushButton(icon=load_icon("replace-user"),text=tr("Replace Session File", "menu_btn"))
        self.replace_btn.setToolTip(tr("Save current state and replace File in the Profile Folder", "menu_tooltip"))
        self.settings_btn = QPushButton(icon=load_icon("adjustments"),text=tr("Settings", "menu_btn"))
        self.settings_btn.setToolTip(tr("Open Settings Dialog, obviously", "menu_tooltip"))

        btn_layout.addWidget(self.load_btn)
        btn_layout.addWidget(self.import_btn)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.export_btn)
        btn_layout.addWidget(self.replace_btn)
        btn_layout.addWidget(self.settings_btn)

        # Duplication Detection
        dup_layout_group = QGroupBox(tr("Filter Duplicates", "menu_label"))
        dup_layout = QVBoxLayout()

        self.dup_title_cb = QCheckBox(tr("By Title", "menu_checkbox"))
        self.dup_url_cb = QCheckBox(tr("By URL", "menu_checkbox"))
        self.regex_checkbox = QCheckBox(tr("Apply Regex:", "menu_checkbox"))
        self.regex_checkbox.setToolTip(tr("Enable/Disable usage of Regex Filtering", "menu_tooltip"))
        
        rgx_layout = QHBoxLayout()
        self.regex_input = QComboBox()
        self.regex_input.setToolTip(tr("Enter a Regular Expression to filter the tabs", "menu_tooltip"))
        self.regex_input.setPlaceholderText(tr("Enter Regex...", "menu_input"))
        self.regex_input.setEditable(True)
        self.save_regex_btn = QPushButton(icon=load_icon("device-floppy"), text="")
        self.save_regex_btn.setToolTip(tr("Save current Regex input", "menu_tooltip"))
        
        rgx_layout.addWidget(self.regex_input, 1)
        rgx_layout.addWidget(self.save_regex_btn, 0)
            
        self.dup_keep_group = QCheckBox(tr("Keep Groups", "menu_checkbox"))
        self.dup_keep_group.setToolTip(tr("Keep the Tab Groups (Containers) when filtering duplicates", "menu_tooltip"))

        dup_layout.addWidget(self.dup_title_cb)
        dup_layout.addWidget(self.dup_url_cb)
        dup_layout.addWidget(self.regex_checkbox)
        dup_layout.addLayout(rgx_layout)
        dup_layout.addWidget(self.dup_keep_group)
        dup_layout_group.setLayout(dup_layout)

        # Tools
        tools_layout_group = QGroupBox(tr("Tools", "menu_label"))
        tools_layout = QVBoxLayout()

        self.export_bkm_btn = QPushButton(icon=load_icon("bookmark"), text=tr("Export as Bookmarks", "tools_btn"))
        self.export_bkm_btn.setToolTip(tr("Export Bookmarks from the current loaded Session", "tools_tooltip"))
        self.tc_btn = QPushButton(icon=load_icon("scissors"), text=tr("Title Cleaner", "tools_btn"))
        self.tc_btn.setToolTip(tr("Open Title Cleaner Dialog", "tools_tooltip"))
        self.ge_btn = QPushButton(icon=load_icon("edit"), text=tr("Group Editor", "tools_btn"))
        self.ge_btn.setToolTip(tr("Open Group Editor", "tools_tooltip"))

        tools_layout.addWidget(self.export_bkm_btn)
        tools_layout.addItem(QSpacerItem(20, 10, QSizePolicy.Minimum, QSizePolicy.Minimum))
        tools_layout.addWidget(self.tc_btn)
        tools_layout.addWidget(self.ge_btn)
        tools_layout_group.setLayout(tools_layout)

        # Plugins
        plugins_layout_group = QGroupBox(tr("Plugins", "menu_label"))
        plugins_layout = QVBoxLayout()
        
        self.lbi_btn = QPushButton(icon=load_icon("image-in-picture"), text=tr("Load Missing Images", "plugins_btn"))
        self.lbi_btn.setToolTip(tr("coming soon..."))
        #self.lbi_btn.setToolTip(tr("Load missing Images with XPath", "plugins_tooltip"))
        self.ext_url_btn = QPushButton(icon=load_icon("link"), text=tr("Show Extended URLs", "plugins_btn"))
        self.ext_url_btn.setToolTip(tr("coming soon..."))
        #self.ext_url_btn.setToolTip(tr("Show saved Extended URLs with all parameters", "plugins_tooltip"))
        self.xph_edit_rules_btn = QPushButton(icon=load_icon("pencil-code"), text=tr("Edit XPath Rules", "plugins_btn"))
        self.xph_edit_rules_btn.setToolTip(tr("Opens the XPath Rules Editor", "plugins_tooltip"))
        

        plugins_layout.addWidget(self.lbi_btn)
        plugins_layout.addWidget(self.ext_url_btn)
        plugins_layout.addWidget(self.xph_edit_rules_btn)
        plugins_layout_group.setLayout(plugins_layout)

        # Add everything to main layout
        self.lcw_layout.addWidget(btn_group)
        self.lcw_layout.addItem(QSpacerItem(30, 10, QSizePolicy.Minimum))
        self.lcw_layout.addWidget(dup_layout_group)
        self.lcw_layout.addItem(QSpacerItem(30, 10, QSizePolicy.Minimum, QSizePolicy.Expanding))
        self.lcw_layout.addWidget(tools_layout_group)
        self.lcw_layout.addItem(QSpacerItem(30, 10, QSizePolicy.Minimum))
        self.lcw_layout.addWidget(plugins_layout_group)

