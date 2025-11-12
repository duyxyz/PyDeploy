import sys
import subprocess
import ast
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QFileDialog, 
                             QCheckBox, QLineEdit, QComboBox, QTextEdit, 
                             QGroupBox, QMessageBox, QProgressBar, QListWidget,
                             QListWidgetItem, QTabWidget, QScrollArea)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QIcon


class ConvertThread(QThread):
    """Thread để chạy PyInstaller không block UI"""
    finished = pyqtSignal(bool, str)
    output = pyqtSignal(str)
    progress = pyqtSignal(int)
    
    def __init__(self, command):
        super().__init__()
        self.command = command
    
    def run(self):
        try:
            process = subprocess.Popen(
                self.command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            progress_keywords = {
                'building': 15, 'analyzing': 25, 'running': 35,
                'processing': 45, 'collecting': 55, 'copying': 65,
                'building exe': 75, 'building pyz': 80,
                'appending': 85, 'completed successfully': 100
            }
            
            current_progress = 5
            self.progress.emit(5)
            all_output = []
            
            for line in process.stdout:
                line_lower = line.lower().strip()
                self.output.emit(line.strip())
                all_output.append(line.strip())
                
                for keyword, progress_value in progress_keywords.items():
                    if keyword in line_lower:
                        if progress_value > current_progress:
                            current_progress = progress_value
                            self.progress.emit(current_progress)
                        break
                
                if current_progress < 90 and line.strip():
                    current_progress = min(current_progress + 1, 90)
                    self.progress.emit(current_progress)
            
            process.wait()
            
            if process.returncode == 0:
                self.progress.emit(100)
                self.finished.emit(True, "Chuyển đổi thành công!")
            else:
                error_lines = [line for line in all_output if 'error' in line.lower() or 'failed' in line.lower()]
                error_msg = '\n'.join(error_lines[-5:]) if error_lines else '\n'.join(all_output[-10:])
                self.finished.emit(False, f"PyInstaller lỗi (code {process.returncode}):\n\n{error_msg}")
                
        except Exception as e:
            self.finished.emit(False, f"Lỗi: {str(e)}")


class PyToExeConverter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.selected_file = None
        self.convert_thread = None
        self.used_modules = set()
        self.output_dir = "dist"
        self.init_ui()
        
        # Kích hoạt drag & drop
        self.setAcceptDrops(True)
    
    def analyze_imports(self, file_path):
        """Phân tích file Python để tìm modules được import"""
        imports = set()
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                tree = ast.parse(f.read(), filename=file_path)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.add(node.module.split('.')[0])
            
            return imports
        except Exception as e:
            print(f"Lỗi phân tích file: {e}")
            return set()
    
    def center_on_screen(self):
        """Căn giữa cửa sổ trên màn hình (sát trên, căn giữa ngang)"""
        screen_geometry = QApplication.desktop().screenGeometry()
        window_geometry = self.geometry()
        x = (screen_geometry.width() - window_geometry.width()) // 2
        y = 0  # Sát bên trên màn hình
        self.move(x, y)
    
    def dragEnterEvent(self, event):
        """Xử lý khi kéo file vào"""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1 and urls[0].toLocalFile().endswith('.py'):
                event.accept()
            else:
                event.ignore()
        else:
            event.ignore()
    
    def dropEvent(self, event):
        """Xử lý khi thả file"""
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.endswith('.py'):
                self.load_python_file(file_path)
    
    def init_ui(self):
        self.setWindowTitle('Python to EXE Converter')
        self.setGeometry(100, 100, 900, 650)
        
        # Đặt icon cho app
        if os.path.exists('icon.ico'):
            self.setWindowIcon(QIcon('icon.ico'))
        
        # Căn giữa màn hình
        self.center_on_screen()
        
        self.setStyleSheet("""
            QMainWindow {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #e3f2fd, stop:1 #bbdefb);
            }
            QGroupBox {
                font-weight: bold;
                border: 2px solid #2196F3;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
                background: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        
        # Header
        header = QWidget()
        header.setStyleSheet('background: #1976D2; border-radius: 10px; padding: 15px;')
        header_layout = QVBoxLayout()
        
        title = QLabel('🐍 Python to EXE Converter')
        title.setFont(QFont('Arial', 18, QFont.Bold))
        title.setStyleSheet('color: white;')
        title.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(title)
        

        
        header.setLayout(header_layout)
        main_layout.addWidget(header)
        
        # File selection
        file_group = QGroupBox('📁 File Python')
        file_layout = QHBoxLayout()
        
        self.file_label = QLabel('Chưa chọn file... (Kéo thả file .py vào đây)')
        self.file_label.setStyleSheet('padding: 8px; background: #f5f5f5; border-radius: 5px;')
        file_layout.addWidget(self.file_label, 3)
        
        browse_btn = QPushButton('📂 Chọn File')
        browse_btn.clicked.connect(self.browse_file)
        browse_btn.setStyleSheet('padding: 8px 15px; background: #4CAF50; color: white; border: none; border-radius: 5px; font-weight: bold;')
        file_layout.addWidget(browse_btn, 1)
        
        file_group.setLayout(file_layout)
        main_layout.addWidget(file_group)
        
        # Tabs for options
        tabs = QTabWidget()
        tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 2px solid #2196F3;
                border-radius: 5px;
                background: white;
            }
            QTabBar::tab {
                background: #E3F2FD;
                padding: 8px 20px;
                margin-right: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
            QTabBar::tab:selected {
                background: #2196F3;
                color: white;
                font-weight: bold;
            }
        """)
        
        # Tab 1: Cơ bản
        basic_tab = QWidget()
        basic_layout = QVBoxLayout()
        
        self.onefile_cb = QCheckBox('✅ One File - Đóng gói thành 1 file duy nhất')
        self.onefile_cb.setChecked(True)
        basic_layout.addWidget(self.onefile_cb)
        
        self.noconsole_cb = QCheckBox('🖥️ No Console - Ẩn cửa sổ console (GUI app)')
        basic_layout.addWidget(self.noconsole_cb)
        
        self.clean_build_cb = QCheckBox('🧹 Clean Build - Xóa build cũ')
        self.clean_build_cb.setChecked(True)
        basic_layout.addWidget(self.clean_build_cb)
        
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel('📝 Tên output:'))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText('my_app')
        name_layout.addWidget(self.name_input)
        basic_layout.addLayout(name_layout)
        
        icon_layout = QHBoxLayout()
        icon_layout.addWidget(QLabel('🎨 Icon:'))
        self.icon_input = QLineEdit()
        self.icon_input.setPlaceholderText('Chọn icon .ico (tùy chọn)')
        icon_layout.addWidget(self.icon_input)
        icon_browse_btn = QPushButton('...')
        icon_browse_btn.clicked.connect(self.browse_icon)
        icon_browse_btn.setMaximumWidth(40)
        icon_layout.addWidget(icon_browse_btn)
        basic_layout.addLayout(icon_layout)
        
        gui_layout = QHBoxLayout()
        gui_layout.addWidget(QLabel('🎨 GUI Framework:'))
        self.gui_combo = QComboBox()
        self.gui_combo.addItems(['Không có', 'Tkinter', 'CustomTkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'Kivy', 'Pygame'])
        gui_layout.addWidget(self.gui_combo)
        basic_layout.addLayout(gui_layout)
        
        basic_layout.addStretch()
        basic_tab.setLayout(basic_layout)
        tabs.addTab(basic_tab, "⚙️ Cơ bản")
        
        # Tab 2: Nâng cao
        advanced_tab = QWidget()
        advanced_layout = QVBoxLayout()
        
        advanced_layout.addWidget(QLabel('➕ Hidden Imports:'))
        self.hidden_input = QLineEdit()
        self.hidden_input.setPlaceholderText('numpy, pandas, matplotlib')
        advanced_layout.addWidget(self.hidden_input)
        
        exclude_header = QHBoxLayout()
        exclude_header.addWidget(QLabel('🚫 Exclude Modules:'))
        self.analyze_btn = QPushButton('🔍 Tự động')
        self.analyze_btn.setMaximumWidth(100)
        self.analyze_btn.setStyleSheet('padding: 5px; background: #FF9800; color: white; border-radius: 3px; font-weight: bold;')
        self.analyze_btn.clicked.connect(self.auto_detect_excludes)
        self.analyze_btn.setEnabled(False)
        exclude_header.addWidget(self.analyze_btn)
        exclude_header.addStretch()
        advanced_layout.addLayout(exclude_header)
        
        self.exclude_list = QListWidget()
        self.exclude_list.setMaximumHeight(120)
        self.exclude_list.setSelectionMode(QListWidget.MultiSelection)
        
        self.common_excludes = {
            'unittest': '🧪', 'test': '🧪', 'doctest': '📝', 'pydoc': '📄',
            'tkinter': '🎨', 'PyQt5': '🎨', 'PyQt6': '🎨', 'PySide2': '🎨', 
            'PySide6': '🎨', 'matplotlib': '📊', 'scipy': '🔬', 'pandas': '📈',
            'numpy': '🔢', 'PIL': '🖼️', 'wx': '🎨', 'sqlite3': '💾', 'email': '📧'
        }
        
        for module, icon in self.common_excludes.items():
            item = QListWidgetItem(f"{icon} {module}")
            item.setData(Qt.UserRole, module)
            self.exclude_list.addItem(item)
        
        advanced_layout.addWidget(self.exclude_list)
        
        self.custom_exclude_input = QLineEdit()
        self.custom_exclude_input.setPlaceholderText('Thêm module khác...')
        advanced_layout.addWidget(self.custom_exclude_input)
        
        advanced_tab.setLayout(advanced_layout)
        tabs.addTab(advanced_tab, "🔧 Nâng cao")
        
        main_layout.addWidget(tabs)
        
        # Connect signals
        for widget in [self.onefile_cb, self.noconsole_cb, self.clean_build_cb]:
            widget.stateChanged.connect(self.update_command)
        for widget in [self.name_input, self.icon_input, self.hidden_input, self.custom_exclude_input]:
            widget.textChanged.connect(self.update_command)
        self.gui_combo.currentTextChanged.connect(self.update_command)
        self.exclude_list.itemSelectionChanged.connect(self.update_command)
        
        # Progress
        progress_group = QGroupBox('📊 Tiến trình')
        progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet('''
            QProgressBar {
                border: 2px solid #2196F3;
                border-radius: 8px;
                text-align: center;
                height: 30px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4CAF50, stop:1 #8BC34A);
                border-radius: 6px;
            }
        ''')
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel('⏳ Chưa bắt đầu')
        self.progress_label.setAlignment(Qt.AlignCenter)
        self.progress_label.setStyleSheet('font-weight: bold; color: #666;')
        progress_layout.addWidget(self.progress_label)
        
        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.convert_btn = QPushButton('🚀 Chuyển đổi sang EXE')
        self.convert_btn.clicked.connect(self.convert)
        self.convert_btn.setStyleSheet('''
            QPushButton {
                padding: 12px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #2196F3, stop:1 #1976D2);
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #1565C0;
            }
            QPushButton:disabled {
                background: #ccc;
            }
        ''')
        btn_layout.addWidget(self.convert_btn, 3)
        
        self.open_folder_btn = QPushButton('📁 Mở thư mục')
        self.open_folder_btn.clicked.connect(self.open_output_folder)
        self.open_folder_btn.setEnabled(False)
        self.open_folder_btn.setStyleSheet('''
            QPushButton {
                padding: 12px;
                background: #FF9800;
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: #F57C00;
            }
            QPushButton:disabled {
                background: #ccc;
            }
        ''')
        btn_layout.addWidget(self.open_folder_btn, 1)
        
        main_layout.addLayout(btn_layout)
        
        # Command + Log in collapsible section
        details_group = QGroupBox('💻 Chi tiết')
        details_layout = QVBoxLayout()
        
        details_layout.addWidget(QLabel('Lệnh:'))
        self.cmd_display = QTextEdit()
        self.cmd_display.setMaximumHeight(60)
        self.cmd_display.setReadOnly(True)
        self.cmd_display.setStyleSheet('background: #263238; color: #4CAF50; font-family: Consolas; padding: 8px; border-radius: 5px;')
        details_layout.addWidget(self.cmd_display)
        
        details_layout.addWidget(QLabel('Log:'))
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMaximumHeight(80)
        self.log_display.setStyleSheet('background: #f5f5f5; border-radius: 5px; padding: 5px;')
        details_layout.addWidget(self.log_display)
        
        details_group.setLayout(details_layout)
        main_layout.addWidget(details_group)
        
        # Info footer
        info_label = QLabel('💡 Cài đặt: <code>pip install pyinstaller</code> | 🟢 Xanh = Loại bỏ được | 🔴 Đỏ = Đang dùng | 📥 Kéo thả file .py vào đây')
        info_label.setWordWrap(True)
        info_label.setStyleSheet('background: #FFF9C4; padding: 8px; border-radius: 5px; font-size: 11px;')
        main_layout.addWidget(info_label)
    
    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Chọn file Python', '', 'Python Files (*.py)')
        if file_path:
            self.load_python_file(file_path)
    
    def load_python_file(self, file_path):
        """Load file Python và cập nhật thông tin"""
        self.selected_file = file_path
        self.file_label.setText(os.path.basename(file_path))
        
        # Cập nhật output_dir thành thư mục chứa file .py
        self.output_dir = os.path.join(os.path.dirname(file_path), 'dist')
        
        if not self.name_input.text():
            name = os.path.splitext(os.path.basename(file_path))[0]
            self.name_input.setText(name)
        
        self.analyze_btn.setEnabled(True)
        self.used_modules = self.analyze_imports(file_path)
        self.update_exclude_list_colors()
        self.update_command()
    
    def browse_icon(self):
        icon_path, _ = QFileDialog.getOpenFileName(self, 'Chọn icon', '', 'Icon Files (*.ico)')
        if icon_path:
            self.icon_input.setText(icon_path)
    
    def open_output_folder(self):
        """Mở thư mục chứa file exe"""
        if os.path.exists(self.output_dir):
            if sys.platform == 'win32':
                os.startfile(self.output_dir)
            elif sys.platform == 'darwin':
                subprocess.run(['open', self.output_dir])
            else:
                subprocess.run(['xdg-open', self.output_dir])
        else:
            QMessageBox.warning(self, 'Lỗi', 'Thư mục dist/ không tồn tại!')
    
    def update_exclude_list_colors(self):
        """Tô màu modules"""
        for i in range(self.exclude_list.count()):
            item = self.exclude_list.item(i)
            module_name = item.data(Qt.UserRole)
            
            if module_name in self.used_modules:
                item.setBackground(QColor(255, 200, 200))
                item.setForeground(QColor(139, 0, 0))
            else:
                item.setBackground(QColor(200, 255, 200))
                item.setForeground(QColor(0, 100, 0))
    
    def auto_detect_excludes(self):
        """Tự động chọn modules an toàn"""
        if not self.selected_file:
            return
        
        for i in range(self.exclude_list.count()):
            self.exclude_list.item(i).setSelected(False)
        
        safe_to_exclude = []
        for i in range(self.exclude_list.count()):
            item = self.exclude_list.item(i)
            module_name = item.data(Qt.UserRole)
            
            if module_name not in self.used_modules:
                item.setSelected(True)
                safe_to_exclude.append(module_name)
        
        if safe_to_exclude:
            QMessageBox.information(self, '✅ Hoàn tất', 
                f'Đã chọn {len(safe_to_exclude)} modules:\n{", ".join(safe_to_exclude[:8])}...')
        else:
            QMessageBox.information(self, 'ℹ️ Thông báo', 
                'Không tìm thấy module nào an toàn để loại bỏ.')
        
        self.update_command()
    
    def get_gui_imports(self, framework):
        imports_map = {
            'Tkinter': ['tkinter', 'tkinter.ttk', '_tkinter'],
            'CustomTkinter': ['customtkinter', 'tkinter', '_tkinter'],
            'PyQt5': ['PyQt5', 'PyQt5.QtCore', 'PyQt5.QtGui', 'PyQt5.QtWidgets'],
            'PyQt6': ['PyQt6', 'PyQt6.QtCore', 'PyQt6.QtGui', 'PyQt6.QtWidgets'],
            'PySide2': ['PySide2', 'PySide2.QtCore', 'PySide2.QtGui', 'PySide2.QtWidgets'],
            'PySide6': ['PySide6', 'PySide6.QtCore', 'PySide6.QtGui', 'PySide6.QtWidgets'],
            'Kivy': ['kivy', 'kivy.core.window'],
            'Pygame': ['pygame', 'pygame.mixer', 'pygame.font']
        }
        return imports_map.get(framework, [])
    
    def generate_command(self):
        if not self.selected_file:
            return ''
        
        cmd = 'pyinstaller '
        
        if self.clean_build_cb.isChecked():
            cmd += '--clean -y '
        if self.onefile_cb.isChecked():
            cmd += '--onefile '
        if self.noconsole_cb.isChecked():
            cmd += '--noconsole '
        if self.name_input.text():
            cmd += f'--name="{self.name_input.text()}" '
        if self.icon_input.text():
            cmd += f'--icon="{self.icon_input.text()}" '
        
        # Thêm --distpath để output nằm cùng thư mục file .py
        file_dir = os.path.dirname(self.selected_file)
        cmd += f'--distpath="{os.path.join(file_dir, "dist")}" '
        cmd += f'--workpath="{os.path.join(file_dir, "build")}" '
        cmd += f'--specpath="{file_dir}" '
        
        gui_imports = self.get_gui_imports(self.gui_combo.currentText())
        hidden_imports = [h.strip() for h in self.hidden_input.text().split(',') if h.strip()]
        
        for imp in gui_imports + hidden_imports:
            cmd += f'--hidden-import="{imp}" '
        
        excluded = []
        for item in self.exclude_list.selectedItems():
            excluded.append(item.data(Qt.UserRole))
        
        custom_excludes = [e.strip() for e in self.custom_exclude_input.text().split(',') if e.strip()]
        
        for module in excluded + custom_excludes:
            cmd += f'--exclude-module={module} '
        
        cmd += f'"{self.selected_file}"'
        return cmd
    
    def update_command(self):
        self.cmd_display.setPlainText(self.generate_command())
    
    def convert(self):
        if not self.selected_file:
            QMessageBox.warning(self, '⚠️ Cảnh báo', 'Vui lòng chọn file Python trước!')
            return
        
        self.progress_bar.setValue(0)
        self.progress_label.setText('⏳ Đang chuẩn bị...')
        self.convert_btn.setEnabled(False)
        self.convert_btn.setText('⏳ Đang chuyển đổi...')
        self.open_folder_btn.setEnabled(False)
        self.log_display.clear()
        self.log_display.append('🚀 Bắt đầu...\n')
        
        self.convert_thread = ConvertThread(self.generate_command())
        self.convert_thread.output.connect(self.on_output)
        self.convert_thread.progress.connect(self.on_progress)
        self.convert_thread.finished.connect(self.on_finished)
        self.convert_thread.start()
    
    def on_output(self, line):
        self.log_display.append(line)
        self.log_display.verticalScrollBar().setValue(
            self.log_display.verticalScrollBar().maximum()
        )
    
    def on_progress(self, value):
        self.progress_bar.setValue(value)
        
        stages = [
            (10, '⚙️ Khởi động'),
            (30, '🔍 Phân tích'),
            (50, '📦 Thu thập'),
            (70, '🔨 Build'),
            (90, '📦 Đóng gói'),
            (100, '✅ Hoàn thành')
        ]
        
        for threshold, label in stages:
            if value <= threshold:
                self.progress_label.setText(f'{label}... {value}%')
                break
    
    def on_finished(self, success, message):
        self.convert_btn.setEnabled(True)
        self.convert_btn.setText('🚀 Chuyển đổi sang EXE')
        
        if success:
            self.progress_bar.setValue(100)
            self.progress_label.setText('✅ Hoàn thành!')
            self.log_display.append(f'\n✅ {message}')
            self.log_display.append(f'📁 Vị trí: {self.output_dir}/{self.name_input.text()}.exe')
            self.open_folder_btn.setEnabled(True)
            QMessageBox.information(self, '🎉 Thành công', 
                f'Build thành công!\n\nFile: {self.output_dir}/{self.name_input.text()}.exe')
        else:
            self.progress_bar.setValue(0)
            self.progress_label.setText('❌ Lỗi')
            self.log_display.append(f'\n❌ {message}')
            
            error_box = QMessageBox(self)
            error_box.setIcon(QMessageBox.Critical)
            error_box.setWindowTitle('❌ Lỗi')
            error_box.setText('PyInstaller gặp lỗi khi build:')
            error_box.setDetailedText(message)
            error_box.exec_()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = PyToExeConverter()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()