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
    QSizePolicy, QGroupBox, QMainWindow, QSpacerItem, QGridLayout # Import QGridLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QAction, QColor, QPalette

# =============================================================================
# CÁC HÀM VÀ LỚP LOGIC (Giữ nguyên)
# =============================================================================

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
        
        # THAY ĐỔI: Thêm biểu tượng cho cửa sổ popup
        default_icon_path = "app_icon.ico"
        if os.path.isfile(default_icon_path):
            self.setWindowIcon(QIcon(default_icon_path))
            
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

# =============================================================================
# LỚP GIAO DIỆN CHÍNH (Đã điều chỉnh _init_ui)
# =============================================================================

class PyInstallerBuilder(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyInstaller Builder by Minh Duy")
        self.resize(900, 550)
        self.extra_files = []
        self.dist_folder = os.path.abspath("dist")
        self.selected_modules = []
        self.available_modules = []

        self.setAcceptDrops(True)

        default_icon_path = "app_icon.ico"
        if os.path.isfile(default_icon_path):
            self.setWindowIcon(QIcon(default_icon_path))

        self._init_ui()
        self.update_command_preview()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        files = [url.toLocalFile() for url in urls if url.isLocalFile()]
        for file in files:
            self.handle_dropped_file(file)

    def _init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)


        left_column_layout = QVBoxLayout()
        left_column_layout.setSpacing(8)

        # --- Cài đặt chung (Input Options) ---
        group_input = QGroupBox("Cài đặt chung")
        # THAY ĐỔI: Bỏ đặt chiều rộng tối thiểu cho group_input
        # group_input.setMinimumWidth(640) # Đã xóa dòng này
        
        layout_input = QGridLayout()
        layout_input.setContentsMargins(8, 20, 8, 8)
        layout_input.setSpacing(4)

        # Script (.py)
        row = self._create_file_selection_row_grid("Script (.py):", "py_path_edit", self.select_py_file)
        layout_input.addLayout(row, 0, 0, 1, 3)

        # Icon (.ico)
        row = self._create_file_selection_row_grid("Icon (.ico):", "icon_path_edit", self.select_icon_file)
        layout_input.addLayout(row, 1, 0, 1, 3)

        # Thư mục đầu ra
        row = self._create_file_selection_row_grid("Thư mục đầu ra:", "dist_path_edit", self.select_dist_folder)
        layout_input.addLayout(row, 2, 0, 1, 3)
        self.dist_path_edit.setText(self.dist_folder)

        # Build Options (checkboxes)
        options_layout = QHBoxLayout()
        options_layout.setSpacing(8)
        self.chk_onefile = QCheckBox("Một tệp")
        self.chk_noconsole = QCheckBox("Không console")
        self.chk_collectall = QCheckBox("Thu thập modules")
        self.chk_clean = QCheckBox("Xóa build tạm")
        
        # THAY ĐỔI: Bỏ stretch=1 và thêm addStretch()
        options_layout.addWidget(self.chk_onefile)
        options_layout.addWidget(self.chk_noconsole)
        options_layout.addWidget(self.chk_collectall)
        options_layout.addWidget(self.chk_clean)
        options_layout.addStretch() # THAY ĐỔI: Thêm stretch để các ô tích không giãn

        layout_input.addLayout(options_layout, 3, 0, 1, 3)

        group_input.setLayout(layout_input)
        left_column_layout.addWidget(group_input, stretch=0) 

        # --- Dữ liệu bổ sung (Extra Files) ---
        group_extra_files = QGroupBox("Dữ liệu bổ sung")
        layout_extra_files = QVBoxLayout()
        layout_extra_files.setContentsMargins(8, 20, 8, 8)
        layout_extra_files.setSpacing(4)

        self.extra_files_list = QListWidget()
        self.extra_files_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.extra_files_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        layout_extra_files.addWidget(self.extra_files_list, stretch=1)

        extra_buttons_layout = QHBoxLayout()
        extra_buttons_layout.setSpacing(4)
        btn_add_files = QPushButton("Thêm...")
        btn_remove_files = QPushButton("Xóa chọn")
        btn_clear_files = QPushButton("Xóa tất cả")
        btn_open_dist = QPushButton("Mở thư mục đầu ra")

        btn_add_files.setFixedWidth(100)
        btn_remove_files.setFixedWidth(100)
        btn_clear_files.setFixedWidth(100)
        btn_open_dist.setFixedWidth(120)

        extra_buttons_layout.addWidget(btn_add_files)
        extra_buttons_layout.addWidget(btn_remove_files)
        extra_buttons_layout.addWidget(btn_clear_files)
        extra_buttons_layout.addWidget(btn_open_dist)
        extra_buttons_layout.addStretch()
        layout_extra_files.addLayout(extra_buttons_layout)

        group_extra_files.setLayout(layout_extra_files)
        left_column_layout.addWidget(group_extra_files, stretch=1) 
        
        main_layout.addLayout(left_column_layout, 1)

        # --- Xây dựng & Nhật ký (Build & Log) ---
        right_column_layout = QVBoxLayout()
        right_column_layout.setSpacing(8)

        group_build = QGroupBox("Xây dựng & Nhật ký")
        layout_build = QVBoxLayout()
        layout_build.setContentsMargins(8, 20, 8, 8)
        layout_build.setSpacing(4)

        layout_build.addWidget(QLabel("Lệnh PyInstaller:"))
        self.command_preview = QLineEdit()
        self.command_preview.setReadOnly(True)
        layout_build.addWidget(self.command_preview)

        self.btn_build = QPushButton("BẮT ĐẦU XÂY DỰNG")
        self.btn_build.setStyleSheet("font-size: 14px; padding: 7px; background-color: #0078D4; color: white; font-weight: bold; border-radius: 5px;")
        layout_build.addWidget(self.btn_build)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(0)
        self.progress_bar.hide()
        layout_build.addWidget(self.progress_bar)

        layout_build.addWidget(QLabel("Nhật ký xây dựng:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout_build.addWidget(self.log_text, stretch=1)
        
        group_build.setLayout(layout_build)
        right_column_layout.addWidget(group_build, stretch=1)
        
        main_layout.addLayout(right_column_layout, 1)

        # Connections (Thêm kết nối cho ô tích mới)
        self.chk_onefile.stateChanged.connect(self.update_command_preview)
        self.chk_noconsole.stateChanged.connect(self.update_command_preview)
        self.chk_collectall.stateChanged.connect(self.on_collectall_toggled)
        self.chk_clean.stateChanged.connect(self.update_command_preview)
        self.py_path_edit.textChanged.connect(self.update_command_preview)
        self.icon_path_edit.textChanged.connect(self.update_command_preview)
        self.dist_path_edit.textChanged.connect(self.update_command_preview)
        btn_add_files.clicked.connect(self.add_extra_files)
        btn_remove_files.clicked.connect(self.remove_selected_files)
        btn_clear_files.clicked.connect(self.clear_all_files)
        btn_open_dist.clicked.connect(self.open_dist_folder) 
        self.btn_build.clicked.connect(self.build_exe)

        
    def _create_file_selection_row_grid(self, label_text, line_edit_name, on_click):
        layout = QHBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(4)
        label = QLabel(label_text)
        label.setFixedWidth(100)
        line_edit = QLineEdit()
        setattr(self, line_edit_name, line_edit)
        button = QPushButton("...")
        button.setFixedWidth(28)
        button.clicked.connect(on_click)
        layout.addWidget(label)
        layout.addWidget(line_edit)
        layout.addWidget(button)
        return layout

    def handle_dropped_file(self, file_path):
        ext = os.path.splitext(file_path)[1].lower()
        if ext == '.py':
            self.py_path_edit.setText(file_path)
        elif ext == '.ico':
            self.icon_path_edit.setText(file_path)
            self.setWindowIcon(QIcon(file_path))
        else:
            if file_path not in self.extra_files:
                self.extra_files.append(f)
                self.extra_files_list.addItem(f)
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
                content = f.read()
            self.available_modules = get_imported_modules_from_content(content)
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
        if self.chk_clean.isChecked(): parts.append("--clean")
        
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
            QMessageBox.information(self, "Thành công", msg)
        else:
            QMessageBox.critical(self, "Lỗi", msg)

    def download_python(self):
        webbrowser.open("https://www.python.org/downloads/")

    def install_pyinstaller_button(self):
        try:
            subprocess.Popen([sys.executable, "-m", "pip", "install", "--upgrade", "pyinstaller"])
            QMessageBox.information(self, "Thành công", "Quá trình cài đặt PyInstaller đã bắt đầu trong nền.")
        except Exception as e:
            QMessageBox.critical(self, "Lỗi", f"Không thể bắt đầu cài đặt pyinstaller:\n{e}")

# =============================================================================
# KHỐI THỰC THI CHÍNH (Đã điều chỉnh QSS)
# =============================================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)

    app.setStyleSheet("""
        QWidget {
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 13px;
            color: #333333;
        }
        QMainWindow, QDialog {
            background-color: #F0F0F0;
        }
        QGroupBox {
            background-color: #FFFFFF;
            border: 1px solid #CCCCCC;
            border-radius: 5px;
            margin-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 1px 6px;
            background-color: #E0E0E0;
            border: 1px solid #BBBBBB;
            border-radius: 4px;
            color: #333333;
            font-weight: bold;
            font-size: 12px;
            left: 7px;
        }
        QPushButton {
            background-color: #0078D4;
            color: white;
            border: 1px solid #005BB5;
            padding: 6px 10px;
            border-radius: 5px;
            font-weight: 600;
            outline: none;
        }
        QPushButton:hover {
            background-color: #006BBF;
        }
        QPushButton:pressed {
            background-color: #004F9F;
        }
        QPushButton[text="..."], QPushButton[text="Thêm..."], 
        QPushButton[text="Xóa chọn"], QPushButton[text="Xóa tất cả"],
        QPushButton[text="Mở thư mục đầu ra"] { 
            background-color: #E0E0E0;
            color: #333333;
            border: 1px solid #BBBBBB;
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: normal;
            font-size: 12px;
        }
        QPushButton[text="..."]:hover, QPushButton[text="Thêm..."]:hover, 
        QPushButton[text="Xóa chọn"]:hover, QPushButton[text="Xóa tất cả"]:hover,
        QPushButton[text="Mở thư mục đầu ra"]:hover {
            background-color: #D0D0D0;
        }
        QLineEdit, QTextEdit, QListWidget {
            background-color: #FFFFFF;
            border: 1px solid #BBBBBB;
            border-radius: 3px;
            padding: 3px;
            selection-background-color: #0078D4;
            selection-color: white;
        }
        QLineEdit:focus, QTextEdit:focus, QListWidget:focus {
            border: 1px solid #0078D4;
            outline: none;
        }
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
        QCheckBox {
            spacing: 5px;
            color: #333333;
            font-size: 12px;
        }
        QCheckBox::indicator {
            width: 16px; 
            height: 16px; 
            border-radius: 8px; /* Đảm bảo hình tròn */
            border: 1px solid #888888;
            background-color: #FFFFFF;
        }
        QCheckBox::indicator:hover { 
            border: 1px solid #005BB5; 
            background-color: #F0F0F0; 
        }
        QCheckBox::indicator:checked {
            background-color: #0078D4; /* Tô màu xanh cho hình tròn khi được chọn */
            border: 1px solid #0078D4; /* Viền cùng màu với nền */
            image: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAACXBIWXMAAAsTAAALEwEAmpwYAAABH0lEQVR4nI2TMUrDQBSGv0r+K+79X27hQoPg4sQoHoNjoXgDjo0XIB7cK6kK3MQ5bXnJ4iBxcXgY0tJSzC2Tf+A7xMhOkhj2P4kQ981rNpvN2+t2u317JpOJXC6X7/M8D9vtdpfGYrG4QqvV+nFmS+C83W6/kMmk/1bXdQbBYDD5qNVqtVwuF8Pruq6Wlpb+yE6r1eonkUhkXlZW1lR2NptNJpPJXlVVVbslGo3GE2Sbpml2LBaLr6urq78c+f0WwOVy+R6LxWKXWCwWi1NTU/+Wz+e/EAS9Xn/Mjo6O03A4/B5lWU6SJJ2z2Wy7vV7vD6PRaBwOh0P4XyKR+CKRyPyQyGQ+JpNJfB+n+8wL8QcW3eQxQAAAAABJRU5ErkJggg==);
            background-repeat: no-repeat;
            background-position: center;
        }
        QCheckBox::indicator:disabled {
            background-color: #EEEEEE;
            border: 1px solid #CCCCCC;
        }
        QProgressBar {
            border: 1px solid #BBBBBB;
            border-radius: 4px;
            text-align: center;
            height: 16px;
            background-color: #E0E0E0;
            color: #333333;
        }
        QProgressBar::chunk {
            background-color: #0078D4;
            border-radius: 3px;
        }
        QLabel {
            font-size: 12px;
        }
    """)

    window = PyInstallerBuilder()
    window.show()
    sys.exit(app.exec())
