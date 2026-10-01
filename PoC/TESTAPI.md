# Test API — Decision Pipeline PoC

Các lệnh dưới đây đã được chạy thật và xác nhận hoạt động trên máy Windows (PowerShell, `curl.exe` 8.21.0 tại `C:\Windows\system32\curl.exe`) ngày 2026-10-01.

## Lưu ý quan trọng về `curl.exe` trên PowerShell

**Truyền body JSON inline bằng toán tử dừng phân tích `--%` của PowerShell, escape dấu `"` bằng `\"`.**

```powershell
curl.exe --% -s -X POST <url> -H "Content-Type: application/json; charset=utf-8" -d "{\"key\":\"value\"}"
```

`--%` phải đứng ngay sau `curl.exe`, trước mọi tham số khác. Nó bảo PowerShell **không đụng vào** phần phía sau — chuyển thẳng chuỗi cho `curl.exe` xử lý theo quy tắc riêng (giống cmd.exe), nên `\"` escape đúng như JSON thật.

Đã tự kiểm chứng bằng một server echo tạm thời bắt đúng byte thô của request: với `--%`, chuỗi `"không bị khóa đồng sở hữu ư ơ đ"` gửi đi khớp **chính xác từng byte UTF-8** với bản encode chuẩn của Python. Cách này an toàn cho cả tiếng Việt có dấu.

**Không dùng** `-d '{"a":"b"}'` hay `-d '{""a"":""b""}'` khi không có `--%` — PowerShell tự escape chuỗi cho tiến trình ngoài theo quy tắc riêng trước khi `curl.exe` nhận được, cho kết quả **không ổn định**: có lúc chạy đúng, có lúc báo lỗi `JSON decode error` dù nội dung nhìn giống hệt nhau.

Nếu payload quá dài để gõ trên một dòng, dùng file sẽ dễ đọc hơn (vẫn hoạt động đúng, không bắt buộc):
```powershell
curl.exe -s -X POST <url> -H "Content-Type: application/json; charset=utf-8" --data "@path\to\file.json"
```

## Cấu trúc thư mục

`laya-server/` và `PoC/` có `.venv` **riêng biệt hoàn toàn**, không chia sẻ dependency:

```
D:\AI\JEV\
  laya-server\      # chạy laya-serve, venv riêng (torch + laya[serve])
    .venv\
    start.ps1
  PoC\              # API Decision Pipeline, venv riêng (fastapi + httpx + pydantic)
    .venv\
    .env            # cấu hình provider, có API key — không commit
    app\
```

## Chuẩn bị môi trường

```powershell
# 1. Laya tự host (cổng 8000)
cd D:\AI\JEV\laya-server
.\start.ps1

# 2. API Decision Pipeline PoC (cổng 8010) — đọc PoC\.env
cd D:\AI\JEV\PoC
.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --port 8010
```

Kiểm tra cả hai đã sẵn sàng:
```powershell
curl.exe -s http://127.0.0.1:8000/health
curl.exe -s http://127.0.0.1:8010/health
curl.exe -s http://127.0.0.1:8010/api/v1/providers
```

`PoC\.env` hiện bật cả `laya` và `openrouter` (`DECISION_ENABLED_PROVIDERS=laya,openrouter`). Xem [laya-server/README.md](../laya-server/README.md) để biết chi tiết cấu hình Laya.

## 1. P1 — Condition Relation, qua Laya

```powershell
curl.exe --% -s -X POST http://127.0.0.1:8010/api/v1/condition-relation/decide -H "Content-Type: application/json; charset=utf-8" -d "{\"service_platform\":\"laya\",\"input_json\":{\"clause_text\":\"Là tài khoản có trạng thái hoạt động, không bị khóa ghi nợ, không đồng sở hữu và không có người giám hộ.\",\"left_condition\":\"có trạng thái hoạt động\",\"right_condition\":\"không bị khóa ghi nợ\"}}"
```

Kết quả thật (HTTP 200, body nguyên văn của Laya):
```json
{"model":"laya-rl-agent","answers":{"relation":{"type":"choice","choice":"or","probabilities":{"and":0.0841,"or":0.7818,"insufficient_evidence":0.1341},"confidence":0.3901,"answer_confidence":0.7818,"action":{"act_probability":1.0}}},"usage":{"input_tokens":153,"output_tokens":0},"routing":{"model":"multilingual","repo":"convaiinnovations/laya/multilingual","reason":"explicit model='multilingual'","detection":null,"workflow":null}}
```

## 2. P2 — Performer Lane, qua Laya

```powershell
curl.exe --% -s -X POST http://127.0.0.1:8010/api/v1/performer-lane/decide -H "Content-Type: application/json; charset=utf-8" -d "{\"service_platform\":\"laya\",\"input_json\":{\"row_text\":\"Mở webview ID Safe\",\"subject\":{\"text\":\"Hệ thống\",\"resolution\":\"generic\"},\"members\":[{\"id\":\"pmkt_frontend\",\"name\":\"PMKT (Front-end)\",\"tier\":\"client\",\"description\":\"Giao diện website\"},{\"id\":\"pmkt_core\",\"name\":\"PMKT (Core)\",\"tier\":\"server\",\"description\":\"Xử lý nghiệp vụ\"}]}}"
```

