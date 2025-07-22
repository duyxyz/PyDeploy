import sys
import os
import ast
import subprocess
import pathlib
import webbrowser
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QLineEdit, QTextEdit,
    QCheckBox, QFileDialog, QHBoxLayout, QVBoxLayout, QMessageBox,
    QListWidget, QProgressBar, QDialog, QScrollArea, QDialogButtonBox,
    QSizePolicy, QGroupBox, QMainWindow, QSpacerItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QAction, QColor, QPalette

# =============================================================================
# CÁC HÀM VÀ LỚP LOGIC (GIỮ NGUYÊN KHÔNG THAY ĐỔI)
# =============================================================================

def get_imported_modules(pyfile):
    modules = set()
    try:
        with open(pyfile, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), f.read()) # Lỗi: f.read() được gọi 2 lần, cần chỉnh lại
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    modules.add(n.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    modules.add(node.module.split('.')[0])
    except Exception:
        pass
    return sorted(modules)

class BuildThread(QThread):
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, cmd, cwd):
        super().__init__()
        self.cmd = cmd
        self.cwd = cwd

    def run(self):
        try:
            process = subprocess.Popen(
                self.cmd, shell=True, cwd=self.cwd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                universal_newlines=True, encoding='utf-8'
            )
            for line in process.stdout:
                self.log_signal.emit(line.rstrip())
            process.wait()
            if process.returncode == 0:
                self.finished_signal.emit(True, "Build completed successfully.")
            else:
                self.finished_signal.emit(False, "Build error. Check logs for details.")
        except Exception as e:
            self.finished_signal.emit(False, f"Error: {e}")

class CollectModulesDialog(QDialog):
    def __init__(self, modules, selected_modules):
        super().__init__()
        self.setWindowTitle("Chọn các module cho --collect-all")
        self.resize(350, 400)
        self.modules = modules
        self.selected_modules = set(selected_modules)
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        vbox = QVBoxLayout()

        self.checkboxes = []
        for mod in self.modules:
            cb = QCheckBox(mod)
            if mod in self.selected_modules:
                cb.setChecked(True)
            vbox.addWidget(cb)
            self.checkboxes.append(cb)

        container.setLayout(vbox)
        scroll.setWidget(container)
        layout.addWidget(scroll)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)
        self.setLayout(layout)

    def get_selected_modules(self):
        return [cb.text() for cb in self.checkboxes if cb.isChecked()]

