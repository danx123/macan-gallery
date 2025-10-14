import sys
import os
import cv2
import platform
import subprocess
import hashlib
import shutil
from functools import partial

# --- Core PySide6 Libraries ---
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QScrollArea,
    QVBoxLayout, QHBoxLayout, QFileDialog, QMenu, QStatusBar, QToolBar,
    QSizePolicy, QPushButton, QMessageBox, QToolButton, QDialog,
    QDialogButtonBox, QListWidget, QListWidgetItem, QGridLayout,
    QStackedWidget, QSpacerItem
)
from PySide6.QtGui import (
    QPixmap, QImage, QAction, QIcon, QKeySequence, QPainter, QCursor, QTransform
)
from PySide6.QtCore import (
    Qt, QSize, QPoint, QRect, QByteArray, QThread, QObject, Signal,
    QSettings, QTimer
)
from PySide6.QtSvg import QSvgRenderer

if platform.system() == "Windows":
    import ctypes

# --- Constants ---
APP_NAME = "Macan Gallery"
ORGANIZATION_NAME = "DanxExodus"
APP_VERSION = "1.0.0"
THUMBNAIL_SIZE = QSize(200, 200)
CACHE_DIR = os.path.join(os.path.expanduser('~'), '.cache', 'MacanGallery', 'thumbnails')
SUPPORTED_IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.bmp', '.webp']

# --- Helper Functions ---
def get_human_readable_size(size_in_bytes):
    """Converts a size in bytes to a human-readable format (KB, MB, etc.)."""
    if size_in_bytes == 0:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(os.path.floor(os.path.log(size_in_bytes, 1024)))
    p = os.path.pow(1024, i)
    s = round(size_in_bytes / p, 2)
    return f"{s} {size_name[i]}"

# --- Worker for Thumbnail Generation ---
class ThumbnailWorker(QObject):
    """
    Runs on a separate thread to generate thumbnails without freezing the UI.
    """
    thumbnail_ready = Signal(str, QPixmap)
    finished = Signal()

    def __init__(self, file_paths):
        super().__init__()
        self.file_paths = file_paths
        self.is_running = True

    def run(self):
        """Processes the list of image files."""
        os.makedirs(CACHE_DIR, exist_ok=True)
        for path in self.file_paths:
            if not self.is_running:
                break

            # Create a unique, safe filename for the cache from the path hash
            path_hash = hashlib.md5(path.encode()).hexdigest()
            cache_path = os.path.join(CACHE_DIR, f"{path_hash}.jpg")

            pixmap = None
            if os.path.exists(cache_path):
                # Load from cache
                pixmap = QPixmap(cache_path)
            else:
                # Generate new thumbnail
                try:
                    img = cv2.imread(path)
                    if img is not None:
                        h, w, _ = img.shape
                        # Resize while maintaining aspect ratio
                        if w > h:
                            new_w = THUMBNAIL_SIZE.width()
                            new_h = int((h / w) * new_w)
                        else:
                            new_h = THUMBNAIL_SIZE.height()
                            new_w = int((w / h) * new_h)
                        
                        resized_img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
                        
                        # Convert OpenCV image (BGR) to QImage (RGB)
                        rgb_image = cv2.cvtColor(resized_img, cv2.COLOR_BGR2RGB)
                        h, w, ch = rgb_image.shape
                        bytes_per_line = ch * w
                        q_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
                        
                        pixmap = QPixmap.fromImage(q_image)
                        # Save to cache for next time
                        pixmap.save(cache_path, "JPG", 85)
                except Exception as e:
                    print(f"Error creating thumbnail for {path}: {e}")
            
            if pixmap:
                self.thumbnail_ready.emit(path, pixmap)
        
        self.finished.emit()

    def stop(self):
        self.is_running = False

