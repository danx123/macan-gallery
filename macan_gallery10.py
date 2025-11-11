import sys
import os
import cv2
import platform
import subprocess
import hashlib
import shutil
import math
from functools import partial
from collections import defaultdict

# --- Core PySide6 Libraries ---
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QScrollArea,
    QVBoxLayout, QHBoxLayout, QFileDialog, QMenu, QStatusBar, QToolBar,
    QSizePolicy, QPushButton, QMessageBox, QToolButton, QDialog,
    QDialogButtonBox, QListWidget, QListWidgetItem, QGridLayout,
    QStackedWidget, QSpacerItem, QFrame, QLineEdit, QSlider
)
from PySide6.QtGui import (
    QPixmap, QImage, QAction, QIcon, QKeySequence, QPainter, QCursor, QTransform,
    QColor, QMouseEvent, QDrag, QActionGroup
)
from PySide6.QtCore import (
    Qt, QSize, QPoint, QRect, QByteArray, QThread, QObject, Signal,
    QSettings, QTimer, QMimeData, QUrl, QEvent
)
from PySide6.QtSvg import QSvgRenderer

if platform.system() == "Windows":
    import ctypes

# --- Constants ---
APP_NAME = "Macan Gallery"
ORGANIZATION_NAME = "DanxExodus"
APP_VERSION = "1.4.0" # [PERUBAHAN] Versi diperbarui dengan perbaikan cache dan fitur sort by
THUMBNAIL_IMAGE_SIZE = QSize(220, 124) # [PERUBAHAN] Ukuran target untuk gambar thumbnail
CACHE_DIR = os.path.join(os.path.expanduser('~'), '.cache', 'MacanGallery', 'thumbnails')
SUPPORTED_IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.bmp', '.webp']

# --- Helper Functions ---
def get_human_readable_size(size_in_bytes):
    """Converts a size in bytes to a human-readable format (KB, MB, etc.)."""
    if size_in_bytes is None or size_in_bytes == 0:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_in_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_in_bytes / p, 2)
    return f"{s} {size_name[i]}"

# --- Worker for Thumbnail Generation ---
class ThumbnailWorker(QObject):
    """
    [PERBAIKAN] Runs on a separate thread to generate thumbnails.
    Emits a signal for each thumbnail created for real-time UI updates.
    """
    thumbnail_ready = Signal(str, str)  # original_path, cache_path
    finished = Signal()

    def __init__(self, file_paths):
        super().__init__()
        self.file_paths = file_paths
        self.is_running = True

    def run(self):
        """Processes the list of image files to generate and cache thumbnails."""
        os.makedirs(CACHE_DIR, exist_ok=True)
        for path in self.file_paths:
            if not self.is_running:
                break

            path_hash = hashlib.md5(path.encode()).hexdigest()
            cache_path = os.path.join(CACHE_DIR, f"{path_hash}.jpg")

            if os.path.exists(cache_path):
                continue

            try:
                # [PERBAIKAN] Logika resize dan crop disederhanakan dan lebih robust
                img = cv2.imread(path)
                if img is None:
                    continue

                h, w = img.shape[:2]
                target_h, target_w = THUMBNAIL_IMAGE_SIZE.height(), THUMBNAIL_IMAGE_SIZE.width()
                
                # Scale image to fill the target size while maintaining aspect ratio
                aspect_ratio_img = w / h
                aspect_ratio_target = target_w / target_h

                if aspect_ratio_img > aspect_ratio_target:
                    # Image is wider than target, scale based on height
                    new_h = target_h
                    new_w = int(aspect_ratio_img * new_h)
                else:
                    # Image is taller than target, scale based on width
                    new_w = target_w
                    new_h = int(new_w / aspect_ratio_img)

                resized_img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)

                # Crop from the center
                y_start = (new_h - target_h) // 2
                x_start = (new_w - target_w) // 2
                cropped_img = resized_img[y_start:y_start+target_h, x_start:x_start+target_w]
                
                if cv2.imwrite(cache_path, cropped_img, [int(cv2.IMWRITE_JPEG_QUALITY), 90]):
                     self.thumbnail_ready.emit(path, cache_path)

            except Exception as e:
                print(f"Error creating thumbnail for {path}: {e}")
        
        self.finished.emit()

    def stop(self):
        self.is_running = False

