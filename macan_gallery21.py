import sys
import os
import cv2
import platform
import subprocess
import hashlib
import shutil
import math
import json
import numpy as np
from functools import partial
from collections import defaultdict

# --- Library Pihak Ketiga (wajib install) ---
from PIL import Image
from PIL.ExifTags import TAGS
from send2trash import send2trash

# --- Core PySide6 Libraries ---
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QScrollArea,
    QVBoxLayout, QHBoxLayout, QFileDialog, QMenu, QStatusBar, QToolBar,
    QSizePolicy, QPushButton, QMessageBox, QToolButton, QDialog,
    QDialogButtonBox, QListWidget, QListWidgetItem, QGridLayout,
    QStackedWidget, QSpacerItem, QFrame, QLineEdit, QSlider,
    QTextEdit, QDockWidget, QCheckBox
)
from PySide6.QtGui import (
    QPixmap, QImage, QAction, QIcon, QKeySequence, QPainter, QCursor, QTransform,
    QColor, QMouseEvent, QDrag, QActionGroup, QFont
)
from PySide6.QtCore import (
    Qt, QSize, QPoint, QRect, QByteArray, QThread, QObject, Signal,
    QSettings, QTimer, QMimeData, QUrl, QEvent
)
from PySide6.QtSvg import QSvgRenderer

if platform.system() == "Windows":
    import ctypes

# --- Constants ---
APP_NAME = "Macan Gallery Pro"
ORGANIZATION_NAME = "DanxExodus"
APP_VERSION = "3.2.0" 
THUMBNAIL_IMAGE_SIZE = QSize(220, 124) 
CACHE_DIR = os.path.join(os.path.expanduser('~'), '.cache', 'MacanGallery', 'thumbnails')
SUPPORTED_IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.bmp', '.webp']
METADATA_SUFFIX = ".meta.json"

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

# --- Metadata (Rating/Label) Management ---
def get_metadata_path(image_path):
    """Mendapatkan path file metadata untuk sebuah gambar."""
    return image_path + METADATA_SUFFIX

def read_metadata(image_path):
    """Membaca metadata dari file .json."""
    meta_path = get_metadata_path(image_path)
    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}

def write_metadata(image_path, data):
    """Menulis atau memperbarui metadata ke file .json."""
    meta_path = get_metadata_path(image_path)
    existing_data = read_metadata(image_path)
    existing_data.update(data)
    with open(meta_path, 'w') as f:
        json.dump(existing_data, f, indent=4)

