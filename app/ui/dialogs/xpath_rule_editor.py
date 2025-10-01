import re
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QTableWidget, QTableWidgetItem, QWidget, QHeaderView,
    QLineEdit, QTextEdit, QPushButton, QFormLayout, QGroupBox, QMessageBox, QSizePolicy, QToolButton, QSpinBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from app.utils.db_handler import DBHandler
from app.src.settings import AppSettings
from app.utils import tr
from app.utils import Logger
from app.ui.helpers import load_icon  # icon helper

class XPathRuleEditorDialog(QDialog):
    def __init__(self, db_handler: DBHandler, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.db = db_handler
        self.settings = settings
        self.logger = Logger.get_logger("XPathRuleEditor")
        self.current_rule_id = None  # Track current rule for edit
        self.setWindowTitle(tr("XPath Rule Editor", "dialog"))
        self.setModal(True)
        self.resize(800, 500)
        self._init_ui()
        self._load_domains()
        self._load_rules()
        self._update_save_button_label()  # initial

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Filter Section
        filter_group = QGroupBox(tr("Filter Rules", "dialog"))
        filter_layout = QHBoxLayout(filter_group)
        self.domain_combo = QComboBox()
        self.domain_combo.addItem(tr("All Domains", "dialog"), "")
        self.domain_combo.currentIndexChanged.connect(self._on_domain_changed)
        filter_layout.addWidget(QLabel(tr("Domain:", "dialog")))
        filter_layout.addWidget(self.domain_combo)

        self.url_contains_combo = QComboBox()
        self.url_contains_combo.addItem(tr("All URL Contains", "dialog"), "")
        self.url_contains_combo.currentIndexChanged.connect(self._on_url_contains_changed)
        filter_layout.addWidget(QLabel(tr("URL Contains:", "dialog")))
        filter_layout.addWidget(self.url_contains_combo)
        layout.addWidget(filter_group)

        # Rules Table
        self.rules_table = QTableWidget()
        self.rules_table.setColumnCount(6)
        self.rules_table.setHorizontalHeaderLabels([tr("Name", "dialog"), tr("Rule", "dialog"), tr("Filter", "dialog"), tr("Cover", "dialog"), tr("Global", "dialog"), tr("Priority", "dialog")])
        #self.rules_table.setColumnWidth # Spaltenbreiten auto außer rule
        self.rules_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.rules_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.rules_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Rule column stretches
        self.rules_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.rules_table.cellClicked.connect(self._load_rule_for_edit)
        layout.addWidget(self.rules_table)

        # Form Section (left: form, right: toggles)
        form_group = QGroupBox(tr("Add/Edit Rule", "dialog"))
        form_row = QHBoxLayout(form_group)

        # Left form (fields)
        left_container = QWidget()
        form_layout = QFormLayout(left_container)
        self.domain_edit = QLineEdit()
        form_layout.addRow(tr("Domain:", "dialog"), self.domain_edit)
        self.url_contains_edit = QLineEdit()
        form_layout.addRow(tr("URL Contains:", "dialog"), self.url_contains_edit)
        self.name_edit = QLineEdit()
        form_layout.addRow(tr("Name:", "dialog"), self.name_edit)
        self.xpath_edit = QTextEdit()
        self.xpath_edit.textChanged.connect(self._validate_xpath)
        form_layout.addRow(tr("XPath:", "dialog"), self.xpath_edit)
        form_row.addWidget(left_container, 1)

        # Right column (toggle buttons + priority)
        right_container = QWidget()
        right_container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        right_col = QVBoxLayout(right_container)

        self.is_image_cb = QToolButton()
        self.is_image_cb.setCheckable(True)
        self.is_image_cb.toggled.connect(lambda c: self._set_toggle_icon(self.is_image_cb, c))
        self._set_toggle_icon(self.is_image_cb, False)
        right_col.addWidget(self._wrap_toggle_with_label(tr("Is Image", "dialog"), self.is_image_cb))

        self.is_filter_cb = QToolButton()
        self.is_filter_cb.setCheckable(True)
        self.is_filter_cb.toggled.connect(lambda c: self._set_toggle_icon(self.is_filter_cb, c))
        self._set_toggle_icon(self.is_filter_cb, False)
        right_col.addWidget(self._wrap_toggle_with_label(tr("Is Filter", "dialog"), self.is_filter_cb))

        self.is_global_cb = QToolButton()
        self.is_global_cb.setCheckable(True)
        self.is_global_cb.toggled.connect(self._on_global_toggled)
        self._set_toggle_icon(self.is_global_cb, False)
        right_col.addWidget(self._wrap_toggle_with_label(tr("Is Global", "dialog"), self.is_global_cb))

        # Priority spinner
        prio_wrap = QWidget()
        prio_lay = QHBoxLayout(prio_wrap)
        prio_lay.setContentsMargins(0, 0, 0, 0)
        prio_label = QLabel(tr("Priority", "dialog"))
        self.priority_spinbox = QSpinBox()
        prio_lay.addWidget(prio_label)
        prio_lay.addWidget(self.priority_spinbox)
        right_col.addWidget(prio_wrap)

        right_col.addStretch(1)
        form_row.addWidget(right_container, 0, Qt.AlignTop)

        layout.addWidget(form_group)

        # Buttons
        btn_layout = QHBoxLayout()
        self.save_btn = QPushButton()  # label set dynamically
        self.save_btn.clicked.connect(self._save_rule)
        btn_layout.addWidget(self.save_btn)
        self.delete_btn = QPushButton(tr("Delete", "dialog"))
        self.delete_btn.clicked.connect(self._delete_rule)
        btn_layout.addWidget(self.delete_btn)
        self.clear_btn = QPushButton(tr("Clear", "dialog"))
        self.clear_btn.clicked.connect(self._clear_form)
        btn_layout.addWidget(self.clear_btn)
        layout.addLayout(btn_layout)

    def _wrap_toggle_with_label(self, text, btn: QToolButton) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        label = QLabel(text)
        lay.addWidget(label)
        lay.addWidget(btn, 0, Qt.AlignRight)
        return w

    def _set_toggle_icon(self, btn: QToolButton, checked: bool):
        if checked:
            #btn.setIcon(colored_svg_icon("assets/icons/toggle-right.svg", "#2ecc71", size=20))
            btn.setIcon(load_icon("toggle-right", "#2ecc71", size=20))
        else:
            btn.setIcon(load_icon("toggle-left", None, size=20))

    def _update_save_button_label(self):
        self.save_btn.setText(tr("Update", "dialog") if self.current_rule_id else tr("Save", "dialog"))

    def _load_domains(self):
        self.domain_combo.blockSignals(True)
        self.domain_combo.clear()
        self.domain_combo.addItem(tr("All Domains", "dialog"), "")
        domains = self.db.get_url_contains_for_domain("")  # Placeholder, adjust if needed
        # Assuming domains are unique, load distinct domains
        with self.db.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT DISTINCT domain FROM xpath_domains")
            domains = [row[0] for row in cursor.fetchall()]
        for domain in domains:
            self.domain_combo.addItem(domain, domain)
        self.domain_combo.blockSignals(False)
        # Initial load of rules for all
        self._load_rules()

    def _on_domain_changed(self, idx: int):
        domain = self.domain_combo.currentData()
        # Formular vorbelegen
        self.domain_edit.setText(domain or "")
        # URL-Contains neu befüllen
        self.url_contains_combo.blockSignals(True)
        self.url_contains_combo.clear()
        self.url_contains_combo.addItem(tr("All URL Contains", "dialog"), "")
        if domain:
            url_contains_list = self.db.get_url_contains_for_domain(domain)
            for uc in url_contains_list:
                self.url_contains_combo.addItem(uc, uc)
        self.url_contains_combo.blockSignals(False)
        # Liste laden
        self._load_rules(domain or "", "")

    def _on_url_contains_changed(self, idx: int):
        domain = self.domain_combo.currentData() or ""
        url_contains = self.url_contains_combo.currentData() or ""
        # Formular vorbelegen (nur wenn nicht global)
        if not self.is_global_cb.isChecked():
            self.url_contains_edit.setText(url_contains)
        self._load_rules(domain, url_contains)

    def _load_rules(self, domain="", url_contains=""):
        self.rules_table.setRowCount(0)
        rules = self.db.get_xpath_rules(domain or "", url_contains or "")
        for rule in rules:
            row = self.rules_table.rowCount()
            self.rules_table.insertRow(row)
            self.rules_table.setItem(row, 0, QTableWidgetItem(rule['name']))
            self.rules_table.setItem(row, 1, QTableWidgetItem(rule['xpath']))
            self.rules_table.setItem(row, 2, QTableWidgetItem("Yes" if rule['is_filter'] else "No"))
            self.rules_table.setItem(row, 3, QTableWidgetItem("Yes" if rule['is_image'] else "No"))
            self.rules_table.setItem(row, 4, QTableWidgetItem("Yes" if rule['is_global'] else "No"))
            self.rules_table.setItem(row, 5, QTableWidgetItem(str(rule['priority'])))
            # Rule inkl. domain/url_contains speichern
            self.rules_table.item(row, 0).setData(Qt.UserRole, rule)
            if rule['is_global']:
                for col in range(6):
                    item = self.rules_table.item(row, col)
                    if item:
                        item.setBackground(QColor("#e0f7fa"))

    def _load_rule_for_edit(self, row, column):
        item = self.rules_table.item(row, 0)
        if not item:
            return
        rule = item.data(Qt.UserRole)
        self.current_rule_id = rule['id']

        # Formular füllen (aus der Regel, nicht aus den Combos)
        self.domain_edit.setText(rule.get('domain', '') or '')
        self.url_contains_edit.setText(rule.get('url_contains', '') or '')
        self.name_edit.setText(rule['name'])
        self.xpath_edit.setText(rule['xpath'])
        self.is_image_cb.setChecked(bool(rule['is_image']))
        self.is_filter_cb.setChecked(bool(rule['is_filter']))
        self.is_global_cb.setChecked(bool(rule['is_global']))
        self.priority_spinbox.setValue(int(rule.get('priority', 0)))

        # Dropdowns passend zur Regel setzen (Signale blocken)
        dom = rule.get('domain') or ''
        uc = rule.get('url_contains') or ''
        self.domain_combo.blockSignals(True)
        # Domain auswählen
        idx_dom = self.domain_combo.findData(dom) if dom else 0
        if idx_dom < 0:
            idx_dom = 0
        self.domain_combo.setCurrentIndex(idx_dom)
        self.domain_combo.blockSignals(False)

        # url_contains neu befüllen für die Domain und auswählen
        self.url_contains_combo.blockSignals(True)
        self.url_contains_combo.clear()
        self.url_contains_combo.addItem(tr("All URL Contains", "dialog"), "")
        if dom:
            for uc_opt in self.db.get_url_contains_for_domain(dom):
                self.url_contains_combo.addItem(uc_opt, uc_opt)
        # passenden Eintrag setzen
        idx_uc = self.url_contains_combo.findData(uc) if uc else 0
        if idx_uc < 0:
            idx_uc = 0
        self.url_contains_combo.setCurrentIndex(idx_uc)
        self.url_contains_combo.blockSignals(False)

        self._update_save_button_label()

    def _validate_xpath(self):
        xpath = self.xpath_edit.toPlainText()
        if not xpath.endswith("/text()"):
            self.xpath_edit.setStyleSheet("border: 1px solid red;")
        else:
            self.xpath_edit.setStyleSheet("")

    def _on_global_toggled(self, checked: bool):
        self._set_toggle_icon(self.is_global_cb, checked)
        if checked:
            self.url_contains_edit.setText("")

    def _save_rule(self):
        domain = self.domain_edit.text().strip()
        url_contains = "" if self.is_global_cb.isChecked() else self.url_contains_edit.text().strip()
        name = self.name_edit.text().strip()
        xpath = self.xpath_edit.toPlainText().strip()
        priority = int(self.priority_spinbox.value())
        if not domain or not name or not xpath:
            QMessageBox.warning(self, tr("Error", "dialog"), tr("Domain, Name, and XPath are required.", "dialog"))
            return
        rule = {
            "id": self.current_rule_id,
            "name": name,
            "xpath": xpath,
            "is_filter": self.is_filter_cb.isChecked(),
            "is_image": self.is_image_cb.isChecked(),
            "priority": priority,
            "is_global": self.is_global_cb.isChecked()
        }
        self.db.save_xpath_rules(domain, url_contains, [rule])
        # Reload rules with current filter
        current_domain = self.domain_combo.currentData() or ""
        current_url_contains = self.url_contains_combo.currentData() or ""
        self._load_rules(current_domain, current_url_contains)
        # Clear but keep domain/url_contains for rapid multi-insert
        self._clear_form(preserve_context=True)

    def _delete_rule(self):
        if not self.current_rule_id:
            QMessageBox.warning(self, tr("Error", "dialog"), tr("No rule selected.", "dialog"))
            return
        try:
            self.db.delete_xpath_rule(self.current_rule_id)
            # Nach Löschen Tabelle aktualisieren
            current_domain = self.domain_combo.currentData() or ""
            current_url_contains = self.url_contains_combo.currentData() or ""
            self._load_rules(current_domain, current_url_contains)
            self._clear_form()
        except Exception as e:
            QMessageBox.critical(self, tr("Error", "dialog"), str(e))

    def _clear_form(self, preserve_context: bool = False):
        keep_domain = self.domain_edit.text()
        keep_url_contains = self.url_contains_edit.text()
        self.current_rule_id = None
        if not preserve_context:
            self.domain_edit.clear()
            self.url_contains_edit.clear()
        else:
            self.domain_edit.setText(keep_domain)
            self.url_contains_edit.setText(keep_url_contains)
        self.name_edit.clear()
        self.xpath_edit.clear()
        self.is_image_cb.setChecked(False)
        self.is_filter_cb.setChecked(False)
        self.is_global_cb.setChecked(False)
        self.priority_spinbox.setValue(0)
        self._update_save_button_label()
        self.name_edit.setFocus()