# --- Thumbnail Widgets ---
class ThumbnailWidget(QFrame):
    """Widget kustom untuk menampilkan thumbnail gambar dan namanya."""
    def __init__(self, file_path, main_window, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.main_window = main_window

        self.setFixedSize(220, 180)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("thumbnailCard")
        self.setStyleSheet("""
            #thumbnailCard {
                background-color: #3B4252; border: 1px solid #434C5E; border-radius: 8px;
            }
            #thumbnailCard:hover {
                background-color: #434C5E; border: 1px solid #88C0D0;
            }
            QLabel { color: #ECEFF4; border: none; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self.thumbnail_label = QLabel()
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setStyleSheet("border-radius: 5px; background-color: #2E3440;")
        self.thumbnail_label.setFixedSize(210, 118)

        # [PERBAIKAN] Moved pixmap loading to a separate method for clarity
        self.update_pixmap()

        file_name = os.path.splitext(os.path.basename(file_path))[0]
        self.title_label = QLabel(file_name)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.title_label.setWordWrap(True)

        layout.addWidget(self.thumbnail_label)
        layout.addWidget(self.title_label)
        
    def update_pixmap(self):
        """Loads the thumbnail from cache or sets a placeholder."""
        path_hash = hashlib.md5(self.file_path.encode()).hexdigest()
        cache_path = os.path.join(CACHE_DIR, f"{path_hash}.jpg")
        pixmap = QPixmap(cache_path)

        if pixmap.isNull():
            self.thumbnail_label.setText("...")
        else:
            # Scaled to fit the label, which is slightly smaller than the target size
            scaled_pixmap = pixmap.scaled(self.thumbnail_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.thumbnail_label.setPixmap(scaled_pixmap)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.main_window.show_image_view(self.file_path)
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if (event.position().toPoint() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return
        
        drag = QDrag(self)
        mime_data = QMimeData()
        
        url = QUrl.fromLocalFile(self.file_path)
        mime_data.setUrls([url])
        
        drag.setMimeData(mime_data)
        
        pixmap = self.thumbnail_label.pixmap()
        if pixmap:
            drag.setPixmap(pixmap.scaled(QSize(120, 68), Qt.AspectRatioMode.KeepAspectRatio))
        
        drag.exec(Qt.DropAction.CopyAction)
        
class FolderThumbnailWidget(QFrame):
    """Widget untuk menampilkan folder dengan thumbnail komposit 2x2."""
    def __init__(self, folder_path, image_paths, main_window, parent=None):
        super().__init__(parent)
        self.folder_path = folder_path
        self.image_paths = image_paths
        self.main_window = main_window

        self.setFixedSize(220, 180)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("thumbnailCard")
        self.setStyleSheet("""
            #thumbnailCard {
                background-color: #3B4252; border: 1px solid #434C5E; border-radius: 8px;
            }
            #thumbnailCard:hover {
                background-color: #434C5E; border: 1px solid #88C0D0;
            }
            QLabel { color: #ECEFF4; border: none; }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)

        thumbnail_container = QWidget()
        thumbnail_container.setFixedSize(210, 118)
        thumbnail_container.setStyleSheet("border-radius: 5px; background-color: #2E3440;")
        
        grid_layout = QGridLayout(thumbnail_container)
        grid_layout.setContentsMargins(2, 2, 2, 2)
        grid_layout.setSpacing(2)

        videos_to_preview = self.image_paths[:4]
        positions = [(0, 0), (0, 1), (1, 0), (1, 1)]
        
        for i, path in enumerate(videos_to_preview):
            thumb_label = QLabel()
            path_hash = hashlib.md5(path.encode()).hexdigest()
            cache_path = os.path.join(CACHE_DIR, f"{path_hash}.jpg")
            pixmap = QPixmap(cache_path)
            
            if not pixmap.isNull():
                thumb_label.setPixmap(pixmap.scaled(QSize(103, 57), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation))
            else:
                thumb_label.setText("...")
            thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid_layout.addWidget(thumb_label, positions[i][0], positions[i][1])

        folder_name = os.path.basename(self.folder_path)
        item_count = len(self.image_paths)
        self.title_label = QLabel(f"{folder_name}\n({item_count} items)")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.title_label.setWordWrap(True)

        main_layout.addWidget(thumbnail_container)
        main_layout.addWidget(self.title_label)
        
    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.main_window.show_folder_contents(self.folder_path)
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_position = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.MouseButton.LeftButton):
            return
        if (event.position().toPoint() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance():
            return
        
        drag = QDrag(self)
        mime_data = QMimeData()
        
        url = QUrl.fromLocalFile(self.folder_path)
        mime_data.setUrls([url])
        
        drag.setMimeData(mime_data)
        
        preview_pixmap = self.grab(QRect(QPoint(0,0), self.size().toSize()))
        drag.setPixmap(preview_pixmap)
        
        drag.exec(Qt.DropAction.CopyAction)

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
        if not selected_items: return
        for item in selected_items:
            self.folder_list_widget.takeItem(self.folder_list_widget.row(item))
    def update_cache_info(self):
        try:
            if not os.path.exists(CACHE_DIR):
                self.cache_info_label.setText(f"Location: {CACHE_DIR}\nCache is empty.")
                return
            total_size = sum(os.path.getsize(os.path.join(CACHE_DIR, f)) for f in os.listdir(CACHE_DIR) if os.path.isfile(os.path.join(CACHE_DIR, f)))
            file_count = len(os.listdir(CACHE_DIR))
            self.cache_info_label.setText(f"Location: {CACHE_DIR}\nSize: {get_human_readable_size(total_size)} ({file_count} files)")
        except Exception as e:
            self.cache_info_label.setText(f"Could not read cache info: {e}")
    def clear_cache(self):
        reply = QMessageBox.question(self, "Confirm Clear Cache",
                                     "Are you sure you want to delete all cached thumbnails?\nThey will be regenerated when you next open the gallery.",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if os.path.exists(CACHE_DIR):
                    shutil.rmtree(CACHE_DIR)
                    os.makedirs(CACHE_DIR, exist_ok=True)
                QMessageBox.information(self, "Success", "Thumbnail cache cleared successfully.")
                self.update_cache_info()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to clear cache: {e}")
    def accept(self):
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
        
        self.grouped_images = {}
        self.thumbnail_widgets = {} # [PERBAIKAN] Untuk melacak widget agar bisa diupdate
        
        self.current_view = 'folders'
        self.selected_folder = None

        self.current_viewer_pixmap = None
        
        # [FITUR BARU] Variabel untuk sorting
        self.current_sort_method = self.settings.value("sort_method", "name_asc")

        # Variabel untuk state pan mode
        self.is_panning = False
        self.pan_last_mouse_pos = QPoint()

        self.init_ui()
        self.load_settings()
        QTimer.singleShot(100, self.start_scanning_folders)

    def init_ui(self):
        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(800, 600)
        self.setMouseTracking(True)
        
        icon_path = "macan_gallery.ico"
        if hasattr(sys, "_MEIPASS"):
            icon_path = os.path.join(sys._MEIPASS, icon_path)
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.apply_stylesheet()
        
        self.main_stack = QStackedWidget()
        self.setCentralWidget(self.main_stack)

        # --- View 1: Gallery (Folders/Images) ---
        gallery_widget = QWidget()
        gallery_layout = QVBoxLayout(gallery_widget)
        gallery_layout.setContentsMargins(10, 5, 10, 5)
        gallery_layout.setSpacing(10)

        controls_layout = QHBoxLayout()
        self.back_button = QPushButton("◄ Back to Folder List")
        self.back_button.clicked.connect(self.show_folders_view)
        self.back_button.setVisible(False)
        self.back_button.setFixedWidth(200)
        controls_layout.addWidget(self.back_button)
        controls_layout.addStretch()
        gallery_layout.addLayout(controls_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.grid_container = QWidget()
        self.grid_layout = QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(15)
        
        self.scroll_area.setWidget(self.grid_container)
        gallery_layout.addWidget(self.scroll_area)
        self.main_stack.addWidget(gallery_widget)
        
        # --- View 2: Image Viewer ---
        viewer_widget = QWidget()
        viewer_layout = QVBoxLayout(viewer_widget)
        self.viewer_label = QLabel()
        self.viewer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Instalasi event filter untuk pan mode
        self.viewer_label.setMouseTracking(True)
        self.viewer_label.installEventFilter(self)

        self.viewer_scroll_area = QScrollArea()
        self.viewer_scroll_area.setWidget(self.viewer_label)
        self.viewer_scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        viewer_back_button = QPushButton("◄ Back to Gallery")
        viewer_back_button.clicked.connect(self.show_gallery_view)
        viewer_back_button.setFixedWidth(150)
        
        viewer_top_layout = QHBoxLayout()
        viewer_top_layout.addWidget(viewer_back_button)
        viewer_top_layout.addStretch()
        
        viewer_layout.addLayout(viewer_top_layout)
        viewer_layout.addWidget(self.viewer_scroll_area)
        self.main_stack.addWidget(viewer_widget)

        self.create_actions()
        self.create_tool_bar()
        self.create_status_bar()
        
        self.grid_container.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid_container.customContextMenuRequested.connect(self.show_context_menu)
        
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.reflow_ui)

    def apply_stylesheet(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #2E3440; border-radius: 8px; }
            QToolBar { 
                background-color: #3B4252; 
                border: none; padding: 5px; 
                border-bottom: 1px solid #4C566A;
            }
            QToolBar QToolButton { 
                background-color: transparent; color: #ECEFF4; 
                border: none; padding: 8px; margin: 0 2px; font-weight: bold; 
            }
            QToolBar QToolButton:hover { background-color: #4C566A; border-radius: 3px; }
            QToolBar QToolButton#close_button:hover { background-color: #BF616A; }
            QLineEdit {
                background-color: #2E3440;
                color: #ECEFF4;
                border: 1px solid #4C566A;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QMenu { background-color: #3B4252; color: #ECEFF4; border: 1px solid #4C566A; }
            QMenu::item:selected { background-color: #5E81AC; }
            QStatusBar { 
                background-color: #3B4252; 
                color: #ECEFF4;
                border-top: 1px solid #4C566A; 
            }
            /* Style untuk QSlider di status bar */
            QStatusBar::item { border: none; }
            QSlider::groove:horizontal {
                border: 1px solid #4C566A;
                background: #2E3440;
                height: 4px;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #88C0D0;
                border: 1px solid #88C0D0;
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
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

        # Aksi untuk zoom
        self.zoom_in_action = QAction("Zoom In", self)
        self.zoom_in_action.setShortcuts([QKeySequence.StandardKey.ZoomIn, QKeySequence("+")])
        self.zoom_in_action.triggered.connect(self.zoom_in)
        
        self.zoom_out_action = QAction("Zoom Out", self)
        self.zoom_out_action.setShortcuts([QKeySequence.StandardKey.ZoomOut, QKeySequence("-")])
        self.zoom_out_action.triggered.connect(self.zoom_out)
        
        self.addActions([self.zoom_in_action, self.zoom_out_action])

    def create_tool_bar(self):
        self.tool_bar = QToolBar("Main Toolbar")
        self.tool_bar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.tool_bar)
        
        manage_svg = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path><circle cx="12" cy="13" r="1"></circle><circle cx="17" cy="13" r="1"></circle><circle cx="7" cy="13" r="1"></circle></svg>'
        refresh_svg = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>'
        sort_svg = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>'
        self.manage_action.setIcon(self._create_svg_icon(manage_svg))
        self.refresh_action.setIcon(self._create_svg_icon(refresh_svg))

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
        
        # [FITUR BARU] Tombol dan Menu Sort By
        sort_button = QToolButton(self)
        sort_button.setIcon(self._create_svg_icon(sort_svg))
        sort_button.setText("Sort By")
        sort_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        
        sort_menu = QMenu(self)
        sort_group = QActionGroup(self)
        sort_group.setExclusive(True)
        
        sort_actions = {
            "Name (A-Z)": "name_asc",
            "Name (Z-A)": "name_desc",
            "Date (Newest First)": "date_new",
            "Date (Oldest First)": "date_old",
            "Size (Largest First)": "size_large",
            "Size (Smallest First)": "size_small"
        }
        
        for text, data in sort_actions.items():
            action = QAction(text, self, checkable=True)
            action.setData(data)
            if self.current_sort_method == data:
                action.setChecked(True)
            sort_menu.addAction(action)
            sort_group.addAction(action)

        sort_group.triggered.connect(self.set_sort_method)
        sort_button.setMenu(sort_menu)
        self.tool_bar.addWidget(sort_button)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search items...")
        self.search_bar.setMaximumWidth(300)
        self.search_bar.textChanged.connect(lambda: self.search_timer.start(300))
        self.tool_bar.addWidget(self.search_bar)
        
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.tool_bar.addWidget(spacer)
        
        minimize_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 12 L20 12"></path></svg>'
        maximize_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect></svg>'
        self.restore_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path></svg>'
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

    # [FITUR BARU] Method untuk handle sorting
    def set_sort_method(self, action):
        """Sets the current sort method and redraws the UI."""
        self.current_sort_method = action.data()
        self.settings.setValue("sort_method", self.current_sort_method)
        self.reflow_ui()

    def create_status_bar(self):
        self.statusbar = self.statusBar()
        self.status_label = QLabel("Ready")
        self.statusbar.addWidget(self.status_label, 1)

        # Widget untuk informasi file gambar
        self.image_res_label = QLabel()
        self.image_file_type_label = QLabel()
        self.image_size_label = QLabel()
        self.statusbar.addPermanentWidget(self.image_res_label)
        self.statusbar.addPermanentWidget(self.image_file_type_label)
        self.statusbar.addPermanentWidget(self.image_size_label)
        self.image_res_label.hide()
        self.image_file_type_label.hide()
        self.image_size_label.hide()

        # Widget untuk zoom
        separator = QLabel(" | ")
        self.zoom_label = QLabel("100%")
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 400) # Zoom 10% - 400%
        self.zoom_slider.setValue(100)
        self.zoom_slider.setFixedWidth(150)
        self.zoom_slider.valueChanged.connect(self.update_zoom)
        self.statusbar.addPermanentWidget(separator)
        self.statusbar.addPermanentWidget(self.zoom_label)
        self.statusbar.addPermanentWidget(self.zoom_slider)
        separator.hide()
        self.zoom_label.hide()
        self.zoom_slider.hide()

        self.file_count_label = QLabel("")
        self.statusbar.addPermanentWidget(self.file_count_label)
        
    def start_scanning_folders(self):
        if self.thumbnail_thread and self.thumbnail_thread.isRunning():
            self.thumbnail_worker.stop()
            self.thumbnail_thread.quit()
            self.thumbnail_thread.wait()

        self.grouped_images.clear()
        
        folders = self.settings.value("gallery_folders", [], type=list)
        if not folders:
            self.status_label.setText("No folders selected. Go to File > Manage to add folders.")
            self.file_count_label.setText("0 images")
            self.reflow_ui()
            return

        all_image_paths = []
        for base_folder in folders:
            self.status_label.setText(f"Scanning {base_folder}...")
            QApplication.processEvents()
            try:
                for dirpath, _, filenames in os.walk(base_folder):
                    images_in_current_folder = []
                    for filename in filenames:
                        _, ext = os.path.splitext(filename)
                        if ext.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                            full_path = os.path.join(dirpath, filename)
                            images_in_current_folder.append(full_path)

                    if images_in_current_folder:
                        self.grouped_images[dirpath] = sorted(images_in_current_folder)
                        all_image_paths.extend(images_in_current_folder)
            except Exception as e:
                print(f"Could not scan folder {base_folder}: {e}")
        
        self.file_count_label.setText(f"{len(self.grouped_images)} folders, {len(all_image_paths)} images")
        self.status_label.setText("Generating thumbnails in background...")
        
        # [PERBAIKAN] Langsung tampilkan UI dengan placeholder, lalu update thumbnail secara real-time
        self.show_folders_view() 

        self.thumbnail_thread = QThread()
        self.thumbnail_worker = ThumbnailWorker(all_image_paths)
        self.thumbnail_worker.moveToThread(self.thumbnail_thread)
        self.thumbnail_worker.thumbnail_ready.connect(self.update_thumbnail_widget) # [PERBAIKAN] Connect ke slot update
        self.thumbnail_worker.finished.connect(self.on_thumbnailing_finished)
        self.thumbnail_thread.started.connect(self.thumbnail_worker.run)
        self.thumbnail_thread.start()

    # [PERBAIKAN] Slot baru untuk mengupdate widget thumbnail secara individu
    def update_thumbnail_widget(self, original_path, cache_path):
        if original_path in self.thumbnail_widgets:
            widget = self.thumbnail_widgets[original_path]
            widget.update_pixmap()
            
    def on_thumbnailing_finished(self):
        self.status_label.setText("Ready")
        if self.thumbnail_thread:
            self.thumbnail_thread.quit()
            self.thumbnail_thread.wait()
        # [PERBAIKAN] Panggil reflow_ui di akhir untuk memastikan folder thumbnail juga terupdate
        self.reflow_ui()

    def reflow_ui(self):
        """Redraws the UI based on the current view, search query, and sort method."""
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        self.thumbnail_widgets.clear() # [PERBAIKAN] Kosongkan daftar widget setiap kali UI digambar ulang
        
        columns = max(1, (self.scroll_area.width() - 30) // 240)
        
        search_term = self.search_bar.text().lower()
        
        if self.current_view == 'folders':
            self.back_button.setVisible(False)
            folder_paths = sorted(self.grouped_images.keys())
            
            # [FITUR BARU] Sorting folder (hanya berdasarkan nama)
            if self.current_sort_method == "name_desc":
                folder_paths.reverse()
            
            if search_term:
                folder_paths = [f for f in folder_paths if search_term in os.path.basename(f).lower()]

            for i, folder_path in enumerate(folder_paths):
                image_paths = self.grouped_images[folder_path]
                if not image_paths: continue
                folder_widget = FolderThumbnailWidget(folder_path, image_paths, self)
                row, col = divmod(i, columns)
                self.grid_layout.addWidget(folder_widget, row, col)

        elif self.current_view == 'images' and self.selected_folder:
            self.back_button.setVisible(True)
            image_paths = self.grouped_images.get(self.selected_folder, []).copy()
            
            # [FITUR BARU] Logika sorting untuk file gambar
            try:
                if self.current_sort_method == 'name_asc':
                    image_paths.sort()
                elif self.current_sort_method == 'name_desc':
                    image_paths.sort(reverse=True)
                elif self.current_sort_method == 'date_new':
                    image_paths.sort(key=os.path.getmtime, reverse=True)
                elif self.current_sort_method == 'date_old':
                    image_paths.sort(key=os.path.getmtime)
                elif self.current_sort_method == 'size_large':
                    image_paths.sort(key=os.path.getsize, reverse=True)
                elif self.current_sort_method == 'size_small':
                    image_paths.sort(key=os.path.getsize)
            except FileNotFoundError:
                print("Warning: Some files could not be found during sorting.")
            
            if search_term:
                image_paths = [p for p in image_paths if search_term in os.path.basename(p).lower()]

            for i, path in enumerate(image_paths):
                thumb_widget = ThumbnailWidget(path, self)
                # [PERBAIKAN] Daftarkan widget untuk bisa diupdate nanti
                self.thumbnail_widgets[path] = thumb_widget
                row, col = divmod(i, columns)
                self.grid_layout.addWidget(thumb_widget, row, col)

        self.grid_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding), self.grid_layout.rowCount(), 0, 1, -1)

    def show_folder_contents(self, folder_path):
        """Switches view to show images inside a selected folder."""
        self.current_view = 'images'
        self.selected_folder = folder_path
        self.search_bar.clear()
        self.scroll_area.verticalScrollBar().setValue(0) # Reset scroll
        self.reflow_ui()
        
    def show_folders_view(self):
        """Switches view back to the main folder list."""
        self.current_view = 'folders'
        self.selected_folder = None
        self.search_bar.clear()
        self.scroll_area.verticalScrollBar().setValue(0) # Reset scroll
        self.reflow_ui()

    def show_image_view(self, path):
        try:
            cv_image = cv2.imread(path, cv2.IMREAD_UNCHANGED)
            if cv_image is None:
                raise Exception(f"OpenCV failed to open the image file.")

            h_orig, w_orig, *channels = cv_image.shape
            num_channels = channels[0] if channels else 3

            if num_channels == 4:
                rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGRA2RGBA)
                bytes_per_line = num_channels * w_orig
                qt_image = QImage(rgb_image.data, w_orig, h_orig, bytes_per_line, QImage.Format.Format_RGBA8888)
            else:
                if len(cv_image.shape) == 2:
                    cv_image = cv2.cvtColor(cv_image, cv2.COLOR_GRAY2BGR)
                
                rgb_image = cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB)
                bytes_per_line = 3 * w_orig
                qt_image = QImage(rgb_image.data, w_orig, h_orig, bytes_per_line, QImage.Format.Format_RGB888)
            
            if qt_image.isNull():
                raise Exception("Failed to convert the OpenCV image to a QImage.")

            pixmap = QPixmap.fromImage(qt_image)
            self.current_viewer_pixmap = pixmap
            
            # Tampilkan info file & kontrol zoom di status bar
            size_bytes = os.path.getsize(path)
            file_ext = os.path.splitext(path)[1].upper().replace('.', '')
            self.image_res_label.setText(f"{w_orig}x{h_orig}")
            self.image_file_type_label.setText(f"{file_ext} Image")
            self.image_size_label.setText(get_human_readable_size(size_bytes))
            self.image_res_label.show()
            self.image_file_type_label.show()
            self.image_size_label.show()
            
            self.zoom_slider.parent().show() # Show separator
            self.zoom_label.show()
            self.zoom_slider.show()
            
            # Set gambar kosong dulu, lalu panggil fit-to-window setelah UI siap
            self.viewer_label.setPixmap(QPixmap()) # Clear previous image
            self.main_stack.setCurrentIndex(1)
            QTimer.singleShot(0, self.fit_image_to_window)

        except Exception as e:
            QMessageBox.critical(self, "Error Opening Image", f"Could not open the image file:\n{path}\n\nReason: {e}")

    def fit_image_to_window(self):
        if self.current_viewer_pixmap is None:
            return

        img_size = self.current_viewer_pixmap.size()
        viewport_size = self.viewer_scroll_area.viewport().size()
        
        if img_size.width() <= 0 or img_size.height() <= 0: return

        # Hitung skala agar gambar pas di jendela
        w_ratio = viewport_size.width() / img_size.width()
        h_ratio = viewport_size.height() / img_size.height()
        scale_factor = min(w_ratio, h_ratio)
        
        # Jangan perbesar gambar kecil, biarkan 100%
        if scale_factor > 1.0:
            scale_factor = 1.0

        fit_zoom_value = int(scale_factor * 100)
        self.zoom_slider.setValue(fit_zoom_value)
        self.update_zoom(fit_zoom_value)

    def show_gallery_view(self):
        self.main_stack.setCurrentIndex(0)
        self.current_viewer_pixmap = None
        self.viewer_label.clear()
        self.viewer_label.unsetCursor()

        # Sembunyikan info & kontrol zoom
        self.image_res_label.hide()
        self.image_file_type_label.hide()
        self.image_size_label.hide()
        self.zoom_slider.parent().hide() # Hide separator
        self.zoom_label.hide()
        self.zoom_slider.hide()

        self.reflow_ui()
        
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
        global_pos = self.grid_container.mapToGlobal(pos)
        widget_at = self.childAt(self.grid_container.mapFromGlobal(global_pos))
        thumb_widget = widget_at
        while thumb_widget and not isinstance(thumb_widget, (ThumbnailWidget, FolderThumbnailWidget)):
            thumb_widget = thumb_widget.parent()

        if not thumb_widget: return

        context_menu = QMenu(self)

        if isinstance(thumb_widget, ThumbnailWidget):
            self.status_label.setText(os.path.basename(thumb_widget.file_path))
            cut_action = context_menu.addAction("Cut")
            cut_action.triggered.connect(lambda: self.file_op_cut(thumb_widget.file_path))
            copy_action = context_menu.addAction("Copy (File Path)")
            copy_action.triggered.connect(lambda: self.file_op_copy(thumb_widget.file_path))
            context_menu.addSeparator()
            file_info_action = context_menu.addAction("File Info")
            file_info_action.triggered.connect(lambda: self.show_file_info(thumb_widget.file_path))
            set_wallpaper_action = context_menu.addAction("Set as Wallpaper")
            set_wallpaper_action.triggered.connect(lambda: self.set_as_wallpaper(thumb_widget.file_path))
        elif isinstance(thumb_widget, FolderThumbnailWidget):
             self.status_label.setText(os.path.basename(thumb_widget.folder_path))
             paste_action = context_menu.addAction("Paste")
             paste_action.setEnabled(bool(self.clipboard_cut_path))
             paste_action.triggered.connect(lambda: self.file_op_paste(thumb_widget.folder_path))
             context_menu.addSeparator()
             remove_action = context_menu.addAction("Remove from list")
             remove_action.triggered.connect(lambda: self.remove_folder_from_gallery(thumb_widget.folder_path))
        
        context_menu.exec(global_pos)

    # --- File Operations & Other Methods ---
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
            QTimer.singleShot(100, self.start_scanning_folders)
        except Exception as e:
            QMessageBox.critical(self, "Paste Error", f"Could not move file:\n{e}")

    def remove_folder_from_gallery(self, folder_path):
        folders = self.settings.value("gallery_folders", [], type=list)
        if folder_path in folders:
            folders.remove(folder_path)
            self.settings.setValue("gallery_folders", folders)
            self.status_label.setText(f"Removed '{os.path.basename(folder_path)}' from gallery.")
            QTimer.singleShot(50, self.start_scanning_folders)

    def show_file_info(self, file_path):
        try:
            stat_info = os.stat(file_path)
            size_bytes = stat_info.st_size
            img = cv2.imread(file_path)
            if img is None: raise IOError()
            h, w, *_ = img.shape
            info_text = (
                f"<b>Filename:</b> {os.path.basename(file_path)}<br>"
                f"<b>Path:</b> {os.path.dirname(file_path)}<br>"
                f"<b>Dimensions:</b> {w} x {h} pixels<br>"
                f"<b>File Size:</b> {get_human_readable_size(size_bytes)} ({size_bytes:,} bytes)"
            )
            QMessageBox.information(self, "File Info", info_text)
        except Exception:
            QMessageBox.critical(self, "Error", f"Could not get file info for:\n{file_path}")
            
    def set_as_wallpaper(self, file_path):
        path = os.path.abspath(file_path)
        system = platform.system()
        try:
            if system == "Windows":
                ctypes.windll.user32.SystemParametersInfoW(20, 0, path, 3)
            elif system == "Darwin":
                subprocess.run(f'osascript -e \'tell application "Finder" to set desktop picture to POSIX file "{path}"\'', shell=True, check=True)
            else:
                # This is a common method for GNOME-based desktops
                subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", f"file://{path}"], check=True)
            self.status_label.setText("Wallpaper set successfully.")
        except Exception as e:
            QMessageBox.critical(self, "Set Wallpaper Error", f"Failed to set wallpaper:\n{e}")

    def update_zoom(self, value):
        if self.current_viewer_pixmap is None:
            return
        
        scale = value / 100.0
        new_size = self.current_viewer_pixmap.size() * scale
        
        scaled_pixmap = self.current_viewer_pixmap.scaled(
            new_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.viewer_label.setPixmap(scaled_pixmap)
        self.viewer_label.adjustSize()
        self.zoom_label.setText(f"{value}%")
        self._update_pan_cursor()

    def zoom_in(self):
        current_val = self.zoom_slider.value()
        self.zoom_slider.setValue(current_val + 10)

    def zoom_out(self):
        current_val = self.zoom_slider.value()
        self.zoom_slider.setValue(current_val - 10)

    def _update_pan_cursor(self):
        """Sets the cursor to a hand if the image is larger than the viewport."""
        if self.current_viewer_pixmap:
            pixmap_size = self.viewer_label.pixmap().size()
            viewport_size = self.viewer_scroll_area.viewport().size()
            if pixmap_size.width() > viewport_size.width() or pixmap_size.height() > viewport_size.height():
                self.viewer_label.setCursor(Qt.CursorShape.OpenHandCursor)
            else:
                self.viewer_label.unsetCursor()
    
    def eventFilter(self, source, event):
        if source is self.viewer_label and self.current_viewer_pixmap:
            # Mulai pan
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                if self.viewer_label.cursor().shape() == Qt.CursorShape.OpenHandCursor:
                    self.is_panning = True
                    self.pan_last_mouse_pos = event.globalPosition().toPoint()
                    self.viewer_label.setCursor(Qt.CursorShape.ClosedHandCursor)
                    return True

            # Selesai pan
            elif event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                if self.is_panning:
                    self.is_panning = False
                    self._update_pan_cursor() # Set cursor kembali ke open hand atau default
                    return True

            # Proses panning (menggeser gambar)
            elif event.type() == QEvent.Type.MouseMove and self.is_panning:
                delta = event.globalPosition().toPoint() - self.pan_last_mouse_pos
                self.pan_last_mouse_pos = event.globalPosition().toPoint()
                
                h_bar = self.viewer_scroll_area.horizontalScrollBar()
                v_bar = self.viewer_scroll_area.verticalScrollBar()
                h_bar.setValue(h_bar.value() - delta.x())
                v_bar.setValue(v_bar.value() - delta.y())
                return True

        return super().eventFilter(source, event)


    # --- Frameless Window Logic ---
    def toggle_maximize_restore(self):
        if self.isMaximized():
            self.showNormal()
            self.maximize_action.setIcon(self._create_svg_icon('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect></svg>'))
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
        self.old_pos = None
        self.is_resizing = False
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
            if self.tool_bar.geometry().contains(event.position().toPoint()):
                self.toggle_maximize_restore()
        super().mouseDoubleClickEvent(event)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, 'resize_timer'):
            self.resize_timer = QTimer()
            self.resize_timer.setSingleShot(True)
            self.resize_timer.timeout.connect(self.reflow_ui)
        self.resize_timer.start(100)
        
        if self.main_stack.currentIndex() == 1 and self.current_viewer_pixmap:
             self.update_zoom(self.zoom_slider.value())
    
    def load_settings(self):
        geometry = self.settings.value("geometry", QByteArray())
        if geometry.size() > 0:
            self.restoreGeometry(geometry)
        else:
            self.setGeometry(100, 100, 1200, 800)
    def save_settings(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("sort_method", self.current_sort_method) # [FITUR BARU] Simpan metode sort
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