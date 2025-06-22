import sys
import os
import ast
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QLineEdit, QTextEdit,
    QCheckBox, QFileDialog, QHBoxLayout, QVBoxLayout, QMessageBox,
    QListWidget, QProgressBar, QDialog, QScrollArea, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import QDialog

def obtener_modulos_importados(archivo_py):
    modulos = set()
    try:
        with open(archivo_py, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), archivo_py)
        for nodo in ast.walk(tree):
            if isinstance(nodo, ast.Import):
                for n in nodo.names:
                    modulos.add(n.name.split('.')[0])
            elif isinstance(nodo, ast.ImportFrom):
                if nodo.module:
                    modulos.add(nodo.module.split('.')[0])
    except Exception:
        pass
    return sorted(modulos)

class HiloConstruccion(QThread):
    senal_log = pyqtSignal(str)
    senal_terminado = pyqtSignal(bool, str)

    def __init__(self, cmd, cwd):
        super().__init__()
        self.cmd = cmd
        self.cwd = cwd

    def run(self):
        try:
            proceso = subprocess.Popen(
                self.cmd, shell=True, cwd=self.cwd,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT
            )
            for linea in iter(proceso.stdout.readline, b''):
                try:
                    texto = linea.decode('utf-8')
                except UnicodeDecodeError:
                    texto = linea.decode('utf-8', errors='replace')
                self.senal_log.emit(texto.rstrip())
            proceso.wait()
            if proceso.returncode == 0:
                self.senal_terminado.emit(True, "Construcción completada.")
            else:
                self.senal_terminado.emit(False, "Error en la construcción. Ver logs para detalles.")
        except Exception as e:
            self.senal_terminado.emit(False, f"Error: {e}")

class DialogoSeleccionModulos(QDialog):
    def __init__(self, modulos, modulos_seleccionados):
        super().__init__()
        self.setWindowTitle("Selecciona módulos para --collect-all")
        self.resize(350, 400)
        self.modulos = modulos
        self.modulos_seleccionados = set(modulos_seleccionados)
        self.inicializar_ui()

    def inicializar_ui(self):
        layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        contenedor = QWidget()
        vbox = QVBoxLayout()

        self.checkboxes = []
        for mod in self.modulos:
            cb = QCheckBox(mod)
            if mod in self.modulos_seleccionados:
                cb.setChecked(True)
            vbox.addWidget(cb)
            self.checkboxes.append(cb)

        contenedor.setLayout(vbox)
        scroll.setWidget(contenedor)
        layout.addWidget(scroll)

        botones = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botones.accepted.connect(self.accept)
        botones.rejected.connect(self.reject)
        layout.addWidget(botones)
        self.setLayout(layout)

    def obtener_modulos_seleccionados(self):
        return [cb.text() for cb in self.checkboxes if cb.isChecked()]

