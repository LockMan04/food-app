# Food Detection & Recipe App

## Giới thiệu
Food Detection & Recipe App là ứng dụng AI giúp nhận diện nguyên liệu từ ảnh và gợi ý công thức món ăn Việt Nam. Ứng dụng kết hợp mô hình YOLO để nhận diện hình ảnh và mô hình ngôn ngữ lớn để sinh công thức, mẹo nấu ăn, trả lời câu hỏi về món ăn.

## Tính năng chính
- Nhận diện nguyên liệu từ ảnh chụp.
- Gợi ý công thức món ăn Việt Nam dựa trên nguyên liệu nhận diện được.
- Chat hỏi đáp về món ăn: thời gian nấu, mẹo, khẩu phần, v.v.
- Hỗ trợ thay đổi mô hình AI dễ dàng.
- Giao diện web trực quan, dễ sử dụng.

Ứng dụng nhận diện nguyên liệu từ ảnh và gợi ý công thức món ăn Việt Nam bằng AI

## 1. Yêu cầu hệ thống
- Python 3.8+
- Node.js 16+
- pip (Python package manager)

## 2. Cài đặt Backend (Flask + YOLO + LM Studio)

### Bước 1: Cài đặt Python packages

```bash
pip install -r requirements.txt
```

### Bước 2: Chuẩn bị mô hình YOLO
- Đặt file mô hình YOLO đã train (`best.pt`) vào thư mục `models/` (tạo thư mục nếu chưa có).
- Đảm bảo đường dẫn trong `main.py` là `./models/best.pt`.

> Tải xuống mô hình YOLOv11 đã fine-tune sẵn của tôi [best.pt](https://drive.google.com/uc?export=download&id=18FB3cotnpbXoBS-WSHhLJ4r1YmL_j5Kc
)

### Bước 3: Cài đặt và chạy LM Studio (hoặc OpenAI API local)
- Tải và cài LM Studio: https://lmstudio.ai/
- Chọn model hỗ trợ chat (ví dụ: Google Gemma, Llama, v.v.)
- Chạy LM Studio ở chế độ API server (mặc định: http://localhost:1234/v1)

### Bước 4: Chạy server Flask

```bash
python main.py
```
- Server sẽ chạy tại: http://localhost:5000

## 3. Cài đặt Frontend (React)

### Bước 1: Cài đặt dependencies

```bash
npm install
```

### Bước 2: Chạy ứng dụng React

```bash
npm start
```
- Ứng dụng sẽ chạy tại: http://localhost:3000

## 4. Sử dụng
- Upload ảnh nguyên liệu ở panel bên trái.
- Nhấn "Tạo Công Thức Món Ăn" để nhận gợi ý công thức.
- Có thể hỏi thêm về thời gian nấu, mẹo, khẩu phần, v.v. ở phần chat.

## 5. API Backend
- `POST /detect`: Nhận diện nguyên liệu từ ảnh (multipart/form-data, key: `image`)
- `GET /classes`: Lấy danh sách nguyên liệu mà model nhận diện được
- `POST /generate-recipe`: Sinh công thức từ danh sách nguyên liệu (JSON: `{ "ingredients": ["...", ...] }`)
- `POST /generate-questions`: Sinh câu hỏi thông minh về món ăn

## 6. Lưu ý
- Nếu gặp lỗi YOLO model, kiểm tra lại file `best.pt` và thư mục `models/`.
- Nếu gặp lỗi LM Studio, kiểm tra LM Studio đã chạy ở chế độ API server chưa.
- Có thể thay đổi model AI bằng cách đổi tên model trong `main.py`.

## 7. Liên hệ & đóng góp
- Mọi ý kiến đóng góp hoặc báo lỗi, vui lòng tạo issue hoặc liên hệ trực tiếp qua Github.
