# Đặc tả nghiệp vụ (BA) — Decision Pipeline API cho P1 Condition Relation và P2 Performer Lane

| Mục | Giá trị |
|---|---|
| Phiên bản | 0.2 |
| Ngày | 2026-09-30 |
| Thay đổi so với 0.1 | Mỗi request xử lý đúng **1 mẫu**. Đầu vào chỉ còn `service_platform` + `input_json`. Đầu ra trả **nguyên response của provider**. Việc chấm đúng/sai và áp ngưỡng chuyển sang script đánh giá, không nằm trong API. |
| Code | `PoC/app/` |

---

## 0. Bối cảnh và mục tiêu

### 0.1 Vấn đề
Hai bài toán đang có dữ liệu mẫu:
- **P1 Condition Relation** (`p1_condition_relation_poc_200_1.csv`): cho một câu điều khoản và hai vế điều kiện, xác định quan hệ `and` / `or` / `insufficient_evidence`.
- **P2 Performer Lane** (`p2_performer_lane_poc_200_1.csv`): cho một dòng mô tả bước và danh sách cấu phần (`members`), xác định cấu phần thực hiện (`performer`), loại căn cứ (`evidence`) và bước có trộn nhiều tier hay không (`mixed_lanes`).

Có nhiều nhà cung cấp mô hình quyết định cùng theo chuẩn Jev: Laya tự host, OpenRouter Decisions API, TypeSafe Jev, Vercel AI Gateway. Mỗi bên khác nhau ở endpoint, cách xác thực và loại câu hỏi hỗ trợ. Hệ thống nghiệp vụ cần gọi **một API duy nhất**, còn việc chọn nhà cung cấp chỉ là **một tham số**.

### 0.2 Mục tiêu
1. Cung cấp 2 API: một cho P1, một cho P2. Mỗi request là một mẫu.
2. Xử lý theo pipeline 4 chặng tách biệt: **Tiếp nhận → Chuẩn hóa → Thực thi → Trả kết quả**.
3. `RequestExecutor` chọn nhà cung cấp theo `service_platform`, đọc endpoint, key và model từ `.env`.
4. Trả lại response của nhà cung cấp gần như nguyên văn. Hệ thống không diễn giải, không chấm điểm, không áp ngưỡng.
5. Thêm một nhà cung cấp chuẩn Jev mới chỉ cần khai báo trong `.env`.

### 0.3 Ngoài phạm vi API
- Xử lý nhiều mẫu trong một request. Muốn chạy cả file CSV thì gọi lặp; script `scripts/run_csv_through_api.py` làm việc này.
- So với nhãn, tính accuracy, coverage theo ngưỡng 0.8/0.9: làm trong script đánh giá.
- Chọn model theo từng request: model lấy từ `.env` của từng provider.

### 0.4 Sự thật đã kiểm chứng (ràng buộc thiết kế)

| # | Sự thật | Nguồn kiểm chứng |
|---|---|---|
| F1 | Laya `POST /v1/systemone` nhận `state` là chuỗi hoặc object, hỗ trợ `choice`/`score`/`noul`. Response gồm `model`, `answers`, `usage`, `routing`. | Gọi thật |
| F2 | Câu `noul` dùng `criteria` là `{"true": ..., "false": ...}`, giống nhau ở Laya và Respan. | `laya/common.py` + lỗi 400 thật của Respan |
| F3 | OpenRouter `POST https://openrouter.ai/api/alpha/decisions`, xác thực `Authorization: Bearer <key>`, body `{state, questions, model}`. | Curl thật, HTTP 200 |
| F4 | Model `respan/span-01-lite:free` **chỉ nhận câu `noul`** và `state` phải là chuỗi. | Lỗi 400 thật |
| F5 | Response Respan: `{"model", "answers": {qid: {"type":"noul","noul": p}}, "usage", "id", "provider"}`. `model` trả về có thể khác tên đã gửi. | Response thật |

**Hệ quả thiết kế:** loại câu hỏi mà bài toán cần (ví dụ `choice` 3 lựa chọn) có thể không được provider hỗ trợ (Respan chỉ có `noul`). Vì vậy chặng 3 có bước **thích ứng theo năng lực provider**, và chặng 4 phải **gộp lại** kết quả phân rã để client luôn nhận được câu trả lời theo câu hỏi gốc.

