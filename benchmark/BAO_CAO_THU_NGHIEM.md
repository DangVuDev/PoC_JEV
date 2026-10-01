# Báo cáo thử nghiệm model quyết định có cấu trúc (JEV) cho P1 và P2

Ngày thực hiện: 2026-10-01. Ba model được thử: **TypeSafe Jev**, **model miễn phí trên OpenRouter** (Respan span-01-lite) và **Laya** (bản mã nguồn mở tương thích Jev).

## 1. Tóm tắt

- **Chỉ TypeSafe Jev dùng được**, cho P1 (99.0%) và P2 `performer` (87.0%). Mỗi lần gọi khoảng 260 ms, chi phí khoảng 0.02 USD cho 1.000 mẫu P1.
- **Model miễn phí OpenRouter và Laya không dùng được:** cả hai thấp hơn mức luôn đoán nhãn phổ biến nhất ở mọi chỉ tiêu.
- Với TypeSafe Jev, hai chỉ tiêu P2 còn lại (`evidence`, `mixed_lanes`) cũng chưa dùng được.

## 2. Giới thiệu JEV

**Jev** là model của hãng TypeSafe thuộc dòng "System One". Nó nhận một ngữ cảnh (`state`) cùng các câu hỏi có kiểu, và trả về đáp án có cấu trúc kèm xác suất, không viết văn bản. TypeSafe hiện có `jev-latest` (đang là `jev-1.13.0`) và `jev-preview`. Mỗi request tối đa 64.000 token.

**Ba bài toán Jev giải quyết** (ba kiểu câu hỏi):

| Kiểu | Bài toán | Kết quả trả về | Dùng trong thử nghiệm |
|---|---|---|---|
| `choice` | Chọn một trong nhiều phương án | Phương án được chọn, xác suất từng phương án | P1 `relation`; P2 `performer`, `evidence` |
| `score` | Xếp vào một mức trên thang điểm (ví dụ mức khẩn cấp từ bình thường đến rất gấp) | Mức điểm, phân phối xác suất | Chưa dùng |
| `noul` | Trả lời có/không | Xác suất của "có" | P2 `mixed_lanes` |

**Ba bên được so sánh** đều dùng chung cấu trúc yêu cầu và phản hồi này:

| Bên | Là gì | Chi phí |
|---|---|---|
| **TypeSafe Jev** | Model Jev gốc của TypeSafe, gọi qua `api.typesafe.ai`. Cột "jev-typescript" trong yêu cầu được hiểu là model này | Tính theo token |
| **OpenRouter (miễn phí)** | `respan/span-01-lite:free` qua API Decisions (alpha). Chỉ nhận câu hỏi `noul`, nên câu `choice` phải tách thành nhiều câu có/không | Miễn phí, bị giới hạn tốc độ |
| **Laya** | Engine mã nguồn mở của Convai Innovations, tự host (thử với checkpoint `multilingual` trên CPU). Định dạng trả lời giống Jev nhưng là model khác | Không tốn phí gọi |

## 3. Hai bài toán thử nghiệm

- **P1 Condition Relation:** cho câu điều khoản và hai vế điều kiện, xác định quan hệ `and`, `or` hay `insufficient_evidence` (không đủ căn cứ). Gửi 1 câu `choice`.
- **P2 Performer Lane:** cho một bước nghiệp vụ, xác định cấu phần thực hiện (`performer`), loại manh mối (`evidence`: `object`, `verb`, `context`) và bước có gộp việc của cả client lẫn server không (`mixed_lanes`). Gửi 2 câu `choice` và 1 câu `noul`.

Cả ba model chạy qua cùng một API, cùng prompt, mỗi mẫu một request, mỗi bộ 200 mẫu (P2 là 600 quyết định), chạy một lần, không mẫu nào lỗi.

## 4. Kết quả thực nghiệm

