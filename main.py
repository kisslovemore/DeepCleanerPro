import os
import sys
import hashlib
import cv2
import time
from pathlib import Path
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import imagehash
from send2trash import send2trash
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QTableWidget, QTableWidgetItem, 
                             QPushButton, QCheckBox, QComboBox, QLineEdit, 
                             QLabel, QFileDialog, QMessageBox, QHeaderView, QProgressBar, QStatusBar)
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtGui import QPixmap

# --- 1. 后台删除线程：解决界面假死 ---
class DeleteThread(QThread):
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(int)

    def __init__(self, file_paths):
        super().__init__()
        self.file_paths = file_paths

    def run(self):
        total = len(self.file_paths)
        success_count = 0
        for i, path in enumerate(self.file_paths):
            try:
                if os.path.exists(path):
                    send2trash(path)
                    success_count += 1
            except Exception as e:
                print(f"删除失败: {path}, {e}")
            
            # 实时反馈进度
            progress = int((i + 1) / total * 100)
            self.progress_signal.emit(progress)
            self.status_signal.emit(f"正在移至回收站: {i+1}/{total}")
        
        self.finished_signal.emit(success_count)

# --- 2. 后台扫描线程：支持多种去重模式 ---
def get_video_fingerprint(path):
    try:
        cap = cv2.VideoCapture(str(path))
        fps = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        hashes = []
        for i in range(1, 4):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(fps * i / 4))
            ret, frame = cap.read()
            if ret:
                img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                hashes.append(str(imagehash.phash(img)))
        cap.release()
        return "VID-" + "-".join(hashes) if hashes else None
    except: return None

class ProScanThread(QThread):
    progress_signal = pyqtSignal(int)
    status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(list)

    def __init__(self, root_path, scan_mode, strategy, use_phash):
        super().__init__()
        self.root_path = Path(root_path)
        self.scan_mode = scan_mode
        self.strategy = strategy
        self.use_phash = use_phash

    def run(self):
        self.status_signal.emit("正在构建索引...")
        all_files = []
        for root, _, files in os.walk(self.root_path):
            for f in files: all_files.append(Path(root) / f)
        
        if not all_files:
            self.finished_signal.emit([])
            return

        group_map = defaultdict(list)
        total = len(all_files)

        if self.scan_mode == "按名称(同名文件)":
            for i, path in enumerate(all_files):
                stat = path.stat()
                group_map[path.name.lower()].append({
                    "path": str(path), "size": stat.st_size, "time": stat.st_mtime, "name": path.name
                })
                if i % 50 == 0: self.progress_signal.emit(int(i/total*100))
        else:
            img_exts = {'.jpg', '.png', '.jpeg', '.bmp', '.webp'}
            vid_exts = {'.mp4', '.mkv', '.avi', '.mov'}
            with ThreadPoolExecutor() as executor:
                future_to_path = {}
                for i, path in enumerate(all_files):
                    ext = path.suffix.lower()
                    if self.use_phash and ext in img_exts:
                        future_to_path[executor.submit(imagehash.phash, Image.open(path))] = path
                    elif ext in vid_exts:
                        future_to_path[executor.submit(get_video_fingerprint, path)] = path
                    else:
                        future_to_path[executor.submit(lambda p: hashlib.md5(open(p,'rb').read(8192)).hexdigest(), path)] = path
                    
                    if i % 10 == 0:
                        self.progress_signal.emit(int(i/total*100))
                        self.status_signal.emit(f"特征提取中: {i}/{total}")

                for future in future_to_path:
                    path = future_to_path[future]
                    try:
                        fp = str(future.result())
                        if fp:
                            stat = path.stat()
                            group_map[fp].append({"path": str(path), "size": stat.st_size, "time": stat.st_mtime, "name": path.name})
                    except: continue

        final_results = []
        for gid, items in group_map.items():
            if len(items) > 1:
                sort_key = 'size' if self.strategy == "保留最大" else 'time'
                sorted_items = sorted(items, key=lambda x: x[sort_key], reverse=True)
                for i, item in enumerate(sorted_items):
                    item['is_duplicate'] = (i > 0)
                    item['group_id'] = gid[:15]
                    final_results.append(item)
        
        self.finished_signal.emit(final_results)

