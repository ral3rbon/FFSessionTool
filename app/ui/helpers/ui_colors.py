##*** app/utils/colors.py
from PySide6.QtGui import QColor, QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import Qt


COLORS = {
    "blue":   QColor(9, 86, 198),
    "purple": QColor(131, 47, 164),
    "cyan":   QColor(22, 119, 144),
    "orange": QColor(171, 37, 19),
    "yellow": QColor(150, 85, 23),
    "pink":   QColor(169, 18, 89),
    "green":  QColor(23, 118, 22),
    "gray":   QColor(95, 106, 118),
    "red":    QColor(175, 16, 58),
}

GUI_COLORS = {
    "g_blue":   QColor(11, 48, 155),
    "g_white":  QColor(255, 255, 255)
}

def colored_svg_icon(svg_path: str, color: QColor, size=16) -> QIcon:
    renderer = QSvgRenderer(svg_path)
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(pixmap.rect(), color)
    painter.end()
    return QIcon(pixmap)

def get_color(name: str) -> QColor:
    """
    Gibt eine Farbe aus COLORS oder GUI_COLORS zurück.
    
    :param name: Farbname (z.B. 'blue', 'g_blue')
    :return: QColor-Objekt
    """
    if name in COLORS:
        return COLORS[name]
    elif name in GUI_COLORS:
        return GUI_COLORS[name]
    else:
        available = list(COLORS.keys()) + list(GUI_COLORS.keys())
        raise ValueError(f"Farbe '{name}' nicht gefunden. Verfügbare Farben: {available}")

def get_color_hex(name: str) -> str:
    """
    Gibt eine Farbe als Hex-String zurück.
    
    :param name: Farbname
    :return: Hex-String (z.B. '#0956C6')
    """
    return get_color(name).name()

def list_colors() -> list:
    """Gibt alle verfügbaren Farbnamen zurück."""
    return list(COLORS.keys()) + list(GUI_COLORS.keys())