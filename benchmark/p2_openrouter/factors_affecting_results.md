# Các yếu tố ảnh hưởng tới kết quả model trả về (P2 qua OpenRouter/Respan)

Phân tích dựa trên code thật (`PoC/app/pipeline/`) và dữ liệu thật trong `result_*.json` của lần chạy này, không suy đoán.

## Tóm tắt kết quả đang phân tích

| Trường | Accuracy |
|---|---|
| evidence | 64.0% (128/200) |
| mixed_lanes | 73.5% (147/200) |
| performer | **3.5% (7/200)** |

`performer` thấp bất thường so với 2 trường còn lại — đây là trọng tâm phân tích.

---

## 1. Chiến lược phân rã câu hỏi (`noul_decomposition`) — yếu tố kỹ thuật lớn nhất

**Cơ chế thật** (`app/pipeline/executor/adapters/noul_decomposition.py`): OpenRouter (model `respan/span-01-lite:free`) chỉ nhận câu hỏi kiểu yes/no (`noul`), không nhận câu hỏi nhiều lựa chọn (`choice`). Vì `performer` vốn là câu hỏi chọn 1 trong N cấu phần, hệ thống phải **tách thành N câu hỏi độc lập**, mỗi câu hỏi riêng biệt dạng:

> "Cấu phần nào trực tiếp thực hiện bước được mô tả? Phương án đang xét: `<tên cấu phần>`. Phương án này có phải là đáp án đúng không?"

Hệ quả: **model không bao giờ nhìn thấy toàn bộ danh sách lựa chọn cùng lúc.** Nó trả lời từng cấu phần một cách tách biệt ("đây có phải là X không?" — đúng/sai), không có cơ hội so sánh trực tiếp giữa các ứng viên như khi hỏi 1 câu `choice` thật. Đây là khác biệt căn bản so với cách Laya xử lý (`jev_native`, hỏi `choice` trực tiếp).

**Bằng chứng từ dữ liệu thật** (`result_1_20.json`, mẫu `T15-001`):
```json
"probabilities": {
  "pmkt_frontend": 0.085,
  "pmkt_core": 0.272,
  "insufficient_evidence": 0.881
}
```
Model chấm từng cấu phần với độ tin cậy "đúng" khá thấp (0.085, 0.272), nhưng câu `insufficient_evidence` lại được chấm độ tin cậy cao (0.881). Vì không có sự ép buộc "phải chọn 1 trong các cấu phần", model có xu hướng trả lời "không phải" cho từng cấu phần riêng lẻ, và vì `insufficient_evidence` cũng được hỏi theo kiểu tương tự ("đây có phải insufficient_evidence không?"), nó dễ được chấm "đúng" độc lập mà không bị ràng buộc bởi các câu trả lời kia.

→ **Đây là yếu tố kỹ thuật chính** khiến `performer` kém hơn hẳn `evidence` (3 lựa chọn cố định, ít phương án hơn nên phân rã ít gây nhiễu hơn) và `mixed_lanes` (vốn đã là câu hỏi yes/no tự nhiên, không cần phân rã).

## 2. Độ dài và độ phức tạp của `row_text`

**Bằng chứng thật** (CSV gốc, mẫu `T15-001`):
```
row_text: "Đóng popup, nạp chứng từ gốc vào vùng ①, kế thừa toàn bộ dòng hàng sang bảng
           Dòng hàng trên hoá đơn theo quan hệ một–một, dựng khối Hoá đơn của chứng từ
           với một tờ hoá đơn và bốn ô nhà cung cấp lấy sẵn từ hồ sơ nhà cung cấp của
           chứng từ gốc, điền sẵn Diễn giải theo số chứng từ gốc, và hiện thông báo
           nêu số dòng hàng đã kế thừa (BR-06, BR-08, BR-09)"
substeps[0].quote: "kế thừa toàn bộ dòng hàng sang bảng Dòng hàng trên hoá đơn theo quan hệ một–một"
expected_performer: pmkt_core
```

`row_text` gộp **5 hành động khác nhau** trong 1 câu dài (đóng popup, nạp chứng từ, kế thừa dòng hàng, dựng khối hóa đơn, hiện thông báo). `substeps[].quote` đã chỉ đúng câu con cần xét ("kế thừa toàn bộ dòng hàng..."), nhưng ngay cả khi có thông tin này trong state, model vẫn trả lời `insufficient_evidence`. Điều này cho thấy mức độ phức tạp ngôn ngữ của câu (nhiều mệnh đề, thuật ngữ nghiệp vụ chuyên ngành như "kế thừa dòng hàng", "quan hệ một–một") vượt quá khả năng phân tích ngữ nghĩa của model ở kích thước `span-01-lite`, dù đã được cấp đủ thông tin cần thiết.