# --- Thumbnail Widget ---
class ThumbnailWidget(QToolButton):
    """
    A custom widget to display a thumbnail and its name in the grid.
    """
    def __init__(self, file_path, pixmap, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        
        self.setIcon(QIcon(pixmap))
        self.setIconSize(THUMBNAIL_SIZE - QSize(10, 30)) # Give space for text
        self.setText(os.path.basename(file_path))
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        
        self.setFixedSize(THUMBNAIL_SIZE)
        self.setStyleSheet("""
            QToolButton {
                background-color: #3B4252;
                color: #ECEFF4;
                border: 1px solid #4C566A;
                border-radius: 4px;
                padding: 4px;
            }
            QToolButton:hover {
                background-color: #4C566A;
                border: 1px solid #88C0D0;
            }
        """)
        self.setToolTip(file_path)

# --- Manage Folders & Cache Dialog ---
class ManageDialog(QDialog):
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle("Manage Gallery")
        self.setMinimumSize(500, 400)

        self.setStyleSheet("""
            QDialog { background-color: #2E3440; color: #ECEFF4; }
            QListWidget { background-color: #3B4252; border: 1px solid #4C566A; }
            QLabel { font-size: 11pt; }
            QPushButton {
                background-color: #5E81AC; color: #ECEFF4; border: none;
                padding: 8px 12px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #81A1C1; }
            QPushButton#clearCacheButton { background-color: #BF616A; }
            QPushButton#clearCacheButton:hover { background-color: #D08770; }
        """)
        
        main_layout = QVBoxLayout(self)
        
        # --- Folder Management ---
        main_layout.addWidget(QLabel("<b>Gallery Folders:</b>"))
        self.folder_list_widget = QListWidget()
        self.load_folders()
        main_layout.addWidget(self.folder_list_widget)
        
        folder_buttons_layout = QHBoxLayout()
        add_folder_btn = QPushButton("Add Folder...")
        add_folder_btn.clicked.connect(self.add_folder)
        remove_folder_btn = QPushButton("Remove Selected")
        remove_folder_btn.clicked.connect(self.remove_folder)
        folder_buttons_layout.addWidget(add_folder_btn)
        folder_buttons_layout.addWidget(remove_folder_btn)
        folder_buttons_layout.addStretch()
        main_layout.addLayout(folder_buttons_layout)

        # --- Cache Management ---
        main_layout.addSpacing(20)
        main_layout.addWidget(QLabel("<b>Thumbnail Cache:</b>"))
        
        self.cache_info_label = QLabel("Calculating cache size...")
        main_layout.addWidget(self.cache_info_label)
        
        clear_cache_btn = QPushButton("Clear Cache")
        clear_cache_btn.setObjectName("clearCacheButton")
        clear_cache_btn.clicked.connect(self.clear_cache)
        
        cache_layout = QHBoxLayout()
        cache_layout.addWidget(clear_cache_btn)
        cache_layout.addStretch()
        main_layout.addLayout(cache_layout)
        
        # --- Dialog Buttons ---
        main_layout.addStretch()
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
        
        self.update_cache_info()

    def load_folders(self):
        folders = self.settings.value("gallery_folders", [], type=list)
        self.folder_list_widget.addItems(folders)

    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Add to Gallery")
        if folder:
            items = [self.folder_list_widget.item(i).text() for i in range(self.folder_list_widget.count())]
            if folder not in items:
                self.folder_list_widget.addItem(folder)

    def remove_folder(self):
        selected_items = self.folder_list_widget.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            self.folder_list_widget.takeItem(self.folder_list_widget.row(item))

    def update_cache_info(self):
        try:
            total_size = sum(os.path.getsize(os.path.join(CACHE_DIR, f)) for f in os.listdir(CACHE_DIR) if os.path.isfile(os.path.join(CACHE_DIR, f)))
            file_count = len(os.listdir(CACHE_DIR))
            self.cache_info_label.setText(f"Location: {CACHE_DIR}\nSize: {get_human_readable_size(total_size)} ({file_count} files)")
        except FileNotFoundError:
            self.cache_info_label.setText(f"Location: {CACHE_DIR}\nCache is empty or does not exist.")
        except Exception as e:
            self.cache_info_label.setText(f"Could not read cache info: {e}")

    def clear_cache(self):
        reply = QMessageBox.question(self, "Confirm Clear Cache",
                                     "Are you sure you want to delete all cached thumbnails?\nThey will be regenerated when you next open the gallery.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                for filename in os.listdir(CACHE_DIR):
                    file_path = os.path.join(CACHE_DIR, filename)
                    os.unlink(file_path)
                QMessageBox.information(self, "Success", "Thumbnail cache cleared successfully.")
                self.update_cache_info()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear cache: {e}")

    def accept(self):
        # Save the folder list to settings
        folders = [self.folder_list_widget.item(i).text() for i in range(self.folder_list_widget.count())]
        self.settings.setValue("gallery_folders", folders)
        super().accept()

# --- Main Application Window ---
class MacanGallery(QMainWindow):
    def __init__(self):
        super().__init__()

        self.settings = QSettings(ORGANIZATION_NAME, APP_NAME)
        self.clipboard_cut_path = None
        self.thumbnail_thread = None
        self.thumbnail_worker = None
        self.all_image_paths = []
        self.thumbnail_widgets = {} # {path: widget}

        self.init_ui()
        self.load_settings()
        QTimer.singleShot(100, self.start_scanning_folders) # Start scan after UI is shown

    def init_ui(self):
        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(800, 600)
        self.setMouseTracking(True)
        
        icon_path = "macan_gallery.ico" # You can create an icon for your app
        if hasattr(sys, "_MEIPASS"):
            icon_path = os.path.join(sys._MEIPASS, icon_path)
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.apply_stylesheet()
        
        # --- Central Widget Setup ---
        self.main_stack = QStackedWidget()
        self.setCentralWidget(self.main_stack)

        # --- View 1: Gallery Grid ---
        gallery_widget = QWidget()
        gallery_layout = QVBoxLayout(gallery_widget)
        gallery_layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(10)
        
        self.scroll_area.setWidget(self.grid_container)
        gallery_layout.addWidget(self.scroll_area)
        self.main_stack.addWidget(gallery_widget)
        
        # --- View 2: Image Viewer ---
        viewer_widget = QWidget()
        viewer_layout = QVBoxLayout(viewer_widget)
        self.viewer_label = QLabel("Image Viewer")
        self.viewer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.viewer_scroll_area = QScrollArea()
        self.viewer_scroll_area.setWidget(self.viewer_label)
        self.viewer_scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        back_button = QPushButton("◄ Back to Gallery")
        back_button.clicked.connect(self.show_gallery_view)
        back_button.setFixedWidth(150)
        
        viewer_top_layout = QHBoxLayout()
        viewer_top_layout.addWidget(back_button)
        viewer_top_layout.addStretch()
        
        viewer_layout.addLayout(viewer_top_layout)
        viewer_layout.addWidget(self.viewer_scroll_area)
        self.main_stack.addWidget(viewer_widget)

        self.create_actions()
        self.create_tool_bar()
        self.create_status_bar()
        
        self.grid_container.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid_container.customContextMenuRequested.connect(self.show_context_menu)

    def apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #2E3440; border-radius: 8px; }
            QToolBar { background-color: #202020; border: none; padding: 5px; }
            QToolBar QToolButton { background-color: transparent; color: #ECEFF4; border: none; padding: 8px; margin: 0 2px; }
            QToolBar QToolButton:hover { background-color: #3c3c3c; border-radius: 3px; }
            QToolBar QToolButton#close_button:hover { background-color: #BF616A; }
            QMenu { background-color: #2b2b2b; color: #f0f0f0; border: 1px solid #4C566A; }
            QMenu::item:selected { background-color: #4C566A; }
            QStatusBar { background-color: #202020; color: #ECEFF4; border-top: 1px solid #4C566A; }
            QScrollArea { border: none; background-color: #2E3440; }
            QPushButton {
                background-color: #5E81AC; color: #ECEFF4; border: none;
                padding: 8px 12px; border-radius: 4px;
            }
            QPushButton:hover { background-color: #81A1C1; }
        """)

    def _create_svg_icon(self, svg_xml, color="#ECEFF4"):
        svg_xml_colored = svg_xml.replace('currentColor', color)
        renderer = QSvgRenderer(QByteArray(svg_xml_colored.encode('utf-8')))
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return QIcon(pixmap)

    def create_actions(self):
        self.manage_action = QAction("Manage", self)
        self.manage_action.triggered.connect(self.open_manage_dialog)
        
        self.refresh_action = QAction("Refresh", self)
        self.refresh_action.triggered.connect(self.start_scanning_folders)

        self.about_action = QAction("About", self)
        self.about_action.triggered.connect(self.show_about_dialog)

        self.exit_action = QAction("Exit", self)
        self.exit_action.triggered.connect(self.close)

    def create_tool_bar(self):
        self.tool_bar = QToolBar("Main Toolbar")
        self.tool_bar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.tool_bar)
        
        # --- SVG Icons ---
        manage_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M20 6h-8l-2-2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V8c0-1.1-.9-2-2-2zm0 12H4V6h5.17l2 2H20v10z"/></svg>'
        refresh_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M17.65 6.35C16.2 4.9 14.21 4 12 4c-4.42 0-7.99 3.58-7.99 8s3.57 8 7.99 8c3.73 0 6.84-2.55 7.73-6h-2.08c-.82 2.33-3.04 4-5.65 4-3.31 0-6-2.69-6-6s2.69-6 6-6c1.66 0 3.14.69 4.22 1.78L13 11h7V4l-2.35 2.35z"/></svg>'
        
        self.manage_action.setIcon(self._create_svg_icon(manage_svg))
        self.refresh_action.setIcon(self._create_svg_icon(refresh_svg))

        # --- Menu Setup ---
        file_menu_button = QToolButton(self)
        file_menu_button.setText("File")
        file_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        file_menu = QMenu(self)
        file_menu.addAction(self.manage_action)
        file_menu.addAction(self.refresh_action)
        file_menu.addSeparator()
        file_menu.addAction(self.about_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)
        file_menu_button.setMenu(file_menu)

        self.tool_bar.addWidget(file_menu_button)
        self.tool_bar.addAction(self.manage_action)
        self.tool_bar.addAction(self.refresh_action)

        # --- Custom Title Bar Buttons ---
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.tool_bar.addWidget(spacer)
        
        minimize_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 12 L20 12"></path></svg>'
        maximize_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 4 L20 4 L20 20 L4 20 Z"></path></svg>'
        self.restore_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 9 L20 9 L20 20 L9 20 Z M4 4 L15 4 L15 15 L4 15 Z"></path></svg>'
        close_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6 L18 18 M18 6 L6 18"></path></svg>'

        self.minimize_action = QAction(self._create_svg_icon(minimize_svg), "Minimize", self)
        self.minimize_action.triggered.connect(self.showMinimized)
        self.maximize_action = QAction(self._create_svg_icon(maximize_svg), "Maximize", self)
        self.maximize_action.triggered.connect(self.toggle_maximize_restore)
        self.close_action = QAction(self._create_svg_icon(close_svg), "Close", self)
        self.close_action.setObjectName("close_button")
        self.close_action.triggered.connect(self.close)

        self.tool_bar.addAction(self.minimize_action)
        self.tool_bar.addAction(self.maximize_action)
        self.tool_bar.addAction(self.close_action)

    def create_status_bar(self):
        self.statusbar = self.statusBar()
        self.status_label = QLabel("Ready")
        self.statusbar.addWidget(self.status_label, 1)
        self.file_count_label = QLabel("")
        self.statusbar.addPermanentWidget(self.file_count_label)
        
    def start_scanning_folders(self):
        if self.thumbnail_thread and self.thumbnail_thread.isRunning():
            self.thumbnail_worker.stop()
            self.thumbnail_thread.quit()
            self.thumbnail_thread.wait()

        # Clear existing grid
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self.thumbnail_widgets.clear()
        
        self.all_image_paths = []
        folders = self.settings.value("gallery_folders", [], type=list)
        if not folders:
            self.status_label.setText("No folders selected. Go to File > Manage to add folders.")
            return

        for folder in folders:
            self.status_label.setText(f"Scanning {folder}...")
            try:
                for entry in os.scandir(folder):
                    if entry.is_file():
                        _, ext = os.path.splitext(entry.name)
                        if ext.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                            self.all_image_paths.append(entry.path)
            except Exception as e:
                print(f"Could not scan folder {folder}: {e}")
        
        self.file_count_label.setText(f"{len(self.all_image_paths)} images")
        self.status_label.setText("Generating thumbnails...")

        self.thumbnail_thread = QThread()
        self.thumbnail_worker = ThumbnailWorker(self.all_image_paths)
        self.thumbnail_worker.moveToThread(self.thumbnail_thread)

        self.thumbnail_worker.thumbnail_ready.connect(self.add_thumbnail_to_grid)
        self.thumbnail_worker.finished.connect(self.on_thumbnailing_finished)
        self.thumbnail_thread.started.connect(self.thumbnail_worker.run)
        
        self.thumbnail_thread.start()

    def add_thumbnail_to_grid(self, path, pixmap):
        if path in self.thumbnail_widgets: return
            
        thumb_widget = ThumbnailWidget(path, pixmap)
        thumb_widget.doubleClicked.connect(lambda: self.show_image_view(path))
        
        # Calculate position in grid
        count = self.grid_layout.count()
        columns = max(1, self.scroll_area.width() // THUMBNAIL_SIZE.width())
        row = count // columns
        col = count % columns
        
        self.grid_layout.addWidget(thumb_widget, row, col)
        self.thumbnail_widgets[path] = thumb_widget

    def on_thumbnailing_finished(self):
        self.status_label.setText("Ready")
        self.grid_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding), self.grid_layout.rowCount(), 0)
        self.thumbnail_thread.quit()
        self.thumbnail_thread.wait()

    def reflow_grid(self):
        if self.main_stack.currentIndex() != 0: return # Only reflow if gallery is visible
        
        columns = max(1, self.scroll_area.width() // THUMBNAIL_SIZE.width())
        
        widgets = []
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                widgets.append(item.widget())
        
        for i, widget in enumerate(widgets):
            row = i // columns
            col = i % columns
            self.grid_layout.addWidget(widget, row, col)

    def show_image_view(self, path):
        try:
            pixmap = QPixmap(path)
            self.viewer_label.setPixmap(pixmap.scaled(self.viewer_scroll_area.size() - QSize(20,20), 
                                                      Qt.AspectRatioMode.KeepAspectRatio, 
                                                      Qt.TransformationMode.SmoothTransformation))
            self.main_stack.setCurrentIndex(1)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open image:\n{e}")

    def show_gallery_view(self):
        self.main_stack.setCurrentIndex(0)
        self.reflow_grid()
        
    def open_manage_dialog(self):
        dialog = ManageDialog(self.settings, self)
        if dialog.exec():
            self.start_scanning_folders()
            
    def show_about_dialog(self):
        QMessageBox.about(self, f"About {APP_NAME}",
                          f"<b>{APP_NAME} v{APP_VERSION}</b><br><br>"
                          "A professional, enterprise-grade gallery application "
                          "built with Python, PySide6, and OpenCV.<br><br>"
                          f"©2025 {ORGANIZATION_NAME}")
                          
    def show_context_menu(self, pos):
        # Find which thumbnail was clicked
        global_pos = self.grid_container.mapToGlobal(pos)
        widget_at = QApplication.widgetAt(global_pos)
        
        # Traverse up to find the ThumbnailWidget
        thumb_widget = widget_at
        while thumb_widget and not isinstance(thumb_widget, ThumbnailWidget):
            thumb_widget = thumb_widget.parent()

        context_menu = QMenu(self)
        
        if thumb_widget:
            self.status_label.setText(os.path.basename(thumb_widget.file_path))
            
            cut_action = context_menu.addAction("Cut")
            cut_action.triggered.connect(lambda: self.file_op_cut(thumb_widget.file_path))
            
            copy_action = context_menu.addAction("Copy (File Path)")
            copy_action.triggered.connect(lambda: self.file_op_copy(thumb_widget.file_path))
            
        paste_action = context_menu.addAction("Paste")
        paste_action.setEnabled(bool(self.clipboard_cut_path) and thumb_widget is not None)
        if thumb_widget:
            paste_action.triggered.connect(lambda: self.file_op_paste(os.path.dirname(thumb_widget.file_path)))
        
        context_menu.addSeparator()

        if thumb_widget:
            file_info_action = context_menu.addAction("File Info")
            file_info_action.triggered.connect(lambda: self.show_file_info(thumb_widget.file_path))
            
            set_wallpaper_action = context_menu.addAction("Set as Wallpaper")
            set_wallpaper_action.triggered.connect(lambda: self.set_as_wallpaper(thumb_widget.file_path))

        context_menu.exec(global_pos)
        
    def file_op_cut(self, path):
        self.clipboard_cut_path = path
        self.status_label.setText(f"Cut: {os.path.basename(path)}")
        
    def file_op_copy(self, path):
        QApplication.clipboard().setText(path)
        self.status_label.setText(f"Copied path: {os.path.basename(path)}")

    def file_op_paste(self, dest_folder):
        if not self.clipboard_cut_path: return
        
        source_path = self.clipboard_cut_path
        filename = os.path.basename(source_path)
        dest_path = os.path.join(dest_folder, filename)
        
        if source_path == dest_path:
            self.clipboard_cut_path = None
            return
            
        try:
            shutil.move(source_path, dest_path)
            self.status_label.setText(f"Moved {filename} to {dest_folder}")
            self.clipboard_cut_path = None
            # A full refresh is easiest to ensure consistency
            QTimer.singleShot(100, self.start_scanning_folders)
        except Exception as e:
            QMessageBox.critical(self, "Paste Error", f"Could not move file:\n{e}")
            
    def show_file_info(self, file_path):
        try:
            size_bytes = os.path.getsize(file_path)
            img = cv2.imread(file_path)
            h, w, _ = img.shape
            
            info_text = (
                f"<b>Filename:</b> {os.path.basename(file_path)}<br>"
                f"<b>Path:</b> {os.path.dirname(file_path)}<br>"
                f"<b>Dimensions:</b> {w} x {h} pixels<br>"
                f"<b>File Size:</b> {get_human_readable_size(size_bytes)} ({size_bytes:,} bytes)"
            )
            QMessageBox.information(self, "File Info", info_text)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not get file info: {e}")
            
    def set_as_wallpaper(self, file_path):
        path = os.path.abspath(file_path)
        system = platform.system()
        try:
            if system == "Windows":
                ctypes.windll.user32.SystemParametersInfoW(20, 0, path, 3)
            elif system == "Darwin": # macOS
                subprocess.run(f'osascript -e \'tell application "Finder" to set desktop picture to POSIX file "{path}"\'', shell=True, check=True)
            else: # Linux (GSettings for GNOME/Cinnamon)
                subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", f"file://{path}"], check=True)
            self.status_label.setText("Wallpaper set successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Set Wallpaper Error", f"Failed to set wallpaper:\n{e}")

    # --- Frameless Window Logic (from reference) ---
    def toggle_maximize_restore(self):
        if self.isMaximized():
            self.showNormal()
            self.maximize_action.setIcon(self._create_svg_icon(self.restore_svg, color="#ECEFF4").transformed(QTransform().rotate(180))) # Visual fix
        else:
            self.showMaximized()
            self.maximize_action.setIcon(self._create_svg_icon(self.restore_svg))

    def get_edge(self, pos):
        rect = self.rect()
        margin = 8
        if pos.y() < margin:
            if pos.x() < margin: return Qt.CursorShape.SizeFDiagCursor
            if pos.x() > rect.right() - margin: return Qt.CursorShape.SizeBDiagCursor
            return Qt.CursorShape.SizeVerCursor
        if pos.y() > rect.bottom() - margin:
            if pos.x() < margin: return Qt.CursorShape.SizeBDiagCursor
            if pos.x() > rect.right() - margin: return Qt.CursorShape.SizeFDiagCursor
            return Qt.CursorShape.SizeVerCursor
        if pos.x() < margin: return Qt.CursorShape.SizeHorCursor
        if pos.x() > rect.right() - margin: return Qt.CursorShape.SizeHorCursor
        return None

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            self.resize_edge = self.get_edge(pos)
            if self.resize_edge:
                self.is_resizing = True
                self.old_pos = event.globalPosition().toPoint()
            elif self.tool_bar.geometry().contains(pos):
                self.old_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        if hasattr(self, 'is_resizing') and self.is_resizing and self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.old_pos = event.globalPosition().toPoint()
            geom = self.geometry()
            if self.resize_edge in (Qt.CursorShape.SizeVerCursor, Qt.CursorShape.SizeFDiagCursor, Qt.CursorShape.SizeBDiagCursor):
                if pos.y() < 8: geom.setTop(geom.top() + delta.y())
                else: geom.setBottom(geom.bottom() + delta.y())
            if self.resize_edge in (Qt.CursorShape.SizeHorCursor, Qt.CursorShape.SizeFDiagCursor, Qt.CursorShape.SizeBDiagCursor):
                if pos.x() < 8: geom.setLeft(geom.left() + delta.x())
                else: geom.setRight(geom.right() + delta.x())
            self.setGeometry(geom)
            event.accept()
        elif event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, 'old_pos') and self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.old_pos = event.globalPosition().toPoint()
            event.accept()
        else:
            edge = self.get_edge(pos)
            if edge: self.setCursor(QCursor(edge))
            else: self.unsetCursor()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.old_pos = None
        self.is_resizing = False
        self.resize_edge = None
        self.unsetCursor()
        super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if event.position().y() < self.tool_bar.height():
                self.toggle_maximize_restore()
        super().mouseDoubleClickEvent(event)
        
    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(50, self.reflow_grid)
        if self.main_stack.currentIndex() == 1: # If viewer is active
             self.viewer_label.pixmap().scaled(self.viewer_scroll_area.size() - QSize(20,20), 
                                                Qt.AspectRatioMode.KeepAspectRatio, 
                                                Qt.TransformationMode.SmoothTransformation)
    
    def load_settings(self):
        geometry = self.settings.value("geometry", QByteArray())
        if geometry.size() > 0:
            self.restoreGeometry(geometry)
        else:
            self.setGeometry(100, 100, 1200, 800)
        
    def save_settings(self):
        self.settings.setValue("geometry", self.saveGeometry())
             
    def closeEvent(self, event):
        if self.thumbnail_thread and self.thumbnail_thread.isRunning():
            self.thumbnail_worker.stop()
            self.thumbnail_thread.quit()
            self.thumbnail_thread.wait()
        self.save_settings()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    gallery = MacanGallery()
    gallery.show()
    sys.exit(app.exec())