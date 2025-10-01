from PySide6.QtWidgets import QDialog, QVBoxLayout, QPlainTextEdit, QHBoxLayout, QPushButton, QLabel
from PySide6.QtCore import QSettings
from app.utils import tr

class TitleCleanerDialog(QDialog):
    SETTINGS_KEY = "StripPatterns"

    def __init__(self, app_settings, parent=None):
        """
        :param app_settings: Instanz der Klasse, die QSettings verwaltet (z.B. AppSettings)
        """
        super().__init__(parent)
        self.setWindowTitle("Title Cleaner")
        self.resize(600, 400)

        self.app_settings = app_settings

        layout = QVBoxLayout(self)

        # Beschreibung
        description_label = QLabel(
            "Please enter the strings you want to remove from display in the GUI, line by line.\n"
            "The data in the session file will NOT be overwritten!"
        )
        description_label.setWordWrap(True)
        layout.addWidget(description_label)

        self.text_edit = QPlainTextEdit()
        layout.addWidget(self.text_edit)

        self.load_patterns()

        # Buttons Speichern & Abbrechen
        button_layout = QHBoxLayout()
        save_button = QPushButton("Save")
        cancel_button = QPushButton("Cancel")
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        save_button.clicked.connect(self.on_save_clicked)
        cancel_button.clicked.connect(self.reject)

    def load_patterns(self):
        patterns = self.app_settings.get(self.SETTINGS_KEY, [])
        if isinstance(patterns, str):
            patterns = [p.strip() for p in patterns.split(",") if p.strip()]
        self.text_edit.setPlainText("\n".join(patterns))
        return patterns or []

    def on_save_clicked(self):
        patterns_text = self.text_edit.toPlainText()
        lines = [line.strip() for line in patterns_text.splitlines() if line.strip()]
        self.app_settings.set(self.SETTINGS_KEY, lines)
        self.accept()
