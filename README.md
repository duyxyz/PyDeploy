

**PyDeloy** là ứng dụng giúp bạn đóng gói file Python (.py) thành file thực thi (.exe) cho Windows chỉ với vài cú click chuột.

---

## Tính năng nổi bật

- **Kéo thả** file .py, .ico, .wav vào một ô lớn – nhận diện tự động loại file.
- **Thêm icon** cho file .exe dễ dàng.
- **Nhúng nhiều file phụ** (.wav) trực tiếp vào EXE.
- **Chọn thư mục lưu EXE** tuỳ ý, không bắt buộc “dist”.
- **Xem log đóng gói** chi tiết ngay trên giao diện, kèm thanh tiến trình.
- **Tùy chỉnh lệnh PyInstaller** nâng cao nếu bạn là coder.

---

## Hướng dẫn sử dụng

1. **Cài PyInstaller trước khi dùng:**  
   Mở CMD và chạy: ` pip install pyinstaller `

2. **Chạy ứng dụng `PyDeploy`:**  
- Kéo thả file .py, .ico, .wav vào ô lớn, hoặc chọn qua các nút.
- Tuỳ chỉnh icon, file WAV và các tuỳ chọn khác nếu muốn.
- Chọn thư mục lưu file .exe.
- Bấm **"Đóng gói"** và chờ hoàn tất.

3. **Mở thư mục chứa EXE** bằng nút “Mở thư mục EXE”.

---

## Yêu cầu hệ thống

- Python : https://www.python.org/downloads/release/python-3133/
- PyQt6 - PyInstaller 

```
   pip install pyqt6 pyinstaller
```


- Windows 10/11



## Lưu ý

- Nếu đóng gói không thành công, vui lòng xem chi tiết log trên giao diện để khắc phục lỗi.
- App hoạt động tốt nhất với script .py chuẩn (main entry).


