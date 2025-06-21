import sys
import os
import ast
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QLineEdit, QTextEdit,
    QCheckBox, QFileDialog, QHBoxLayout, QVBoxLayout, QMessageBox, QDialog,
    QScrollArea, QGridLayout, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

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
            process = subprocess.Popen(self.cmd, shell=True, cwd=self.cwd,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT,
                                       universal_newlines=True,
                                       encoding='utf-8')
            for line in process.stdout:
                self.log_signal.emit(line.rstrip())
            process.wait()
            if process.returncode == 0:
                self.finished_signal.emit(True, "Đã đóng gói xong.")
            else:
                self.finished_signal.emit(False, "Lỗi đóng gói. Xem log để biết chi tiết.")
        except Exception as e:
            self.finished_signal.emit(False, f"Lỗi: {e}")

class CollectModulesDialog(QDialog):
    def __init__(self, modules, selected):
        super().__init__()
        self.setWindowTitle("Chọn module để collect-all")
        self.setMinimumSize(300, 400)
        self.selected = selected.copy()
        self.modules = modules
        self.initUI()

    def initUI(self):
        layout = QVBoxLayout()
        self.checkboxes = []
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container_layout = QVBoxLayout()

        for mod in self.modules:
            checkbox = QCheckBox(mod)
            checkbox.setChecked(mod in self.selected)
            container_layout.addWidget(checkbox)
            self.checkboxes.append(checkbox)

        container.setLayout(container_layout)
        scroll.setWidget(container)
        layout.addWidget(scroll)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.setLayout(layout)

    def get_selected_modules(self):
        return [cb.text() for cb in self.checkboxes if cb.isChecked()]

