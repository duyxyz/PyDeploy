import os
import ast
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

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

class ExeBuilderApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Python → EXE Builder (Tkinter thuần)")
        self.geometry("720x780")
        self.minsize(700, 700)

        self.extra_files = []
        self.dist_folder = os.path.abspath("dist")
        self.selected_collectall_modules = []

        self.create_widgets()
        self.update_command()

    def create_widgets(self):
        padx = 12
        pady = 8

        self.info_label = tk.Label(self, text="Chọn file .py, icon và các file bổ sung bằng nút bên dưới", fg="blue")
        self.info_label.grid(row=0, column=0, columnspan=3, padx=padx, pady=(pady, pady*2), sticky="w")

        tk.Label(self, text="Chọn file .py chính:", width=25, anchor="w").grid(row=1, column=0, padx=padx, pady=pady, sticky="w")
        self.py_path_var = tk.StringVar()
        self.py_entry = tk.Entry(self, textvariable=self.py_path_var, width=62)
        self.py_entry.grid(row=1, column=1, sticky="ew", padx=padx, pady=pady)
        tk.Button(self, text="Chọn file .py", width=16, command=self.select_py_file).grid(row=1, column=2, padx=padx, pady=pady)

        tk.Label(self, text="Chọn icon (.ico):", width=25, anchor="w").grid(row=2, column=0, padx=padx, pady=pady, sticky="w")
        self.icon_path_var = tk.StringVar()
        self.icon_entry = tk.Entry(self, textvariable=self.icon_path_var, width=62)
        self.icon_entry.grid(row=2, column=1, sticky="ew", padx=padx, pady=pady)
        tk.Button(self, text="Chọn icon", width=16, command=self.select_icon_file).grid(row=2, column=2, padx=padx, pady=pady)

        tk.Label(self, text="Thêm file bổ sung:", width=25, anchor="w").grid(row=3, column=0, padx=padx, pady=pady, sticky="w")
        self.extra_files_var = tk.StringVar()
        self.extra_files_entry = tk.Entry(self, textvariable=self.extra_files_var, width=62, state="readonly")
        self.extra_files_entry.grid(row=3, column=1, sticky="ew", padx=padx, pady=pady)
        tk.Button(self, text="Thêm file", width=16, command=self.select_extra_files).grid(row=3, column=2, padx=padx, pady=pady)

        tk.Label(self, text="Danh sách file bổ sung:", width=25, anchor="nw").grid(row=4, column=0, padx=padx, pady=pady, sticky="nw")
        self.extra_files_listbox = tk.Listbox(self, height=8, width=62)
        self.extra_files_listbox.grid(row=4, column=1, columnspan=2, sticky="nsew", padx=padx, pady=pady)

        tk.Label(self, text="Thư mục lưu EXE:", width=25, anchor="w").grid(row=5, column=0, padx=padx, pady=(pady*2, pady), sticky="w")
        self.dist_path_var = tk.StringVar(value=self.dist_folder)
        self.dist_entry = tk.Entry(self, textvariable=self.dist_path_var, width=62)
        self.dist_entry.grid(row=5, column=1, sticky="ew", padx=padx, pady=(pady*2, pady))

        self.onefile_var = tk.BooleanVar()
        self.noconsole_var = tk.BooleanVar()
        self.collectall_enabled_var = tk.BooleanVar(value=False)

        tk.Checkbutton(self, text="Đóng gói 1 file (--onefile)", variable=self.onefile_var, command=self.update_command).grid(row=6, column=0, sticky="w", padx=padx, pady=pady)
        tk.Checkbutton(self, text="Ẩn console (--noconsole)", variable=self.noconsole_var, command=self.update_command).grid(row=7, column=0, sticky="w", padx=padx, pady=pady)
        tk.Checkbutton(self, text="Thu thập module (--collect-all):", variable=self.collectall_enabled_var,
                       command=self.on_collectall_toggled).grid(row=8, column=0, padx=padx, pady=pady, sticky="w")

        btn_frame = tk.Frame(self)
        btn_frame.grid(row=9, column=0, columnspan=3, sticky="w", padx=padx, pady=pady)

        tk.Button(btn_frame, text="Bỏ chọn tất cả module đã chọn", command=self.clear_collectall_selection).pack(side="left", padx=(0, 15))
        tk.Button(btn_frame, text="Chọn thư mục lưu", command=self.select_dist_folder).pack(side="left", padx=(0, 15))
        tk.Button(btn_frame, text="Mở thư mục EXE", command=self.open_dist_folder).pack(side="left")

        tk.Label(self, text="Lệnh sẽ chạy (có thể sửa):", width=25, anchor="w").grid(row=10, column=0, padx=padx, pady=(pady*2, pady), sticky="w")
        self.command_entry = tk.Entry(self, width=75)
        self.command_entry.grid(row=10, column=1, columnspan=2, sticky="ew", padx=padx, pady=(pady*2, pady))

        self.progress = ttk.Progressbar(self, mode="indeterminate")
        self.progress.grid(row=11, column=0, columnspan=3, sticky="ew", padx=padx, pady=pady)
        self.progress.grid_remove()

        tk.Label(self, text="Log quá trình đóng gói:", width=25, anchor="nw").grid(row=12, column=0, padx=padx, pady=pady, sticky="nw")
        self.log_text = tk.Text(self, height=14, width=62, state="disabled")
        self.log_text.grid(row=12, column=1, columnspan=2, sticky="nsew", padx=padx, pady=pady)

        self.btn_build = tk.Button(self, text="Đóng gói", width=16, command=self.build_exe)
        self.btn_build.grid(row=13, column=1, pady=(pady*2, pady))

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(4, weight=1)
        self.grid_rowconfigure(12, weight=1)

    def select_extra_files(self):
        filetypes = [
            ("Media files", "*.wav *.mp3 *.ogg *.flac *.aac"),
            ("Image files", "*.png *.jpg *.jpeg *.gif *.bmp"),
            ("Text files", "*.txt *.json *.csv"),
            ("All files", "*.*")
        ]
        files = filedialog.askopenfilenames(filetypes=filetypes)
        for f in files:
            if f not in self.extra_files:
                self.extra_files.append(f)
                self.extra_files_listbox.insert(tk.END, os.path.basename(f))
        self.extra_files_var.set(", ".join([os.path.basename(x) for x in self.extra_files]))
        self.update_command()

    def on_collectall_toggled(self):
        if self.collectall_enabled_var.get():
            self.open_collectall_popup()
        else:
            self.selected_collectall_modules = []
            self.update_command()

    def open_collectall_popup(self):
        pyfile = self.py_path_var.get()
        if not os.path.isfile(pyfile):
            messagebox.showwarning("Lỗi", "Vui lòng chọn file .py hợp lệ trước khi chọn module!")
            self.collectall_enabled_var.set(False)
            return

        modules = get_imported_modules(pyfile)
        if not modules:
            messagebox.showinfo("Thông báo", "Không tìm thấy module nào trong file .py!")
            self.collectall_enabled_var.set(False)
            return

        popup = tk.Toplevel(self)
        popup.title("Chọn module để collect-all")
        popup.geometry("350x400")
        popup.transient(self)
        popup.grab_set()

        vars = {}
        frame = tk.Frame(popup)
        frame.pack(fill="both", expand=True, padx=10, pady=10)

        canvas = tk.Canvas(frame)
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas)

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        for m in modules:
            var = tk.BooleanVar(value=m in self.selected_collectall_modules)
            cb = tk.Checkbutton(scroll_frame, text=m, variable=var, anchor="w")
            cb.pack(fill="x", padx=2, pady=1)
            vars[m] = var

        def on_ok():
            self.selected_collectall_modules = [m for m, v in vars.items() if v.get()]
            popup.destroy()
            self.update_command()

        def on_cancel():
            self.collectall_enabled_var.set(False)
            popup.destroy()

        btn_frame = tk.Frame(popup)
        btn_frame.pack(pady=5)
        tk.Button(btn_frame, text="OK", width=10, command=on_ok).pack(side="left", padx=5)
        tk.Button(btn_frame, text="Hủy", width=10, command=on_cancel).pack(side="left", padx=5)

    def clear_collectall_selection(self):
        self.selected_collectall_modules = []
        self.collectall_enabled_var.set(False)
        self.update_command()

    def select_py_file(self):
        file = filedialog.askopenfilename(filetypes=[("Python files", "*.py")])
        if file:
            self.py_path_var.set(file)

    def select_icon_file(self):
        file = filedialog.askopenfilename(filetypes=[("Icon files", "*.ico")])
        if file:
            self.icon_path_var.set(file)

    def select_dist_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.dist_path_var.set(folder)

    def open_dist_folder(self):
        folder = self.dist_path_var.get()
        if os.path.isdir(folder):
            os.startfile(folder)
        else:
            messagebox.showwarning("Lỗi", "Thư mục không tồn tại.")

    def update_command(self):
        py = self.py_path_var.get()
        ico = self.icon_path_var.get()
        dist = self.dist_path_var.get()
        options = []
        if self.onefile_var.get():
            options.append("--onefile")
        if self.noconsole_var.get():
            options.append("--noconsole")

        if self.collectall_enabled_var.get():
            for mod in self.selected_collectall_modules:
                options.append(f"--collect-all {mod}")

        if ico:
            options.append(f'--icon="{ico}"')
        if dist:
            options.append(f'--distpath "{dist}"')

        add_data = []
        for f in self.extra_files:
            add_data.append(f'--add-data "{f};."')

        if py:
            cmd = f'pyinstaller {" ".join(options)} {" ".join(add_data)} "{py}"'
            self.command_entry.delete(0, tk.END)
            self.command_entry.insert(0, cmd)
        else:
            self.command_entry.delete(0, tk.END)

    def build_exe(self):
        py_file = self.py_path_var.get()
        if not py_file or not os.path.isfile(py_file):
            messagebox.showwarning("Lỗi", "Vui lòng chọn file .py hợp lệ.")
            return
        cmd = self.command_entry.get()

        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state=tk.DISABLED)

        self.progress.grid()
        self.progress.start(10)
        self.btn_build.config(state=tk.DISABLED)

        threading.Thread(target=self.run_build_thread, args=(cmd, os.path.dirname(py_file)), daemon=True).start()

    def run_build_thread(self, cmd, cwd):
        try:
            process = subprocess.Popen(cmd, shell=True, cwd=cwd,
                                       stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT,
                                       bufsize=1,
                                       universal_newlines=True,
                                       encoding="utf-8")
            for line in process.stdout:
                self.append_log(line.rstrip())
            process.wait()
            if process.returncode == 0:
                self.append_log("\n=== Đã đóng gói xong ===")
                self.show_message("Hoàn tất", "Đã đóng gói xong.")
            else:
                self.append_log("\n=== Lỗi đóng gói ===")
                self.show_message("Lỗi", "Đóng gói thất bại. Xem log để biết chi tiết.")
        except Exception as e:
            self.append_log(f"\nLỗi: {e}")
            self.show_message("Lỗi", str(e))
        finally:
            self.progress.stop()
            self.progress.grid_remove()
            self.btn_build.config(state=tk.NORMAL)

    def append_log(self, text):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def show_message(self, title, msg):
        messagebox.showinfo(title, msg)

if __name__ == "__main__":
    app = ExeBuilderApp()
    app.mainloop()
