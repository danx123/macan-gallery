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
<img width="1197" height="690" alt="Screenshot 2025-10-15 012817" src="https://github.com/user-attachments/assets/8ee212e9-af44-4c8f-b7e8-0400a51069a5" />

<img width="1198" height="688" alt="Screenshot 2025-10-15 012855" src="https://github.com/user-attachments/assets/b3589be5-2d69-4b2d-89c0-5ed24ad90da9" />

---
📝 Changelov v2.0.0
Improvement Summary:
- Fullscreen Mode: Immersive, uninterrupted viewing by pressing F11.
- Automatic Slideshow: Enjoy your image collection automatically at a customizable interval.

- Metadata Panel (EXIF Info): View detailed camera information (model, shutter speed, ISO, etc.) right next to the image.

- Star Rating & Color Labels: Organize and manage your photos professionally with a 5-star rating system and color labels (Red, Yellow, Green, Blue).

- Filter by Rating/Label: Filter the gallery to only display images with a specific rating or color label.

- Delete Function (Move to Trash): Securely delete images (move them to the Recycle Bin/Trash) directly from the app.

- Basic Image Editor:
Rotation: Rotate images 90 degrees left or right.
Flip: Flip images horizontally or vertically.
Changes are saved directly to the original file with confirmation.

- UI/UX Improvements:
Dedicated Toolbar in Image Viewer: Quick access to rotate, delete, info, and slideshow functions.
Rating Display in Thumbnails: See star ratings directly in the gallery view.
New Icons & Tooltips: Clearer and more descriptive icons with tooltips for each button.

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