# --- Worker for Thumbnail Generation ---
class ThumbnailWorker(QObject):
    thumbnail_ready = Signal(str, str)
    finished = Signal()

    def __init__(self, file_paths):
        super().__init__()
        self.file_paths = file_paths
        self.is_running = True

    def run(self):
        os.makedirs(CACHE_DIR, exist_ok=True)
        for path in self.file_paths:
            if not self.is_running:
                break
            path_hash = hashlib.md5(path.encode()).hexdigest()
            cache_path = os.path.join(CACHE_DIR, f"{path_hash}.jpg")
            if os.path.exists(cache_path):
                self.thumbnail_ready.emit(path, cache_path)
                continue
            try:
                img = cv2.imread(path)
                if img is None: continue
                h, w = img.shape[:2]
                target_h, target_w = THUMBNAIL_IMAGE_SIZE.height(), THUMBNAIL_IMAGE_SIZE.width()
                aspect_ratio_img = w / h
                aspect_ratio_target = target_w / target_h
                if aspect_ratio_img > aspect_ratio_target:
                    new_h = target_h
                    new_w = int(aspect_ratio_img * new_h)
                else:
                    new_w = target_w
                    new_h = int(new_w / aspect_ratio_img)
                resized_img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
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
    def __init__(self, file_path, main_window, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.main_window = main_window
        self.metadata = read_metadata(self.file_path)

        self.setFixedSize(220, 180)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("thumbnailCard")
        self.setStyleSheet("""
            #thumbnailCard {
                background-color: #252526; border: 1px solid #333333; border-radius: 8px;
            }
            #thumbnailCard:hover {
                background-color: #333333; border: 1px solid #007ACC;
            }
            QLabel { color: #FFFFFF; border: none; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)

        self.thumbnail_label = QLabel()
        self.thumbnail_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail_label.setStyleSheet("border-radius: 5px; background-color: #1E1E1E;")
        self.thumbnail_label.setFixedSize(210, 118)

        self.update_pixmap()

        title_layout = QHBoxLayout()
        file_name = os.path.splitext(os.path.basename(file_path))[0]
        self.title_label = QLabel(file_name)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.title_label.setWordWrap(True)

        info_layout = QHBoxLayout()
        info_layout.setContentsMargins(5, 0, 5, 0)
        
        # [PERUBAHAN] Checkbox ditambahkan
        self.select_check = QCheckBox()
        self.select_check.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_check.toggled.connect(self.on_selection_changed)
        
        self.rating_label = QLabel()
        self.color_label_indicator = QLabel()
        self.color_label_indicator.setFixedSize(10, 10)
        
        info_layout.addWidget(self.select_check)
        info_layout.addWidget(self.rating_label)
        info_layout.addStretch()
        info_layout.addWidget(self.color_label_indicator)
        self.update_metadata_display()

        layout.addWidget(self.thumbnail_label)
        layout.addWidget(self.title_label)
        layout.addLayout(info_layout)
        layout.addStretch()

    # [PERUBAHAN] Fungsi baru untuk menangani klik checkbox
    def on_selection_changed(self, checked):
        if checked:
            self.main_window.selected_files.add(self.file_path)
        else:
            self.main_window.selected_files.discard(self.file_path)
        self.main_window.update_selection_status()

    def update_metadata_display(self):
        self.metadata = read_metadata(self.file_path)
        rating = self.metadata.get('rating', 0)
        self.rating_label.setText("★" * rating + "☆" * (5 - rating))
        
        # [PERUBAHAN] Warna disesuaikan
        color_map = {"red": "#D16969", "yellow": "#EBCB8B", "green": "#A3BE8C", "blue": "#007ACC"}
        label_color = self.metadata.get('label_color')
        if label_color in color_map:
            self.color_label_indicator.setStyleSheet(f"background-color: {color_map[label_color]}; border-radius: 5px;")
            self.color_label_indicator.setVisible(True)
        else:
            self.color_label_indicator.setVisible(False)

    def update_pixmap(self):
        path_hash = hashlib.md5(self.file_path.encode()).hexdigest()
        cache_path = os.path.join(CACHE_DIR, f"{path_hash}.jpg")
        pixmap = QPixmap(cache_path)
        if pixmap.isNull():
            self.thumbnail_label.setText("...")
        else:
            scaled_pixmap = pixmap.scaled(self.thumbnail_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.thumbnail_label.setPixmap(scaled_pixmap)

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.main_window.show_image_view(self.file_path)
        super().mouseDoubleClickEvent(event)
        
    def mousePressEvent(self, event: QMouseEvent):
        # [PERUBAHAN] Jangan mulai drag jika mengklik checkbox
        if event.button() == Qt.MouseButton.LeftButton:
            if not self.select_check.geometry().contains(event.position().toPoint()):
                self.drag_start_position = event.position().toPoint()
            else:
                self.drag_start_position = None # Reset drag
        super().mousePressEvent(event)
        
    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.MouseButton.LeftButton) or self.drag_start_position is None: return
        if (event.position().toPoint() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance(): return

        drag, mime_data = QDrag(self), QMimeData()

        # [MODIFIKASI] Cek apakah file ini bagian dari seleksi
        selected_files_list = list(self.main_window.selected_files)

        if self.file_path in selected_files_list and len(selected_files_list) > 0:
            # Jika ya, siapkan SEMUA file yang terseleksi untuk di-drag
            urls = [QUrl.fromLocalFile(path) for path in selected_files_list]
            mime_data.setUrls(urls)

            # [TAMBAHAN] Buat pixmap preview kustom untuk multi-drag
            preview_pixmap = self.create_multi_drag_pixmap(selected_files_list)
            drag.setPixmap(preview_pixmap)

        else:
            # Logika lama: hanya drag satu file ini
            url = QUrl.fromLocalFile(self.file_path)
            mime_data.setUrls([url])
            pixmap = self.thumbnail_label.pixmap()
            if pixmap: drag.setPixmap(pixmap.scaled(QSize(120, 68), Qt.AspectRatioMode.KeepAspectRatio))

        drag.setMimeData(mime_data)
        drag.exec(Qt.DropAction.CopyAction)

    # [TAMBAHAN] Fungsi baru di dalam class ThumbnailWidget
    def create_multi_drag_pixmap(self, files_list):
        """Membuat pixmap preview untuk multi-drag."""
        count = len(files_list)
        base_pixmap = self.thumbnail_label.pixmap()
        if base_pixmap.isNull():
            base_pixmap = QPixmap(120, 68)
            base_pixmap.fill(QColor("#333333"))
        else:
            base_pixmap = base_pixmap.scaled(QSize(120, 68), Qt.AspectRatioMode.KeepAspectRatio)

        # Buat pixmap baru untuk menampung badge
        final_pixmap = QPixmap(base_pixmap.size())
        final_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(final_pixmap)
        painter.drawPixmap(0, 0, base_pixmap)
        
        # Gambar badge jumlah
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        painter.setFont(font)
        
        badge_rect = QRect(final_pixmap.width() - 28, 5, 24, 24)
        painter.setBrush(QColor("#007ACC"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(badge_rect)
        
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, f"{count}")
        
        painter.end()
        return final_pixmap

class FolderThumbnailWidget(QFrame):
    def __init__(self, folder_path, image_paths, main_window, parent=None):
        super().__init__(parent)
        self.folder_path, self.image_paths, self.main_window = folder_path, image_paths, main_window
        self.setFixedSize(220, 180)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("thumbnailCard")
        # [PERUBAHAN] Stylesheet diubah ke hitam
        self.setStyleSheet("""
            #thumbnailCard { background-color: #252526; border: 1px solid #333333; border-radius: 8px; }
            #thumbnailCard:hover { background-color: #333333; border: 1px solid #007ACC; }
            QLabel { color: #FFFFFF; border: none; }
        """)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        thumbnail_container = QWidget()
        thumbnail_container.setFixedSize(210, 118)
        thumbnail_container.setStyleSheet("border-radius: 5px; background-color: #1E1E1E;")
        grid_layout = QGridLayout(thumbnail_container)
        grid_layout.setContentsMargins(2, 2, 2, 2)
        grid_layout.setSpacing(2)
        images_to_preview, positions = self.image_paths[:4], [(0, 0), (0, 1), (1, 0), (1, 1)]
        for i, path in enumerate(images_to_preview):
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
        folder_name, item_count = os.path.basename(self.folder_path), len(self.image_paths)
        self.title_label = QLabel(f"{folder_name}\n({item_count} items)")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.title_label.setWordWrap(True)
        main_layout.addWidget(thumbnail_container)
        main_layout.addWidget(self.title_label)
    def mouseDoubleClickEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton: self.main_window.show_folder_contents(self.folder_path)
        super().mouseDoubleClickEvent(event)
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton: self.drag_start_position = event.position().toPoint()
        super().mousePressEvent(event)
    def mouseMoveEvent(self, event: QMouseEvent):
        if not (event.buttons() & Qt.MouseButton.LeftButton): return
        if (event.position().toPoint() - self.drag_start_position).manhattanLength() < QApplication.startDragDistance(): return
        drag, mime_data = QDrag(self), QMimeData()
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
        # [PERUBAHAN] Stylesheet diubah ke hitam
        self.setStyleSheet("""
            QDialog { background-color: #1E1E1E; color: #FFFFFF; }
            QListWidget { background-color: #252526; border: 1px solid #444444; color: #FFFFFF; }
            QLabel { font-size: 11pt; }
            QPushButton { background-color: #007ACC; color: #FFFFFF; border: none; padding: 5px 10px; border-radius: 4px; }
            QPushButton:hover { background-color: #0090F0; }
            QPushButton#clearCacheButton { background-color: #D16969; }
            QPushButton#clearCacheButton:hover { background-color: #E09070; }
        """)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(QLabel("<b>Gallery Folders:</b>"))
        self.folder_list_widget = QListWidget()
        self.load_folders()
        main_layout.addWidget(self.folder_list_widget)
        folder_buttons_layout = QHBoxLayout()
        add_folder_btn, remove_folder_btn = QPushButton("Add Folder..."), QPushButton("Remove Selected")
        add_folder_btn.clicked.connect(self.add_folder)
        remove_folder_btn.clicked.connect(self.remove_folder)
        folder_buttons_layout.addWidget(add_folder_btn), folder_buttons_layout.addWidget(remove_folder_btn), folder_buttons_layout.addStretch()
        main_layout.addLayout(folder_buttons_layout), main_layout.addSpacing(20)
        main_layout.addWidget(QLabel("<b>Thumbnail Cache:</b>"))
        self.cache_info_label = QLabel("Calculating cache size...")
        main_layout.addWidget(self.cache_info_label)
        clear_cache_btn = QPushButton("Clear Cache")
        clear_cache_btn.setObjectName("clearCacheButton"), clear_cache_btn.clicked.connect(self.clear_cache)
        cache_layout = QHBoxLayout()
        cache_layout.addWidget(clear_cache_btn), cache_layout.addStretch()
        main_layout.addLayout(cache_layout), main_layout.addStretch()
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        button_box.accepted.connect(self.accept), button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
        self.update_cache_info()
    def load_folders(self): self.folder_list_widget.addItems(self.settings.value("gallery_folders", [], type=list))
    def add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder to Add to Gallery")
        if folder:
            items = [self.folder_list_widget.item(i).text() for i in range(self.folder_list_widget.count())]
            if folder not in items: self.folder_list_widget.addItem(folder)
    def remove_folder(self):
        selected_items = self.folder_list_widget.selectedItems()
        if not selected_items: return
        for item in selected_items: self.folder_list_widget.takeItem(self.folder_list_widget.row(item))
    def update_cache_info(self):
        try:
            if not os.path.exists(CACHE_DIR):
                self.cache_info_label.setText(f"Location: {CACHE_DIR}\nCache is empty.")
                return
            total_size = sum(os.path.getsize(os.path.join(CACHE_DIR, f)) for f in os.listdir(CACHE_DIR) if os.path.isfile(os.path.join(CACHE_DIR, f)))
            file_count = len(os.listdir(CACHE_DIR))
            self.cache_info_label.setText(f"Location: {CACHE_DIR}\nSize: {get_human_readable_size(total_size)} ({file_count} files)")
        except Exception as e: self.cache_info_label.setText(f"Could not read cache info: {e}")
    def clear_cache(self):
        reply = QMessageBox.question(self, "Confirm Clear Cache", "Are you sure you want to delete all cached thumbnails?\nThey will be regenerated when you next open the gallery.", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                if os.path.exists(CACHE_DIR):
                    shutil.rmtree(CACHE_DIR)
                    os.makedirs(CACHE_DIR, exist_ok=True)
                QMessageBox.information(self, "Success", "Thumbnail cache cleared successfully.")
                self.update_cache_info()
            except Exception as e: QMessageBox.critical(self, "Error", f"Failed to clear cache: {e}")
    def accept(self):
        folders = [self.folder_list_widget.item(i).text() for i in range(self.folder_list_widget.count())]
        self.settings.setValue("gallery_folders", folders)
        super().accept()

# --- Main Application Window ---
class MacanGallery(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings(ORGANIZATION_NAME, APP_NAME)
        self.clipboard_cut_path, self.thumbnail_thread, self.thumbnail_worker = None, None, None
        self.grouped_images, self.thumbnail_widgets = {}, {}
        self.current_view, self.selected_folder = 'folders', None
        self.current_viewer_pixmap = None
        self.original_pixmap_for_editing = None 
        self.original_cv_image = None 
        self.current_image_path, self.current_image_list, self.current_image_index = None, [], -1
        self.current_sort_method = self.settings.value("sort_method", "name_asc")
        self.current_filter_method = "filter_all"
        self.is_panning = False
        self.pan_last_mouse_pos = QPoint()
        self.slideshow_timer = QTimer(self)
        self.slideshow_timer.timeout.connect(self.show_next_image)
        
        # [PERUBAHAN] Set untuk melacak file yang dipilih
        self.selected_files = set()

        self.current_edits = {'brightness': 0, 'contrast': 1.0, 'saturation': 1.0}

        self.init_ui()
        self.load_settings()
        QTimer.singleShot(100, self.start_scanning_folders)

    def init_ui(self):
        self.setWindowTitle(APP_NAME)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setMinimumSize(800, 600)
        self.setMouseTracking(True)
        icon_path = "macan_gallery.ico"
        if hasattr(sys, "_MEIPASS"): icon_path = os.path.join(sys._MEIPASS, icon_path)
        if os.path.exists(icon_path): self.setWindowIcon(QIcon(icon_path))
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
        self.back_button.setFixedWidth(180) # [PERUBAHAN] Ukuran tombol diperkecil
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
        viewer_main_layout = QHBoxLayout(viewer_widget)
        viewer_main_layout.setContentsMargins(0, 5, 0, 0)
        viewer_main_layout.setSpacing(5)

        viewer_content_widget = QWidget()
        viewer_layout = QVBoxLayout(viewer_content_widget)
        viewer_layout.setContentsMargins(0,0,0,0)
        viewer_layout.setSpacing(5)

        self.viewer_label = QLabel()
        self.viewer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.viewer_label.setMouseTracking(True)
        self.viewer_label.installEventFilter(self)
        self.viewer_scroll_area = QScrollArea()
        self.viewer_scroll_area.setWidget(self.viewer_label)
        self.viewer_scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.viewer_scroll_area.setWidgetResizable(True)
        self.viewer_scroll_area.setStyleSheet("border: none;")
        self.create_viewer_toolbar() 
        viewer_back_button = QPushButton("◄ Back to Gallery")
        viewer_back_button.clicked.connect(self.show_gallery_view)
        viewer_back_button.setFixedWidth(130) # [PERUBAHAN] Ukuran tombol diperkecil
        viewer_top_layout = QHBoxLayout()
        viewer_top_layout.setContentsMargins(10, 0, 10, 0)
        viewer_top_layout.addWidget(viewer_back_button)
        viewer_top_layout.addWidget(self.viewer_toolbar)
        viewer_top_layout.addStretch()
        viewer_layout.addLayout(viewer_top_layout)
        self.image_container = QWidget()
        image_container_layout = QHBoxLayout(self.image_container)
        image_container_layout.setContentsMargins(0, 0, 0, 0)
        image_container_layout.addWidget(self.viewer_scroll_area)
        
        prev_svg = '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>'
        next_svg = '<svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>'
        self.prev_button, self.next_button = QPushButton(self.image_container), QPushButton(self.image_container)
        
        # [PERUBAHAN] Ukuran tombol navigasi diperkecil
        self.prev_button.setIcon(self._create_svg_icon(prev_svg)), self.prev_button.setIconSize(QSize(24, 24)), self.prev_button.setFixedSize(40, 40)
        self.prev_button.setObjectName("navButton"), self.prev_button.setCursor(Qt.CursorShape.PointingHandCursor), self.prev_button.setVisible(False)
        self.prev_button.clicked.connect(self.show_previous_image)
        self.next_button.setIcon(self._create_svg_icon(next_svg)), self.next_button.setIconSize(QSize(24, 24)), self.next_button.setFixedSize(40, 40)
        self.next_button.setObjectName("navButton"), self.next_button.setCursor(Qt.CursorShape.PointingHandCursor), self.next_button.setVisible(False)
        self.next_button.clicked.connect(self.show_next_image)
        
        viewer_layout.addWidget(self.image_container)
        viewer_main_layout.addWidget(viewer_content_widget)

        self.main_stack.addWidget(viewer_widget)

        self._create_info_dock_widget()

        self.create_actions()
        self.create_tool_bar()
        self.create_status_bar()
        self.grid_container.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.grid_container.customContextMenuRequested.connect(self.show_context_menu)
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.reflow_ui)

    def apply_stylesheet(self):
        # [PERUBAHAN] Stylesheet diubah ke hitam, padding tombol diperkecil
        self.setStyleSheet("""
            QMainWindow { background-color: #1E1E1E; }
            QDockWidget { background-color: #252526; color: #FFFFFF; }
            
            /* [PERUBAHAN] Ditambahkan color: #FFFFFF; untuk title dock */
            QDockWidget::title { text-align: center; background: #333333; padding: 5px; color: #FFFFFF; }
            
            /* [PERUBAHAN] Ditambahkan untuk memastikan label di dalam dock berwarna putih */
            QDockWidget QLabel { color: #FFFFFF; }
            
            QTextEdit { background-color: #1E1E1E; color: #FFFFFF; border: 1px solid #444444; font-family: Monospace; }
            QToolBar { background-color: #252526; border: none; padding: 5px; border-bottom: 1px solid #333333; }
            QToolBar#viewerToolbar { border: none; }
            QToolBar QToolButton { background-color: transparent; color: #FFFFFF; border: none; padding: 5px; margin: 0 2px; font-weight: bold; }
            QToolBar QToolButton:hover { background-color: #444444; border-radius: 3px; }
            QToolBar QToolButton#close_button:hover { background-color: #D16969; }
            QLineEdit { background-color: #1E1E1E; color: #FFFFFF; border: 1px solid #444444; border-radius: 4px; padding: 4px 8px; }
            QMenu { background-color: #252526; color: #FFFFFF; border: 1px solid #444444; }
            QMenu::item:selected { background-color: #007ACC; }
            QStatusBar { background-color: #252526; color: #FFFFFF; border-top: 1px solid #333333; }
            QStatusBar::item { border: none; }
            QStatusBar QLabel { color: #FFFFFF; }
            QSlider::groove:horizontal { border: 1px solid #444444; background: #1E1E1E; height: 4px; border-radius: 2px; }
            QSlider::handle:horizontal { background: #007ACC; border: 1px solid #007ACC; width: 14px; margin: -5px 0; border-radius: 7px; }
            QScrollArea { border: none; background-color: #1E1E1E; }
            QPushButton { background-color: #007ACC; color: #FFFFFF; border: none; padding: 5px 10px; border-radius: 4px; }
            QPushButton:hover { background-color: #0090F0; }
            QPushButton#navButton { background-color: rgba(30, 30, 30, 0.6); border: 1px solid #444444; border-radius: 20px; }
            QPushButton#navButton:hover { background-color: rgba(50, 50, 50, 0.8); }
            QCheckBox { color: #FFFFFF; spacing: 5px; }
            QCheckBox::indicator {
                border: 1px solid #555555;
                background-color: #252526;
                width: 14px;
                height: 14px;
                border-radius: 3px;
            }
            QCheckBox::indicator:hover {
                border: 1px solid #007ACC;
            }
            QCheckBox::indicator:checked {
                background-color: #007ACC;
                border: 1px solid #007ACC;
            }
        """)

    def _create_svg_icon(self, svg_xml, color="#FFFFFF"): # [PERUBAHAN] Warna default ke putih
        renderer = QSvgRenderer(QByteArray(svg_xml.replace('currentColor', color).encode('utf-8')))
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter), painter.end()
        return QIcon(pixmap)

    def create_actions(self):
        self.manage_action = QAction("Manage Folders", self, triggered=self.open_manage_dialog)
        self.refresh_action = QAction("Refresh", self, triggered=self.start_scanning_folders)
        self.about_action = QAction("About", self, triggered=self.show_about_dialog)
        self.exit_action = QAction("Exit", self, triggered=self.close)        
        self.zoom_in_action = QAction("Zoom In", self, shortcuts=[QKeySequence.StandardKey.ZoomIn, QKeySequence("+")], triggered=self.zoom_in)
        self.zoom_out_action = QAction("Zoom Out", self, shortcuts=[QKeySequence.StandardKey.ZoomOut, QKeySequence("-")], triggered=self.zoom_out)
        self.next_image_action = QAction("Next Image", self, shortcut=QKeySequence(Qt.Key.Key_Right), triggered=self.show_next_image)
        self.prev_image_action = QAction("Previous Image", self, shortcut=QKeySequence(Qt.Key.Key_Left), triggered=self.show_previous_image)
        self.fullscreen_action = QAction("Fullscreen", self, shortcut=QKeySequence(Qt.Key.Key_F11), triggered=self.toggle_fullscreen)
        self.addActions([self.zoom_in_action, self.zoom_out_action, self.next_image_action, self.prev_image_action, self.fullscreen_action])
        # [TAMBAHAN] Aksi untuk Select All (CTRL+A)
        self.select_all_shortcut_action = QAction("Select All", self)
        self.select_all_shortcut_action.setShortcut(QKeySequence.StandardKey.SelectAll)
        self.select_all_shortcut_action.triggered.connect(self.select_all_visible_shortcut)
        # [MODIFIKASI] Tambahkan aksi baru ke self.addActions
        self.addActions([self.zoom_in_action, self.zoom_out_action, self.next_image_action, 
                         self.prev_image_action, self.fullscreen_action, self.select_all_shortcut_action])

    def create_tool_bar(self):
        self.tool_bar = QToolBar("Main Toolbar")
        self.tool_bar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self.tool_bar)
        
        manage_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>'
        refresh_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>'
        sort_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>'
        filter_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon></svg>'

        self.manage_action.setIcon(self._create_svg_icon(manage_svg))
        self.refresh_action.setIcon(self._create_svg_icon(refresh_svg))

        file_menu_button = QToolButton(self)
        file_menu_button.setText("File"), file_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        file_menu = QMenu(self)
        file_menu.addAction(self.manage_action), file_menu.addAction(self.refresh_action), file_menu.addSeparator()
        file_menu.addAction(self.about_action), file_menu.addSeparator(), file_menu.addAction(self.exit_action)
        file_menu_button.setMenu(file_menu)
        self.tool_bar.addWidget(file_menu_button)
        
        sort_button = QToolButton(self)
        sort_button.setIcon(self._create_svg_icon(sort_svg)), sort_button.setText("Sort By"), sort_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        sort_menu, sort_group = QMenu(self), QActionGroup(self)
        sort_group.setExclusive(True)
        sort_actions = {"Name (A-Z)": "name_asc", "Name (Z-A)": "name_desc", "Date (Newest First)": "date_new", "Date (Oldest First)": "date_old", "Size (Largest First)": "size_large", "Size (Smallest First)": "size_small"}
        for text, data in sort_actions.items():
            action = QAction(text, self, checkable=True, data=data)
            if self.current_sort_method == data: action.setChecked(True)
            sort_menu.addAction(action), sort_group.addAction(action)
        sort_group.triggered.connect(self.set_sort_method)
        sort_button.setMenu(sort_menu), self.tool_bar.addWidget(sort_button)

        filter_button = QToolButton(self)
        filter_button.setIcon(self._create_svg_icon(filter_svg)), filter_button.setText("Filter"), filter_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        filter_menu, filter_group = QMenu(self), QActionGroup(self)
        filter_group.setExclusive(True)
        filter_actions = { "Show All": "filter_all", "No Rating": "filter_rating_0" }
        for i in range(1, 6): filter_actions[f"★ {i} Star"+("s" if i>1 else "")]= f"filter_rating_{i}"
        filter_menu.addSeparator()
        filter_actions.update({"Red Label": "filter_color_red", "Yellow Label": "filter_color_yellow", "Green Label": "filter_color_green", "Blue Label": "filter_color_blue", "No Label": "filter_color_none"})
        for text, data in filter_actions.items():
             action = QAction(text, self, checkable=True, data=data)
             if self.current_filter_method == data: action.setChecked(True)
             filter_menu.addAction(action), filter_group.addAction(action)
        filter_group.triggered.connect(self.set_filter_method)
        filter_button.setMenu(filter_menu), self.tool_bar.addWidget(filter_button)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search items..."), self.search_bar.setMaximumWidth(300)
        self.search_bar.textChanged.connect(lambda: self.search_timer.start(300))
        self.tool_bar.addWidget(self.search_bar)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.tool_bar.addWidget(spacer)
        
        minimize_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 12 L20 12"></path></svg>'
        maximize_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect></svg>'
        self.restore_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3"></path></svg>'
        close_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 6 L18 18 M18 6 L6 18"></path></svg>'
        self.minimize_action = QAction(self._create_svg_icon(minimize_svg), "Minimize", self, triggered=self.showMinimized)
        self.maximize_action = QAction(self._create_svg_icon(maximize_svg), "Maximize", self, triggered=self.toggle_maximize_restore)
        self.close_action = QAction(self._create_svg_icon(close_svg), "Close", self, objectName="close_button", triggered=self.close)
        self.tool_bar.addAction(self.minimize_action), self.tool_bar.addAction(self.maximize_action), self.tool_bar.addAction(self.close_action)

    def create_viewer_toolbar(self):
        self.viewer_toolbar = QToolBar("Image Viewer Toolbar")
        self.viewer_toolbar.setObjectName("viewerToolbar")
        self.viewer_toolbar.setIconSize(QSize(24, 24))

        icon_color = "#f0f0f0"
        rot_left_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2.5 2v6h6M2.66 15.57a10 10 0 1 0 .57-8.38"/></svg>'
        rot_right_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38"/></svg>'
        flip_v_svg = f'<svg viewBox="0 0 24 24"><path fill="{icon_color}" d="M15 21h2v-2h-2v2zm4-12h2V7h-2v2zM3 5v14c0 1.1.9 2 2 2h4v-2H5V5h4V3H5c-1.1 0-2 .9-2 2zm16-2v2h2c0-1.1-.9-2-2-2zm-8 20h2V1h-2v22zm8-6h2v-2h-2v2zm-4 0h2v-2h-2v2zm4-4h2v-2h-2v2zm-12 4h2v-2H7v2z"/></svg>'
        flip_h_svg = f'<svg viewBox="0 0 24 24" transform="rotate(90 12 12)"><path fill="{icon_color}" d="M15 21h2v-2h-2v2zm4-12h2V7h-2v2zM3 5v14c0 1.1.9 2 2 2h4v-2H5V5h4V3H5c-1.1 0-2 .9-2 2zm16-2v2h2c0-1.1-.9-2-2-2zm-8 20h2V1h-2v22zm8-6h2v-2h-2v2zm-4 0h2v-2h-2v2zm4-4h2v-2h-2v2zm-12 4h2v-2H7v2z"/></svg>'
        trash_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path><line x1="10" y1="11" x2="10" y2="17"></line><line x1="14" y1="11" x2="14" y2="17"></line></svg>'
        info_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>'
        self.play_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 4.5v15l13.5-7.5L5 4.5z"/></svg>'
        self.pause_svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>'

        self.rotate_left_action = QAction(self._create_svg_icon(rot_left_svg), "Rotate Left (90°)", self, triggered=lambda: self.rotate_image(-90))
        self.rotate_right_action = QAction(self._create_svg_icon(rot_right_svg), "Rotate Right (90°)", self, triggered=lambda: self.rotate_image(90))
        self.flip_h_action = QAction(self._create_svg_icon(flip_h_svg), "Flip Horizontal", self, triggered=lambda: self.flip_image('h'))
        self.flip_v_action = QAction(self._create_svg_icon(flip_v_svg), "Flip Vertical", self, triggered=lambda: self.flip_image('v'))
        self.delete_action = QAction(self._create_svg_icon(trash_svg), "Delete Image (Move to Trash)", self, shortcut=QKeySequence.StandardKey.Delete, triggered=self.delete_current_image)
        self.toggle_info_action = QAction(self._create_svg_icon(info_svg), "Toggle Info Panel", self, checkable=True, triggered=self.toggle_info_panel)
        # [PERUBAHAN] Buat dan simpan kedua icon
        self.play_icon = self._create_svg_icon(self.play_svg)
        self.pause_icon = self._create_svg_icon(self.pause_svg)
        
        # [PERUBAHAN] Gunakan play_icon saat membuat action
        self.slideshow_action = QAction(self.play_icon, "Start/Stop Slideshow (3s)", self, checkable=True, triggered=self.toggle_slideshow)
        
        self.addActions([self.delete_action])

        self.viewer_toolbar.addAction(self.rotate_left_action)
        self.viewer_toolbar.addAction(self.rotate_right_action)
        self.viewer_toolbar.addAction(self.flip_h_action)
        self.viewer_toolbar.addAction(self.flip_v_action)
        self.viewer_toolbar.addSeparator()
        self.viewer_toolbar.addAction(self.delete_action)
        self.viewer_toolbar.addSeparator()
        self.viewer_toolbar.addAction(self.slideshow_action)
        
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.viewer_toolbar.addWidget(spacer)
        
        self.viewer_toolbar.addAction(self.toggle_info_action)

    def set_sort_method(self, action):
        self.current_sort_method = action.data()
        self.settings.setValue("sort_method", self.current_sort_method)
        self.reflow_ui()

    def set_filter_method(self, action):
        self.current_filter_method = action.data()
        self.settings.setValue("filter_method", self.current_filter_method)
        self.reflow_ui()

    def create_status_bar(self):
        self.statusbar = self.statusBar()
        self.status_label = QLabel("Ready")
        self.statusbar.addWidget(self.status_label, 1)
        self.image_res_label, self.image_file_type_label, self.image_size_label = QLabel(), QLabel(), QLabel()
        self.statusbar.addPermanentWidget(self.image_res_label)
        self.statusbar.addPermanentWidget(self.image_file_type_label)
        self.statusbar.addPermanentWidget(self.image_size_label)
        self.image_res_label.hide(), self.image_file_type_label.hide(), self.image_size_label.hide()
        separator, self.zoom_label = QLabel(" | "), QLabel("100%")
        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setRange(10, 400), self.zoom_slider.setValue(100)
        self.zoom_slider.setFixedWidth(150), self.zoom_slider.valueChanged.connect(self.update_zoom)
        self.statusbar.addPermanentWidget(separator), self.statusbar.addPermanentWidget(self.zoom_label), self.statusbar.addPermanentWidget(self.zoom_slider)
        separator.hide(), self.zoom_label.hide(), self.zoom_slider.hide()
        self.file_count_label = QLabel("")
        self.statusbar.addPermanentWidget(self.file_count_label)

    # [PERUBAHAN] Fungsi baru untuk update status seleksi
    def update_selection_status(self):
        count = len(self.selected_files)
        if self.current_view == 'images':
            if count == 0:
                self.status_label.setText("Ready")
            else:
                self.status_label.setText(f"{count} item{'s' if count > 1 else ''} selected")
        else:
            # Reset status jika tidak di image view
            if self.status_label.text().endswith("selected"):
                self.status_label.setText("Ready")
        
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
            self.status_label.setText(f"Scanning {base_folder}..."), QApplication.processEvents()
            try:
                for dirpath, _, filenames in os.walk(base_folder):
                    images_in_current_folder = []
                    for filename in filenames:
                        _, ext = os.path.splitext(filename)
                        if ext.lower() in SUPPORTED_IMAGE_EXTENSIONS:
                            images_in_current_folder.append(os.path.join(dirpath, filename))
                    if images_in_current_folder:
                        self.grouped_images[dirpath] = sorted(images_in_current_folder)
                        all_image_paths.extend(images_in_current_folder)
            except Exception as e: print(f"Could not scan folder {base_folder}: {e}")
        self.file_count_label.setText(f"{len(self.grouped_images)} folders, {len(all_image_paths)} images")
        self.status_label.setText("Generating thumbnails in background...")
        self.show_folders_view() 
        self.thumbnail_thread, self.thumbnail_worker = QThread(), ThumbnailWorker(all_image_paths)
        self.thumbnail_worker.moveToThread(self.thumbnail_thread)
        self.thumbnail_worker.thumbnail_ready.connect(self.update_thumbnail_widget)
        self.thumbnail_worker.finished.connect(self.on_thumbnailing_finished)
        self.thumbnail_thread.started.connect(self.thumbnail_worker.run), self.thumbnail_thread.start()

    def update_thumbnail_widget(self, original_path, cache_path):
        if original_path in self.thumbnail_widgets:
            widget = self.thumbnail_widgets[original_path]
            widget.update_pixmap()
            widget.update_metadata_display()
            
    def on_thumbnailing_finished(self):
        self.status_label.setText("Ready")
        self.update_selection_status() # Pastikan status selection benar
        if self.thumbnail_thread:
            self.thumbnail_thread.quit(), self.thumbnail_thread.wait()

    def reflow_ui(self):
        while self.grid_layout.count():
            child = self.grid_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        self.thumbnail_widgets.clear()
        columns, search_term = max(1, (self.scroll_area.width() - 30) // 240), self.search_bar.text().lower()
        if self.current_view == 'folders':
            self.back_button.setVisible(False)
            folder_paths = sorted(self.grouped_images.keys())
            if self.current_sort_method == "name_desc": folder_paths.reverse()
            if search_term: folder_paths = [f for f in folder_paths if search_term in os.path.basename(f).lower()]
            row, col = 0, 0
            for folder_path in folder_paths:
                image_paths = self.grouped_images[folder_path]
                if not image_paths: continue
                folder_widget = FolderThumbnailWidget(folder_path, image_paths, self)
                self.grid_layout.addWidget(folder_widget, row, col)
                col += 1
                if col >= columns: col, row = 0, row + 1
        elif self.current_view == 'images' and self.selected_folder:
            self.back_button.setVisible(True)
            image_paths = self._get_filtered_and_sorted_list()
        
            if search_term:
                filtered_by_search = []
                for p in image_paths:
                    if search_term in os.path.basename(p).lower():
                        filtered_by_search.append(p)
                        continue
                    metadata = read_metadata(p)
                    tags = metadata.get('tags', [])
                    if any(search_term in tag.lower() for tag in tags):
                        filtered_by_search.append(p)
                image_paths = filtered_by_search
            
            row, col = 0, 0
            for path in image_paths:
                thumb_widget = ThumbnailWidget(path, self)
                
                # [PERUBAHAN] Set status checkbox sesuai data seleksi
                if path in self.selected_files:
                    thumb_widget.select_check.blockSignals(True)
                    thumb_widget.select_check.setChecked(True)
                    thumb_widget.select_check.blockSignals(False)
                    
                self.thumbnail_widgets[path] = thumb_widget
                self.grid_layout.addWidget(thumb_widget, row, col)
                col += 1
                if col >= columns: col, row = 0, row + 1
        self.grid_layout.addItem(QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding), self.grid_layout.rowCount(), 0, 1, -1)
        self.update_selection_status() # Update status setelah reflow

    def _get_filtered_and_sorted_list(self):
        image_paths = self._get_sorted_image_list()
        if self.current_filter_method == 'filter_all' or not self.current_filter_method:
            return image_paths
        
        filtered_paths = []
        filter_type, _, filter_value = self.current_filter_method.partition('_')
        
        for path in image_paths:
            metadata = read_metadata(path)
            if filter_type == 'filter' and filter_value.startswith('rating'):
                rating = metadata.get('rating', 0)
                if str(rating) == filter_value.split('_')[1]:
                    filtered_paths.append(path)
            elif filter_type == 'filter' and filter_value.startswith('color'):
                color = metadata.get('label_color', 'none')
                if color == filter_value.split('_')[1]:
                    filtered_paths.append(path)

        return filtered_paths

    def _get_sorted_image_list(self):
        if not self.selected_folder: return []
        image_paths = self.grouped_images.get(self.selected_folder, []).copy()
        try:
            if self.current_sort_method == 'name_asc': image_paths.sort()
            elif self.current_sort_method == 'name_desc': image_paths.sort(reverse=True)
            elif self.current_sort_method == 'date_new': image_paths.sort(key=os.path.getmtime, reverse=True)
            elif self.current_sort_method == 'date_old': image_paths.sort(key=os.path.getmtime)
            elif self.current_sort_method == 'size_large': image_paths.sort(key=os.path.getsize, reverse=True)
            elif self.current_sort_method == 'size_small': image_paths.sort(key=os.path.getsize)
        except FileNotFoundError:
            print("Warning: Some files could not be found during sorting.")
            image_paths = [p for p in image_paths if os.path.exists(p)]
        return image_paths

    def show_folder_contents(self, folder_path):
        self.current_view, self.selected_folder = 'images', folder_path
        self.search_bar.clear()
        self.scroll_area.verticalScrollBar().setValue(0)
        # [PERUBAHAN] Kosongkan seleksi saat ganti folder
        self.selected_files.clear()
        self.reflow_ui()
        
    def show_folders_view(self):
        self.current_view, self.selected_folder = 'folders', None
        self.search_bar.clear()
        self.scroll_area.verticalScrollBar().setValue(0)
        # [PERUBAHAN] Kosongkan seleksi saat kembali ke folder
        self.selected_files.clear()
        self.reflow_ui()

    def show_image_view(self, path, reload_from_disk=True):
        if reload_from_disk:
            self.current_image_list = self._get_filtered_and_sorted_list()
            if path in self.current_image_list:
                self.current_image_index = self.current_image_list.index(path)
            else:
                self.current_image_list, self.current_image_index = [path], 0
            self.current_image_path = path

        try:
            # --- [PERBAIKAN LOGIKA] ---
            # Hanya baca metadata dan set slider saat gambar pertama kali dimuat.
            # Jangan lakukan ini saat live preview (reload_from_disk=False).
            if reload_from_disk:
                metadata = read_metadata(self.current_image_path)
                edits = metadata.get('edits', {})
                self.current_edits = {
                    'brightness': edits.get('brightness', 0),
                    'contrast': edits.get('contrast', 1.0),
                    'saturation': edits.get('saturation', 1.0)
                }
                
                # Update posisi slider agar sesuai dengan data yang tersimpan
                self.brightness_slider.blockSignals(True)
                self.contrast_slider.blockSignals(True)
                self.saturation_slider.blockSignals(True)
                self.brightness_slider.setValue(self.current_edits['brightness'])
                self.contrast_slider.setValue(int(self.current_edits['contrast'] * 100))
                self.saturation_slider.setValue(int(self.current_edits['saturation'] * 100))
                self.brightness_slider.blockSignals(False)
                self.contrast_slider.blockSignals(False)
                self.saturation_slider.blockSignals(False)

                # Muat gambar asli dari disk dan simpan ke memori
                cv_image = cv2.imread(self.current_image_path, cv2.IMREAD_COLOR) 
                if cv_image is None: raise Exception("OpenCV failed to open the image file.")
                self.original_cv_image = cv_image
        
            # Terapkan penyesuaian (baik yang tersimpan atau yang live) ke gambar asli
            edited_image = self.apply_image_edits(self.original_cv_image, self.current_edits)
        
            h_orig, w_orig, *_ = edited_image.shape
            bytes_per_line = 3 * w_orig
            
            qt_image = QImage(edited_image.data, w_orig, h_orig, bytes_per_line, QImage.Format.Format_BGR888)

            if qt_image.isNull(): raise Exception("Failed to convert the OpenCV image to a QImage.")
            
            pixmap = QPixmap.fromImage(qt_image)
            
            if reload_from_disk:
                self.original_pixmap_for_editing = pixmap.copy()

            self.current_viewer_pixmap = pixmap
            
            size_bytes, file_ext = os.path.getsize(path), os.path.splitext(path)[1].upper().replace('.', '')
            self.image_res_label.setText(f"{w_orig}x{h_orig}")
            self.image_file_type_label.setText(f"{file_ext} Image"), self.image_size_label.setText(get_human_readable_size(size_bytes))
            self.image_res_label.show(), self.image_file_type_label.show(), self.image_size_label.show()
            self.prev_button.setVisible(True), self.next_button.setVisible(True)
            self.zoom_slider.parent().show(), self.zoom_label.show(), self.zoom_slider.show()
            self.viewer_label.setPixmap(QPixmap())
            self.main_stack.setCurrentIndex(1)
            self.toggle_info_action.setChecked(self.metadata_dock.isVisible())
            self.load_exif_data(path)
            self.update_tag_display()
            if reload_from_disk:
                QTimer.singleShot(0, self.fit_image_to_window)
            else:
                self.update_zoom(self.zoom_slider.value())
            QTimer.singleShot(0, self._update_nav_buttons_position)
        except Exception as e:
            QMessageBox.critical(self, "Error Opening Image", f"Could not open image:\n{path}\n\nReason: {e}")

    def fit_image_to_window(self):
        if self.current_viewer_pixmap is None: return
        img_size, viewport_size = self.current_viewer_pixmap.size(), self.viewer_scroll_area.viewport().size()
        if img_size.width() <= 0 or img_size.height() <= 0: return
        scale_factor = min(viewport_size.width() / img_size.width(), viewport_size.height() / img_size.height())
        if scale_factor > 1.0: scale_factor = 1.0
        fit_zoom_value = int(scale_factor * 100)
        self.zoom_slider.setValue(fit_zoom_value)
        self.update_zoom(fit_zoom_value)

    def show_gallery_view(self):
        if self.slideshow_timer.isActive(): self.toggle_slideshow()
        self.main_stack.setCurrentIndex(0)
        self.current_viewer_pixmap = None
        self.original_pixmap_for_editing = None
        self.original_cv_image = None
        self.viewer_label.clear(), self.viewer_label.unsetCursor()
        self.prev_button.setVisible(False), self.next_button.setVisible(False)
        self.metadata_dock.setVisible(False)
        self.current_image_path, self.current_image_list, self.current_image_index = None, [], -1
        self.image_res_label.hide(), self.image_file_type_label.hide(), self.image_size_label.hide()
        self.zoom_slider.parent().hide(), self.zoom_label.hide(), self.zoom_slider.hide()
        # [PERUBAHAN] Jangan hapus seleksi saat kembali, biarkan
        # self.selected_files.clear() 
        # self.update_selection_status()
        self.reflow_ui() # Reflow akan update status

    def show_previous_image(self):
        if not self.current_image_list or len(self.current_image_list) <= 1: return
        new_index = (self.current_image_index - 1) % len(self.current_image_list)
        self.show_image_view(self.current_image_list[new_index])

    def show_next_image(self):
        if not self.current_image_list or len(self.current_image_list) <= 1: return
        new_index = (self.current_image_index + 1) % len(self.current_image_list)
        self.show_image_view(self.current_image_list[new_index])

    def _update_nav_buttons_position(self):
        container_size, button_size = self.image_container.size(), self.prev_button.size()
        y_pos = (container_size.height() - button_size.height()) // 2
        self.prev_button.move(15, y_pos)
        self.next_button.move(container_size.width() - button_size.width() - 15, y_pos)
        
    def open_manage_dialog(self):
        dialog = ManageDialog(self.settings, self)
        if dialog.exec(): self.start_scanning_folders()
            
    def show_about_dialog(self):
        QMessageBox.about(self, f"About {APP_NAME}", f"<b>{APP_NAME} v{APP_VERSION}</b><br><br>A professional, enterprise-grade gallery application built with Python, PySide6, and OpenCV.<br><br>©2025 {ORGANIZATION_NAME}")
                          
    def show_context_menu(self, pos):
        global_pos = self.grid_container.mapToGlobal(pos)
        widget_at = self.childAt(self.grid_container.mapFromGlobal(global_pos))
        thumb_widget = widget_at
        while thumb_widget and not isinstance(thumb_widget, (ThumbnailWidget, FolderThumbnailWidget)): thumb_widget = thumb_widget.parent()

        context_menu = QMenu(self)

        # [PERUBAHAN] Tambahkan menu seleksi jika di view 'images'
        if self.current_view == 'images':
            select_all_action = context_menu.addAction("Select All Visible")
            select_all_action.triggered.connect(self.select_all_visible)
            deselect_all_action = context_menu.addAction("Deselect All Visible")
            deselect_all_action.triggered.connect(self.deselect_all_visible)
            context_menu.addSeparator()

            if self.selected_files:
                delete_selected_action = context_menu.addAction(f"Delete Selected ({len(self.selected_files)})")
                delete_selected_action.triggered.connect(self.delete_selected_images)
                
                selected_rating_menu = context_menu.addMenu("Set Rating for Selected")
                for i in range(6):
                    action = selected_rating_menu.addAction(f"{i} Stars" if i > 0 else "No Rating")
                    action.triggered.connect(partial(self.set_rating_for_selected, i))

                selected_label_menu = context_menu.addMenu("Set Label for Selected")
                colors = {"No Label": "none", "Red": "red", "Yellow": "yellow", "Green": "green", "Blue": "blue"}
                for name, color_val in colors.items():
                    action = selected_label_menu.addAction(name)
                    action.triggered.connect(partial(self.set_label_for_selected, color_val))
                
                context_menu.addSeparator()
        
        if not thumb_widget: 
            context_menu.exec(global_pos) # Tampilkan menu seleksi meskipun tidak klik item
            return

        if isinstance(thumb_widget, ThumbnailWidget):
            self.status_label.setText(os.path.basename(thumb_widget.file_path))
            rating_menu = context_menu.addMenu("Set Rating")
            for i in range(6):
                action = rating_menu.addAction(f"{i} Stars" if i > 0 else "No Rating")
                action.triggered.connect(partial(self.set_rating, thumb_widget, i))
            label_menu = context_menu.addMenu("Set Label Color")
            colors = {"No Label": "none", "Red": "red", "Yellow": "yellow", "Green": "green", "Blue": "blue"}
            for name, color_val in colors.items():
                action = label_menu.addAction(name)
                action.triggered.connect(partial(self.set_label_color, thumb_widget, color_val))
            context_menu.addSeparator()
            cut_action = context_menu.addAction("Cut")
            cut_action.triggered.connect(lambda: self.file_op_cut(thumb_widget.file_path))
            copy_action = context_menu.addAction("Copy (File Path)")
            copy_action.triggered.connect(lambda: self.file_op_copy(thumb_widget.file_path))
            context_menu.addSeparator()
            delete_action = context_menu.addAction("Delete (Move to Trash)")
            delete_action.triggered.connect(lambda: self.delete_single_image(thumb_widget.file_path))
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

    # [TAMBAHAN] Fungsi baru untuk handle shortcut CTRL+A
    def select_all_visible_shortcut(self):
        """Hanya jalankan Select All jika di gallery view (index 0) dan mode 'images'."""
        if self.main_stack.currentIndex() == 0 and self.current_view == 'images':
            self.select_all_visible()

    # [PERUBAHAN] Fungsi baru untuk seleksi
    def select_all_visible(self):
        for path, widget in self.thumbnail_widgets.items():
            widget.select_check.setChecked(True)
        self.update_selection_status()

    def deselect_all_visible(self):
        for path, widget in self.thumbnail_widgets.items():
            widget.select_check.setChecked(False)
        self.update_selection_status()
    
    def delete_selected_images(self):
        count = len(self.selected_files)
        if count == 0: return
        
        reply = QMessageBox.question(self, "Confirm Delete",
                                     f"Are you sure you want to move {count} item(s) to the Trash?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        
        if reply == QMessageBox.StandardButton.Yes:
            deleted_count = 0
            for path in list(self.selected_files):
                try:
                    send2trash(os.path.normpath(path))
                    meta_path = get_metadata_path(path)
                    if os.path.exists(meta_path):
                        send2trash(os.path.normpath(meta_path))
                    self.selected_files.discard(path)
                    deleted_count += 1
                except Exception as e:
                    print(f"Failed to delete {path}: {e}")
            
            self.status_label.setText(f"Moved {deleted_count} item(s) to Trash.")
            self.start_scanning_folders() # Ini akan clear selection dan reflow

    def set_rating_for_selected(self, rating):
        if not self.selected_files: return
        for path in self.selected_files:
            write_metadata(path, {'rating': rating})
            if path in self.thumbnail_widgets:
                self.thumbnail_widgets[path].update_metadata_display()
        self.status_label.setText(f"Set rating for {len(self.selected_files)} item(s).")
                
    def set_label_for_selected(self, color):
        if not self.selected_files: return
        for path in self.selected_files:
            if color == 'none':
                meta = read_metadata(path)
                meta.pop('label_color', None)
                write_metadata(path, meta)
            else:
                write_metadata(path, {'label_color': color})
            
            if path in self.thumbnail_widgets:
                self.thumbnail_widgets[path].update_metadata_display()
        self.status_label.setText(f"Set label for {len(self.selected_files)} item(s).")

    def file_op_cut(self, path):
        self.clipboard_cut_path = path
        self.status_label.setText(f"Cut: {os.path.basename(path)}")

    def file_op_copy(self, path):
        QApplication.clipboard().setText(path)
        self.status_label.setText(f"Copied path: {os.path.basename(path)}")

    def file_op_paste(self, dest_folder):
        if not self.clipboard_cut_path: return
        source_path, filename = self.clipboard_cut_path, os.path.basename(self.clipboard_cut_path)
        dest_path = os.path.join(dest_folder, filename)
        if source_path == dest_path: self.clipboard_cut_path = None; return
        try:
            shutil.move(source_path, dest_path)
            meta_source = get_metadata_path(source_path)
            if os.path.exists(meta_source):
                shutil.move(meta_source, get_metadata_path(dest_path))
            self.status_label.setText(f"Moved {filename} to {dest_folder}")
            self.clipboard_cut_path = None
            QTimer.singleShot(100, self.start_scanning_folders)
        except Exception as e: QMessageBox.critical(self, "Paste Error", f"Could not move file:\n{e}")

    def remove_folder_from_gallery(self, folder_path):
        folders = self.settings.value("gallery_folders", [], type=list)
        if folder_path in folders:
            folders.remove(folder_path)
            self.settings.setValue("gallery_folders", folders)
            self.status_label.setText(f"Removed '{os.path.basename(folder_path)}' from gallery.")
            QTimer.singleShot(50, self.start_scanning_folders)

    def show_file_info(self, file_path):
        try:
            stat_info, size_bytes = os.stat(file_path), os.stat(file_path).st_size
            img = cv2.imread(file_path)
            if img is None: raise IOError()
            h, w, *_ = img.shape
            info_text = (f"<b>Filename:</b> {os.path.basename(file_path)}<br>"
                         f"<b>Path:</b> {os.path.dirname(file_path)}<br>"
                         f"<b>Dimensions:</b> {w} x {h} pixels<br>"
                         f"<b>File Size:</b> {get_human_readable_size(size_bytes)} ({size_bytes:,} bytes)")
            QMessageBox.information(self, "File Info", info_text)
        except Exception: QMessageBox.critical(self, "Error", f"Could not get file info for:\n{file_path}")
            
    def set_as_wallpaper(self, file_path):
        path, system = os.path.abspath(file_path), platform.system()
        try:
            if system == "Windows": ctypes.windll.user32.SystemParametersInfoW(20, 0, path, 3)
            elif system == "Darwin": subprocess.run(f'osascript -e \'tell application "Finder" to set desktop picture to POSIX file "{path}"\'', shell=True, check=True)
            else: subprocess.run(["gsettings", "set", "org.gnome.desktop.background", "picture-uri", f"file://{path}"], check=True)
            self.status_label.setText("Wallpaper set successfully.")
        except Exception as e: QMessageBox.critical(self, "Set Wallpaper Error", f"Failed to set wallpaper:\n{e}")

    def update_zoom(self, value):
        if self.current_viewer_pixmap is None: return
        scaled_pixmap = self.current_viewer_pixmap.scaled(self.current_viewer_pixmap.size() * (value / 100.0), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        self.viewer_label.setPixmap(scaled_pixmap)
        self.viewer_label.adjustSize()
        self.zoom_label.setText(f"{value}%")
        self._update_pan_cursor()

    def zoom_in(self): self.zoom_slider.setValue(self.zoom_slider.value() + 10)
    def zoom_out(self): self.zoom_slider.setValue(self.zoom_slider.value() - 10)

    def _update_pan_cursor(self):
        if self.current_viewer_pixmap:
            if self.viewer_label.pixmap().width() > self.viewer_scroll_area.viewport().width() or self.viewer_label.pixmap().height() > self.viewer_scroll_area.viewport().height():
                self.viewer_label.setCursor(Qt.CursorShape.OpenHandCursor)
            else: self.viewer_label.unsetCursor()
    
    def eventFilter(self, source, event):
        # [MODIFIKASI] Tambahkan blok 'elif' baru untuk WheelEvent
        if source is self.viewer_label and self.current_viewer_pixmap:
            if event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                if self.viewer_label.cursor().shape() == Qt.CursorShape.OpenHandCursor:
                    self.is_panning, self.pan_last_mouse_pos = True, event.globalPosition().toPoint()
                    self.viewer_label.setCursor(Qt.CursorShape.ClosedHandCursor)
                    return True
            elif event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                if self.is_panning: self.is_panning = False; self._update_pan_cursor(); return True
            elif event.type() == QEvent.Type.MouseMove and self.is_panning:
                delta = event.globalPosition().toPoint() - self.pan_last_mouse_pos
                self.pan_last_mouse_pos = event.globalPosition().toPoint()
                h_bar, v_bar = self.viewer_scroll_area.horizontalScrollBar(), self.viewer_scroll_area.verticalScrollBar()
                h_bar.setValue(h_bar.value() - delta.x())
                v_bar.setValue(v_bar.value() - delta.y())
                return True
                
            # [TAMBAHAN] Logika untuk Zoom dengan Mouse Wheel
            elif event.type() == QEvent.Type.Wheel:
                # Tentukan seberapa besar step zoom
                # (angleDelta() biasanya 120 per "klik" scroll)
                num_degrees = event.angleDelta().y() / 8
                num_steps = num_degrees / 15  # default 120 / 8 / 15 = 1 step
                
                zoom_step_amount = 5 # Zoom 5% per "klik" scroll
                
                if num_steps > 0:
                    self.zoom_slider.setValue(self.zoom_slider.value() + zoom_step_amount)
                else:
                    self.zoom_slider.setValue(self.zoom_slider.value() - zoom_step_amount)
                    
                event.accept()
                return True
                    
        return super().eventFilter(source, event)

    def set_rating(self, widget, rating):
        write_metadata(widget.file_path, {'rating': rating})
        widget.update_metadata_display()

    def set_label_color(self, widget, color):
        if color == 'none':
            meta = read_metadata(widget.file_path)
            meta.pop('label_color', None)
            write_metadata(widget.file_path, meta)
        else:
            write_metadata(widget.file_path, {'label_color': color})
        widget.update_metadata_display()

    def delete_single_image(self, path):
        reply = QMessageBox.question(self, "Confirm Delete",
                                     f"Are you sure you want to move this file to the Trash?\n\n{os.path.basename(path)}",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                normalized_path = os.path.normpath(path)
                send2trash(normalized_path)
                
                # [PERUBAHAN] Hapus dari set seleksi jika ada
                self.selected_files.discard(path)

                meta_path = get_metadata_path(path)
                if os.path.exists(meta_path):
                    normalized_meta_path = os.path.normpath(meta_path)
                    send2trash(normalized_meta_path)
                    
                self.status_label.setText(f"Moved '{os.path.basename(path)}' to Trash.")
                self.start_scanning_folders() # Ini akan refresh UI
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete file: {e}")

    def delete_current_image(self):
        if not self.current_image_path: return
        path_to_delete = self.current_image_path
        
        # [PERUBAHAN] Hapus dari set seleksi jika ada
        self.selected_files.discard(path_to_delete)
        
        self.show_next_image()
        self.delete_single_image(path_to_delete)
        self.current_image_list = self._get_filtered_and_sorted_list()
        if not self.current_image_list:
            self.show_gallery_view()

    def load_exif_data(self, path):
        try:
            img = Image.open(path)
            exif_data_raw = img.getexif()
            if not exif_data_raw:
                self.metadata_viewer.setHtml("<b>No EXIF data found.</b>")
                return

            exif_data = {TAGS.get(tag, tag): value for tag, value in exif_data_raw.items()}
            
            html = "<style>td { padding: 2px 5px; }</style><table>"
            display_tags = ['Model', 'Make', 'DateTimeOriginal', 'ExposureTime', 'FNumber', 'ISOSpeedRatings', 'FocalLength', 'LensModel']
            
            for tag in display_tags:
                if tag in exif_data:
                    value = exif_data[tag]
                    if isinstance(value, bytes):
                        value = value.decode(errors='ignore')
                    html += f"<tr><td><b>{tag}</b></td><td>{value}</td></tr>"

            html += "</table>"
            self.metadata_viewer.setHtml(html)

        except Exception as e:
            self.metadata_viewer.setHtml(f"<b>Could not read EXIF data.</b><br><br>Reason: {e}")

    def toggle_info_panel(self):
        self.metadata_dock.setVisible(not self.metadata_dock.isVisible())
        self.toggle_info_action.setChecked(self.metadata_dock.isVisible())

    def toggle_slideshow(self):
        if self.slideshow_timer.isActive():
            self.slideshow_timer.stop()
            self.status_label.setText("Slideshow stopped.")
            self.slideshow_action.setChecked(False)
            self.slideshow_action.setIcon(self.play_icon) # <-- TAMBAHKAN INI
        else:
            if len(self.current_image_list) > 1:
                self.slideshow_timer.start(3000) # 3 seconds
                self.status_label.setText("Slideshow running (3s interval)...")
                self.slideshow_action.setChecked(True)
                self.slideshow_action.setIcon(self.pause_icon) # <-- TAMBAHKAN INI
            else:
                self.status_label.setText("Not enough images for a slideshow.")
                self.slideshow_action.setChecked(False)
    
    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
    
    def rotate_image(self, angle):
        if self.original_pixmap_for_editing is None: return
        transform = QTransform().rotate(angle)
        self.original_pixmap_for_editing = self.original_pixmap_for_editing.transformed(transform, Qt.TransformationMode.SmoothTransformation)
        self.current_viewer_pixmap = self.original_pixmap_for_editing
        self.update_zoom(self.zoom_slider.value())
        self._save_image_changes_overwrite()

    def flip_image(self, direction):
        if self.original_pixmap_for_editing is None: return
        self.original_pixmap_for_editing = self.original_pixmap_for_editing.transformed(QTransform().scale(-1 if direction == 'h' else 1, -1 if direction == 'v' else 1))
        self.current_viewer_pixmap = self.original_pixmap_for_editing
        self.update_zoom(self.zoom_slider.value())
        self._save_image_changes_overwrite()
    
    def _save_image_changes_overwrite(self):
        reply = QMessageBox.question(self, "Confirm Save",
                                     "This will overwrite the original file with the current rotation/flip. Are you sure?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.Yes)
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self.original_pixmap_for_editing.save(self.current_image_path, quality=95)
                self.status_label.setText(f"Saved changes to {os.path.basename(self.current_image_path)}")
                self.original_cv_image = cv2.imread(self.current_image_path, cv2.IMREAD_COLOR)
            except Exception as e:
                QMessageBox.critical(self, "Save Error", f"Could not save changes to file: {e}")
                self.show_image_view(self.current_image_path, reload_from_disk=True)
        else:
            self.show_image_view(self.current_image_path, reload_from_disk=True)

    def toggle_maximize_restore(self):
        if self.isMaximized():
            self.showNormal()
            self.maximize_action.setIcon(self._create_svg_icon('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect></svg>'))
        else:
            self.showMaximized()
            self.maximize_action.setIcon(self._create_svg_icon(self.restore_svg))
    def get_edge(self, pos):
        rect, margin = self.rect(), 8
        if self.isMaximized(): return None
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
        self.old_pos, self.is_resizing = None, False
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            self.resize_edge = self.get_edge(pos)
            if self.resize_edge:
                self.is_resizing, self.old_pos = True, event.globalPosition().toPoint()
            elif self.tool_bar.geometry().contains(pos):
                self.old_pos = event.globalPosition().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        if hasattr(self, 'is_resizing') and self.is_resizing and self.old_pos:
            delta = event.globalPosition().toPoint() - self.old_pos
            self.old_pos, geom = event.globalPosition().toPoint(), self.geometry()
            if self.resize_edge in (Qt.CursorShape.SizeVerCursor, Qt.CursorShape.SizeFDiagCursor, Qt.CursorShape.SizeBDiagCursor):
                if pos.y() < 8: geom.setTop(geom.top() + delta.y())
                else: geom.setBottom(geom.bottom() + delta.y())
            if self.resize_edge in (Qt.CursorShape.SizeHorCursor, Qt.CursorShape.SizeFDiagCursor, Qt.CursorShape.SizeBDiagCursor):
                if pos.x() < 8: geom.setLeft(geom.left() + delta.x())
                else: geom.setRight(geom.right() + delta.x())
            self.setGeometry(geom), event.accept()
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
        self.old_pos, self.is_resizing, self.resize_edge = None, False, None
        self.unsetCursor(), super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.tool_bar.geometry().contains(event.position().toPoint()):
            self.toggle_maximize_restore()
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event):
        """Menangani penekanan tombol keyboard."""
        if event.key() == Qt.Key.Key_Escape:
            if self.isFullScreen():
                # Prioritas 1: Keluar dari fullscreen jika aktif
                self.toggle_fullscreen()
                event.accept()
                return
            elif self.slideshow_timer.isActive():
                # Prioritas 2: Hentikan slideshow jika sedang berjalan
                self.toggle_slideshow()
                event.accept()
                return
        
        # Panggil fungsi parent untuk shortcut lain (spt F11, arrow keys, dll)
        super().keyPressEvent(event)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not hasattr(self, 'resize_timer'):
            self.resize_timer = QTimer()
            self.resize_timer.setSingleShot(True)
            self.resize_timer.timeout.connect(self.reflow_ui)
        self.resize_timer.start(100)
        if self.main_stack.currentIndex() == 1:
             self._update_nav_buttons_position()
             if self.current_viewer_pixmap: self.update_zoom(self.zoom_slider.value())

    def _create_info_dock_widget(self):
        """Menciptakan dock widget untuk info, edit, dan tag."""
        self.metadata_dock = QDockWidget("Info & Edit", self)
        self.metadata_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.metadata_dock.setMinimumWidth(280)

        dock_main_widget = QWidget()
        dock_layout = QVBoxLayout(dock_main_widget)
        dock_layout.setContentsMargins(10, 10, 10, 10)
        dock_layout.setSpacing(10)

        edit_label = QLabel("<b>Image Adjustments</b>")
        dock_layout.addWidget(edit_label)

        dock_layout.addWidget(QLabel("Brightness"))
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setRange(-100, 100)
        self.brightness_slider.setValue(0)
        self.brightness_slider.valueChanged.connect(self.update_image_edits)
        dock_layout.addWidget(self.brightness_slider)

        dock_layout.addWidget(QLabel("Contrast"))
        self.contrast_slider = QSlider(Qt.Orientation.Horizontal)
        self.contrast_slider.setRange(0, 200)
        self.contrast_slider.setValue(100)
        self.contrast_slider.valueChanged.connect(self.update_image_edits)
        dock_layout.addWidget(self.contrast_slider)

        dock_layout.addWidget(QLabel("Saturation"))
        self.saturation_slider = QSlider(Qt.Orientation.Horizontal)
        self.saturation_slider.setRange(0, 200)
        self.saturation_slider.setValue(100)
        self.saturation_slider.valueChanged.connect(self.update_image_edits)
        dock_layout.addWidget(self.saturation_slider)
    
        edit_buttons_layout = QHBoxLayout()
        self.save_edits_button = QPushButton("Save Adjustments")
        self.save_edits_button.clicked.connect(self.save_metadata_edits)
        self.reset_edits_button = QPushButton("Reset")
        self.reset_edits_button.clicked.connect(self.reset_image_edits)
        edit_buttons_layout.addWidget(self.save_edits_button)
        edit_buttons_layout.addWidget(self.reset_edits_button)
        dock_layout.addLayout(edit_buttons_layout)

        dock_layout.addWidget(QFrame(self, frameShape=QFrame.Shape.HLine))

        tag_label = QLabel("<b>Tags</b>")
        dock_layout.addWidget(tag_label)
        
        self.tag_container = QWidget()
        self.tag_display_layout = QVBoxLayout(self.tag_container)
        self.tag_display_layout.setContentsMargins(0,0,0,0)
        self.tag_display_layout.setSpacing(5)
        
        tag_scroll_area = QScrollArea()
        tag_scroll_area.setWidgetResizable(True)
        tag_scroll_area.setWidget(self.tag_container)
        tag_scroll_area.setFixedHeight(100)
        dock_layout.addWidget(tag_scroll_area)

        tag_input_layout = QHBoxLayout()
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("Add a tag...")
        self.tag_input.returnPressed.connect(self.add_tag)
        self.add_tag_button = QPushButton("+")
        self.add_tag_button.setFixedSize(28,28) # [PERUBAHAN] Ukuran tombol diperkecil
        self.add_tag_button.clicked.connect(self.add_tag)
        tag_input_layout.addWidget(self.tag_input)
        tag_input_layout.addWidget(self.add_tag_button)
        dock_layout.addLayout(tag_input_layout)

        dock_layout.addWidget(QFrame(self, frameShape=QFrame.Shape.HLine))
    
        exif_label = QLabel("<b>EXIF Data</b>")
        dock_layout.addWidget(exif_label)
        self.metadata_viewer = QTextEdit()
        self.metadata_viewer.setReadOnly(True)
        dock_layout.addWidget(self.metadata_viewer)

        dock_layout.addStretch()
        self.metadata_dock.setWidget(dock_main_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.metadata_dock)
        self.metadata_dock.setVisible(False)

    def apply_image_edits(self, cv_image, edits):
        """
        Menerapkan editan (brightness, contrast, saturation) ke gambar OpenCV
        dengan metode yang lebih robust.
        """
        if cv_image is None:
            return None

        brightness = edits.get('brightness', 0)
        contrast = edits.get('contrast', 1.0)
        saturation = edits.get('saturation', 1.0)

        if brightness == 0 and contrast == 1.0 and saturation == 1.0:
            return cv_image.copy()

        img_float = cv_image.astype(np.float32)
        img_float = img_float * contrast + brightness
        img_float = np.clip(img_float, 0, 255)
        img_after_br_co = img_float.astype(np.uint8)

        if saturation == 1.0:
            return img_after_br_co

        hsv = cv2.cvtColor(img_after_br_co, cv2.COLOR_BGR2HSV)
        hsv_float = hsv.astype(np.float32)
        h, s, v = cv2.split(hsv_float)

        s = s * saturation
        s = np.clip(s, 0, 255)

        final_hsv = cv2.merge((h, s, v))
        final_hsv_uint8 = final_hsv.astype(np.uint8)
        img_final = cv2.cvtColor(final_hsv_uint8, cv2.COLOR_HSV2BGR)
        return img_final

    def update_image_edits(self):
        """Dipanggil saat slider diubah, menerapkan preview editan."""
        if self.original_cv_image is None: return

        self.current_edits['brightness'] = self.brightness_slider.value()
        self.current_edits['contrast'] = self.contrast_slider.value() / 100.0
        self.current_edits['saturation'] = self.saturation_slider.value() / 100.0
    
        self.show_image_view(self.current_image_path, reload_from_disk=False)

    def reset_image_edits(self):
        """Mereset slider dan gambar ke kondisi semula."""
        self.brightness_slider.blockSignals(True)
        self.contrast_slider.blockSignals(True)
        self.saturation_slider.blockSignals(True)

        self.brightness_slider.setValue(0)
        self.contrast_slider.setValue(100)
        self.saturation_slider.setValue(100)
        
        self.brightness_slider.blockSignals(False)
        self.contrast_slider.blockSignals(False)
        self.saturation_slider.blockSignals(False)
        
        meta = read_metadata(self.current_image_path)
        if 'edits' in meta:
            del meta['edits']
            write_metadata(self.current_image_path, meta)
            self.status_label.setText("Adjustments have been reset.")
        
        self.update_image_edits()

    def save_metadata_edits(self):
        """Menyimpan nilai edit saat ini ke file metadata .json."""
        if not self.current_image_path: return
        write_metadata(self.current_image_path, {'edits': self.current_edits})
        self.status_label.setText(f"Adjustments saved for {os.path.basename(self.current_image_path)}")

    def add_tag(self):
        """Menambahkan tag baru dari input ke metadata."""
        tag_text = self.tag_input.text().strip().lower()
        if not tag_text or not self.current_image_path: return

        metadata = read_metadata(self.current_image_path)
        tags = set(metadata.get('tags', []))
        tags.add(tag_text)
        write_metadata(self.current_image_path, {'tags': sorted(list(tags))})
    
        self.tag_input.clear()
        self.update_tag_display()

    def remove_tag(self, tag_to_remove):
        """Menghapus tag yang ada dari metadata."""
        if not self.current_image_path: return
        metadata = read_metadata(self.current_image_path)
        tags = metadata.get('tags', [])
        if tag_to_remove in tags:
            tags.remove(tag_to_remove)
            write_metadata(self.current_image_path, {'tags': tags})
            self.update_tag_display()

    def update_tag_display(self):
        """Memperbarui tampilan tag di panel info."""
        while self.tag_display_layout.count():
            child = self.tag_display_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
    
        if not self.current_image_path: 
            self.tag_display_layout.addStretch()
            return
    
        metadata = read_metadata(self.current_image_path)
        tags = metadata.get('tags', [])
    
        for tag in tags:
            tag_widget = QFrame()
            # [PERUBAHAN] Warna diubah
            tag_widget.setStyleSheet("QFrame { background-color: #444444; border-radius: 4px; }")
            tag_layout = QHBoxLayout(tag_widget)
            tag_layout.setContentsMargins(5, 2, 2, 2)
            tag_layout.setSpacing(5)
        
            label = QLabel(tag)
            remove_btn = QPushButton("x")
            # [PERUBAHAN] Ukuran dan warna diubah
            remove_btn.setFixedSize(18, 18)
            remove_btn.setStyleSheet("background-color: #D16969; border-radius: 9px; font-weight: bold; color: #FFFFFF;")
            remove_btn.clicked.connect(partial(self.remove_tag, tag))
        
            tag_layout.addWidget(label)
            tag_layout.addWidget(remove_btn)
            self.tag_display_layout.addWidget(tag_widget)
        
        self.tag_display_layout.addStretch()
    
    def load_settings(self):
        geometry = self.settings.value("geometry", QByteArray())
        if geometry.size() > 0: self.restoreGeometry(geometry)
        else: self.setGeometry(100, 100, 1200, 800)
            
    def save_settings(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("sort_method", self.current_sort_method)
        
    def closeEvent(self, event):
        if self.thumbnail_thread and self.thumbnail_thread.isRunning():
            self.thumbnail_worker.stop()
            self.thumbnail_thread.quit()
            self.thumbnail_thread.wait()
        self.save_settings(), event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    gallery = MacanGallery()
    gallery.show()
    sys.exit(app.exec())