---

## 1. Kiến trúc tổng thể

```
 Client
   │  POST /api/v1/condition-relation/decide   {service_platform, input_json}
   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ CHẶNG 1 — Intake            app/pipeline/intake.py                  │
│  chọn provider, parse input_json, lọc trường, kiểm tra bắt buộc     │
└──────────────┬──────────────────────────────────────────────────────┘
               ▼ IntakeRecord
┌─────────────────────────────────────────────────────────────────────┐
│ CHẶNG 2 — Normalizer        app/pipeline/normalizer/                │
│  input -> CanonicalDecisionRequest chuẩn Jev (choice|score|noul)    │
│  không biết gì về provider                                          │
└──────────────┬──────────────────────────────────────────────────────┘
               ▼ CanonicalDecisionRequest
┌─────────────────────────────────────────────────────────────────────┐
│ CHẶNG 3 — RequestExecutor   app/pipeline/executor/                  │
│  3a registry: service_platform -> ProviderConfig (.env)             │
│  3b adapter: jev_native | noul_decomposition                        │
│  3c guard chống rò rỉ nhãn  3d transport: auth, retry, rate limit   │
└──────────────┬──────────────────────────────────────────────────────┘
               ▼ ExecutionResult (response thô + kế hoạch phân rã)
┌─────────────────────────────────────────────────────────────────────┐
│ CHẶNG 4 — Response          app/pipeline/response/                  │
│  4a recombine: gộp câu noul đã phân rã về câu gốc (nếu có)          │
│  4b builder: trả nguyên response provider                           │
└──────────────┬──────────────────────────────────────────────────────┘
               ▼
        Body = response của provider; metadata vận hành nằm ở header
```

---

## 2. Hợp đồng API

### 2.1 Endpoint

| Method | Path | Mô tả |
|---|---|---|
| `POST` | `/api/v1/condition-relation/decide` | P1, một mẫu |
| `POST` | `/api/v1/performer-lane/decide` | P2, một mẫu |
| `GET` | `/api/v1/providers` | Danh sách provider, trạng thái bật/tắt. **Không trả API key thật** (chỉ bản đã che). |
| `GET` | `/health` | Trạng thái dịch vụ |

### 2.2 Request
```json
{
  "service_platform": "laya",
  "input_json": {
    "clause_text": "Là tài khoản có trạng thái hoạt động, không bị khóa ghi nợ, ...",
    "left_condition": "có trạng thái hoạt động",
    "right_condition": "không bị khóa ghi nợ"
  }
}
```

| Trường | Bắt buộc | Kiểu | Quy tắc |
|---|---|---|---|
| `service_platform` | có | string | Tên provider đã bật trong `.env`, không phân biệt hoa thường. |
| `input_json` | có | object hoặc chuỗi JSON | Nội dung giống cột `input_json` của CSV. |
| Mọi trường khác | — | — | **Bị bỏ qua**, ví dụ `sample_id`, `expected_*`, `pair_scope`, `label_status`, `split`, `options`. Nhờ vậy client có thể gửi nguyên một dòng CSV. |

Trường dùng trong `input_json`. Khóa khác trong `input_json` bị loại bỏ trước khi đi tiếp.

| Bài toán | Bắt buộc, không rỗng | Tùy chọn |
|---|---|---|
| P1 | `clause_text`, `left_condition`, `right_condition` | — |
| P2 | `row_text`; `members` có ít nhất 1 phần tử, mỗi phần tử có `id` không rỗng, không trùng nhau và khác `insufficient_evidence` | `subject`, `substeps`, `hints`, `members[].name/tier/description` |

### 2.3 Response thành công (HTTP 200)
**Body là response của provider.**

Laya (`jev_native`): giữ nguyên nội dung JSON: đủ khóa, đủ giá trị, không thêm bớt. Khoảng trắng và định dạng có thể khác, vì body được đọc rồi ghi lại.
```json
{"model":"laya-rl-agent",
 "answers":{"relation":{"type":"choice","choice":"and",
   "probabilities":{"and":0.4063,"or":0.3651,"insufficient_evidence":0.2286},
   "confidence":0.025,"answer_confidence":0.4063,"action":{"act_probability":1.0}}},
 "usage":{"input_tokens":283,"output_tokens":0},
 "routing":{"model":"typed-decisions", "...": "..."}}
```

