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
from PyQt6.QtGui import QIcon, QAction

# =============================================================================
# CÁC HÀM VÀ LỚP LOGIC (GIỮ NGUYÊN KHÔNG THAY ĐỔI)
# =============================================================================

def get_imported_modules(pyfile):
    modules = set()
    try:
        with open(pyfile, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), pyfile)
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
                border: 2px dashed #a0a0a0;
                border-radius: 8px; /* Giảm bo góc */
                padding: 15px; /* Giảm padding */
                font-size: 15px; /* Giảm font chữ */
                color: #555;
                background-color: #f8f8f8; /* Màu nền nhẹ nhàng hơn */
            }
            QLabel:hover {
                background-color: #e8e8e8;
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
        self.resize(1000, 600) # Kích thước cửa sổ hình chữ nhật ngang
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
        # Sử dụng QVBoxLayout để xếp chồng các GroupBox lên nhau trong cột này
        left_column_layout = QVBoxLayout()
        left_column_layout.setSpacing(10) # Khoảng cách giữa các GroupBox

        # Group Box 1: Input & Options
        group_input_options = QGroupBox("Cài đặt chính")
        layout_input_options = QVBoxLayout()
        layout_input_options.setSpacing(5)

        self.drop_area = DropArea()
        self.drop_area.setFixedHeight(60) # Chiều cao cố định cho drop area
        layout_input_options.addWidget(self.drop_area)

        layout_input_options.addLayout(self._create_file_selection_row("Script (*.py):", "py_path_edit", self.select_py_file))
        layout_input_options.addLayout(self._create_file_selection_row("Icon (*.ico):", "icon_path_edit", self.select_icon_file))
        layout_input_options.addLayout(self._create_file_selection_row("Thư mục đầu ra:", "dist_path_edit", self.select_dist_folder))
        self.dist_path_edit.setText(self.dist_folder)

        options_layout = QHBoxLayout()
        self.chk_onefile = QCheckBox("Một tệp")
        self.chk_noconsole = QCheckBox("Không console")
        self.chk_collectall = QCheckBox("Thu thập modules")
        options_layout.addWidget(self.chk_onefile)
        options_layout.addWidget(self.chk_noconsole)
        options_layout.addWidget(self.chk_collectall)
        options_layout.addStretch() # Đẩy các checkbox sang trái
        layout_input_options.addLayout(options_layout)
        
        group_input_options.setLayout(layout_input_options)
        left_column_layout.addWidget(group_input_options)

        # Group Box 2: Additional Data
        group_extra_files = QGroupBox("Dữ liệu bổ sung (--add-data)")
        layout_extra_files = QVBoxLayout()
        layout_extra_files.setSpacing(5)

        self.extra_files_list = QListWidget()
        self.extra_files_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        # Bỏ setFixedHeight ở đây để nó tự giãn nở cân đối với log_text
        layout_extra_files.addWidget(self.extra_files_list, stretch=1) # stretch=1 để nó co giãn theo không gian

        extra_buttons_layout = QHBoxLayout()
        btn_add_files = QPushButton("Thêm...")
        btn_remove_files = QPushButton("Xóa chọn")
        btn_clear_files = QPushButton("Xóa tất cả")
        extra_buttons_layout.addWidget(btn_add_files)
        extra_buttons_layout.addWidget(btn_remove_files)
        extra_buttons_layout.addWidget(btn_clear_files)
        extra_buttons_layout.addStretch() # Đẩy các nút sang trái
        layout_extra_files.addLayout(extra_buttons_layout)

        group_extra_files.setLayout(layout_extra_files)
        left_column_layout.addWidget(group_extra_files, stretch=1) # stretch=1 để GroupBox này tự giãn nở

        main_layout.addLayout(left_column_layout, 1) # Cột trái chiếm 1 phần không gian

        # ---- Cột Phải: Build & Output ----
        right_column_layout = QVBoxLayout()
        right_column_layout.setSpacing(10)

        group_build = QGroupBox("Xây dựng & Nhật ký")
        layout_build = QVBoxLayout()
        layout_build.setSpacing(5)
        
        layout_build.addWidget(QLabel("Lệnh PyInstaller:"))
        self.command_preview = QLineEdit()
        self.command_preview.setReadOnly(True)
        layout_build.addWidget(self.command_preview)

        self.btn_build = QPushButton("BẮT ĐẦU XÂY DỰNG")
        self.btn_build.setStyleSheet("font-size: 16px; padding: 10px; background-color: #007acc; color: white; font-weight: bold;")
        layout_build.addWidget(self.btn_build)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(0)
        self.progress_bar.hide()
        layout_build.addWidget(self.progress_bar)

        layout_build.addWidget(QLabel("Nhật ký xây dựng:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        # Bỏ setMinimumHeight ở đây để nó tự giãn nở cân đối
        layout_build.addWidget(self.log_text, stretch=1) # stretch=1 để log_text chiếm phần còn lại của không gian
        
        self.status_label = QLabel("Sẵn sàng")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-weight: bold; color: #333;")
        layout_build.addWidget(self.status_label)
        
        group_build.setLayout(layout_build)
        right_column_layout.addWidget(group_build, stretch=1) # Cột phải chứa GroupBox build
        
        main_layout.addLayout(right_column_layout, 1) # Cột phải cũng chiếm 1 phần không gian, làm cho 2 cột cân đối

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
        label.setFixedWidth(120)
        line_edit = QLineEdit()
        setattr(self, line_edit_name, line_edit)
        button = QPushButton("Duyệt...")
        button.setFixedWidth(80)
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
            self.available_modules = get_imported_modules(pyfile)
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

        self.status_label.setText("Đang xây dựng...")
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
            self.status_label.setText("Xây dựng thành công.")
            QMessageBox.information(self, "Thành công", msg)
        else:
            self.status_label.setText("Xây dựng thất bại!")
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
# KHỐI THỰC THI CHÍNH
# =============================================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Giao diện được thiết kế lại
    app.setStyleSheet("""
        QWidget {
            font-family: 'Segoe UI', Arial, sans-serif;
            font-size: 13px;
            color: #333;
        }
        QMainWindow, QDialog {
            background-color: #f0f3f6;
        }
        QGroupBox {
            border: 1px solid #d0d5db;
            border-radius: 8px;
            margin-top: 20px;
            background-color: #ffffff;
            padding-top: 10px;
            padding-bottom: 5px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 2px 10px;
            background-color: #e6edf3;
            border: 1px solid #d0d5db;
            border-radius: 5px;
            color: #444;
            font-weight: bold;
            font-size: 14px;
            left: 10px;
        }
        QPushButton {
            background-color: #007acc;
            color: white;
            border: none;
            padding: 8px 15px;
            border-radius: 5px;
            font-weight: 500;
        }
        QPushButton:hover {
            background-color: #005f99;
        }
        QPushButton:pressed {
            background-color: #004c7a;
        }
        QPushButton[text="Duyệt..."], QPushButton[text="Thêm..."], 
        QPushButton[text="Xóa chọn"], QPushButton[text="Xóa tất cả"] {
            background-color: #e0e0e0;
            color: #333;
            border: 1px solid #ccc;
            padding: 6px 10px;
        }
        QPushButton[text="Duyệt..."]:hover, QPushButton[text="Thêm..."]:hover, 
        QPushButton[text="Xóa chọn"]:hover, QPushButton[text="Xóa tất cả"]:hover {
            background-color: #d0d0d0;
        }
        QLineEdit, QTextEdit, QListWidget {
            background-color: #ffffff;
            border: 1px solid #c0c0c0;
            border-radius: 4px;
            padding: 5px;
        }
        QLineEdit:focus, QTextEdit:focus, QListWidget:focus {
            border: 1px solid #007acc;
        }
        QMenuBar {
            background-color: #e6edf3;
            border-bottom: 1px solid #d0d5db;
        }
        QMenuBar::item:selected {
            background-color: #d0d5db;
            color: #333;
        }
        QMenu {
             background-color: #ffffff;
             border: 1px solid #d0d5db;
             border-radius: 4px;
        }
        QMenu::item {
            padding: 5px 15px;
        }
        QMenu::item:selected {
            background-color: #007acc;
            color: white;
        }
        QCheckBox {
            spacing: 5px;
        }
        QProgressBar {
            border: 1px solid #b0b0b0;
            border-radius: 4px;
            text-align: center;
            height: 20px;
            background-color: #e0e0e0;
        }
        QProgressBar::chunk {
            background-color: #4CAF50;
            border-radius: 3px;
        }
        QLabel#status_label {
            font-size: 14px;
            padding-top: 5px;
            color: #005f99;
        }
    """)

    window = PyInstallerBuilder()
    window.show()
    sys.exit(app.exec())
