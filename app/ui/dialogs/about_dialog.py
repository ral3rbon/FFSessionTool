from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QTextEdit, QTabWidget, QWidget, QHBoxLayout
from PySide6.QtCore import Qt
from app.utils.ui_translator import tr
from PySide6.QtGui import QIcon

class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("About FFSessionTool", "settings"))
        self.setModal(True)
        self.resize(700, 500)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        # Tab widget for different sections
        tab_widget = QTabWidget()
        
        # About Tab
        about_tab = QWidget()
        about_layout = QVBoxLayout(about_tab)
        
        # Application info
        app_info = QLabel("""
<h2>FFSessionTool</h2>
<p><b>Version:</b> 0.0.1</p>
<p><b>Description:</b> A PySide6-based desktop application for analyzing and managing Firefox session files.</p>
<p><b>Author:</b> Reinhold Alerbon</p>
<p><b>License:</b> MIT License (see LICENSE file)</p>
<p><b>Copyright:</b> (c) 2025 Reinhold Alerbon</p>

<p>Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:</p>

<p>The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.</p>

<p>THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.</p>
        """)
        app_info.setAlignment(Qt.AlignTop)
        app_info.setWordWrap(True)
        about_layout.addWidget(app_info)
        about_layout.addStretch()
        
        tab_widget.addTab(about_tab, "About")
        
        # Dependencies Tab
        deps_tab = QWidget()
        deps_layout = QVBoxLayout(deps_tab)
        
        deps_text = QTextEdit()
        deps_text.setReadOnly(True)
        deps_text.setPlainText(self._get_dependencies_text())
        deps_layout.addWidget(deps_text)
        
        tab_widget.addTab(deps_tab, "Dependencies")
        
        # Licenses Tab
        licenses_tab = QWidget()
        licenses_layout = QVBoxLayout(licenses_tab)
        
        licenses_text = QTextEdit()
        licenses_text.setReadOnly(True)
        licenses_text.setPlainText(self._get_licenses_text())
        licenses_layout.addWidget(licenses_text)
        
        tab_widget.addTab(licenses_tab, "Third-Party Licenses")
        
        # Acknowledgments Tab
        ack_tab = QWidget()
        ack_layout = QVBoxLayout(ack_tab)
        
        ack_text = QTextEdit()
        ack_text.setReadOnly(True)
        ack_text.setPlainText(self._get_acknowledgments_text())
        ack_layout.addWidget(ack_text)
        
        tab_widget.addTab(ack_tab, "Acknowledgments")
        
        layout.addWidget(tab_widget)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _get_dependencies_text(self):
        return """Main Dependencies:

• PySide6 - Qt6 Python bindings (LGPL v3)
• lxml - XML/HTML processing library (BSD License)
• lz4 - LZ4 compression bindings (BSD License)
• requests - HTTP library (Apache 2.0)
• shiboken6 - Qt6 Python bindings support (LGPL v3)

Optional Dependencies:

• playwright - Web automation (Apache 2.0)
• googletrans - Google Translate API (MIT License)

Development Dependencies:

• Python 3.8+ - Programming language (PSF License)
• SQLite3 - Database (Public Domain)
• pathlib - Path handling (Python Standard Library)
"""

    def _get_licenses_text(self):
        return """Third-Party License Notices:

=== PySide6 / Qt6 ===
Licensed under LGPL v3
Copyright (C) 2022 The Qt Company Ltd.
https://www.qt.io/licensing/

=== lxml ===
Licensed under BSD License
Copyright (c) 2004 Infrae. All rights reserved.
https://github.com/lxml/lxml/blob/master/LICENSE.txt

=== lz4 ===
Licensed under BSD License
Copyright (c) 2012-2013, Python-lz4 contributors
https://github.com/python-lz4/python-lz4/blob/master/LICENSE

=== requests ===
Licensed under Apache License 2.0
Copyright 2019 Kenneth Reitz
https://github.com/psf/requests/blob/main/LICENSE

=== Mozilla Session File Format ===
The mozLz4 decompression algorithm is based on Mozilla's implementation.
Mozilla Public License Version 2.0
https://mozilla.org/MPL/2.0/

=== Tabler Icons ===
Licensed under MIT License
Copyright (c) 2020-2023 Paweł Kuna
https://github.com/tabler/tabler-icons/blob/master/LICENSE

All icons in assets/icons/ are from Tabler Icons or custom created.

=== FlowLayout ===
Based on the Qt example code, licensed under BSD-3-Clause

Using the Example of https://doc.qt.io/qtforpython-6/examples/example_widgets_layouts_flowlayout.html
"""

    def _get_acknowledgments_text(self):
        return """Acknowledgments and Code Attribution:

=== Session File Parsing ===
The Firefox session file decompression (mozLz4 format) is based on:
- Mozilla's jsonlz4 format specification
- Community reverse engineering efforts
- Reference implementations from various Firefox session tools

=== UI Components ===
- Theme system inspired by Qt's styling capabilities
- Translation system follows Qt's internationalization patterns
- Icon loading system uses standard Qt resource patterns

=== Database Schema ===
- SQLite schema design for XPath rules and extracted data
- URL hashing for efficient tab lookup and duplicate detection

=== Firefox Integration ===
- Profile detection based on Firefox's profiles.ini format
- Session file locations follow Firefox's standard directory structure

=== Special Thanks ===
- Qt/PySide6 community for excellent documentation
- Mozilla developers for the open Firefox architecture
- Python community for robust libraries and tools
- All open source contributors whose work made this project possible

=== Code Review Notes ===
If you recognize any code patterns that require specific attribution
or license compliance, please contact me (apps@rd-an.de) for proper
acknowledgment and license compliance.
"""