class PyInstallerBuilder(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyInstaller Builder (PyQt6)")
        self.setMinimumSize(720, 700)
        self.extra_files = []
        self.selected_modules = []
        self.dist_folder = os.path.abspath("dist")
        self.initUI()
        self.setAcceptDrops(True)  # Enable drag and drop

    def initUI(self):
        layout = QGridLayout()
        layout.setSpacing(8)

        # File py
        layout.addWidget(QLabel("Chọn file .py chính:"), 0, 0)
        self.py_path = QLineEdit()
        layout.addWidget(self.py_path, 0, 1)
        btn_py = QPushButton("Chọn file .py")
        btn_py.clicked.connect(self.select_py_file)
        layout.addWidget(btn_py, 0, 2)

        # Icon
        layout.addWidget(QLabel("Chọn icon (.ico):"), 1, 0)
        self.icon_path = QLineEdit()
        layout.addWidget(self.icon_path, 1, 1)
        btn_icon = QPushButton("Chọn icon")
        btn_icon.clicked.connect(self.select_icon_file)
        layout.addWidget(btn_icon, 1, 2)

        # Extra files input
        layout.addWidget(QLabel("Thêm file bổ sung:"), 2, 0)
        self.extra_files_entry = QLineEdit()
        self.extra_files_entry.setReadOnly(True)
        layout.addWidget(self.extra_files_entry, 2, 1)

        btn_add_files = QPushButton("Thêm file")
        btn_add_files.clicked.connect(self.add_extra_files)
        layout.addWidget(btn_add_files, 2, 2)

        btn_view_extra = QPushButton("Xem các file đã thêm")
        btn_view_extra.clicked.connect(self.show_extra_files_popup)
        layout.addWidget(btn_view_extra, 3, 2)  # Nút nằm dưới nút thêm file

        # Dist folder + nút chọn + nút mở
        layout.addWidget(QLabel("Thư mục lưu EXE:"), 4, 0)
        self.dist_path = QLineEdit(self.dist_folder)
        layout.addWidget(self.dist_path, 4, 1)
        btn_dist = QPushButton("Chọn thư mục lưu")
        btn_dist.clicked.connect(self.select_dist_folder)
        layout.addWidget(btn_dist, 4, 2)

        btn_open_dist = QPushButton("Mở thư mục EXE")
        btn_open_dist.clicked.connect(self.open_dist_folder)
        layout.addWidget(btn_open_dist, 5, 2)

        # Checkboxes
        self.onefile_cb = QCheckBox("Đóng gói 1 file (--onefile)")
        self.onefile_cb.stateChanged.connect(self.update_command)
        layout.addWidget(self.onefile_cb, 5, 0)

        self.noconsole_cb = QCheckBox("Ẩn console (--noconsole)")
        self.noconsole_cb.stateChanged.connect(self.update_command)
        layout.addWidget(self.noconsole_cb, 6, 0)

        self.collectall_cb = QCheckBox("Thu thập module (--collect-all):")
        self.collectall_cb.stateChanged.connect(self.on_collectall_toggled)
        layout.addWidget(self.collectall_cb, 7, 0)

        # Buttons row: Bỏ chọn module + Đóng gói
        btn_frame = QHBoxLayout()
        btn_clear_modules = QPushButton("Bỏ chọn tất cả module đã chọn")
        btn_clear_modules.clicked.connect(self.clear_selected_modules)
        btn_frame.addWidget(btn_clear_modules)
        btn_frame.addStretch(1)
        btn_build = QPushButton("Đóng gói")
        btn_build.clicked.connect(self.build_exe)
        self.btn_build = btn_build
        btn_frame.addWidget(btn_build)
        layout.addLayout(btn_frame, 8, 0, 1, 3)

        # Command line input
        layout.addWidget(QLabel("Lệnh sẽ chạy (có thể sửa):"), 9, 0)
        self.cmd_line = QLineEdit()
        layout.addWidget(self.cmd_line, 9, 1, 1, 2)

        # Log output
        layout.addWidget(QLabel("Log quá trình đóng gói:"), 10, 0)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text, 11, 0, 1, 3)

        self.setLayout(layout)

        # Kết nối update lệnh
        self.py_path.textChanged.connect(self.update_command)
        self.icon_path.textChanged.connect(self.update_command)
        self.dist_path.textChanged.connect(self.update_command)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            file_path = url.toLocalFile()
            ext = os.path.splitext(file_path)[1].lower()
            if ext == '.py':
                self.py_path.setText(file_path)
            elif ext == '.ico':
                self.icon_path.setText(file_path)
            else:
                if file_path not in self.extra_files:
                    self.extra_files.append(file_path)
                self.update_extra_files_entry()
        self.update_command()

    def select_py_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "Chọn file .py", "", "Python Files (*.py)")
        if file:
            self.py_path.setText(file)

    def select_icon_file(self):
        file, _ = QFileDialog.getOpenFileName(self, "Chọn icon (.ico)", "", "Icon Files (*.ico)")
        if file:
            self.icon_path.setText(file)

    def add_extra_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Thêm file bổ sung")
        if files:
            for f in files:
                if f not in self.extra_files:
                    self.extra_files.append(f)
            self.update_extra_files_entry()
            self.update_command()

    def update_extra_files_entry(self):
        self.extra_files_entry.setText(", ".join(os.path.basename(f) for f in self.extra_files))

    def show_extra_files_popup(self):
        if not self.extra_files:
            QMessageBox.information(self, "Thông báo", "Chưa có file bổ sung nào được thêm.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Danh sách file bổ sung")
        dlg.setMinimumSize(500, 400)
        vbox = QVBoxLayout()
        for f in self.extra_files:
            label = QLabel(f)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            vbox.addWidget(label)
        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn_box.accepted.connect(dlg.accept)
        vbox.addWidget(btn_box)
        dlg.setLayout(vbox)
        dlg.exec()

    def select_dist_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn thư mục lưu")
        if folder:
            self.dist_path.setText(folder)

    def open_dist_folder(self):
        folder = self.dist_path.text()
        if os.path.isdir(folder):
            os.startfile(folder)
        else:
            QMessageBox.warning(self, "Lỗi", "Thư mục không tồn tại.")

    def clear_selected_modules(self):
        self.selected_modules = []
        self.collectall_cb.setChecked(False)
        self.update_command()

    def on_collectall_toggled(self):
        if self.collectall_cb.isChecked():
            pyfile = self.py_path.text()
            if not os.path.isfile(pyfile):
                QMessageBox.warning(self, "Lỗi", "Vui lòng chọn file .py hợp lệ trước khi chọn module!")
                self.collectall_cb.setChecked(False)
                return
            modules = get_imported_modules(pyfile)
            if not modules:
                QMessageBox.information(self, "Thông báo", "Không tìm thấy module nào trong file .py!")
                self.collectall_cb.setChecked(False)
                return
            dlg = CollectModulesDialog(modules, self.selected_modules)
            if dlg.exec():
                self.selected_modules = dlg.get_selected_modules()
            else:
                self.collectall_cb.setChecked(False)
            self.update_command()
        else:
            self.selected_modules = []
            self.update_command()

    def update_command(self):
        py = self.py_path.text()
        ico = self.icon_path.text()
        dist = self.dist_path.text()
        options = []
        if self.onefile_cb.isChecked():
            options.append("--onefile")
        if self.noconsole_cb.isChecked():
            options.append("--noconsole")
        if self.collectall_cb.isChecked():
            for m in self.selected_modules:
                options.append(f"--collect-all {m}")
        if ico:
            options.append(f'--icon="{ico}"')
        if dist:
            options.append(f'--distpath "{dist}"')
        add_data = []
        for f in self.extra_files:
            add_data.append(f'--add-data "{f};."')
        cmd = ''
        if py:
            cmd = f'pyinstaller {" ".join(options)} {" ".join(add_data)} "{py}"'
        self.cmd_line.setText(cmd)

    def build_exe(self):
        py_file = self.py_path.text()
        if not py_file or not os.path.isfile(py_file):
            QMessageBox.warning(self, "Lỗi", "Vui lòng chọn file .py hợp lệ.")
            return
        cmd = self.cmd_line.text()
        self.log_text.clear()
        self.btn_build.setEnabled(False)
        self.thread = BuildThread(cmd, os.path.dirname(py_file))
        self.thread.log_signal.connect(self.append_log)
        self.thread.finished_signal.connect(self.on_build_finished)
        self.thread.start()

    def append_log(self, text):
        self.log_text.append(text)

    def on_build_finished(self, success, msg):
        QMessageBox.information(self, "Thông báo", msg)
        self.btn_build.setEnabled(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PyInstallerBuilder()
    window.show()
    sys.exit(app.exec())
