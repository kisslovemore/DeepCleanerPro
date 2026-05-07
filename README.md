# AI File Cleaner Pro (v1.0) 🚀

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![PyQt6](https://img.shields.io/badge/GUI-PyQt6-green.svg)
![License](https://img.shields.io/badge/License-MIT-orange.svg)

**AI File Cleaner Pro** 是一款基于 PyQt6 开发的高性能多线程文件管理与清理工具。它不仅能通过文件名匹配，还能利用 **感知哈希 (pHash)** 和 **视频关键帧技术** 识别视觉上重复的图片和视频，帮助你深度释放磁盘空间。



---

## ✨ 核心功能

- **🚀 双线程执行架构**：扫描与删除操作均在独立后台线程运行，处理万级文件时 UI 依然丝滑，不假死。
- **📸 视觉相似对比**：采用 pHash 算法，即使图片被压缩、缩放或转换格式，也能精准识别重复项。
- **🎬 视频关键帧检测**：通过 OpenCV 提取视频关键帧指纹，秒杀内容重复但文件名不同的视频。
- **🔍 双模式扫描**：
    - **内容模式**：基于文件指纹（MD5/pHash）进行深度比对。
    - **同名模式**：毫秒级扫描同名文件，适合清理多版本冗余。
- **⚖️ 智能保留策略**：一键筛选“保留最大”或“保留最新”，自动勾选建议删除项。
- **🗑️ 安全清理机制**：集成 `send2trash`，所有删除操作均移至系统回收站，防止误删。
- **👁️ 实时文件预览**：支持图片点击预览，配合左下角详细统计栏，确保清理过程透明可控。

---

## 🛠️ 安装与运行

### 1. 克隆项目
```bash
git clone [https://github.com/kisslovemore/DeepCleanerPro.git](https://github.com/kisslovemore/DeepCleanerPro.git)
cd DeepCleanerPro

### 2. 安装依赖
Bash

pip install PyQt6 Pillow imagehash send2trash opencv-python

### 3. 运行程序
Bash

python main.py

---
