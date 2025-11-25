import sys
import subprocess
import ast
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QFileDialog, 
                             QCheckBox, QLineEdit, QComboBox, QTextEdit, 
                             QGroupBox, QMessageBox, QProgressBar, QListWidget,
                             QListWidgetItem, QTabWidget, QFrame)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon
from PyQt5.QtWidgets import QSizePolicy


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
    
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1 and urls[0].toLocalFile().endswith('.py'):
                event.accept()
            else:
                event.ignore()
        else:
            event.ignore()
    
    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if urls:
            file_path = urls[0].toLocalFile()
            if file_path.endswith('.py'):
                self.load_python_file(file_path)
    
    def init_ui(self):
        self.setWindowTitle('Python to EXE Converter - Install: pip install pyinstaller')
        self.setMinimumWidth(650)
        self.setMaximumWidth(800)
        self.resize(700, 750)
        
        if os.path.exists('icon.ico'):
            self.setWindowIcon(QIcon('icon.ico'))
        
        # Main widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_widget.setLayout(main_layout)
        

        
        # File selection group
        file_group = QGroupBox('Python File')
        file_layout = QVBoxLayout()
        file_layout.setSpacing(8)
        
        # Drop zone with frame
        drop_frame = QFrame()
        drop_frame.setFrameShape(QFrame.StyledPanel)
        drop_frame.setLineWidth(2)
        drop_frame_layout = QVBoxLayout()
        
        self.file_label = QLabel('Drop .py file here or click Browse')
        self.file_label.setAlignment(Qt.AlignCenter)
        self.file_label.setWordWrap(True)
        self.file_label.setMinimumHeight(60)
        drop_frame_layout.addWidget(self.file_label)
        drop_frame.setLayout(drop_frame_layout)
        file_layout.addWidget(drop_frame)
        
        browse_btn = QPushButton('Browse...')
        browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(browse_btn)
        
        file_group.setLayout(file_layout)
        main_layout.addWidget(file_group)
        
        # Tabs for options
        tabs = QTabWidget()
        
        # Tab 1: Basic
        basic_tab = QWidget()
        basic_layout = QVBoxLayout()
        basic_layout.setSpacing(10)
        basic_layout.setContentsMargins(10, 10, 10, 10)
        
        # Checkboxes
        self.onefile_cb = QCheckBox('Single file output (--onefile)')
        self.onefile_cb.setChecked(True)
        basic_layout.addWidget(self.onefile_cb)
        
        self.noconsole_cb = QCheckBox('No console window (--noconsole)')
        basic_layout.addWidget(self.noconsole_cb)
        
        self.clean_build_cb = QCheckBox('Clean build (--clean)')
        self.clean_build_cb.setChecked(True)
        basic_layout.addWidget(self.clean_build_cb)
        
        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        basic_layout.addWidget(line)
        
        # GUI Framework
        gui_row = QHBoxLayout()
        gui_label = QLabel('GUI Framework:')
        gui_label.setMinimumWidth(110)
        gui_row.addWidget(gui_label)
        self.gui_combo = QComboBox()
        self.gui_combo.addItems(['None', 'Tkinter', 'CustomTkinter',
                                 'PyQt5', 'PyQt6', 'PySide2', 'PySide6',
                                 'Kivy', 'Pygame'])
        gui_row.addWidget(self.gui_combo)
        basic_layout.addLayout(gui_row)
        
        # Output name
        name_row = QHBoxLayout()
        name_label = QLabel('Output name:')
        name_label.setMinimumWidth(110)
        name_row.addWidget(name_label)
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText('my_app')
        name_row.addWidget(self.name_input)
        basic_layout.addLayout(name_row)
        
        # Icon
        icon_row = QHBoxLayout()
        icon_label = QLabel('Icon file:')
        icon_label.setMinimumWidth(110)
        icon_row.addWidget(icon_label)
        self.icon_input = QLineEdit()
        self.icon_input.setPlaceholderText('Optional .ico file')
        icon_row.addWidget(self.icon_input)
        icon_browse_btn = QPushButton('...')
        icon_browse_btn.clicked.connect(self.browse_icon)
        icon_browse_btn.setFixedWidth(40)
        icon_row.addWidget(icon_browse_btn)
        basic_layout.addLayout(icon_row)
        
        basic_layout.addStretch()
        basic_tab.setLayout(basic_layout)
        tabs.addTab(basic_tab, "Basic")
        
        # Tab 2: Advanced
        advanced_tab = QWidget()
        advanced_layout = QVBoxLayout()
        advanced_layout.setSpacing(10)
        advanced_layout.setContentsMargins(10, 10, 10, 10)
        
        advanced_layout.addWidget(QLabel('Hidden imports (comma separated):'))
        self.hidden_input = QLineEdit()
        self.hidden_input.setPlaceholderText('numpy, pandas, matplotlib')
        advanced_layout.addWidget(self.hidden_input)
        
        exclude_header = QHBoxLayout()
        exclude_header.addWidget(QLabel('Exclude modules:'))
        self.analyze_btn = QPushButton('Auto detect')
        self.analyze_btn.setMaximumWidth(100)
        self.analyze_btn.clicked.connect(self.auto_detect_excludes)
        self.analyze_btn.setEnabled(False)
        exclude_header.addWidget(self.analyze_btn)
        exclude_header.addStretch()
        advanced_layout.addLayout(exclude_header)
        
        self.exclude_list = QListWidget()
        self.exclude_list.setMaximumHeight(140)
        self.exclude_list.setSelectionMode(QListWidget.MultiSelection)
        
        self.common_excludes = [
            'unittest', 'test', 'doctest', 'pydoc',
            'tkinter', 'PyQt5', 'PyQt6', 'PySide2', 
            'PySide6', 'matplotlib', 'scipy', 'pandas',
            'numpy', 'PIL', 'wx', 'sqlite3', 'email'
        ]
        
        for module in self.common_excludes:
            item = QListWidgetItem(module)
            item.setData(Qt.UserRole, module)
            self.exclude_list.addItem(item)
        
        advanced_layout.addWidget(self.exclude_list)
        
        self.custom_exclude_input = QLineEdit()
        self.custom_exclude_input.setPlaceholderText('Custom modules...')
        advanced_layout.addWidget(self.custom_exclude_input)
        
        advanced_layout.addStretch()
        advanced_tab.setLayout(advanced_layout)
        tabs.addTab(advanced_tab, "Advanced")
        
        main_layout.addWidget(tabs)
        
        # Connect signals
        for widget in [self.onefile_cb, self.noconsole_cb, self.clean_build_cb]:
            widget.stateChanged.connect(self.update_command)
        for widget in [self.name_input, self.icon_input, self.hidden_input, self.custom_exclude_input]:
            widget.textChanged.connect(self.update_command)
        self.gui_combo.currentTextChanged.connect(self.update_command)
        self.exclude_list.itemSelectionChanged.connect(self.update_command)
        
        # Progress group
        progress_group = QGroupBox('Progress')
        progress_layout = QVBoxLayout()
        progress_layout.setSpacing(6)
        
        self.progress_label = QLabel('Ready to convert')
        progress_layout.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        progress_layout.addWidget(self.progress_bar)
        
        progress_group.setLayout(progress_layout)
        main_layout.addWidget(progress_group)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        self.convert_btn = QPushButton('Convert to EXE')
        self.convert_btn.clicked.connect(self.convert)
        self.convert_btn.setMinimumHeight(32)
        btn_layout.addWidget(self.convert_btn, 2)
        
        self.open_folder_btn = QPushButton('Open folder')
        self.open_folder_btn.clicked.connect(self.open_output_folder)
        self.open_folder_btn.setEnabled(False)
        self.open_folder_btn.setMinimumHeight(32)
        btn_layout.addWidget(self.open_folder_btn, 1)
        
        main_layout.addLayout(btn_layout)
        
        # Command display group
        cmd_group = QGroupBox('Command')
        cmd_layout = QVBoxLayout()
        
        self.cmd_display = QTextEdit()
        self.cmd_display.setMaximumHeight(70)
        self.cmd_display.setReadOnly(True)
        cmd_font = QFont("Courier New", 9)
        self.cmd_display.setFont(cmd_font)
        cmd_layout.addWidget(self.cmd_display)
        
        cmd_group.setLayout(cmd_layout)
        main_layout.addWidget(cmd_group)
        
        # Log display group
        log_group = QGroupBox('Output log')
        log_layout = QVBoxLayout()
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMaximumHeight(100)
        log_font = QFont("Courier New", 9)
        self.log_display.setFont(log_font)
        log_layout.addWidget(self.log_display)
        
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)
        

    
    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Select Python file', '', 'Python Files (*.py)')
        if file_path:
            self.load_python_file(file_path)
    
    def load_python_file(self, file_path):
        self.selected_file = file_path
        filename = os.path.basename(file_path)
        
        # Truncate long filenames
        if len(filename) > 50:
            filename = filename[:25] + '...' + filename[-22:]
        
        self.file_label.setText(f' {filename}')
        self.file_label.setToolTip(file_path)
        
        # Update label font to bold when file selected
        font = self.file_label.font()
        font.setBold(True)
        self.file_label.setFont(font)
        
        self.output_dir = os.path.join(os.path.dirname(file_path), 'dist')
        
        if not self.name_input.text():
            name = os.path.splitext(os.path.basename(file_path))[0]
            self.name_input.setText(name)
        
        self.analyze_btn.setEnabled(True)
        self.used_modules = self.analyze_imports(file_path)
        self.update_exclude_list_colors()
        self.update_command()
    
    def browse_icon(self):
        icon_path, _ = QFileDialog.getOpenFileName(self, 'Select icon', '', 'Icon Files (*.ico)')
        if icon_path:
            self.icon_input.setText(icon_path)
    
    def open_output_folder(self):
        if os.path.exists(self.output_dir):
            if sys.platform == 'win32':
                os.startfile(self.output_dir)
            elif sys.platform == 'darwin':
                subprocess.run(['open', self.output_dir])
            else:
                subprocess.run(['xdg-open', self.output_dir])
        else:
            QMessageBox.warning(self, 'Error', 'Output directory does not exist!')
    
    def update_exclude_list_colors(self):
        """Mark modules that are in use with different text color"""
        palette = QApplication.palette()
        
        for i in range(self.exclude_list.count()):
            item = self.exclude_list.item(i)
            module_name = item.data(Qt.UserRole)
            
            if module_name in self.used_modules:
                # Red for modules in use
                item.setForeground(QColor(180, 0, 0))
            else:
                # Green for safe to exclude
                item.setForeground(QColor(0, 120, 0))
    
    def auto_detect_excludes(self):
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
            modules_text = ', '.join(safe_to_exclude[:5])
            if len(safe_to_exclude) > 5:
                modules_text += f'... (+{len(safe_to_exclude) - 5} more)'
            QMessageBox.information(self, 'Complete', 
                f'Selected {len(safe_to_exclude)} modules:\n{modules_text}')
        else:
            QMessageBox.information(self, 'Info', 
                'No safe modules to exclude')
        
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
            QMessageBox.warning(self, 'Warning', 'Please select a Python file first!')
            return
        
        self.progress_bar.setValue(0)
        self.progress_label.setText('Starting conversion...')
        self.convert_btn.setEnabled(False)
        self.convert_btn.setText('Converting...')
        self.open_folder_btn.setEnabled(False)
        self.log_display.clear()
        self.log_display.append('Starting PyInstaller...\n')
        
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
            (10, 'Initializing'),
            (30, 'Analyzing dependencies'),
            (50, 'Collecting modules'),
            (70, 'Building executable'),
            (90, 'Finalizing'),
            (100, 'Complete')
        ]
        
        for threshold, label in stages:
            if value <= threshold:
                self.progress_label.setText(f'{label}... {value}%')
                break
    
    def on_finished(self, success, message):
        self.convert_btn.setEnabled(True)
        self.convert_btn.setText('Convert to EXE')
        
        if success:
            self.progress_bar.setValue(100)
            self.progress_label.setText('Complete!')
            self.log_display.append(f'\n{message}')
            exe_path = f'{self.output_dir}/{self.name_input.text()}.exe'
            self.log_display.append(f'Output: {exe_path}')
            self.open_folder_btn.setEnabled(True)
            QMessageBox.information(self, 'Success', 
                f'Build completed!\n\nOutput: {self.name_input.text()}.exe')
        else:
            self.progress_bar.setValue(0)
            self.progress_label.setText('Failed')
            self.log_display.append(f'\n{message}')
            
            error_box = QMessageBox(self)
            error_box.setIcon(QMessageBox.Critical)
            error_box.setWindowTitle('Error')
            error_box.setText('PyInstaller error occurred')
            error_box.setDetailedText(message)
            error_box.exec_()


def main():
    app = QApplication(sys.argv)
    
    # Use native Windows style
    app.setStyle('windowsvista')  # This gives true Windows native look
    
    # Set application font
    font = QFont("Segoe UI", 9)
    app.setFont(font)
    
    window = PyToExeConverter()
    window.show()
    
    # Center window with slight upward offset
    screen = QApplication.primaryScreen().geometry()
    window_width = window.frameGeometry().width()
    window_height = window.frameGeometry().height()
    
    center_x = (screen.width() - window_width) // 2
    center_y = (screen.height() - window_height) // 2
    
    offset_y = -40
    final_y = max(center_y + offset_y, 20)
    
    window.move(center_x, final_y)
    
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
