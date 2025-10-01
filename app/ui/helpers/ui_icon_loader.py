from pathlib import Path
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import QByteArray, Qt
import re
from app.ui.helpers.ui_colors import get_color_hex
from app.ui.helpers.ui_themes import get_icon_color


ICON_DIR = Path(__file__).parent.parent.parent.parent / "assets/icons"

def colorize_svg(svg_content: str, color) -> str:
    """SVG einfärben - gleiche Implementierung wie vorher."""
    if isinstance(color, QColor):
        hex_color = color.name()
    elif isinstance(color, str):
        if color.startswith('#'):
            hex_color = color
        else:
            try:
                hex_color = get_color_hex(color)
            except ValueError:
                qcolor = QColor(color)
                if qcolor.isValid():
                    hex_color = qcolor.name()
                else:
                    hex_color = '#000000'
    else:
        hex_color = '#000000'
    
    svg_content = re.sub(r'fill="(?!none")[^"]*"', f'fill="{hex_color}"', svg_content)
    svg_content = re.sub(r"fill='(?!none)[^']*'", f"fill='{hex_color}'", svg_content)
    svg_content = re.sub(r'stroke="(?!none)[^"]*"', f'stroke="{hex_color}"', svg_content)
    svg_content = re.sub(r"stroke='(?!none)[^']*'", f"stroke='{hex_color}'", svg_content)
    
    if 'fill=' not in svg_content:
        svg_content = re.sub(r'<svg([^>]*?)>', f'<svg\\1 fill="{hex_color}">', svg_content)
    
    return svg_content

def load_icon(name: str, color_or_size=None, size: int = None) -> QIcon:
    """
    Lädt ein SVG-Icon mit automatischer Theme-Unterstützung.
    """
    path = ICON_DIR / f"{name}.svg"
    if not path.exists():
        raise FileNotFoundError(f"Icon '{name}.svg' nicht gefunden in {ICON_DIR}")
    
    target_color = None
    target_size = None
    
    if isinstance(color_or_size, (str, QColor)):
        target_color = color_or_size
        target_size = size
    elif isinstance(color_or_size, int):
        target_size = color_or_size
    
    # Automatische Theme-Farbe wenn keine explizite Farbe angegeben
    if target_color is None:
        target_color = get_icon_color()
    
    svg_content = path.read_text(encoding='utf-8')
    
    if target_color:
        svg_content = colorize_svg(svg_content, target_color)
    
    svg_bytes = QByteArray(svg_content.encode('utf-8'))
    renderer = QSvgRenderer(svg_bytes)
    
    if target_size is None:
        pixmap = QPixmap(renderer.defaultSize())
    else:
        pixmap = QPixmap(target_size, target_size)
    
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return QIcon(pixmap)

def load_colored_icon(name: str, color: str, size: int = None) -> QIcon:
    """
    Lädt ein farbiges Icon.
    
    :param name: Icon-Name
    :param color: Farbe als Hex-String oder Farbname
    :param size: Optional: Größe in Pixel
    :return: QIcon-Objekt
    """
    return load_icon(name, color, size)

def load_white_icon(name: str, size: int = None) -> QIcon:
    """
    Lädt ein weißes Icon für den Darkmode.
    
    :param name: Icon-Name
    :param size: Optional: Größe in Pixel
    :return: QIcon-Objekt
    """
    return load_icon(name, '#FFFFFF', size)