| Model | Bài toán | Số mẫu thử | Số mẫu đúng | Token vào / mẫu | Token ra / mẫu | Tốc độ TB mỗi lần gọi | Chi phí 200 mẫu |
|---|---|---|---|---|---|---|---|
| **TypeSafe Jev** | P1 | 200 | **198 (99.0%)** | 478 | 45 | 261 ms | ≈ 0.0040 USD |
| **TypeSafe Jev** | P2 | 200 | **113 (56.5%)** | 742 | 109 | 262 ms | ≈ 0.0062 USD |
| OpenRouter (miễn phí) | P1 | 200 | 66 (33.0%) | 780 | 0 | 2.170 ms | 0 USD |
| OpenRouter (miễn phí) | P2 | 200 | 0 (0%) | 1.618 | 0 | 1.802 ms | 0 USD |
| Laya | P1 | 200 | 59 (29.5%) | 166 | 0 | 256 ms | 0 USD (tự host) |
| Laya | P2 | 200 | 1 (0.5%) | 586 | 0 | 857 ms | 0 USD (tự host) |

Số mẫu đúng ở P2 tính mẫu đúng cả 3 trường. Tốc độ đo riêng trên 20 mẫu đầu mỗi bài toán, gửi tuần tự, chưa tính thời gian giãn cách giữa các request của hệ thống thử nghiệm.

**P2 theo từng trường** (mức đoán cố định là kết quả khi luôn trả nhãn phổ biến nhất):

| Trường | Mức đoán cố định | TypeSafe Jev | OpenRouter | Laya |
|---|---|---|---|---|
| `performer` | 49/200 (24.5%) | **174 (87.0%)** | 7 (3.5%) | 48 (24.0%) |
| `evidence` | 189/200 (94.5%) | 185 (92.5%) | 128 (64.0%) | 37 (18.5%) |
| `mixed_lanes` | 155/200 (77.5%) | 139 (69.5%) | 147 (73.5%) | 45 (22.5%) |

P1 có mức đoán cố định là 127/200 (63.5%). Chỉ TypeSafe vượt mức này ở P1 và `performer`.

**Chi phí TypeSafe:** 244.046 token vào × 0.042 USD / 1 triệu token ≈ 0.0103 USD cho 400 mẫu (token ra tính 0 USD theo bảng giá). Giá lấy từ Vercel AI Gateway, chưa xác nhận giá gọi trực tiếp `api.typesafe.ai`.

**Tốc độ:** TypeSafe ổn định (p95 dưới 320 ms ở cả hai bài toán). Laya chậm gấp 3 ở P2 vì chạy trên CPU. OpenRouter chậm và dao động mạnh (p95 4.4 đến 6.7 giây).

## 5. Kết luận và hạn chế

**Kết luận:**
1. Chọn TypeSafe Jev cho P1 và `performer`. Ở ngưỡng độ tin cậy 0.8: P1 tự chấp nhận 95% số mẫu với độ chính xác 99.5%; `performer` tự chấp nhận 66.5% với 96.2%; phần còn lại chuyển người duyệt.
2. Chưa tự động hóa `evidence` và `mixed_lanes`. TypeSafe gần như chỉ trả `verb` ở `evidence`, và báo `true` thừa 59/155 mẫu ở `mixed_lanes`.
3. Không dùng Laya `multilingual` và model miễn phí OpenRouter cho hai bài toán này. Laya gần như luôn trả một đáp án cố định (P1 trả `or` 185/200 lần); OpenRouter nghiêng về `insufficient_evidence`, một phần do cách tách câu hỏi.

**Hạn chế:**
- 195/200 nhãn P2 chưa được xác nhận nghiệp vụ, nên một số lỗi có thể do nhãn.
- P1 có 155/200 mẫu tổng hợp với từ nối rõ ràng, nên 99.0% phản ánh cả độ dễ của dữ liệu.
- Mỗi bộ chỉ chạy một lần. Tốc độ đo trên 20 mẫu, từ một máy, một thời điểm.
- Chưa thử: Jev qua Vercel AI Gateway, `laya-typed-decisions`, câu hỏi kiểu `score`.
