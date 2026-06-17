# 🐯 Macan Gallery Pro

Macan Gallery is a modern gallery application developed with Python, PySide6, and OpenCV.

It is designed as a professional gallery manager with high performance, an elegant interface, and full support for efficient caching, sorting, zooming, and viewing of high-resolution images.

---
<img width="1024" height="1536" alt="macan gallery pro v7 6 6" src="https://github.com/user-attachments/assets/0c499b8a-abd0-4e03-9536-70728e61f21b" />



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
<img width="1034" height="718" alt="Screenshot 2026-02-13 180652" src="https://github.com/user-attachments/assets/1d9b29b0-0ecc-492a-b6bb-91c95387276f" />
<img width="1035" height="722" alt="Screenshot 2026-02-13 180717" src="https://github.com/user-attachments/assets/6c116b29-7a1a-43ed-8d32-2266ff6dd96c" />



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
