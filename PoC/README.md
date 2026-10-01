# Decision Pipeline PoC

API gọi các nhà cung cấp mô hình quyết định chuẩn Jev (Laya tự host, OpenRouter Decisions API, ...) qua một endpoint duy nhất, chọn nhà cung cấp bằng tham số `service_platform`. Dùng cho 2 bài toán:

- **P1 Condition Relation** — xác định quan hệ `and` / `or` / `insufficient_evidence` giữa hai vế điều kiện.
- **P2 Performer Lane** — xác định cấu phần thực hiện một bước nghiệp vụ, loại căn cứ, và bước có trộn nhiều tier hay không.

Tài liệu đặc tả nghiệp vụ đầy đủ: [docs/BA_decision_pipeline.md](docs/BA_decision_pipeline.md). Ví dụ lệnh gọi API thật đã kiểm chứng: [TESTAPI.md](TESTAPI.md).

## Kiến trúc

Pipeline 4 chặng, mỗi chặng một thư mục trong `app/pipeline/`:

```
Request {service_platform, input_json}
   │
   ▼
1. Intake (intake.py)            — chọn provider, parse input_json, lọc trường
   ▼
2. Normalizer (normalizer/)      — dựng câu hỏi chuẩn Jev (choice/score/noul)
   ▼
3. RequestExecutor (executor/)   — chọn adapter theo năng lực provider, gửi HTTP
   ▼
4. Response (response/)          — gộp câu hỏi đã phân rã (nếu có), trả nguyên response provider
   ▼
Response = body của provider (header chứa request id, strategy, latency)
```

Thêm một nhà cung cấp chuẩn Jev mới chỉ cần khai báo trong `.env`, không phải sửa code pipeline.

## Yêu cầu

- Python 3.12+
- Một Laya server đang chạy (xem `../laya-server/README.md`) hoặc một API key OpenRouter hợp lệ.

## Cài đặt

```powershell
cd D:\AI\JEV\PoC
py -3.12 -m venv .venv
.venv\Scripts\python.exe -m pip install fastapi httpx pydantic uvicorn pytest
copy .env.example .env
notepad .env   # điền DECISION_OPENROUTER_API_KEY nếu dùng OpenRouter
```

`PoC/.venv` độc lập với venv của `../laya-server/` — hai thư mục không chia sẻ dependency.

## Chạy server

```powershell
cd D:\AI\JEV\PoC
.venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --port 8010
```

Kiểm tra:
```powershell
curl.exe -s http://127.0.0.1:8010/health
curl.exe -s http://127.0.0.1:8010/api/v1/providers
```

## Gọi API

```powershell
curl.exe --% -s -X POST http://127.0.0.1:8010/api/v1/condition-relation/decide -H "Content-Type: application/json; charset=utf-8" -d "{\"service_platform\":\"laya\",\"input_json\":{\"clause_text\":\"...\",\"left_condition\":\"...\",\"right_condition\":\"...\"}}"
```

Chỉ 2 trường được đọc: `service_platform` và `input_json`. Mọi trường khác (`sample_id`, `expected_*`, ...) bị bỏ qua — có thể gửi thẳng một dòng CSV. Response là body nguyên văn của provider. Chi tiết đầy đủ, kể cả cách truyền body đúng trên PowerShell và các trường hợp lỗi: xem [TESTAPI.md](TESTAPI.md).

## Đánh giá trên dữ liệu CSV

```powershell
.venv\Scripts\python.exe scripts\run_csv_through_api.py --task p1 --provider laya --limit 10
.venv\Scripts\python.exe scripts\run_csv_through_api.py --task p2 --provider laya --split dev --limit 10
```

Script gọi API từng dòng CSV, so với cột `expected_*`, in accuracy và coverage theo ngưỡng confidence. Kết quả từng mẫu ghi vào `runs/`.

## Test

```powershell
.venv\Scripts\python.exe -m pytest -q
```

65 test unit/e2e dùng provider giả lập, không cần server thật đang chạy. Test gọi provider thật:
```powershell
$env:DECISION_LIVE_TESTS = "1"
.venv\Scripts\python.exe -m pytest tests\integration -q
```

## Cấu trúc thư mục

```
PoC/
  app/
    main.py                 # FastAPI factory
    config.py                # đọc .env -> ProviderConfig
    errors.py                 # mã lỗi + HTTP status
    api/                       # 3 route: condition-relation, performer-lane, providers
    schemas/                   # request.py (hợp đồng vào), internal.py (dữ liệu giữa các chặng)
    pipeline/
      intake.py                 # chặng 1
      normalizer/                 # chặng 2 — prompts.py, p1_*.py, p2_*.py
      executor/                    # chặng 3 — registry, transport, guards, adapters/
      response/                     # chặng 4 — recombine.py, builder.py
      tasks.py, orchestrator.py, questions.py
  tests/                     # unit/, test_api_e2e.py, integration/ (live)
  scripts/run_csv_through_api.py
  examples/                  # payload mẫu dùng trong TESTAPI.md
  docs/BA_decision_pipeline.md
  .env.example
```

## Trạng thái provider

| Provider | Trạng thái |
|---|---|
| `laya` | Đã kiểm chứng, chạy qua `laya-serve` tự host |
| `openrouter` (model `respan/span-01-lite:free`) | Đã kiểm chứng, cần `DECISION_OPENROUTER_API_KEY` |
| `typesafe` (model `jev-latest`) | Đã kiểm chứng, cần `DECISION_TYPESAFE_ENDPOINT` và `DECISION_TYPESAFE_API_KEY` |
| `vercelgateway` | Chưa kiểm chứng có hỗ trợ API decisions chuẩn Jev hay không |

Xem mục 10 của [BA_decision_pipeline.md](docs/BA_decision_pipeline.md) để biết các câu hỏi còn mở.
