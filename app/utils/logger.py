import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path

class Logger:
    """
    Projektweite Logger-Klasse für die Verwaltung von benannten Loggers.
    Unterstützt separate Log-Dateien für verschiedene Komponenten.
    """
    _loggers = {}  # Cache für Logger-Instanzen

    @classmethod
    def get_logger(cls, name, max_bytes=5*1024*1024, backup_count=3):

        if name in cls._loggers:
            return cls._loggers[name]

        project_root = Path(__file__).resolve().parents[2]
        log_dir = project_root / "user_data" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"log_{name.lower()}.log"

        # Logger erstellen
        logger = logging.getLogger(name)
        logger.setLevel(logging.DEBUG)

        # Formatter für Log-Nachrichten
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"
        )

        # Handler hinzufügen, falls noch keiner existiert
        if not logger.handlers:
            # RotatingFileHandler für Log-Datei
            file_handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
            
            # Console-Handler für stderr (damit Fehler auch in der Konsole erscheinen)
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.WARNING)  # Nur Warnings und Errors in Konsole
            console_formatter = logging.Formatter("%(name)s - %(levelname)s: %(message)s")
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)

        cls._loggers[name] = logger
        return logger