OpenRouter/Respan (`noul_decomposition`): giữ nguyên mọi trường (`model`, `usage`, `id`, `provider`). Chỉ riêng `answers` được gộp từ các câu con `relation__0..2` về câu gốc, theo đúng định dạng `choice` của Jev:
```json
{"model":"respan/span-01-lite-20260925",
 "answers":{"relation":{"type":"choice","choice":"and",
   "probabilities":{"and":0.5107,"or":0.0393,"insufficient_evidence":0.1652}}},
 "usage":{"input_tokens":373,"output_tokens":0,"cost":0},
 "id":"gen-dec-...","provider":"Respan"}
```
> Lưu ý khi đọc kết quả: với `noul_decomposition`, `probabilities` là xác suất **độc lập** của từng câu `noul`, tổng không nhất thiết bằng 1. Không so sánh trực tiếp với `probabilities` dạng softmax của Laya khi chưa hiệu chỉnh riêng.

Header vận hành (không đưa vào body để body giữ nguyên như provider trả):

| Header | Ý nghĩa |
|---|---|
| `X-Request-ID` | Mã truy vết, trùng với log server |
| `X-Service-Platform` | Provider đã gọi |
| `X-Strategy` | `jev_native` hoặc `noul_decomposition` |
| `X-Provider-Latency-Ms` | Thời gian gọi provider |

### 2.4 Response lỗi
```json
{"error": {"code": "PROVIDER_REJECTED_REQUEST", "message": "provider 'openrouter' từ chối request",
           "provider_status": 400,
           "provider_error": {"error": {"message": "Respan only accepts noul questions ...", "code": 400}}}}
```
Khi lỗi đến từ provider, `provider_status` và `provider_error` chứa **nguyên văn** lỗi của provider. Chỉ API key bị che nếu provider lỡ phản hồi lại key. Danh mục mã lỗi ở mục 7.

---

## 3. CHẶNG 1 — Tiếp nhận (`intake.py`)

| Bước | Hành động | Lỗi nếu vi phạm |
|---|---|---|
| 1.0 | Pydantic kiểm tra có `service_platform` (không rỗng) và `input_json`. | 422 `VALIDATION_ERROR` |
| 1.1 | Tra provider trong registry. | 400 `UNKNOWN_PROVIDER` / 503 `PROVIDER_NOT_CONFIGURED` |
| 1.2 | Lấy model từ `DECISION_<P>_DEFAULT_MODEL`. | 503 `PROVIDER_NOT_CONFIGURED` nếu trống |
| 1.3 | Nếu `input_json` là chuỗi thì `json.loads`; kết quả phải là object. | 422 `INVALID_INPUT_JSON` |
| 1.4 | Chỉ giữ các khóa đầu vào đã khai báo (mục 2.2). | — |
| 1.5 | Kiểm tra trường bắt buộc theo bài toán. | 422 `MISSING_INPUT_FIELD` |
| 1.6 | Sinh `request_id` và ghi log `intake.accepted`. Không log nội dung `input_json`. | — |

**Chống rò rỉ nhãn:** có 2 lớp bảo vệ. (1) Trường thừa ở cấp request bị Pydantic bỏ qua, khóa lạ trong `input_json` bị lọc ở bước 1.4. (2) Ngay trước khi gửi, chặng 3 kiểm tra payload không chứa khóa nào trong `FORBIDDEN_PAYLOAD_KEYS` (`sample_id`, `split`, `label_status`, `pair_scope`, `expected_*`). Nếu có, request bị chặn với lỗi 500 `LABEL_LEAK_BLOCKED`.

**Acceptance criteria**
- [x] Nhận `input_json` dạng object lẫn chuỗi.
- [x] Gửi nguyên một dòng CSV (kèm `sample_id`, `expected_*`, `options`) vẫn trả 200, và provider không nhận được các trường đó.
- [x] Thiếu trường bắt buộc trả 422 với mã lỗi rõ ràng.

---

## 4. CHẶNG 2 — Chuẩn hóa (`normalizer/`)

