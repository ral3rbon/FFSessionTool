# bookmark_exporter.py
import base64
from pathlib import Path
from PySide6.QtGui import QPixmap, QPainter, QColor, QIcon
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import Qt, QByteArray, QBuffer


class BookmarkExporter:
    """
    Exports Firefox session data to HTML bookmark files in two formats:
    - Browser Compatible: Standard Netscape bookmark format for browser import
    - Pretty: Modern HTML5 layout with dynamic colors and enhanced styling
    """

    def __init__(self, tree_widget, windows_data, colors, assets_path="assets/icons", favicon_cache_path="assets/cache/favicons"):
        """
        Initialize the bookmark exporter.

        Args:
            tree_widget: QTreeWidget containing all groups and tabs
            windows_data: List of window data from session JSON
            colors: Color mapping {name: QColor}
            assets_path: Path to icon assets
            favicon_cache_path: Path to favicon cache directory
        """
        self.tree_widget = tree_widget
        self.windows_data = windows_data
        self.COLORS = colors
        self.assets_path = Path(assets_path)
        self.favicon_cache_path = Path(favicon_cache_path)

    def _qicon_to_base64(self, svg_path: str, color: QColor = None, size: int = 16) -> str:
        """Convert SVG icon to Base64 PNG with optional color overlay."""
        renderer = QSvgRenderer(str(svg_path))
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        if color:
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), color)
        painter.end()

        ba = QByteArray()
        buffer = QBuffer(ba)
        buffer.open(QBuffer.WriteOnly)
        pixmap.save(buffer, "PNG")
        return base64.b64encode(ba.data()).decode("utf-8")

    def _window_icon_base64(self):
        """Get window icon as Base64 PNG."""
        icon_path = self.assets_path / "app-window.svg"
        if not icon_path.exists():
            return None
        return self._qicon_to_base64(icon_path)

    def _default_tab_icon_base64(self):
        """Get default tab icon as Base64 PNG."""
        icon_path = self.assets_path / "label.svg"
        if not icon_path.exists():
            return None
        return self._qicon_to_base64(icon_path)

    def _group_icon_base64(self, color: QColor = None, ungrouped=False):
        """Get group folder icon as Base64 PNG with optional color."""
        if ungrouped:
            svg_file = self.assets_path / "folder-open.svg"
        else:
            svg_file = self.assets_path / "folder.svg"
        return self._qicon_to_base64(svg_file, color)

    def _favicon_from_cache_to_base64(self, domain: str) -> str:
        """
        Load favicon from cache directory and convert to Base64.

        Args:
            domain: Domain name for the favicon

        Returns:
            Base64-encoded favicon or None if not found
        """
        if not domain:
            return None

        favicon_file = self.favicon_cache_path / f"{domain}.png"

        if not favicon_file.exists():
            return None

        try:
            with open(favicon_file, "rb") as f:
                favicon_data = f.read()
            return base64.b64encode(favicon_data).decode("utf-8")
        except Exception:
            return None

    def _create_group_gradient(self, color: QColor) -> str:
        """
        Create a beautiful gradient based on group color.
        Left: Lightened, soft version of the color
        Right: Original, vibrant color
        """
        if not color:
            return "linear-gradient(135deg, #a8edea 0%, #fed6e3 100%)"

        # Original color (right side)
        r, g, b = color.red(), color.green(), color.blue()
        original_color = f"rgb({r}, {g}, {b})"

        # Lightened version (left side) - blend with white
        light_r = min(255, r + (255 - r) * 0.7)  # 70% lighter
        light_g = min(255, g + (255 - g) * 0.7)
        light_b = min(255, b + (255 - b) * 0.7)
        light_color = f"rgb({int(light_r)}, {int(light_g)}, {int(light_b)})"

        return f"linear-gradient(135deg, {light_color} 0%, {original_color} 100%)"

    def _get_border_color(self, color: QColor) -> str:
        """Create a darker version of the color for the left border."""
        if not color:
            return "#3498db"

        r, g, b = color.red(), color.green(), color.blue()
        dark_r = max(0, int(r * 0.7))  # 30% darker
        dark_g = max(0, int(g * 0.7))
        dark_b = max(0, int(b * 0.7))

        return f"rgb({dark_r}, {dark_g}, {dark_b})"

    def _get_pretty_css(self):
        """Generate CSS for the Pretty HTML5 layout."""
        return """
        <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: rgba(255, 255, 255, 0.95);
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(10px);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            padding: 30px;
            text-align: center;
            position: relative;
        }
        
        .header::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="grain" width="100" height="100" patternUnits="userSpaceOnUse"><circle cx="25" cy="25" r="1" fill="rgba(255,255,255,0.1)"/><circle cx="75" cy="75" r="1" fill="rgba(255,255,255,0.1)"/><circle cx="50" cy="10" r="0.5" fill="rgba(255,255,255,0.05)"/></pattern></defs><rect width="100" height="100" fill="url(%23grain)"/></svg>');
            opacity: 0.3;
        }
        
        .header h1 {
            font-size: 2.5em;
            font-weight: 300;
            margin-bottom: 10px;
            position: relative;
            z-index: 1;
        }
        
        .header .subtitle {
            font-size: 1.1em;
            opacity: 0.9;
            position: relative;
            z-index: 1;
        }
        
        .content {
            padding: 30px;
        }
        
        .window-section {
            margin-bottom: 40px;
            border-radius: 15px;
            background: white;
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.08);
            overflow: hidden;
        }
        
        .window-header {
            background: linear-gradient(135deg, #ff9a9e 0%, #fecfef 100%);
            color: white;
            padding: 20px 25px;
            font-size: 1.3em;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 12px;
        }
        
        .window-header img {
            width: 24px;
            height: 24px;
            filter: brightness(0) invert(1);
        }
        
        .group {
            border-bottom: 1px solid #f0f0f0;
        }
        
        .group:last-child {
            border-bottom: none;
        }
        
        .group-header {
            background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%);
            padding: 15px 25px;
            font-weight: 600;
            color: white;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
            display: flex;
            align-items: center;
            gap: 10px;
            border-left: 4px solid #3498db;
        }
        
        .group-header.ungrouped {
            background: linear-gradient(135deg, #ffeaa7 0%, #fab1a0 100%);
            border-left: 4px solid #e17055;
            color: white;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
        }
        
        .group-header img {
            width: 20px;
            height: 20px;
            opacity: 0.8;
        }
        
        .bookmarks-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 15px;
            padding: 25px;
            background: #fafbfc;
        }
        
        .bookmark-item {
            background: white;
            border-radius: 12px;
            padding: 15px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.05);
            transition: all 0.3s ease;
            border: 1px solid #e8ecef;
            display: flex;
            align-items: center;
            gap: 12px;
            text-decoration: none;
            color: inherit;
        }
        
        .bookmark-item:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
            border-color: #3498db;
        }
        
        .bookmark-icon {
            width: 32px;
            height: 32px;
            border-radius: 8px;
            background: #f8f9fa;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
            border: 1px solid #e9ecef;
        }
        
        .bookmark-icon img {
            width: 20px;
            height: 20px;
            border-radius: 4px;
        }
        
        .bookmark-content {
            flex: 1;
            min-width: 0;
        }
        
        .bookmark-title {
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 4px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .bookmark-url {
            font-size: 0.85em;
            color: #7f8c8d;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        
        .stats {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            text-align: center;
            margin-top: 30px;
            border-radius: 15px;
        }
        
        .export-info {
            background: #e8f4fd;
            border: 1px solid #bee5eb;
            border-radius: 10px;
            padding: 15px;
            margin-bottom: 20px;
            color: #0c5460;
            font-size: 0.9em;
        }
        
        @media (max-width: 768px) {
            .bookmarks-grid {
                grid-template-columns: 1fr;
                padding: 15px;
            }
            
            .header h1 {
                font-size: 2em;
            }
            
            .content {
                padding: 20px;
            }
        }
        </style>
        """

    def export(self, filepath: str, variant: int, groups_as_folders: bool, selected_windows=None):
        """
        Export bookmarks to HTML file.

        Args:
            filepath: Target HTML file path
            variant: 0=Browser Compatible, 1=Pretty HTML5
            groups_as_folders: Export groups as bookmark folders
            selected_windows: List of window indices to export (None for all)
        """
        html_parts = []

        if variant == 1:
            # Pretty HTML5 Layout with modern styling
            html_parts.extend([
                "<!DOCTYPE html>",
                "<html lang='de'>",
                "<head>",
                "<meta charset='UTF-8'>",
                "<meta name='viewport' content='width=device-width, initial-scale=1.0'>",
                "<title>Pretty Bookmarks</title>",
                self._get_pretty_css(),
                "</head>",
                "<body>",
                "<div class='container'>",
                "<div class='header'>",
                "<h1>Pretty Bookmarks</h1>",
                "<div class='subtitle'>Exported from Firefox Session Explorer</div>",
                "</div>",
                "<div class='content'>"
            ])
        else:
            # Standard Netscape Bookmark Format for browser compatibility
            html_parts.extend([
                "<!DOCTYPE NETSCAPE-Bookmark-file-1>",
                "<META HTTP-EQUIV=\"Content-Type\" CONTENT=\"text/html; charset=UTF-8\">",
                "<TITLE>Bookmarks</TITLE>",
                "<H1>Bookmarks</H1>",
                "<DL><p>"
            ])

        # Determine windows to export
        if not self.windows_data:
            windows_to_export = [(0, {"title": "Main Window", "index": 0})]
        else:
            windows_to_export = (
                [(i, w) for i, w in enumerate(self.windows_data)]
                if selected_windows is None else
                [(i, self.windows_data[i]) for i in selected_windows]
            )

        multi_window = len(windows_to_export) > 1

        # Map tree widget items to windows
        window_items = {}
        for i in range(self.tree_widget.topLevelItemCount()):
            item = self.tree_widget.topLevelItem(i)
            item_data = item.data(0, Qt.UserRole)

            if item_data and item_data.get("type") == "window":
                window_items[item_data.get("window_index")] = item
            else:
                window_items[0] = self.tree_widget

        # Process each window
        for win_idx, window_data in windows_to_export:
            current_window_item = window_items.get(win_idx)
            if not current_window_item:
                continue

            # Window header
            if multi_window:
                win_title = f"Window {win_idx + 1}"
                if variant == 1:
                    window_icon_b64 = self._window_icon_base64()
                    icon_html = f'<img src="data:image/png;base64,{window_icon_b64}" alt="Window">' if window_icon_b64 else "🪟"
                    html_parts.extend([
                        f'<div class="window-section">',
                        f'<div class="window-header">{icon_html} {win_title}</div>'
                    ])
                else:
                    window_icon_b64 = self._window_icon_base64()
                    icon_html = f' ICON="data:image/png;base64,{window_icon_b64}"' if window_icon_b64 else ""
                    html_parts.extend([
                        f'<DT><H3 ADD_DATE="0" LAST_MODIFIED="0"{icon_html}>{win_title}</H3>',
                        '<DL><p>'
                    ])
            # elif variant == 1:
            #     win_title = f"Window {win_idx + 1}"
            #     window_icon_b64 = self._window_icon_base64()
            #     icon_html = f'<img src="data:image/png;base64,{window_icon_b64}" alt="Window">' if window_icon_b64 else "🪟"
            #     html_parts.extend([
            #         f'<div class="window-section">',
            #         f'<div class="window-header">{icon_html}{win_title}</div>'
            #     ])
            else:
                # Browser compatible version - only show window headers for multi-window, no icons
                if multi_window:
                    html_parts.extend([
                        f'<DT><H3 ADD_DATE="0" LAST_MODIFIED="0">{win_title}</H3>',
                        '<DL><p>'
                    ])

            # Collect groups in current window
            groups_in_current_window = []
            item_parent = current_window_item

            if item_parent is self.tree_widget:
                # Single-window: top-level items are groups
                for i in range(self.tree_widget.topLevelItemCount()):
                    groups_in_current_window.append(self.tree_widget.topLevelItem(i))
            else:
                # Multi-window: children of window item are groups
                for i in range(item_parent.childCount()):
                    groups_in_current_window.append(item_parent.child(i))

            # Sort groups: regular groups first, ungrouped tabs last
            sorted_groups = []
            ungrouped_items = []

            for g_item in groups_in_current_window:
                gdata = g_item.data(0, Qt.UserRole)
                group_text = g_item.text(0)

                if gdata and gdata.get("type") == "group":
                    group_name = gdata.get("group_name", "")

                    if (group_name == "Ungrouped" or
                        "Ungrouped" in group_text or
                        "ungrouped" in group_text.lower() or
                        group_text.lower().startswith("ungrouped")):
                        ungrouped_items.append(g_item)
                    else:
                        sorted_groups.append(g_item)
                else:
                    # Handle items without proper group data
                    if ("ungrouped" in group_text.lower() or
                        "Ungrouped" in group_text):
                        ungrouped_items.append(g_item)
                        # Create fake group data for consistency
                        fake_gdata = {
                            "type": "group",
                            "group_name": "Ungrouped"
                        }
                        g_item.setData(0, Qt.UserRole, fake_gdata)

            sorted_groups += ungrouped_items

            # Process each group
            for g_item in sorted_groups:
                gdata = g_item.data(0, Qt.UserRole)
                if not gdata or gdata.get("type") != "group":
                    continue

                gname = gdata.get("group_name", "Unnamed")
                ungrouped_flag = (gname == "Ungrouped")

                if variant == 1:
                    # Pretty layout for groups
                    if groups_as_folders:
                        color = g_item.data(0, Qt.UserRole + 1)
                        if isinstance(color, QColor):
                            icon_b64 = self._group_icon_base64(color, ungrouped=ungrouped_flag)
                        else:
                            icon_b64 = self._group_icon_base64(None, ungrouped=ungrouped_flag)

                        icon_html = f'<img src="data:image/png;base64,{icon_b64}" alt="Folder">' if icon_b64 else ("📂" if not ungrouped_flag else "📁")
                        html_parts.append(f'<div class="group">')

                        # Dynamic colors for groups based on their original color
                        if ungrouped_flag:
                            ungrouped_class = " ungrouped"
                            style_attr = ""
                        else:
                            ungrouped_class = ""
                            if isinstance(color, QColor):
                                gradient = self._create_group_gradient(color)
                                border_color = self._get_border_color(color)
                                style_attr = f' style="background: {gradient}; border-left-color: {border_color};"'
                            else:
                                style_attr = ""

                        html_parts.extend([
                            f'<div class="group-header{ungrouped_class}"{style_attr}>{icon_html}{gname}</div>',
                            f'<div class="bookmarks-grid">'
                        ])
                    else:
                        html_parts.append(f'<div class="bookmarks-grid">')
                else:
                    # Standard Netscape format - no icons for maximum browser compatibility
                    if groups_as_folders:
                        html_parts.extend([
                            f'<DT><H3 ADD_DATE="0" LAST_MODIFIED="0">{gname}</H3>',
                            '<DL><p>'
                        ])

                # Process tabs in group
                for t in range(g_item.childCount()):
                    t_item = g_item.child(t)
                    tdata = t_item.data(0, Qt.UserRole)

                    if not tdata:
                        continue

                    url = tdata.get("url")
                    domain = tdata.get("domain")
                    title = tdata.get("title", url)
                    favicon = tdata.get("favicon")

                    if variant == 1:
                        # Pretty layout for bookmarks with favicons
                        favicon_html = ""
                        if favicon and favicon.startswith("data:image"):
                            favicon_html = f'<img src="{favicon}" alt="{domain}">'
                        else:
                            favicon_base64 = self._favicon_from_cache_to_base64(domain)
                            if favicon_base64:
                                favicon_html = f'<img src="data:image/png;base64,{favicon_base64}" alt="{domain}">'
                            else:
                                base64_default = self._default_tab_icon_base64()
                                if base64_default:
                                    favicon_html = f'<img src="data:image/png;base64,{base64_default}" alt="{domain}">'
                                else:
                                    favicon_html = "🔗"

                        # Truncate URL for display
                        display_url = domain if domain else url
                        if len(display_url) > 50:
                            display_url = display_url[:47] + "..."

                        html_parts.append(f'''
                        <a href="{url}" class="bookmark-item" target="_blank">
                            <div class="bookmark-icon">{favicon_html}</div>
                            <div class="bookmark-content">
                                <div class="bookmark-title">{title}</div>
                                <div class="bookmark-url">{display_url}</div>
                            </div>
                        </a>''')
                    else:
                        # Standard Netscape format - no favicons for maximum browser compatibility
                        html_parts.append(f'<DT><A HREF="{url}" ADD_DATE="0">{title}</A>')

                # Close group
                if variant == 1:
                    html_parts.append('</div>')  # bookmarks-grid
                    if groups_as_folders:
                        html_parts.append('</div>')  # group
                else:
                    if groups_as_folders:
                        html_parts.append('</DL><p>')

            # Close window
            if multi_window or variant == 1:
                if variant == 1:
                    html_parts.append('</div>')  # window-section
                else:
                    html_parts.append('</DL><p>')

        # Close document
        if variant == 1:
            total_bookmarks = sum(g_item.childCount() for g_item in sorted_groups if g_item.data(0, Qt.UserRole) and g_item.data(0, Qt.UserRole).get("type") == "group")
            html_parts.extend([
                f'<div class="stats">📊 Total: {total_bookmarks} Bookmarks exported</div>',
                '</div>',  # content
                '</div>',  # container
                '</body>',
                '</html>'
            ])
        else:
            html_parts.append('</DL><p>')

        # Write to file
        Path(filepath).write_text("\n".join(html_parts), encoding="utf-8")