class DropArea(QLabel):
    fileDropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__("🗂️ Kéo và thả tệp .py, .ico và các tệp khác vào đây")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #999999; /* Simple dashed border */
                border-radius: 5px; /* Slightly rounded */
                padding: 10px;
                font-size: 14px;
                color: #555555;
                background-color: #F5F5F5; /* Light grey */
            }
            """)
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        files = [url.toLocalFile() for url in urls if url.isLocalFile()]
        for file in files:
            self.fileDropped.emit(file)

# =============================================================================
# LỚP GIAO DIỆN CHÍNH (ĐÃ ĐƯỢC THIẾT KẾ LẠI HÌNH CHỮ NHẬT NGANG, CÂN ĐỐI)
# =============================================================================

class PyInstallerBuilder(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyInstaller Builder by Minh Duy")
        self.resize(900, 550) # Kích thước hợp lý cho giao diện đơn giản
        self.extra_files = []
        self.dist_folder = os.path.abspath("dist")
        self.selected_modules = []
        self.available_modules = []

        default_icon_path = "app_icon.ico"
        if os.path.isfile(default_icon_path):
            self.setWindowIcon(QIcon(default_icon_path))

        self._init_ui()
        self.update_command_preview()

    def _init_ui(self):
        # ---- Main Widget và Layout ----
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget) # Bố cục chính là ngang
        main_layout.setContentsMargins(15, 15, 15, 15) # Lề ngoài
        main_layout.setSpacing(15) # Khoảng cách giữa các cột chính

        self._create_menu_bar()

        # ---- Cột Trái: Input & Options và Additional Data ----
        left_column_layout = QVBoxLayout()
        left_column_layout.setSpacing(10) # Khoảng cách giữa các GroupBox

        # Group Box 1: Input & Options
        group_input_options = QGroupBox("Tùy chọn")
        layout_input_options = QVBoxLayout()
        layout_input_options.setContentsMargins(10, 25, 10, 10) # Adjust margins for title
        layout_input_options.setSpacing(8)

        self.drop_area = DropArea()
        self.drop_area.setFixedHeight(60)
        layout_input_options.addWidget(self.drop_area)

        layout_input_options.addLayout(self._create_file_selection_row("Script (.py):", "py_path_edit", self.select_py_file))
        layout_input_options.addLayout(self._create_file_selection_row("Icon (.ico):", "icon_path_edit", self.select_icon_file))
        layout_input_options.addLayout(self._create_file_selection_row("Thư mục đầu ra:", "dist_path_edit", self.select_dist_folder))
        self.dist_path_edit.setText(self.dist_folder)

        options_layout = QHBoxLayout()
        self.chk_onefile = QCheckBox("Một tệp")
        self.chk_noconsole = QCheckBox("Không console")
        self.chk_collectall = QCheckBox("Thu thập modules")
        options_layout.addWidget(self.chk_onefile)
        options_layout.addWidget(self.chk_noconsole)
        options_layout.addWidget(self.chk_collectall)
        options_layout.addStretch()
        layout_input_options.addLayout(options_layout)
        
        group_input_options.setLayout(layout_input_options)
        left_column_layout.addWidget(group_input_options)

        # Group Box 2: Additional Data
        group_extra_files = QGroupBox("Dữ liệu bổ sung")
        layout_extra_files = QVBoxLayout()
        layout_extra_files.setContentsMargins(10, 25, 10, 10) # Adjust margins for title
        layout_extra_files.setSpacing(5)

        self.extra_files_list = QListWidget()
        self.extra_files_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        layout_extra_files.addWidget(self.extra_files_list, stretch=1)

        extra_buttons_layout = QHBoxLayout()
        btn_add_files = QPushButton("Thêm...")
        btn_remove_files = QPushButton("Xóa chọn")
        btn_clear_files = QPushButton("Xóa tất cả")
        extra_buttons_layout.addWidget(btn_add_files)
        extra_buttons_layout.addWidget(btn_remove_files)
        extra_buttons_layout.addWidget(btn_clear_files)
        extra_buttons_layout.addStretch()
        layout_extra_files.addLayout(extra_buttons_layout)

        group_extra_files.setLayout(layout_extra_files)
        left_column_layout.addWidget(group_extra_files, stretch=1)

        main_layout.addLayout(left_column_layout, 1)

        # ---- Cột Phải: Build & Output ----
        right_column_layout = QVBoxLayout()
        right_column_layout.setSpacing(10)

        group_build = QGroupBox("Xây dựng & Nhật ký")
        layout_build = QVBoxLayout()
        layout_build.setContentsMargins(10, 25, 10, 10) # Adjust margins for title
        layout_build.setSpacing(8)
        
        layout_build.addWidget(QLabel("Lệnh PyInstaller:"))
        self.command_preview = QLineEdit()
        self.command_preview.setReadOnly(True)
        layout_build.addWidget(self.command_preview)

        self.btn_build = QPushButton("BẮT ĐẦU XÂY DỰNG")
        self.btn_build.setStyleSheet("font-size: 16px; padding: 10px; background-color: #0078D4; color: white; font-weight: bold; border-radius: 5px;") # Accent blue, simpler
        layout_build.addWidget(self.btn_build)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(0)
        self.progress_bar.hide()
        layout_build.addWidget(self.progress_bar)

        layout_build.addWidget(QLabel("Nhật ký xây dựng:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout_build.addWidget(self.log_text, stretch=1)
        
        # Bỏ dòng self.status_label
        # self.status_label = QLabel("Sẵn sàng")
        # self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # self.status_label.setStyleSheet("font-weight: bold; color: #0078D4; font-size: 13px;") # Accent blue
        # layout_build.addWidget(self.status_label)
        
        group_build.setLayout(layout_build)
        right_column_layout.addWidget(group_build, stretch=1)
        
        main_layout.addLayout(right_column_layout, 1)

        # ---- Connect signals (giữ nguyên) ----
        self.drop_area.fileDropped.connect(self.handle_dropped_file)
        self.chk_onefile.stateChanged.connect(self.update_command_preview)
        self.chk_noconsole.stateChanged.connect(self.update_command_preview)
        self.chk_collectall.stateChanged.connect(self.on_collectall_toggled)
        self.py_path_edit.textChanged.connect(self.update_command_preview)
        self.icon_path_edit.textChanged.connect(self.update_command_preview)
        self.dist_path_edit.textChanged.connect(self.update_command_preview)
        btn_add_files.clicked.connect(self.add_extra_files)
        btn_remove_files.clicked.connect(self.remove_selected_files)
        btn_clear_files.clicked.connect(self.clear_all_files)
        self.btn_build.clicked.connect(self.build_exe)


    def _create_menu_bar(self):
        menu_bar = self.menuBar()
        tools_menu = menu_bar.addMenu("Công cụ")

        install_action = QAction("Cài đặt PyInstaller", self)
        install_action.triggered.connect(self.install_pyinstaller_button)
        tools_menu.addAction(install_action)

        download_action = QAction("Tải Python...", self)
        download_action.triggered.connect(self.download_python)
        tools_menu.addAction(download_action)
        
        tools_menu.addSeparator()

        open_folder_action = QAction("Mở thư mục đầu ra", self)
        open_folder_action.triggered.connect(self.open_dist_folder)
        tools_menu.addAction(open_folder_action)

    def _create_file_selection_row(self, label_text, line_edit_name, on_click):
        layout = QHBoxLayout()
        label = QLabel(label_text)
        label.setFixedWidth(110) # Wider label for better alignment
        line_edit = QLineEdit()
        setattr(self, line_edit_name, line_edit)
        button = QPushButton("...") # Simpler button text
        button.setFixedWidth(30) # Smaller button
        button.clicked.connect(on_click)
        layout.addWidget(label)
        layout.addWidget(line_edit)
        layout.addWidget(button)
        return layout

    # --- SLOTS & EVENT HANDLERS (LOGIC GIỮ NGUYÊN) ---

    def handle_dropped_file(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.py':
            self.py_path_edit.setText(file_path)
        elif ext == '.ico':
            self.icon_path_edit.setText(file_path)
            self.setWindowIcon(QIcon(file_path))
        else:
            if file_path not in self.extra_files:
                self.extra_files.append(file_path)
                self.extra_files_list.addItem(file_path)
        self.update_command_preview()

    def select_py_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "Chọn tệp Python (.py)", "", "Python Files (*.py)")
        if file:
            self.py_path_edit.setText(file)

    def select_icon_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "Chọn biểu tượng (.ico)", "", "Icon Files (*.ico)")
        if file:
            self.icon_path_edit.setText(file)
            self.setWindowIcon(QIcon(file))

    def add_extra_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Chọn các tệp bổ sung")
        if files:
            for f in files:
                if f not in self.extra_files:
                    self.extra_files.append(f)
                    self.extra_files_list.addItem(f)
            self.update_command_preview()
            
    def remove_selected_files(self):
        selected_items = self.extra_files_list.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            self.extra_files.remove(item.text())
            self.extra_files_list.takeItem(self.extra_files_list.row(item))
        self.update_command_preview()

    def clear_all_files(self):
        self.extra_files.clear()
        self.extra_files_list.clear()
        self.update_command_preview()

    def select_dist_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục đầu ra cho EXE")
        if folder:
            self.dist_path_edit.setText(folder)

    def open_dist_folder(self):
        folder = self.dist_path_edit.text()
        if os.path.isdir(folder):
            os.startfile(folder)
        else:
            QMessageBox.warning(self, "Lỗi", "Thư mục không tồn tại.")
            
    def on_collectall_toggled(self, state):
        if state == Qt.CheckState.Checked.value:
            pyfile = self.py_path_edit.text()
            if not os.path.isfile(pyfile):
                QMessageBox.warning(self, "Lỗi", "Vui lòng chọn một tệp .py hợp lệ trước khi chọn module!")
                self.chk_collectall.setChecked(False)
                return
            with open(pyfile, "r", encoding="utf-8") as f:
                content = f.read() # Đọc nội dung tệp một lần
            self.available_modules = get_imported_modules_from_content(content) # Truyền nội dung thay vì đường dẫn
            dlg = CollectModulesDialog(self.available_modules, self.selected_modules)
            if dlg.exec():
                self.selected_modules = dlg.get_selected_modules()
            else:
                self.chk_collectall.setChecked(False)
                self.selected_modules = []
        else:
            self.selected_modules = []
        self.update_command_preview()

    def update_command_preview(self):
        py = self.py_path_edit.text()
        if not py:
            self.command_preview.setText("Vui lòng chọn một tập lệnh Python để xây dựng.")
            return

        parts = ["pyinstaller"]
        if self.chk_onefile.isChecked(): parts.append("--onefile")
        if self.chk_noconsole.isChecked(): parts.append("--noconsole")
        
        ico = self.icon_path_edit.text()
        if ico: parts.append(f'--icon="{ico}"')

        dist = self.dist_path_edit.text()
        if dist: parts.append(f'--distpath "{dist}"')
        
        if self.chk_collectall.isChecked():
            for mod in self.selected_modules:
                parts.append(f"--collect-all {mod}")
        
        for f in self.extra_files:
            parts.append(f'--add-data "{f}{os.pathsep}."')
            
        parts.append(f'"{py}"')
        self.command_preview.setText(" ".join(parts))

    def build_exe(self):
        py_file = self.py_path_edit.text()
        if not py_file or not os.path.isfile(py_file):
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn một tệp .py hợp lệ.")
            return
        
        cmd = self.command_preview.text()

        # self.status_label.setText("Đang xây dựng...") # Bỏ dòng này
        self.progress_bar.show()
        self.centralWidget().setEnabled(False)
        self.menuBar().setEnabled(False)
        self.log_text.clear()

        self.thread = BuildThread(cmd, os.path.dirname(py_file))
        self.thread.log_signal.connect(self.append_log)
        self.thread.finished_signal.connect(self.on_build_finished)
        self.thread.start()

    def append_log(self, text):
        self.log_text.append(text)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def on_build_finished(self, success, msg):
        self.progress_bar.hide()
        self.centralWidget().setEnabled(True)
        self.menuBar().setEnabled(True)
        if success:
            # self.status_label.setText("Xây dựng thành công.") # Bỏ dòng này
            QMessageBox.information(self, "Thành công", msg)
        else:
            # self.status_label.setText("Xây dựng thất bại!") # Bỏ dòng này
            QMessageBox.critical(self, "Lỗi", msg)

    def download_python(self):
        webbrowser.open("https://www.python.org/downloads/")

    def install_pyinstaller_button(self):
        try:
            subprocess.Popen([sys.executable, "-m", "pip", "install", "--upgrade", "pyinstaller"])
            QMessageBox.information(self, "Thành công", "Quá trình cài đặt PyInstaller đã bắt đầu trong nền.")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể bắt đầu cài đặt pyinstaller:\n{e}")

# Hàm mới để lấy module từ nội dung tệp
def get_imported_modules_from_content(content):
    modules = set()
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    modules.add(n.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    modules.add(node.module.split('.')[0])
    except Exception:
        pass
    return sorted(modules)

# =============================================================================
# KHỐI THỰC THI CHÍNH
# =============================================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Stylesheet đơn giản, giống Rufus
    app.setStyleSheet("""
        /* General Widget Styling */
        QWidget {
            font-family: 'Segoe UI', Arial, sans-serif; /* Phông chữ hệ thống */
            font-size: 13px;
            color: #333333; /* Màu chữ chính */
        }
        QMainWindow, QDialog {
            background-color: #F0F0F0; /* Nền xám nhạt */
        }

        /* GroupBox Styling (Containers for sections) */
        QGroupBox {
            background-color: #FFFFFF; /* Nền trắng cho các nhóm */
            border: 1px solid #CCCCCC; /* Viền xám đơn giản */
            border-radius: 5px; /* Góc bo nhẹ */
            margin-top: 20px; /* Khoảng cách cho tiêu đề */
            padding-top: 10px;
            padding-bottom: 5px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 3px 8px;
            background-color: #E0E0E0; /* Nền xám cho tiêu đề */
            border: 1px solid #BBBBBB; /* Viền xám cho tiêu đề */
            border-radius: 4px; /* Góc bo nhẹ cho tiêu đề */
            color: #333333; /* Màu chữ tiêu đề */
            font-weight: bold;
            font-size: 14px;
            left: 10px;
        }

        /* QPushButton Styling */
        QPushButton {
            background-color: #0078D4; /* Màu xanh chuẩn của Windows */
            color: white;
            border: 1px solid #005BB5; /* Viền đậm hơn một chút */
            padding: 8px 15px;
            border-radius: 5px;
            font-weight: 600;
            outline: none;
        }
        QPushButton:hover {
            background-color: #006BBF; /* Xanh đậm hơn khi di chuột */
        }
        QPushButton:pressed {
            background-color: #004F9F; /* Xanh đậm hơn nữa khi nhấn */
        }
        
        /* Secondary Buttons (Browse, Add, Remove, Clear) */
        QPushButton[text="..."], QPushButton[text="Thêm..."], 
        QPushButton[text="Xóa chọn"], QPushButton[text="Xóa tất cả"] {
            background-color: #E0E0E0; /* Nền xám nhạt cho nút phụ */
            color: #333333;
            border: 1px solid #BBBBBB;
            padding: 6px 12px;
            border-radius: 4px;
            font-weight: normal;
        }
        QPushButton[text="..."]:hover, QPushButton[text="Thêm..."]:hover, 
        QPushButton[text="Xóa chọn"]:hover, QPushButton[text="Xóa tất cả"]:hover {
            background-color: #D0D0D0; /* Xám đậm hơn khi di chuột */
        }

        /* LineEdit, QTextEdit, QListWidget Styling */
        QLineEdit, QTextEdit, QListWidget {
            background-color: #FFFFFF; /* Nền trắng */
            border: 1px solid #BBBBBB; /* Viền xám */
            border-radius: 3px; /* Góc bo nhẹ */
            padding: 5px;
            selection-background-color: #0078D4; /* Màu chọn */
            selection-color: white;
        }
        QLineEdit:focus, QTextEdit:focus, QListWidget:focus {
            border: 1px solid #0078D4; /* Viền xanh khi focus */
            outline: none;
        }

        /* Menu Bar Styling */
        QMenuBar {
            background-color: #E0E0E0;
            border-bottom: 1px solid #BBBBBB;
            padding: 2px;
            font-size: 13px;
        }
        QMenuBar::item {
            padding: 3px 8px;
            border-radius: 3px;
        }
        QMenuBar::item:selected {
            background-color: #D0D0D0;
            color: #333333;
        }
        QMenu {
             background-color: #FFFFFF;
             border: 1px solid #BBBBBB;
             border-radius: 5px;
             padding: 3px;
        }
        QMenu::item {
            padding: 5px 15px;
            border-radius: 3px;
        }
        QMenu::item:selected {
            background-color: #0078D4;
            color: white;
        }

        /* Checkbox Styling */
        QCheckBox {
            spacing: 5px;
            color: #333333;
        }
        QCheckBox::indicator {
            width: 15px;
            height: 15px;
            border-radius: 3px;
            border: 1px solid #888888;
            background-color: #FFFFFF;
        }
        QCheckBox::indicator:checked {
            background-color: #0078D4;
            border: 1px solid #0078D4;
            image: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsTAAALEwEAmpwYAAABH0lEQVR4nI2TMUrDQBSGv0r+K+79X27hQoPg4sQoHoNjoXgDjo0XIB7cK6kK3MQ5bXnJ4iBxcXgY0tJSzC2Tf+A7xMhOkhj2P4kQ981rNpvN2+t2u317JpOJXC6X7/M8D9vtdpfGYrG4QqvV+nFmS+C83W6/kMmk/1bXdQbBYDD5qNVqtVwuF8Pruq6Wlpb+yE6r1eonkUhkXlZW1lR2NptNJpPJXlVVVbslGo3GE2Sbpml2LBaLr6urq78c+f0WwOVy+R6LxWKXWCwWi1NTU/+Wz+e/EAS9Xn/Mjo6O03A4/B5lWU6SJJ2z2Wy7vV7vD6PRaBwOh0P4XyKR+CKRyPyQyGQ+JpNJfB+n+8wL8QcW3eQxQAAAAABJRU5ErkJggg==); /* Tiny checkmark icon */
            background-repeat: no-repeat;
            background-position: center;
        }
        QCheckBox::indicator:disabled {
            background-color: #EEEEEE;
            border: 1px solid #CCCCCC;
        }

        /* Progress Bar Styling */
        QProgressBar {
            border: 1px solid #BBBBBB;
            border-radius: 4px;
            text-align: center;
            height: 20px;
            background-color: #E0E0E0;
            color: #333333;
        }
        QProgressBar::chunk {
            background-color: #0078D4;
            border-radius: 3px;
        }
        /* Đã bỏ styling cho status_label */
    """)

    window = PyInstallerBuilder()
    window.show()
    sys.exit(app.exec())