## 3. Model không được huấn luyện cho miền nghiệp vụ tiếng Việt chuyên biệt

`members[].description` mô tả cấu phần bằng ngôn ngữ nghiệp vụ domain-specific (ví dụ "Xử lý logic nghiệp vụ, lưu dữ liệu, hạch toán và tích hợp" cho `pmkt_core`). Việc ánh xạ một hành động nghiệp vụ cụ thể ("kế thừa dòng hàng") sang đúng cấu phần kỹ thuật đòi hỏi hiểu biết về kiến trúc hệ thống cụ thể của dự án — đây là kiến thức miền hẹp, nhiều khả năng không có trong dữ liệu huấn luyện chung của model free tier.

## 4. Độ tin cậy giả (overconfidence) trên câu trả lời sai

Model trả `insufficient_evidence` với confidence 0.88 trong ví dụ trên — tức rất "tự tin" khi từ chối trả lời, dù dữ liệu đã đủ để xác định đáp án đúng (`pmkt_core`). Đây không phải là model "biết mình không biết" một cách hợp lý, mà có dấu hiệu thiên lệch hệ thống về phía lựa chọn an toàn `insufficient_evidence` bất kể ngữ cảnh — tương tự thiên lệch đã quan sát ở bài P1 (model luôn đoán `or`).

## 5. Rate limit và retry — ảnh hưởng tới tính liên tục của phép đo, không ảnh hưởng tới từng câu trả lời riêng lẻ

`PoC/.env` cấu hình `DECISION_OPENROUTER_MIN_INTERVAL_S` (ban đầu 1.0s, đã tăng lên 4.0s sau khi gặp lỗi 429 khi chạy benchmark này). Việc bị giới hạn tốc độ không làm sai lệch câu trả lời của một request đã thành công — request bị 429 được retry cho tới khi thành công (`app/pipeline/executor/transport.py`) hoặc báo lỗi rõ ràng, không bao giờ trả về kết quả "đoán mò". Yếu tố này ảnh hưởng tới **thời gian chạy và nguy cơ phải chia nhỏ đoạn benchmark** (dẫn tới việc bị trùng đoạn `51-60`/`51-70` đã phát hiện trong báo cáo), chứ không làm sai lệch số liệu accuracy.

---

## Kết luận

| # | Yếu tố | Mức ảnh hưởng tới `performer` | Có thể khắc phục trong pipeline hiện tại? |
|---|---|---|---|
| 1 | Phân rã `choice` → nhiều câu `noul` độc lập | **Lớn nhất** | Có — đổi sang model/provider hỗ trợ `choice` trực tiếp (`jev_native`), hoặc đổi cách phân rã (ví dụ ép buộc tổng xác suất = 1 bằng softmax thủ công sau khi nhận kết quả, thay vì lấy độc lập) |
| 2 | Độ dài/phức tạp của `row_text` | Trung bình-lớn | Hạn chế — đây là đặc điểm dữ liệu gốc, không sửa được trừ khi tiền xử lý rút gọn câu |
| 3 | Model chưa quen miền nghiệp vụ cụ thể | Trung bình | Hạn chế trong phạm vi model free tier — cần model lớn hơn hoặc fine-tune |
| 4 | Overconfidence vào `insufficient_evidence` | Lớn | Có thể giảm bằng cách thêm calibration/threshold riêng cho `performer`, nhưng chưa có trong pipeline hiện tại |
| 5 | Rate limit/retry | Không ảnh hưởng accuracy, chỉ ảnh hưởng vận hành | Đã xử lý bằng tăng `MIN_INTERVAL_S` |

**Yếu tố số 1 là nguyên nhân kỹ thuật rõ ràng nhất và có thể kiểm chứng trực tiếp qua code** — nó giải thích vì sao `performer` (nhiều lựa chọn, bị phân rã nhiều) kém hẳn `mixed_lanes` (vốn đã là câu hỏi yes/no, không bị phân rã) dù cùng một model, cùng một dữ liệu đầu vào.
