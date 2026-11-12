# E-Commercial Book Store — Team 3 (Release 1.0)

Web bán sách cho đồ án **Software Project Management (72ITSE41503) – VLU, HK261**.
Phạm vi được làm đúng theo *Product Backlog* trong `HK261_SPM_FP_Team3_SprintBacklog.xlsx`
và được kiểm thử theo `HK261_SPM_FP_Team3_TestCase.xlsx` (BM1/BM2).

Stack: **Python 3.10+ · Flask · SQLite** (không cần cài database riêng), giao diện render phía server, responsive.

## Chạy thử

```bash
pip install -r requirements.txt
python wsgi.py            # http://127.0.0.1:5000
python -m pytest -q       # chạy 65 test tự động
```

Lần chạy đầu tiên tự tạo `instance/bookstore.sqlite3` và dữ liệu mẫu (32 sách, 5 danh mục, 8 tác giả).

Tài khoản **test** (chỉ dùng cho môi trường demo/QA — hãy đổi mật khẩu khi deploy):

| Vai trò | Email | Mật khẩu |
|---|---|---|
| Administrator | `admin@bookstore.test` | `Admin@12345` |
| Customer | `customer@bookstore.test` | `Customer@123` |

Biến môi trường: `SECRET_KEY` (bắt buộc đặt khi deploy), `DATABASE_PATH`, `SEED_DEMO_DATA=0` để tắt dữ liệu mẫu, `PORT`.
Deploy (Render/Railway…): `gunicorn wsgi:app`.

## Phạm vi theo Product Backlog

| Story | Sprint | Chức năng | Nơi xử lý |
|---|---|---|---|
| US-01 | S1 | Đăng ký tài khoản Customer, hash mật khẩu, mật khẩu 8–64 ký tự, lỗi theo từng field, server trả 400 | `bookstore/auth.py`, `validation.py` |
| US-02 | S1 | Đăng nhập/đăng xuất, Customer → storefront, Admin → Staff workspace, thông báo chung "Invalid email or password", chuẩn hoá email, chặn Back/URL sau khi đăng xuất | `auth.py`, `security.py` |
| US-11 | S1 | Admin tạo tài khoản (Customer/Administrator), role khác → HTTP 400 | `staff.py` → `/staff/accounts` |
| US-19 | S1 | Khoá/mở khoá tài khoản có hộp xác nhận, user đang đăng nhập bị đá ra kèm thông báo, admin không tự khoá mình (kể cả gọi thẳng server) | `staff.py`, `security.py` |
| US-09 | S2 | Thêm/sửa sách, validate client + server, giá phải > 0 | `/staff/books` |
| US-21 | S2 | Xoá mềm (ẩn khỏi cửa hàng, giữ bản ghi), Customer bị 403 | `/staff/books/<id>/delete` |
| US-22 | S2 | Quản lý danh mục, chặn tên rỗng/trùng (không phân biệt hoa thường) | `/staff/categories` |
| US-23 | S2 | Quản lý tác giả, sách liên kết theo `author_id` | `/staff/authors` |
| US-03 | S2 | Lưới sách (bìa, tên, tác giả, giá), mới nhất trước, 12 sách/trang | `catalog.py` → `/` |
| US-14 | S2 | Tồn kho riêng 3 cửa hàng cố định: District 1, District 3, Thu Duc City; không âm | form sách |
| US-04 | S3 | Trang chi tiết sách (tên, tác giả, danh mục, giá, mô tả, bìa, tồn kho), sách ẩn không xem được | `/books/<id>` |
| US-15 | S3 | Sách không tồn tại → "Book not found" + nút "Back to books" | `catalog/not_found.html` |
| US-16 | S3 | Quay lại đúng trang/bộ lọc của danh sách | tham số `back` |
| US-05 | S3 | Tìm theo tên sách hoặc tác giả (không phân biệt hoa thường, hỗ trợ tiếng Việt), trạng thái rỗng, giữ từ khoá khi phân trang | `/` `?q=` |
| US-17 | S3 | Lọc theo danh mục, giữ khi phân trang | `?category=` |
| US-18 | S3 | Lọc theo khoảng giá (bao gồm 2 đầu), chặn giá âm / min > max, kết hợp với từ khoá + danh mục | `?min_price=&max_price=` |

**CR-03 (bản gốc):** chỉ làm bản MVP 3 cửa hàng cố định trong form sách (US-14) như ghi chú phạm vi.
Phần CR-03 gốc (thêm cửa hàng động, nhãn "Out of stock" ở catalogue — AC-CR03.1/.4) **không** làm vì
ChangeLog ghi *Pending CCB*. Trang chi tiết vẫn hiển thị số lượng từng cửa hàng theo US-04 AC1.

## Test

`tests/` có 65 test tự động; tên hàm mang mã test case của BM2 (ví dụ `test_TC_19_04_admin_cannot_lock_self`)
để đối chiếu với BM1 Traceability. Các TC-CR03-xx không có test vì CR-03 gốc chưa được duyệt.
Kết quả chạy test tự động **không** thay cho việc nhóm tự chạy BM3 RunLog trên môi trường staging và ghi bằng chứng.

## Cấu trúc

```
bookstore/
  __init__.py     app factory, headers no-store, error pages
  db.py           schema SQLite + dữ liệu mẫu
  security.py     nạp user mỗi request, login/admin guard, CSRF
  validation.py   validate tài khoản dùng chung (US-01/US-11)
  auth.py         đăng ký, đăng nhập, đăng xuất, tài khoản
  catalog.py      danh sách, tìm kiếm/lọc, chi tiết, ảnh bìa mẫu
  staff.py        Staff workspace: tài khoản, sách, danh mục, tác giả
  templates/  static/
tests/            pytest, đặt tên theo TC-xx-yy
wsgi.py           entry point
```