Kết quả thật (HTTP 200):
```json
{"model":"laya-rl-agent","answers":{"performer":{"type":"choice","choice":"pmkt_frontend","probabilities":{"pmkt_frontend":0.6649,"pmkt_core":0.103,"insufficient_evidence":0.2321},"confidence":0.2313,"answer_confidence":0.6649,"action":{"act_probability":1.0}},"evidence":{"type":"choice","choice":"object","probabilities":{"object":0.555,"verb":0.132,"context":0.313},"confidence":0.1283,"answer_confidence":0.555,"action":{"act_probability":1.0}},"mixed_lanes":{"type":"noul","noul":0.9655,"confidence":0.9655,"answer_confidence":0.9655,"action":{"act_probability":1.0}}},"usage":{"input_tokens":281,"output_tokens":0},"routing":{"model":"multilingual","repo":"convaiinnovations/laya/multilingual","reason":"explicit model='multilingual'","detection":null,"workflow":null}}
```

## 3. Đổi `service_platform` — cùng dữ liệu, qua OpenRouter

Giống hệt mục 1, chỉ đổi `"service_platform":"openrouter"`:
```powershell
curl.exe --% -s -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8010/api/v1/condition-relation/decide -H "Content-Type: application/json; charset=utf-8" -d "{\"service_platform\":\"openrouter\",\"input_json\":{\"clause_text\":\"x\",\"left_condition\":\"x\",\"right_condition\":\"y\"}}"
```

Kết quả thật khi chưa cấu hình key — HTTP 503:
```
{"error":{"code":"PROVIDER_NOT_CONFIGURED","message":"provider 'openrouter' chưa sẵn sàng: không có trong DECISION_ENABLED_PROVIDERS"}}
HTTP 503
```

Khi đã điền `DECISION_OPENROUTER_API_KEY` thật trong `.env`, thêm `openrouter` vào `DECISION_ENABLED_PROVIDERS` và khởi động lại server, cùng lệnh trên sẽ trả HTTP 200 với `answers.relation` đã được gộp lại từ các câu `noul` phân rã (xem [BA_decision_pipeline.md](docs/BA_decision_pipeline.md) mục 6.1).

## 4. Trường hợp lỗi

### 4.1 Provider không tồn tại (HTTP 400)
```powershell
curl.exe --% -s -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8010/api/v1/condition-relation/decide -H "Content-Type: application/json; charset=utf-8" -d "{\"service_platform\":\"nope\",\"input_json\":{\"clause_text\":\"x\",\"left_condition\":\"x\",\"right_condition\":\"y\"}}"
```
Kết quả thật:
```
{"error":{"code":"UNKNOWN_PROVIDER","message":"service_platform 'nope' không được hỗ trợ. Các giá trị hợp lệ: laya, openrouter, typesafe, vercelgateway"}}
HTTP 400
```

### 4.2 Provider chưa cấu hình (HTTP 503)
Dùng lệnh ở mục 3 khi `openrouter` chưa có key — trả `PROVIDER_NOT_CONFIGURED` như đã thấy ở trên.

### 4.3 Thiếu trường bắt buộc (HTTP 422)
```powershell
curl.exe --% -s -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8010/api/v1/condition-relation/decide -H "Content-Type: application/json; charset=utf-8" -d "{\"service_platform\":\"laya\",\"input_json\":{\"clause_text\":\"x\",\"left_condition\":\"\",\"right_condition\":\"y\"}}"
```
Kết quả thật:
```
{"error":{"code":"MISSING_INPUT_FIELD","message":"thiếu hoặc rỗng trường: left_condition"}}
HTTP 422
```

## 5. Gửi nguyên một dòng CSV (trường thừa bị bỏ qua)

API chỉ đọc `service_platform` và `input_json`; mọi trường khác (`sample_id`, `expected_relation`, `pair_scope`, `label_status`, `options`, ...) bị bỏ qua. Có thể gửi thẳng một dòng CSV đã thêm `service_platform`:

```json
{
  "service_platform": "laya",
  "sample_id": "CR-001",
  "input_json": "{\"clause_text\":\"...\",\"left_condition\":\"...\",\"right_condition\":\"...\"}",
  "pair_scope": "flat",
  "expected_relation": "and",
  "label_status": "curated"
}
```
`input_json` ở dạng chuỗi JSON (như trong CSV gốc) cũng được chấp nhận, không chỉ object.

## 6. Đánh giá hàng loạt trên cả file CSV

Không gọi API thủ công từng dòng — dùng script có sẵn, tự so với nhãn và tính accuracy/coverage theo ngưỡng:

```powershell
cd D:\AI\JEV\PoC
.venv\Scripts\python.exe scripts\run_csv_through_api.py --task p1 --provider laya --limit 10
.venv\Scripts\python.exe scripts\run_csv_through_api.py --task p2 --provider laya --split dev --limit 10
```

Xem chi tiết tham số trong [scripts/run_csv_through_api.py](scripts/run_csv_through_api.py) hoặc mục 8 của [BA_decision_pipeline.md](docs/BA_decision_pipeline.md).

## 7. Chạy test tự động

```powershell
cd D:\AI\JEV\PoC
.venv\Scripts\python.exe -m pytest -q
```
65 test unit/e2e dùng provider giả lập (không cần Laya/OpenRouter đang chạy). Muốn chạy thêm test gọi provider thật:
```powershell
$env:DECISION_LIVE_TESTS = "1"
.venv\Scripts\python.exe -m pytest tests\integration -q
```
