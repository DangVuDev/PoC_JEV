# Laya Server

Thư mục độc lập chạy `laya-serve` (checkpoint `multilingual`), tách khỏi `PoC/` để Laya và API pipeline không chia sẻ venv/dependency với nhau.

## Cài đặt (đã thực hiện)

```powershell
cd D:\AI\JEV\laya-server
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python.exe -m pip install "laya[serve]"
```

## Chạy server

```powershell
cd D:\AI\JEV\laya-server
.\start.ps1
```

Hoặc chạy tay:
```powershell
$env:LAYA_MODELS = "multilingual"
$env:LAYA_DEVICE = "cpu"
$env:LAYA_PRELOAD = "1"
$env:LAYA_LOG_LEVEL = "info"
.venv\Scripts\laya-serve.exe
```

Mặc định lắng nghe tại `http://127.0.0.1:8000`. Kiểm tra:
```powershell
curl.exe -s http://127.0.0.1:8000/health
```

## Lưu ý

- `laya-server/.venv` độc lập hoàn toàn với `PoC/.venv` — mỗi bên tự quản lý dependency của mình.
- `PoC/.env` cấu hình `DECISION_LAYA_ENDPOINT=http://127.0.0.1:8000/v1/systemone` trỏ tới server này.
- Đổi checkpoint: sửa `LAYA_MODELS` (`multilingual`, `english`, `typed-decisions`, hoặc liệt kê nhiều, cách nhau bằng dấu phẩy để preload nhiều checkpoint cùng lúc — tốn RAM/thời gian tải hơn).
