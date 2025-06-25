[![Download PyDeploy](https://a.fsdn.com/con/app/sf-download-button)](https://sourceforge.net/projects/pydeploy-app/files/latest/download)

This `PyDeploy.py` script is a GUI application built with PyQt6 that serves as a PyInstaller builder. It simplifies the process of converting Python scripts into standalone executable files.

Here's a README.md for the provided Python script:

-----

# PyInstaller Builder (PyQt6)

PyInstaller Builder is a graphical user interface (GUI) application developed with PyQt6 to streamline the process of packaging Python applications into standalone executables using PyInstaller.

## Features

  * **Select Main Python File**: Easily choose your main `.py` script.
  * **Select Icon**: Add a custom icon (`.ico` file) for your executable.
  * **Add Extra Files**: Include additional files or directories (e.g., data files, images, configuration files) that your application needs.
  * **Choose Output Directory**: Specify where the final executable will be saved.
  * **One-file Option**: Package your application into a single executable file (`--onefile`).
  * **No Console Option**: Create an executable that runs without a console window (`--noconsole`), ideal for GUI applications.
  * **Collect All Modules**: Automatically detect and allow selection of imported modules for the `--collect-all` option, useful for modules that PyInstaller might miss.
  * **Drag and Drop Support**: Drag `.py` files, `.ico` files, or other additional files directly into the application window.
  * **Live Command Preview**: See the `pyinstaller` command being constructed in real-time as you select options.
  * **Build Log**: View the output of the PyInstaller build process directly within the application.
  * **Open Output Folder**: Conveniently open the directory where your executable is saved after the build.

## How to Use

### Prerequisites

Before running this application, you need to have:

1.  **Python 3**: Make sure Python 3 is installed on your system.
2.  **PyQt6**: Install PyQt6 using pip:
    ```bash
    pip install PyQt6
    ```
3.  **PyInstaller**: Install PyInstaller using pip:
    ```bash
    pip install pyinstaller
    ```

### Running the Application

1.  Save the provided Python script as `PyDeploy.py` (or any other name).
2.  Run the script from your terminal:
    ```bash
    python PyDeploy.py
    ```

### Building Your Executable

1.  **Select main `.py` file**: Click "Chọn file .py" and browse to your application's main Python script. You can also drag and drop a `.py` file into the window.
2.  **Select icon (optional)**: Click "Chọn icon" and choose an `.ico` file for your executable. You can also drag and drop an `.ico` file.
3.  **Add extra files (optional)**: Click "Thêm file" to include any additional files or folders that your application depends on. These will be bundled with your executable. You can drag and drop any file to add it to the extra files list. Click "Xem các file đã thêm" to review the list of added files.
4.  **Choose output directory (optional)**: By default, the output will be saved in a `dist` folder next to the script. Click "Chọn thư mục lưu" to change this.
5.  **Select options**:
      * **Đóng gói 1 file (--onefile)**: Check this if you want a single executable file.
      * **Ẩn console (--noconsole)**: Check this to hide the console window when your application runs (recommended for GUI apps).
      * **Thu thập module (--collect-all)**: Check this to specify modules that PyInstaller should explicitly collect. When checked, a dialog will appear showing modules detected in your main `.py` file, allowing you to select which ones to include. You can click "Bỏ chọn tất cả module đã chọn" to clear your selections.
6.  **Review Command**: The "Lệnh sẽ chạy (có thể sửa):" field will display the `pyinstaller` command that will be executed. You can manually edit this if needed.
7.  **Build**: Click the "Đóng gói" button to start the PyInstaller build process.
8.  **View Log**: The "Log quá trình đóng gói:" area will display the output from PyInstaller, showing the progress and any potential errors.
9.  **Open EXE Folder**: Once the build is complete, you can click "Mở thư mục EXE" to navigate to the output directory containing your executable.

## Troubleshooting

  * **"Lỗi đóng gói. Xem log để biết chi tiết."**: If you encounter this message, review the "Log quá trình đóng gói" area for specific error messages from PyInstaller. Common issues include missing modules, incorrect paths, or syntax errors in your script.
  * **Missing Modules**: If your application crashes or reports missing modules, try using the "Thu thập module (--collect-all)" option to explicitly include them.
  * **Antivirus Software**: Sometimes, antivirus software can interfere with PyInstaller's creation of executables. If you experience issues, consider temporarily disabling your antivirus or adding an exclusion for your project directory.

-----
