# Vì sao state gửi cho model cần nhiều trường, không chỉ 1 đoạn văn bản

Tài liệu này giải thích lý do thiết kế `state_text` (nội dung thật sự gửi cho model qua `/v1/systemone` hoặc `/api/alpha/decisions`) của 2 bài toán P1 và P2 dùng nhiều trường đầu vào thay vì chỉ một trường văn bản tự do. Căn cứ trực tiếp vào code hiện có:

- `app/pipeline/normalizer/p1_condition_relation.py`
- `app/pipeline/normalizer/p2_performer_lane.py`
- `app/pipeline/normalizer/prompts.py`

## Nguyên tắc chung

State không phải là "mô tả cho người đọc hiểu", mà là **toàn bộ thông tin model có để ra quyết định**. Nếu một trường bị bỏ, model phải tự suy luận thay — và phần suy luận hộ đó dễ sai, làm nhiễu kết quả đo đúng cái cần đo. Mỗi trường trong state trả lời một câu hỏi khác nhau; gộp thiếu một câu, model phải tự đoán câu đó, kéo theo sai số không liên quan đến năng lực thật cần đánh giá.

---

## P1 — Condition Relation

### Input: `clause_text`, `left_condition`, `right_condition`

### Template thật (`prompts.py`)
```
Câu điều khoản: {clause_text}
Vế 1: {left_condition}
Vế 2: {right_condition}
```

### Câu hỏi gửi model
*"Trong câu điều khoản, vế 1 và vế 2 có quan hệ logic gì với nhau?"* — chọn `and` / `or` / `insufficient_evidence`.

### Vì sao cần cả 3 trường

| Trường | Trả lời câu hỏi | Nếu thiếu thì sao |
|---|---|---|
| `clause_text` | Quan hệ logic *thật sự được diễn đạt* trong câu gốc là gì? (từ nối "và"/"hoặc", dấu phẩy liệt kê, cấu trúc câu) | Model chỉ có 2 cụm từ rời rạc, không còn ngữ cảnh ngôn ngữ để biết tác giả câu dùng quan hệ gì |
| `left_condition` | Vế thứ nhất **cụ thể nào** trong câu đang được hỏi | Model phải tự đoán "vế 1" là mệnh đề nào trong câu |
| `right_condition` | Vế thứ hai **cụ thể nào** đang được hỏi | Tương tự, không biết "vế 2" là gì |

### Ví dụ thật (từ `examples/p1_request.json`)
```
clause_text:    "Là tài khoản có trạng thái hoạt động, không bị khóa ghi nợ,
                 không đồng sở hữu và không có người giám hộ."
left_condition: "có trạng thái hoạt động"
right_condition:"không bị khóa ghi nợ"
```

Câu gốc có **4 mệnh đề** ("có trạng thái hoạt động", "không bị khóa ghi nợ", "không đồng sở hữu", "không có người giám hộ"), nhưng câu hỏi chỉ xét quan hệ giữa **đúng 2 trong 4**. Nếu bỏ `left_condition`/`right_condition` và chỉ đưa `clause_text`, câu hỏi "vế 1 và vế 2 có quan hệ gì" trở nên vô nghĩa — không ai (kể cả model) biết "vế 1", "vế 2" ứng với mệnh đề nào trong 4 mệnh đề đó.

Ngược lại, nếu bỏ `clause_text` và chỉ đưa 2 cụm từ trần trụi ("có trạng thái hoạt động" / "không bị khóa ghi nợ"), model mất hết ngữ cảnh câu gốc dùng từ nối gì — hai cụm từ đứng riêng không tự thân mang quan hệ logic nào, quan hệ đó nằm ở cách tác giả nối chúng trong câu.

**Kết luận P1:** `clause_text` cho ngữ cảnh ngôn ngữ để suy ra quan hệ; `left_condition`/`right_condition` cho biết chính xác đang so sánh cặp mệnh đề nào. Ba trường không trùng chức năng — thiếu bất kỳ trường nào, bài toán trở nên thiếu xác định (under-specified).

---

## P2 — Performer Lane

### Input: `row_text`, `subject`, `substeps`, `members`

### Hàm dựng state thật (`_state_text`, `p2_performer_lane.py` dòng 47-59)
```
Dòng mô tả bước: {row_text}
Chủ thể: {subject.text}              # chỉ thêm nếu có
Bước con cần xác định: {substeps[].quote nối bằng "; "}   # chỉ thêm nếu có
```
(`members` không đưa vào state — đưa vào `criteria` của câu hỏi `performer`, xem bên dưới)

