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
<img width="1365" height="767" alt="Screenshot 2025-10-15 213639" src="https://github.com/user-attachments/assets/c18dd94f-e8ca-4b36-8eb8-526d861d41da" />


---
📝 Changelov v2.5.1
Major Updates and Fixes (v2.0.0 → v2.5.1)
🐞 Improvements and Stability
Version Update: The app version number has been updated from 2.0.0 to 2.5.1.

Comment Fix: The version comment indicates a "slider fix."

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