### 4.1 Loại câu hỏi chọn theo từng trường kết quả
| Bài toán | Câu hỏi (qid) | Loại | Lựa chọn |
|---|---|---|---|
| P1 | `relation` | `choice` | `and`, `or`, `insufficient_evidence` (thứ tự cố định) |
| P2 | `performer` | `choice` | `members[].id` của chính mẫu, cộng `insufficient_evidence` |
| P2 | `evidence` | `choice` | `object`, `verb`, `context` |
| P2 | `mixed_lanes` | `noul` | true / false |

Builder `score` có sẵn trong `questions.py` và đã có test, để dùng cho bài toán sau này.

### 4.2 Dựng state
- **P1:** `Câu điều khoản: …\nVế 1: …\nVế 2: …`
- **P2:** `row_text`, cộng thêm `subject.text` và `substeps[].quote` nếu có. `members` chỉ nằm trong `criteria` của `performer`, không lặp lại trong state.
- State luôn được dựng thành chuỗi, để mọi provider nhận **cùng một nội dung**. Provider nào hỗ trợ object có thể chuyển sang dạng object bằng `DECISION_<P>_STATE_FORMAT=object`.

### 4.3 Prompt có phiên bản
Nội dung `instructions`/`criteria` nằm trong `normalizer/prompts.py`, theo khóa phiên bản (`p1.v1`, `p2.v1`). Khi sửa prompt thì tạo phiên bản mới, không sửa phiên bản cũ.

**Acceptance criteria**
- [x] P1 sinh 1 câu `choice` gồm đúng 3 lựa chọn theo thứ tự cố định.
- [x] P2 `performer` có `len(members) + 1` lựa chọn.
- [x] Cùng một đầu vào luôn sinh cùng một request (tất định).

---

## 5. CHẶNG 3 — RequestExecutor (`executor/`)

### 5.1 Cấu hình `.env`
Quy ước tên: `DECISION_<PROVIDER>_<THUỘC_TÍNH>` (xem `PoC/.env.example`).

| Thuộc tính | Ý nghĩa |
|---|---|
| `ENDPOINT` | URL gọi |
| `API_KEY` | Gửi dạng `Authorization: Bearer` |
| `DEFAULT_MODEL` | Model gửi trong mọi request |
| `ADAPTER` | `jev_native` hoặc `noul_decomposition` |
| `STATE_FORMAT` | `string` (mặc định) hoặc `object` |
| `TIMEOUT_S`, `MIN_INTERVAL_S`, `MAX_RETRIES`, `MAX_QUESTIONS`, `AUTH_REQUIRED` | Vận hành |

`DECISION_ENABLED_PROVIDERS=laya,openrouter` quyết định provider nào được bật. Một tên mới không có sẵn (ví dụ `my-gateway`) sẽ dùng mặc định `jev_native`. Provider thiếu `ENDPOINT` hoặc thiếu `API_KEY` (khi bắt buộc), hoặc có cấu hình sai, sẽ **bị tắt kèm lý do**; server vẫn chạy bình thường. API key không bao giờ xuất hiện trong log, response hay `repr`.

### 5.2 Năng lực provider

| | Laya | OpenRouter (Respan) | TypeSafe Jev | Vercel Gateway |
|---|---|---|---|---|
| Adapter mặc định | `jev_native` | `noul_decomposition` | `jev_native` | `jev_native` |
| `state` | chuỗi / object ✅ | chỉ chuỗi ✅ | chuỗi ✅ | cần xác minh |
| `choice` / `score` | có ✅ | **không** ✅ | `choice` ✅ (`score` chưa thử) | cần xác minh |
| `noul` criteria `{true,false}` | ✅ | ✅ | ✅ | cần xác minh |

✅ = đã kiểm chứng bằng request thật hoặc mã nguồn.

Ghi chú TypeSafe (kiểm chứng 2026-10-01): endpoint `https://api.typesafe.ai/v1/systemone`, xác thực `Bearer`. Danh sách model lấy được từ `GET /v1/models` chỉ có `jev-latest` và `jev-preview`; tên `jev-1.13` bị từ chối với lỗi `Unknown model`. `jev-latest` hiện trỏ tới phiên bản `jev-1.13.0` (trường `model` trong response). Response không có `answer_confidence`; `confidence` theo định nghĩa của TypeSafe nên khác `max(probabilities)`. `probabilities` của câu `choice` cộng lại bằng 1, `usage.output_tokens` khác 0.

