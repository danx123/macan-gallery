# 🐯 Macan Gallery Pro

Macan Gallery is a modern gallery application developed with Python, PySide6, and OpenCV.

It is designed as a professional gallery manager with high performance, an elegant interface, and full support for efficient caching, sorting, zooming, and viewing of high-resolution images.

---

## 🚀 Key Features

- 🧠 Thumbnail Generation via OpenCV
- Uses OpenCV to generate fast and precise thumbnails.
- Automatic resizing and cropping with accurate aspect ratio calculations.

- ⚙️ Multi-Threaded Thumbnailing
- Thumbnail generation is performed on a separate thread to maintain a responsive UI.

- 📁 Gallery Folder Management
- Add or remove folders from the gallery list.
- Automatic caching for each image.

- 📦 **Cache Manager**
- View cache location, total size, and clear cache directly from the "Manage Gallery" dialog.

- 🧩 **Sorting and Filter**
- Sort by:
- Name (A–Z / Z–A)
- Date (new–old / old–new)
- Size (large–small / small–large)
- Real-time search bar for filtering images and folders.

- 🖼️ **Modern Image Viewer**
- Interactive zoom, fit-to-window, and panning features.
- Displays image information (resolution, file size, file type).
- Supports drag-and-drop and direct wallpaper setting.

---

## 📸 Screenshot
<img width="1009" height="686" alt="Screenshot 2025-10-21 012431" src="https://github.com/user-attachments/assets/73718fe7-af63-44df-98b4-c59244f47fcb" />



---
📝 Changelov v2.6.0
- Added Selection Checkboxes: Each ThumbnailWidget (individual image) will have a checkbox. This allows you to select multiple images.

- Selection Functions: Added logic to track selected files, as well as context menus (right-click) for "Select All," "Deselect All," and performing bulk actions (delete, rate, label) on selected items.

- Changed Color Scheme: Replaced the "Nordic dark blue" color theme with the more neutral "Black/Dark" theme. All dark blue background colors will be changed to very dark gray or black, and all text will be made white (#FFFFFF).

- Reduced Button Sizes: Reduced the padding on QPushButtons and QToolButtons throughout the application, and reduced the size of the navigation buttons (left/right arrows) in the viewer to make them less bulky.

🚀 Performance Improvements
Faster Thumbnail Loading: The thumbnail worker logic (ThumbnailWorker.run) now emits a thumbnail_ready signal as soon as it encounters a cached thumbnail image. This makes the gallery view feel more responsive when loading previously cached images (previously, it would wait until all worker processes were completed or simply skip without notifying the UI).

✨ New Features and Internals
NumPy Support: Added import of the numpy library. This addition is typically required for advanced image processing operations using cv2 (OpenCV).

Image Editing Foundation: Added new internal variables to the main class (MacanGallery) to support image editing features, such as:

self.original_pixmap_for_editing (storing the original image for editing).

self.original_cv_image (storing the original OpenCV image object).

self.current_edits (storing the current editing state, such as brightness, contrast, and saturation).

🔨 Code Refactoring and Cleanliness
Variable Naming: Changed the variable in the FolderThumbnailWidget from videos_to_preview to images_to_preview. This is a minor code cleanup to better fit the context of an image gallery application.
---

- 🧱 **Frameless UI**
- Custom draggable, resizable, and maximized windows.
- Minimalist toolbar with SVG icons.

---

## 🧰 Technologies Used

| Components | Description |
|-----------|------------|
| **Python 3.10+** | Main language |
| **PySide6 (Qt for Python)** | Main GUI framework |
| **OpenCV (cv2)** | Image and thumbnail processing |
| **QtMultithreading (QThread)** | Maintain performance when generating thumbnails |
| **QSettings** | Store user preferences and gallery folders |

---

## 🧑‍💻 How to Run

### 1. Clone Repository
```bash
git clone https://github.com/danx123/macan-gallery.git
cd macan-gallery

📚 Technical Notes
The thumbnail cache is stored at:
~/.cache/MacanGallery/thumbnails

Each image is converted to a cached JPEG using OpenCV for maximum performance.
The application stores settings in the system (QSettings) so user preferences are preserved.

🏢 About
Macan Gallery is part of the Macan Angkasa ecosystem.
Created by Danx Exodus with a spirit of technological independence and high efficiency.
© 2025 Danx Exodus — All rights reserved.

🌐 License
This project is released under the MIT License — please use, modify, and develop further with due credit.