# --- 3. 主界面：包含增强版 QSS 动画 ---
class UltraCleanerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI 文件整理专家Pro版")
        self.resize(1300, 850)
        self.setStyleSheet("""
            QMainWindow { background-color: #f5f6fa; }
            QPushButton#primaryBtn {
                height: 48px; background-color: #27ae60; color: white; 
                font-weight: bold; font-size: 15px; border-radius: 8px; border: none;
            }
            QPushButton#primaryBtn:hover { background-color: #2ecc71; border: 1px solid white; }
            QPushButton#primaryBtn:pressed { background-color: #1e8449; padding-top: 6px; padding-left: 3px; }
            QPushButton#primaryBtn:disabled { background-color: #bdc3c7; }

            QPushButton#actionBtn {
                height: 60px; background-color: #e67e22; color: white; 
                font-size: 16px; font-weight: bold; border-radius: 8px;
            }
            QPushButton#actionBtn:hover { background-color: #f39c12; }
            QPushButton#actionBtn:pressed { background-color: #d35400; padding-top: 6px; }
            QPushButton#actionBtn:disabled { background-color: #bdc3c7; }
        """)
        self.init_ui()

    def init_ui(self):
        container = QWidget()
        self.setCentralWidget(container)
        main_layout = QHBoxLayout(container)
        left_layout = QVBoxLayout()
        right_layout = QVBoxLayout()

        # 头部路径
        path_row = QHBoxLayout()
        self.path_input = QLineEdit()
        btn_browse = QPushButton("选择目录")
        btn_browse.clicked.connect(lambda: self.path_input.setText(QFileDialog.getExistingDirectory()))
        path_row.addWidget(QLabel("扫描路径:"))
        path_row.addWidget(self.path_input)
        path_row.addWidget(btn_browse)
        left_layout.addLayout(path_row)

        # 设置区
        config_row = QHBoxLayout()
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["按内容/视觉相似", "按名称(同名文件)"])
        self.combo_strategy = QComboBox()
        self.combo_strategy.addItems(["保留最大", "保留最新"])
        self.cb_phash = QCheckBox("视觉相似对比")
        self.cb_phash.setChecked(True)
        config_row.addWidget(QLabel("模式:"))
        config_row.addWidget(self.combo_mode)
        config_row.addWidget(QLabel("策略:"))
        config_row.addWidget(self.combo_strategy)
        config_row.addWidget(self.cb_phash)
        config_row.addStretch()
        left_layout.addLayout(config_row)

        # 控制区
        self.btn_scan = QPushButton("🔍 开始分析 (多线程)")
        self.btn_scan.setObjectName("primaryBtn")
        self.btn_scan.clicked.connect(self.start_scan)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(15)
        left_layout.addWidget(self.btn_scan)
        left_layout.addWidget(self.progress_bar)

        # 结果表格
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["删除选项", "指纹ID/名称", "大小(MB)", "最后修改", "文件路径"])
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.itemSelectionChanged.connect(self.update_preview)
        left_layout.addWidget(self.table)

        # 预览区
        self.preview_label = QLabel("预览区域")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setFixedSize(350, 350)
        self.preview_label.setStyleSheet("border: 2px dashed #ccc; background: white; border-radius: 12px;")
        right_layout.addWidget(self.preview_label)
        
        self.info_label = QLabel("选择文件以查看详情...")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #666; font-size: 13px; padding: 10px;")
        right_layout.addWidget(self.info_label)
        right_layout.addStretch()

        self.btn_trash = QPushButton("🗑️ 移至回收站")
        self.btn_trash.setObjectName("actionBtn")
        self.btn_trash.clicked.connect(self.start_trash)
        right_layout.addWidget(self.btn_trash)

        main_layout.addLayout(left_layout, stretch=4)
        main_layout.addLayout(right_layout, stretch=1)

        # 状态栏
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.stat_label = QLabel("就绪")
        self.status_bar.addWidget(self.stat_label)

    def lock_ui(self, locked):
        self.btn_scan.setEnabled(not locked)
        self.btn_trash.setEnabled(not locked)
        self.table.setEnabled(not locked)
        self.combo_mode.setEnabled(not locked)
        self.combo_strategy.setEnabled(not locked)

    def start_scan(self):
        path = self.path_input.text()
        if not os.path.exists(path): return
        self.lock_ui(True)
        self.btn_scan.setText("🚀 正在全力分析中...")
        self.table.setRowCount(0)
        
        self.scan_thread = ProScanThread(path, self.combo_mode.currentText(), self.combo_strategy.currentText(), self.cb_phash.isChecked())
        self.scan_thread.progress_signal.connect(self.progress_bar.setValue)
        self.scan_thread.status_signal.connect(self.stat_label.setText)
        self.scan_thread.finished_signal.connect(self.on_scan_finished)
        self.scan_thread.start()

    def on_scan_finished(self, items):
        self.lock_ui(False)
        self.btn_scan.setText("🔍 开始分析 (多线程)")
        self.table.setRowCount(len(items))
        
        del_count = 0
        for i, item in enumerate(items):
            cb = QCheckBox()
            cb.setChecked(item['is_duplicate'])
            if item['is_duplicate']: del_count += 1
            
            self.table.setCellWidget(i, 0, cb)
            self.table.setItem(i, 1, QTableWidgetItem(str(item.get('group_id', item['name']))))
            self.table.setItem(i, 2, QTableWidgetItem(f"{item['size']/1024/1024:.2f}"))
            mtime = time.strftime('%Y-%m-%d %H:%M', time.localtime(item['time']))
            self.table.setItem(i, 3, QTableWidgetItem(mtime))
            self.table.setItem(i, 4, QTableWidgetItem(item['path']))

            if not item['is_duplicate']:
                for j in range(5):
                    if self.table.item(i, j):
                        self.table.item(i, j).setBackground(Qt.GlobalColor.darkCyan)
                        self.table.item(i, j).setForeground(Qt.GlobalColor.white)
        
        self.stat_label.setText(f"分析完成 | 总计: {len(items)} | 建议删除: {del_count} | 建议保留: {len(items)-del_count}")

    def update_preview(self):
        try:
            row = self.table.currentRow()
            if row < 0: return
            path = self.table.item(row, 4).text()
            self.info_label.setText(f"文件名: {os.path.basename(path)}\n路径: {path}")
            if Path(path).suffix.lower() in {'.jpg', '.png', '.jpeg', '.bmp'}:
                pixmap = QPixmap(path)
                self.preview_label.setPixmap(pixmap.scaled(350, 350, Qt.AspectRatioMode.KeepAspectRatio))
            else:
                self.preview_label.setText("不支持预览此格式")
        except: pass

    def start_trash(self):
        to_trash = []
        for i in range(self.table.rowCount()):
            if self.table.cellWidget(i, 0).isChecked():
                to_trash.append(self.table.item(i, 4).text())
        
        if not to_trash:
            QMessageBox.warning(self, "提示", "请先勾选要清理的文件")
            return
            
        confirm = QMessageBox.question(self, "确认删除", f"确定将选中的 {len(to_trash)} 个文件移至回收站吗？")
        if confirm == QMessageBox.StandardButton.Yes:
            self.lock_ui(True)
            self.btn_trash.setText("正在清理...")
            self.del_thread = DeleteThread(to_trash)
            self.del_thread.progress_signal.connect(self.progress_bar.setValue)
            self.del_thread.status_signal.connect(self.stat_label.setText)
            self.del_thread.finished_signal.connect(self.on_trash_finished)
            self.del_thread.start()

    def on_trash_finished(self, count):
        self.lock_ui(False)
        self.btn_trash.setText("🗑️ 移至回收站")
        QMessageBox.information(self, "完成", f"已成功处理 {count} 个文件")
        self.start_scan() # 自动刷新列表

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = UltraCleanerGUI()
    window.show()
    sys.exit(app.exec())