### 5.3 Adapter
- **`jev_native`**: gửi nguyên câu hỏi.
- **`noul_decomposition`**: câu `choice` K lựa chọn (hoặc `score` K mức) được tách thành K câu `noul` tên `<qid>__<i>`, **gộp chung một request**. Câu `noul` gốc giữ nguyên. Ánh xạ `sub_qid → lựa chọn` được lưu trong `DecompositionPlan` để chặng 4 gộp lại.
- Nếu số câu vượt `MAX_QUESTIONS` thì chia thành nhiều request và ghép kết quả lại.

### 5.4 Transport

| Tình huống | Hành vi |
|---|---|
| 200 | Kiểm tra body là JSON và có `answers`, nếu không thì 502 `PROVIDER_INVALID_RESPONSE` |
| 429, 5xx, timeout, lỗi mạng | Retry có backoff tăng dần, tuân theo `Retry-After`. Hết lượt thì 503 `PROVIDER_UNAVAILABLE` |
| 401 / 403 | Không retry, trả 502 `PROVIDER_AUTH_FAILED` kèm lỗi gốc |
| 400 / 422 | Không retry, trả 502 `PROVIDER_REJECTED_REQUEST` kèm lỗi gốc |

Giới hạn tốc độ: giữ khoảng cách `MIN_INTERVAL_S` giữa hai request tới **cùng một provider**, an toàn khi nhiều request chạy song song.

**Acceptance criteria**
- [x] Cùng một `input_json`, đổi `service_platform` giữa `laya` và `openrouter` đều chạy, không phải sửa code.
- [x] Với OpenRouter, P1 gửi 3 câu `noul` trong **1** request; P2 gửi 7 câu trong 1 request.
- [x] 429 được retry, 400 không được retry.
- [x] API key không có trong log, response hay thông báo lỗi.

---

## 6. CHẶNG 4 — Trả kết quả (`response/`)

### 6.1 Gộp câu hỏi đã phân rã (`recombine.py`)
Chỉ chạy khi có `DecompositionPlan`:
- `choice` → `{"type":"choice","choice": <lựa chọn có noul cao nhất>,"probabilities":{lựa chọn: noul}}`
- `score` → `{"type":"score","score": <mức cao nhất>,"probabilities":{"0": noul, ...}}`
- Khi hòa điểm, chọn theo thứ tự lựa chọn đã khai báo, để kết quả luôn tất định.
- Thiếu hoặc sai giá trị `noul` ở bất kỳ câu con nào thì trả 502 `INCOMPLETE_DECOMPOSITION`.

### 6.2 Dựng response (`builder.py`)
- `jev_native`, 1 request: trả **nguyên văn**.
- Có phân rã: giữ mọi trường của provider, chỉ thay `answers` bằng bản đã gộp.
- Nhiều request: lấy response đầu làm khung, gộp `answers`, cộng các trường số trong `usage`.

**Không làm ở chặng này:** kiểm tra đáp án có nằm trong tập lựa chọn, so với nhãn, áp ngưỡng. Client nhận đúng những gì provider trả.

---

## 7. Danh mục lỗi

| Mã | HTTP | Chặng | Khi nào |
|---|---|---|---|
| `VALIDATION_ERROR` | 422 | 1 | Thiếu `service_platform` / `input_json`, hoặc sai kiểu |
| `UNKNOWN_PROVIDER` | 400 | 1 | `service_platform` không tồn tại |
| `PROVIDER_NOT_CONFIGURED` | 503 | 1 | Provider đang tắt, thiếu cấu hình hoặc thiếu model |
| `INVALID_INPUT_JSON` | 422 | 1 | `input_json` không parse được, hoặc không phải object |
| `MISSING_INPUT_FIELD` | 422 | 1–2 | Thiếu trường bắt buộc |
| `LABEL_LEAK_BLOCKED` | 500 | 3 | Payload chứa trường nhãn (lỗi lập trình, không phải lỗi client) |
| `PROVIDER_REJECTED_REQUEST` | 502 | 3 | Provider trả 400/422 |
| `PROVIDER_AUTH_FAILED` | 502 | 3 | Provider trả 401/403 |
| `PROVIDER_UNAVAILABLE` | 503 | 3 | Hết lượt retry (429, 5xx, timeout) |
| `PROVIDER_INVALID_RESPONSE` | 502 | 3–4 | Response không phải JSON hoặc thiếu `answers` |
| `INCOMPLETE_DECOMPOSITION` | 502 | 4 | Thiếu câu trả lời cho câu con đã phân rã |

