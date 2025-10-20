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
    QSizePolicy, QGroupBox, QMainWindow, QSpacerItem, QGridLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QIcon, QAction, QColor, QPalette, QFont

# =============================================================================
# CÁC HÀM VÀ LỚP LOGIC
# =============================================================================

def check_pyinstaller_installed():
    """Kiểm tra xem PyInstaller đã được cài đặt chưa"""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", "pyinstaller"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False

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

class InstallPyInstallerThread(QThread):
    """Thread để cài đặt PyInstaller"""
    log_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def run(self):
        try:
            self.log_signal.emit("Đang cài đặt PyInstaller...")
            process = subprocess.Popen(
                [sys.executable, "-m", "pip", "install", "--upgrade", "pyinstaller"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                encoding='utf-8'
            )
            
            for line in process.stdout:
                self.log_signal.emit(line.rstrip())
            
            process.wait()
            
            if process.returncode == 0:
                self.finished_signal.emit(True, "PyInstaller đã được cài đặt thành công!")
            else:
                self.finished_signal.emit(False, "Không thể cài đặt PyInstaller. Vui lòng kiểm tra kết nối mạng.")
        except Exception as e:
            self.finished_signal.emit(False, f"Lỗi khi cài đặt PyInstaller: {e}")

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
# LỚP GIAO DIỆN CHÍNH
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
        
        layout_input = QGridLayout()
        layout_input.setContentsMargins(8, 8, 8, 8)
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
        
        options_layout.addWidget(self.chk_onefile)
        options_layout.addWidget(self.chk_noconsole)
        options_layout.addWidget(self.chk_collectall)
        options_layout.addWidget(self.chk_clean)
        options_layout.addStretch()

        layout_input.addLayout(options_layout, 3, 0, 1, 3)

        group_input.setLayout(layout_input)
        left_column_layout.addWidget(group_input, stretch=0) 

        # --- Dữ liệu bổ sung (Extra Files) ---
        group_extra_files = QGroupBox("Dữ liệu bổ sung")
        layout_extra_files = QVBoxLayout()
        layout_extra_files.setContentsMargins(8, 8, 8, 8)
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
        layout_build.setContentsMargins(8, 8, 8, 8)
        layout_build.setSpacing(4)

        layout_build.addWidget(QLabel("Lệnh PyInstaller:"))
        self.command_preview = QLineEdit()
        self.command_preview.setReadOnly(True)
        layout_build.addWidget(self.command_preview)

        self.btn_build = QPushButton("BẮT ĐẦU XÂY DỰNG")
        self.btn_build.setMinimumHeight(40)
        self.btn_build.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        
        layout_build.addWidget(self.btn_build)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMaximum(0)
        self.progress_bar.hide()
        self.progress_bar.setMinimumWidth(self.btn_build.minimumWidth())  
        layout_build.addWidget(self.progress_bar)

        layout_build.addWidget(QLabel("Nhật ký xây dựng:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout_build.addWidget(self.log_text, stretch=1)
        
        group_build.setLayout(layout_build)
        right_column_layout.addWidget(group_build, stretch=1)
        
        main_layout.addLayout(right_column_layout, 1)

        # Connections
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

        # Sử dụng python -m PyInstaller thay vì pyinstaller trực tiếp
        parts = [f'"{sys.executable}" -m PyInstaller']
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

    def install_pyinstaller(self):
        """Cài đặt PyInstaller tự động"""
        self.log_text.clear()
        self.log_text.append("=== BẮT ĐẦU CÀI ĐẶT PYINSTALLER ===\n")
        
        self.progress_bar.show()
        self.centralWidget().setEnabled(False)
        
        self.install_thread = InstallPyInstallerThread()
        self.install_thread.log_signal.connect(self.append_log)
        self.install_thread.finished_signal.connect(self.on_install_finished)
        self.install_thread.start()

    def on_install_finished(self, success, msg):
        """Callback khi cài đặt PyInstaller hoàn tất"""
        self.progress_bar.hide()
        self.centralWidget().setEnabled(True)
        
        if success:
            # Kiểm tra lại xem PyInstaller đã cài thành công chưa
            if check_pyinstaller_installed():
                QMessageBox.information(self, "Thành công", 
                    "PyInstaller đã được cài đặt thành công!\n\n"
                    "Bạn có thể bắt đầu build ngay bây giờ.")
            else:
                QMessageBox.warning(self, "Cảnh báo", 
                    "PyInstaller đã được cài đặt nhưng chưa khả dụng.\n\n"
                    "Vui lòng khởi động lại ứng dụng và thử lại.")
        else:
            QMessageBox.critical(self, "Lỗi", msg)

    def build_exe(self):
        """Kiểm tra PyInstaller và build"""
        py_file = self.py_path_edit.text()
        if not py_file or not os.path.isfile(py_file):
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn một tệp .py hợp lệ.")
            return
        
        # Kiểm tra PyInstaller đã cài đặt chưa
        if not check_pyinstaller_installed():
            reply = QMessageBox.question(
                self, 
                "PyInstaller chưa được cài đặt",
                "PyInstaller chưa được cài đặt trên hệ thống.\n\n"
                "Bạn có muốn cài đặt PyInstaller ngay bây giờ không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.install_pyinstaller()
            return
        
        # Nếu đã có PyInstaller, tiếp tục build
        self.start_build()

    def start_build(self):
        """Bắt đầu quá trình build"""
        py_file = self.py_path_edit.text()
        cmd = self.command_preview.text()

        self.progress_bar.show()
        self.centralWidget().setEnabled(False)
        self.menuBar().setEnabled(False)
        self.log_text.clear()
        self.log_text.append("=== BẮT ĐẦU XÂY DỰNG ===\n")

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

# =============================================================================
# KHỐI THỰC THI CHÍNH
# =============================================================================

if __name__ == "__main__":
    app = QApplication(sys.argv)

    app.setStyleSheet("""
        QMainWindow, QWidget {
            background-color: rgba(20, 20, 20, 220);
            color: white;
        }
        QLineEdit, QTextEdit {
            background-color: rgba(30, 30, 30, 200);
            color: white;
        }
        QPushButton {
            background-color: rgba(45, 45, 45, 200);
            color: white;
        }
        QPushButton:hover {
            background-color: rgba(70, 70, 70, 220);
        }

        /* ==== QProgressBar ==== */
        QProgressBar {
            border: 1px solid #444;
            border-radius: 3px;
            text-align: center;
            background-color: rgba(35, 35, 35, 200);
            color: white;
            min-height: 10px;
            max-height: 12px;
        }
        QProgressBar::chunk {
            background-color: qlineargradient(
                x1:0, y1:0, x2:1, y2:0,
                stop:0 #3daee9,
                stop:1 #005f99
            );
            border-radius: 3px;
        }
    """)

    window = PyInstallerBuilder()
    window.show()
    sys.exit(app.exec())