class AreaArrastrar(QLabel):
    def __init__(self, padre=None):
        super().__init__("🗂️ Arrastra y suelta archivos .py, .ico y archivos adicionales aquí")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                border: 2px dashed #888;
                border-radius: 14px;
                min-height: 70px;
                font-size: 18px;
                background: #f9f9f9;
                color: #666;
            }
            """)
        self.setAcceptDrops(True)
        self.padre = padre

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        archivos = [url.toLocalFile() for url in urls if url.isLocalFile()]
        for archivo in archivos:
            ext = os.path.splitext(archivo)[1].lower()
            if ext == '.py':
                self.padre.py_path_edit.setText(archivo)
            elif ext == '.ico':
                self.padre.icon_path_edit.setText(archivo)
            else:
                if archivo not in self.padre.archivos_adicionales:
                    self.padre.archivos_adicionales.append(archivo)
                    self.padre.extra_files_list.addItem(archivo)
                    self.padre.actualizar_extra_files_entry()
        self.padre.actualizar_vista_comando()

class ConstructorPyInstaller(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Constructor PyInstaller (Popup selección módulos al marcar checkbox)")
        self.resize(750, 730)
        self.archivos_adicionales = []
        self.carpeta_dist = os.path.abspath("dist")
        self.modulos_seleccionados = []
        self.modulos_disponibles = []
        self._inicializar_ui()

    def _inicializar_ui(self):
        layout = QVBoxLayout()

        self.area_arrastrar = AreaArrastrar(self)
        layout.addWidget(self.area_arrastrar)

        fila_py = QHBoxLayout()
        self.py_path_edit = QLineEdit()
        self.py_path_edit.setPlaceholderText("Selecciona el archivo .py principal...")
        btn_py = QPushButton("Seleccionar archivo .py")
        btn_py.setMinimumWidth(140)
        btn_py.setMaximumWidth(140)
        fila_py.addWidget(self.py_path_edit)
        fila_py.addWidget(btn_py)
        layout.addLayout(fila_py)

        fila_icono = QHBoxLayout()
        self.icon_path_edit = QLineEdit()
        self.icon_path_edit.setPlaceholderText("Selecciona icono (.ico) (opcional)...")
        btn_icon = QPushButton("Seleccionar icono")
        btn_icon.setMinimumWidth(140)
        btn_icon.setMaximumWidth(140)
        fila_icono.addWidget(self.icon_path_edit)
        fila_icono.addWidget(btn_icon)
        layout.addLayout(fila_icono)

        fila_extra = QHBoxLayout()
        self.extra_files_edit = QLineEdit()
        self.extra_files_edit.setPlaceholderText("Archivos adicionales seleccionados")
        self.extra_files_edit.setReadOnly(True)
        btn_add_files = QPushButton("Agregar archivos adicionales")
        btn_add_files.setMinimumWidth(140)
        btn_add_files.setMaximumWidth(140)
        fila_extra.addWidget(self.extra_files_edit)
        fila_extra.addWidget(btn_add_files)
        layout.addLayout(fila_extra)

        self.extra_files_list = QListWidget()
        self.extra_files_list.setMaximumHeight(80)
        layout.addWidget(self.extra_files_list)

        fila_dist = QHBoxLayout()
        self.dist_path_edit = QLineEdit(self.carpeta_dist)
        self.dist_path_edit.setPlaceholderText("Carpeta para guardar EXE (dist)...")
        btn_dist = QPushButton("Seleccionar carpeta de destino")
        btn_open_dist = QPushButton("Abrir carpeta EXE")
        btn_dist.setMinimumWidth(140)
        btn_open_dist.setMinimumWidth(140)
        fila_dist.addWidget(self.dist_path_edit)
        fila_dist.addWidget(btn_dist)
        fila_dist.addWidget(btn_open_dist)
        layout.addLayout(fila_dist)

        opciones_layout = QHBoxLayout()
        self.chk_onefile = QCheckBox("Empaquetar en un solo archivo (--onefile)")
        self.chk_noconsole = QCheckBox("Ocultar consola (--noconsole)")
        self.chk_collectall = QCheckBox("Recolectar todos los módulos (--collect-all)")
        opciones_layout.addWidget(self.chk_onefile)
        opciones_layout.addWidget(self.chk_noconsole)
        opciones_layout.addWidget(self.chk_collectall)
        layout.addLayout(opciones_layout)

        layout.addWidget(QLabel("Comando a ejecutar (puedes editarlo):"))
        self.command_preview = QLineEdit()
        layout.addWidget(self.command_preview)

        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(0)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        layout.addWidget(QLabel("Log del proceso de construcción:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(200)
        layout.addWidget(self.log_text)

        self.status_label = QLabel()
        layout.addWidget(self.status_label)

        self.btn_build = QPushButton("Construir")
        layout.addWidget(self.btn_build)

        self.setLayout(layout)

        # Conectar eventos
        btn_py.clicked.connect(self.seleccionar_archivo_py)
        btn_icon.clicked.connect(self.seleccionar_archivo_icono)
        btn_add_files.clicked.connect(self.agregar_archivos_adicionales)
        btn_dist.clicked.connect(self.seleccionar_carpeta_dist)
        btn_open_dist.clicked.connect(self.abrir_carpeta_dist)

        self.chk_onefile.stateChanged.connect(self.actualizar_vista_comando)
        self.chk_noconsole.stateChanged.connect(self.actualizar_vista_comando)
        self.chk_collectall.stateChanged.connect(self.on_collectall_cambiado)

        self.py_path_edit.textChanged.connect(self.actualizar_vista_comando)
        self.icon_path_edit.textChanged.connect(self.actualizar_vista_comando)
        self.dist_path_edit.textChanged.connect(self.actualizar_vista_comando)
        self.btn_build.clicked.connect(self.construir_exe)

    def seleccionar_archivo_py(self):
        archivo, _ = QFileDialog.getOpenFileName(self, "Selecciona archivo .py", "", "Archivos Python (*.py)")
        if archivo:
            self.py_path_edit.setText(archivo)

    def seleccionar_archivo_icono(self):
        archivo, _ = QFileDialog.getOpenFileName(self, "Selecciona icono (.ico)", "", "Archivos Icono (*.ico)")
        if archivo:
            self.icon_path_edit.setText(archivo)

    def agregar_archivos_adicionales(self):
        archivos, _ = QFileDialog.getOpenFileNames(self, "Selecciona archivos adicionales")
        if archivos:
            for f in archivos:
                if f not in self.archivos_adicionales:
                    self.archivos_adicionales.append(f)
                    self.extra_files_list.addItem(f)
            self.actualizar_extra_files_entry()

    def actualizar_extra_files_entry(self):
        self.extra_files_edit.setText(", ".join(os.path.basename(f) for f in self.archivos_adicionales))
        self.actualizar_vista_comando()

    def seleccionar_carpeta_dist(self):
        carpeta = QFileDialog.getExistingDirectory(self, "Selecciona carpeta para guardar EXE")
        if carpeta:
            self.dist_path_edit.setText(carpeta)

    def abrir_carpeta_dist(self):
        carpeta = self.dist_path_edit.text()
        if os.path.isdir(carpeta):
            os.startfile(carpeta)
        else:
            QMessageBox.warning(self, "Error", "La carpeta no existe.")

    def on_collectall_cambiado(self, estado):
        if self.chk_collectall.isChecked():
            archivo_py = self.py_path_edit.text()
            if not os.path.isfile(archivo_py):
                QMessageBox.warning(self, "Error", "Por favor selecciona un archivo .py válido antes de elegir módulos!")
                self.chk_collectall.setChecked(False)
                return
            self.modulos_disponibles = obtener_modulos_importados(archivo_py)
            dlg = DialogoSeleccionModulos(self.modulos_disponibles, self.modulos_seleccionados)
            ret = dlg.exec()
            if ret == QDialog.DialogCode.Accepted:
                self.modulos_seleccionados = dlg.obtener_modulos_seleccionados()
            else:
                self.chk_collectall.setChecked(False)
                self.modulos_seleccionados = []
            self.actualizar_vista_comando()
        else:
            self.modulos_seleccionados = []
            self.actualizar_vista_comando()

    def actualizar_vista_comando(self):
        py = self.py_path_edit.text()
        ico = self.icon_path_edit.text()
        dist = self.dist_path_edit.text()
        opciones = []
        if self.chk_onefile.isChecked():
            opciones.append("--onefile")
        if self.chk_noconsole.isChecked():
            opciones.append("--noconsole")
        if self.chk_collectall.isChecked():
            for mod in self.modulos_seleccionados:
                opciones.append(f"--collect-all {mod}")
        if ico:
            opciones.append(f'--icon="{ico}"')
        if dist:
            opciones.append(f'--distpath "{dist}"')
        add_data = []
        for f in self.archivos_adicionales:
            add_data.append(f'--add-data "{f};."')
        cmd = ''
        if py:
            cmd = f'pyinstaller {" ".join(opciones)} {" ".join(add_data)} "{py}"'
        self.command_preview.setText(cmd)

    def construir_exe(self):
        archivo_py = self.py_path_edit.text()
        if not archivo_py or not os.path.isfile(archivo_py):
            QMessageBox.warning(self, "Error", "Por favor selecciona un archivo .py válido.")
            return
        cmd = self.command_preview.text()

        self.status_label.setText("Construyendo...")
        self.progress_bar.show()
        self.progress_bar.setValue(0)
        self.setEnabled(False)
        self.log_text.clear()

        self.thread = HiloConstruccion(cmd, os.path.dirname(archivo_py))
        self.thread.senal_log.connect(self.agregar_log)
        self.thread.senal_terminado.connect(self.al_terminar_construccion)
        self.thread.start()

    def agregar_log(self, texto):
        self.log_text.append(texto)
        self.log_text.verticalScrollBar().setValue(self.log_text.verticalScrollBar().maximum())

    def al_terminar_construccion(self, exito, msg):
        self.progress_bar.hide()
        self.setEnabled(True)
        if exito:
            self.status_label.setText("Construcción completada.")
            self.log_text.append("\n=== Construcción completada ===")
            QMessageBox.information(self, "Información", msg)
        else:
            self.status_label.setText("Error en construcción!")
            self.log_text.append("\n=== Error en construcción ===")
            QMessageBox.warning(self, "Error", msg)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    ventana = ConstructorPyInstaller()
    ventana.show()
    sys.exit(app.exec())