### 3 câu hỏi gửi model
1. `performer`: *"Cấu phần nào trực tiếp thực hiện bước được mô tả?"* — chọn 1 trong các `members[].id`, hoặc `insufficient_evidence`.
2. `evidence`: *"Căn cứ chính để xác định cấu phần thực hiện nằm ở đâu trong câu?"* — `object` / `verb` / `context`.
3. `mixed_lanes`: *"Bước này có đồng thời chứa việc của phía client và phía server không?"* — yes/no.

### Vì sao cần từng trường

| Trường | Trả lời câu hỏi | Nếu thiếu thì sao |
|---|---|---|
| `row_text` | Nội dung bước nghiệp vụ cần phân loại | Không có gì để phân tích — đây là trường bắt buộc, thiếu thì `validate_input` chặn ngay (dòng 23-24) |
| `subject.text` | **Ai/cái gì** đang thực hiện hành động được mô tả trong câu (ví dụ "Hệ thống", "VCB Digibank") | Model thiếu chủ thể ngữ pháp của câu, dễ nhầm giữa các cấu phần có vai trò gần giống nhau |
| `substeps[].quote` | Khi `row_text` là một đoạn dài gồm **nhiều bước/câu gộp lại**, trường này chỉ đúng **câu con nào** trong đoạn đó là phần đang cần xác định performer | Model phải tự đoán đang được hỏi về phần nào trong cả đoạn dài, dễ phân tích nhầm sang bước khác không liên quan |
| `members` (qua `criteria`, không qua state) | Danh sách ứng viên hợp lệ model được chọn — bao gồm `id`, `name`, `tier`, `description` của từng cấu phần | Không có `members`, bài toán `performer` không còn là "chọn 1 trong N lựa chọn có sẵn" nữa — `validate_input` chặn thẳng (dòng 26-28) vì đây là điều kiện bắt buộc của thiết kế `choice` |

### Ví dụ thật (từ `examples/p2_request.json`, mẫu `T15-006`)
```
row_text:  "Mở webview ID Safe"
subject:   {"text": "Hệ thống", ...}
substeps:  [{"quote": "Mở webview ID Safe", ...}]
members:   [{"id": "pmkt_frontend", "name": "PMKT (Front-end)", "tier": "client", ...},
            {"id": "pmkt_core",     "name": "PMKT (Core)",      "tier": "server", ...}]
```

State thật gửi đi:
```
Dòng mô tả bước: Mở webview ID Safe
Chủ thể: Hệ thống
Bước con cần xác định: Mở webview ID Safe
```

Trong ví dụ này `row_text` và `substeps[].quote` trùng nhau (câu ngắn, chỉ 1 bước), nên `substeps` không thêm giá trị rõ rệt. Giá trị của trường này bộc lộ rõ hơn với các dòng dữ liệu có `row_text` dài, gộp nhiều câu (ví dụ các mẫu `T15-007`, `T15-012` trong CSV gốc có `row_text` chứa nhiều dấu `;` phân tách nhiều ý) — khi đó `substeps[].quote` là cách duy nhất để chỉ đúng câu con cần phân loại, tránh model lẫn sang các câu khác trong cùng đoạn.

`members` không nằm trong `state_text` mà nằm trong `criteria` của câu hỏi `performer` (dòng 66-69) — đây là cách đúng theo chuẩn Jev: với câu hỏi kiểu `choice`, danh sách lựa chọn hợp lệ phải khai báo ở `criteria`, không trộn vào nội dung mô tả tình huống (`state`). Tách riêng hai phần này cũng giữ `state_text` không bị phình to khi số lượng `members` lớn.

**Kết luận P2:** `row_text` là nội dung cốt lõi bắt buộc; `subject` bổ sung chủ thể ngữ pháp; `substeps` cần thiết khi `row_text` là đoạn dài gộp nhiều câu, để chỉ đúng phần đang xét; `members` không vào state nhưng là điều kiện bắt buộc của câu hỏi `performer` vì nó định nghĩa tập lựa chọn hợp lệ.

---

## Tóm tắt chung

Cả hai bài toán tuân theo cùng một nguyên tắc: **mỗi trường input giải quyết đúng một việc mơ hồ (ambiguity) mà nếu bỏ qua, model phải tự đoán thay** — và việc đoán thay đó sẽ làm sai lệch kết quả đo so với năng lực thật cần đánh giá.

| Bài toán | Trường cho "ngữ cảnh/nội dung" | Trường cho "phạm vi chính xác cần xét" |
|---|---|---|
| P1 | `clause_text` | `left_condition`, `right_condition` |
| P2 | `row_text`, `subject` | `substeps[].quote` (khi `row_text` dài) |

Không có trường nào trong số này là dư thừa theo thiết kế hiện tại — toàn bộ đều được code sử dụng thật trong `state_text` hoặc `criteria` gửi đi, có thể kiểm chứng trực tiếp trong `app/pipeline/normalizer/`.
