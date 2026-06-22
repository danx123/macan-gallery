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
<img width="1019" height="733" alt="Screenshot 2026-06-22 090715" src="https://github.com/user-attachments/assets/0ede1183-7c97-4321-8d14-e36ebd24f837" />

<img width="1018" height="730" alt="Screenshot 2026-06-22 090731" src="https://github.com/user-attachments/assets/79b8dc7a-d48d-43d6-bb91-377f2e99a726" />

<img width="1021" height="732" alt="Screenshot 2026-06-22 090748" src="https://github.com/user-attachments/assets/0a8ce623-eee4-4e73-9883-76973abb1075" />

<img width="1017" height="735" alt="Screenshot 2026-06-22 090801" src="https://github.com/user-attachments/assets/9d274661-2bd2-433b-8f95-d1aed0fab922" />






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
