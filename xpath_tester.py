#!/usr/bin/env python3
"""
XPath Rule Tester - Minimal GUI for testing XPath expressions
Standalone tool for the FFSessionTool project
"""

import pprint
import sys
import requests
from lxml import html
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLabel, QLineEdit, QTextEdit, QPushButton, QGroupBox, QCheckBox,
    QProgressBar, QMessageBox, QSplitter
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

class XPathTestWorker(QThread):
    """Worker thread for XPath testing to keep UI responsive"""
    result_ready = Signal(list)  # List of extracted values
    error_occurred = Signal(str)
    html_ready = Signal(str)  # Signal for HTML content
    
    def __init__(self, url: str, xpath: str, is_image: bool = False, render_js: bool = False):
        super().__init__()
        self.url = url
        self.xpath = xpath
        self.is_image = is_image
        self.render_js = render_js
        
    def run(self):
        try:
            html_content = ""
            if self.render_js:
                try:
                    from playwright.sync_api import sync_playwright
                    with sync_playwright() as p:
                        browser = p.chromium.launch()
                        page = browser.new_page()
                        page.goto(self.url, timeout=30000)
                        html_content = page.content()
                        browser.close()
                except ImportError:
                    self.error_occurred.emit("Playwright not installed. Install with: pip install playwright && playwright install")
                    return
                except Exception as e:
                    self.error_occurred.emit(f"Playwright error: {str(e)}")
                    return
            else:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive'
                }
                
                response = requests.get(self.url, headers=headers, timeout=30)
                response.raise_for_status()
                html_content = response.content.decode('utf-8', errors='replace')
            
            tree = html.fromstring(html_content)
            self.html_ready.emit(html_content[:5000])  # Emit decoded HTML for preview
            pprint.pprint(f"XPath: {self.xpath}") #!Debug
            
            # Initial XPath evaluation (only once)
            elements = tree.xpath(self.xpath)
            pprint.pprint(f"Elements found: {len(elements)}")  # Debug
            
            values = []
            
            # Use the same logic as the old working code
            try:
                import re
                # Check for attribute extraction pattern like: //video/@poster
                attr_match = re.match(r"^(.*)/@([\w-]+)$", self.xpath.strip())
                if attr_match:
                    base_xpath, attr = attr_match.groups()
                    pprint.pprint(f"Attribute extraction: base='{base_xpath}', attr='{attr}'")  # Debug
                    elements = tree.xpath(base_xpath)
                    values = [e.get(attr) for e in elements if e.get(attr)]
                else:
                    # Process results directly from initial elements
                    for elem in elements:
                        if isinstance(elem, str):
                            # Direct string result (from XPath like //text() or //@attr)
                            values.append(elem.strip())
                        elif hasattr(elem, 'text_content'):
                            # HTML element with text content
                            text = elem.text_content().strip()
                            if text:
                                values.append(text)
                        elif hasattr(elem, 'text'):
                            # Simple text attribute
                            text = elem.text.strip() if elem.text else ""
                            if text:
                                values.append(text)
                        else:
                            # Fallback: try to get all text nodes
                            try:
                                text = " ".join(elem.xpath(".//text()")).strip()
                                if text:
                                    values.append(text)
                            except Exception:
                                pass
                
                # Clean up values
                values = [v.strip() for v in values if v and str(v).strip()]
                pprint.pprint(f"Final values: {values}")  # Debug
                
            except Exception as e:
                pprint.pprint(f"XPath processing error: {e}")  # Debug
                values = []
            
            self.result_ready.emit(values)
            
        except requests.exceptions.RequestException as e:
            self.error_occurred.emit(f"Network error: {str(e)}")
        except Exception as e:
            self.error_occurred.emit(f"XPath error: {str(e)}")

class XPathTesterWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker = None
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("XPath Rule Tester")
        self.setGeometry(300, 300, 800, 600)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        layout = QVBoxLayout(central_widget)
        
        # Input section
        input_group = QGroupBox("Test Configuration")
        input_layout = QVBoxLayout(input_group)
        
        # URL input
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("URL:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://example.com")
        url_layout.addWidget(self.url_input)
        input_layout.addLayout(url_layout)
        
        # XPath input
        xpath_layout = QHBoxLayout()
        xpath_layout.addWidget(QLabel("XPath:"))
        self.xpath_input = QLineEdit()
        self.xpath_input.setPlaceholderText("//h1/text()")
        xpath_layout.addWidget(self.xpath_input)
        input_layout.addLayout(xpath_layout)
        
        # Options
        options_layout = QHBoxLayout()
        self.is_image_cb = QCheckBox("Extract image sources")
        self.render_js_cb = QCheckBox("Render JavaScript (requires Playwright)")  # New checkbox
        options_layout.addWidget(self.is_image_cb)
        options_layout.addWidget(self.render_js_cb)
        options_layout.addStretch()
        
        # Test button
        self.test_button = QPushButton("Test XPath")
        self.test_button.clicked.connect(self.test_xpath)
        options_layout.addWidget(self.test_button)
        input_layout.addLayout(options_layout)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        input_layout.addWidget(self.progress_bar)
        
        layout.addWidget(input_group)
        
        # Results section using splitter for resizable areas
        splitter = QSplitter(Qt.Vertical)
        
        # Results display
        results_group = QGroupBox("Extracted Results")
        results_layout = QVBoxLayout(results_group)
        
        self.results_text = QTextEdit()
        #self.results_text.setFont(QFont("Consolas", 10))
        self.results_text.setPlaceholderText("Results will appear here after testing...")
        results_layout.addWidget(self.results_text)
        
        splitter.addWidget(results_group)
        
        # Raw HTML preview (optional)
        html_group = QGroupBox("Raw HTML Preview (first 5000 chars)")
        html_layout = QVBoxLayout(html_group)
        
        self.html_preview = QTextEdit()
        self.html_preview.setFont(QFont("Consolas", 9))
        self.html_preview.setMaximumHeight(200)
        html_layout.addWidget(self.html_preview)
        
        splitter.addWidget(html_group)
        
        # Set splitter proportions
        splitter.setSizes([400, 200])
        layout.addWidget(splitter)
        
        # Example XPath patterns
        examples_group = QGroupBox("Common XPath Examples")
        examples_layout = QVBoxLayout(examples_group)
        examples_text = QLabel("""
        Text extraction:
        • //title/text() - Page title
        • //h1/text() - All H1 headings
        • //p/text() - All paragraph text
        • //a/@href - All link URLs
        • //*[@class='price']/text() - Elements with specific class
        
        Image/Media extraction (check "Extract image sources"):
        • //img/@src - Image sources
        • //video/@poster - Video poster images  
        • //img/@data-src - Lazy-loaded images
        • //*[@style]/@style - Inline styles (may contain background images)
        """)
        examples_text.setWordWrap(True)
        examples_text.setStyleSheet("color: #666; font-size: 11px;")
        examples_layout.addWidget(examples_text)
        examples_group.setMaximumHeight(120)
        
        layout.addWidget(examples_group)
        
        # Connect Enter key to test
        self.url_input.returnPressed.connect(self.test_xpath)
        self.xpath_input.returnPressed.connect(self.test_xpath)
        
    def test_xpath(self):
        url = self.url_input.text().strip()
        xpath = self.xpath_input.text().strip()
        
        if not url or not xpath:
            QMessageBox.warning(self, "Input Required", "Please enter both URL and XPath expression.")
            return
            
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
            self.url_input.setText(url)
        
        # Disable UI during processing
        self.test_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminate progress
        
        self.results_text.clear()
        self.html_preview.clear()
        
        # Start worker thread
        self.worker = XPathTestWorker(url, xpath, self.is_image_cb.isChecked(), self.render_js_cb.isChecked())  # Pass render_js
        self.worker.result_ready.connect(self.on_results_ready)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.html_ready.connect(self.on_html_ready)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()
        
    def on_results_ready(self, results):
        if not results:
            self.results_text.setPlainText("No results found.\n\nPossible reasons:\n- XPath doesn't match any elements\n- Matched elements have no text content\n- Page content is loaded dynamically (try different XPath or use a tool that renders JS)")
        else:
            output = f"Found {len(results)} result(s):\n\n"
            for i, result in enumerate(results, 1):
                output += f"{i}. {result}\n"
            self.results_text.setPlainText(output)
            
        # Remove redundant HTML loading here (now handled by worker)
        
    def on_html_ready(self, html):  # New method
        self.html_preview.setPlainText(html)
        
    def on_error(self, error_message):
        self.results_text.setPlainText(f"Error: {error_message}")
        
    def on_finished(self):
        # Re-enable UI
        self.test_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        if self.worker:
            self.worker.deleteLater()
            self.worker = None

def main():
    app = QApplication(sys.argv)
    
    # Set application properties
    app.setApplicationName("XPath Tester")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("FFSessionTool")
    
    window = XPathTesterWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