---

## 8. Đánh giá chất lượng (ngoài API)

`scripts/run_csv_through_api.py` gọi API **từng dòng CSV một**, đọc `answers` và so với cột `expected_*`, rồi in ra:
- accuracy theo từng trường;
- coverage và accuracy ở các ngưỡng `--thresholds` (mặc định 0.8, 0.9). Độ tự tin được lấy bằng xác suất của đáp án được chọn (`choice`), hoặc `max(p, 1 − p)` với `noul`.

Kết quả từng mẫu được ghi vào `PoC/runs/<task>_<provider>_<thời gian>.jsonl`.

---

## 9. Yêu cầu phi chức năng

| Hạng mục | Yêu cầu |
|---|---|
| Bảo mật | Key chỉ nằm trong `.env` (đã có trong `.gitignore`). Không log key, không log body. Có 2 lớp chống rò rỉ nhãn (mục 3). |
| Quan sát | Log JSON theo chặng: `intake.accepted`, `execute.http_call`, `execute.done`. Mỗi request có `X-Request-ID`. |
| Tái lập | Prompt có phiên bản. Model lấy từ `.env`, còn model thực sự đã chạy nằm trong body của provider. |
| Mở rộng | Provider mới: chỉ cần cấu hình. Bài toán mới: thêm 1 normalizer và 1 mục trong `pipeline/tasks.py`. |
| Kiểm thử | Unit test cho từng chặng; e2e với provider giả lập bám theo hành vi thật; test gọi provider thật bật bằng `DECISION_LIVE_TESTS=1`. |

---

## 10. Câu hỏi mở

| # | Câu hỏi | Đề xuất |
|---|---|---|
| Q1 | ~~Endpoint, cách xác thực và schema thật của **TypeSafe Jev**~~ Đã giải quyết 2026-10-01 (xem ghi chú dưới bảng 5.2). Còn lại: `score` chưa thử | Thử khi có bài toán dùng `score` |
| Q2 | **Vercel AI Gateway** có API decisions chuẩn Jev hay chỉ có chat completions? | Nếu chỉ có chat thì đây là một hạng mục riêng, không cấu hình thẳng được |
| Q3 | Qua OpenRouter, mỗi model có năng lực khác nhau (Respan chỉ `noul`, các model khác có thể hỗ trợ `choice`) | Hiện đổi `DECISION_OPENROUTER_ADAPTER` cùng lúc với `DEFAULT_MODEL`. Nếu cần dùng nhiều model song song thì khai báo thành nhiều provider (ví dụ `openrouter-respan`, `openrouter-jev`) |
| Q4 | Chất lượng mô hình trên dữ liệu thật đang thấp | API này để đổi provider nhanh và so sánh công bằng, không phải cam kết chất lượng |

---

## 11. Cấu trúc thư mục

```
PoC/
  docs/BA_decision_pipeline.md
  .env.example   .gitignore   pyproject.toml
  examples/p1_request.json  p2_request.json
  app/
    main.py                       # FastAPI factory, exception handler
    config.py                     # .env -> Settings/ProviderConfig
    errors.py                     # ErrorCode + HTTP status
    observability.py              # log JSON
    api/
      condition_relation.py  performer_lane.py  providers.py  _respond.py
    schemas/
      request.py                  # {service_platform, input_json}
      internal.py                 # dữ liệu giữa các chặng
    pipeline/
      orchestrator.py             # nối 4 chặng
      tasks.py                    # registry P1/P2 + FORBIDDEN_PAYLOAD_KEYS
      questions.py                # builder choice/score/noul
      intake.py                   # chặng 1
      normalizer/                 # chặng 2: prompts.py, p1_…py, p2_…py
      executor/                   # chặng 3: registry, transport, guards, executor, adapters/
      response/                   # chặng 4: recombine.py, builder.py
  tests/
    unit/  test_api_e2e.py  integration/  fakes.py  fixtures.py
  scripts/run_csv_through_api.py
```
