##*** main.py

import sys
import os
try:
    from PySide6.QtWidgets import QApplication, QWidget, QDialog
    from PySide6.QtGui import QPalette
    from PySide6.QtCore import Qt, QObject
except ImportError:
    print("ERROR: PySide6 not installed!")
    print("Please install with: pip install PySide6")
    print("You can also use an venv (recommended) to avoid messing with your system Python.\n\nEXAMPLE:\n\n# python3 -m venv .venv\n# source .venv/bin/activate\n# pip install pyside6\n\nThen run the application again.\nFor the lazy ones, here is the full command: (assuming you are in the project directory, and python3 is your interpreter)\n")
    print("python3 -m venv .venv && source .venv/bin/activate && pip install pyside6 && python3 main.py")
    print("")
    sys.exit(1)

from app.src.settings import AppSettings
from app.ui.helpers.ui_themes import theme_manager
from app.utils.ui_translator import set_language, get_translator
from setup_screen import StartupScreen

def main():
    app = QApplication(sys.argv)
    
    settings = AppSettings()

    sys.excepthook = handle_exception
    # Apply theme based on user settings
    theme_preference = settings.get("theme", "auto")
    theme_manager.apply_theme_by_preference(theme_preference)

    language = settings.get("language", "auto")
    if language != "auto":
        set_language(language)
    translator = get_translator()

    # Check if startup screen should be shown
    startup_screen = StartupScreen(settings, translator)
    if startup_screen.should_show_startup_screen():
        if startup_screen.exec() != QDialog.Accepted:
            # User cancelled startup, exit application
            sys.exit(0)

    from app.ui.app_window import FFsessionToolMainWindow
    
    window = FFsessionToolMainWindow(settings=settings, translator=translator)
    window.show()

    sys.exit(app.exec())

def handle_exception(exc_type, exc_value, exc_traceback):
    # Catch all unhandled exceptions
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    
    print(f"Uncaught exception: {exc_type.__name__}: {exc_value}")
    import traceback
    traceback.print_exception(exc_type, exc_value, exc_traceback)


if __name__ == "__main__":
    main()
