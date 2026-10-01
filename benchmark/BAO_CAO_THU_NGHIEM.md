# Báo cáo thử nghiệm JEV cho hai bài toán P1 và P2

Ngày thực hiện: 2026-10-01. Ba model được thử: **TypeSafe Jev**, **model miễn phí trên OpenRouter** (Respan span-01-lite) và **Laya** (bản mã nguồn mở theo cùng giao thức, chạy `multilingual` trên CPU).

**Tóm tắt:** chỉ TypeSafe Jev dùng được, cho P1 (99.0%) và P2 `performer` (87.0%), khoảng 260 ms mỗi lần gọi, chi phí chưa tới 0.01 USD cho 400 mẫu. Laya và OpenRouter miễn phí thấp hơn cả cách luôn đoán nhãn phổ biến.

---

## 1. Lý thuyết: JEV giải quyết những bài toán nào

### 1.1 JEV là gì

Model ngôn ngữ thông thường viết ra văn bản, mỗi token sinh ra phụ thuộc token trước, nên chậm và đáp án phải được đọc ngược từ đoạn văn. **Jev** (hãng TypeSafe, dòng "System One", tức suy nghĩ nhanh, theo trực giác) đi theo hướng khác: đưa vào một **ngữ cảnh** và một số **câu hỏi có kiểu**, nhận về **đáp án có cấu trúc kèm xác suất**, không sinh văn bản. Nhờ đó:

- Đầu ra luôn thuộc tập giá trị đã định trước (một trong các phương án, một số trong thang điểm, một xác suất có/không). Không có chuyện model trả lời lan man hay sai định dạng.
- Mỗi đáp án đi kèm xác suất, nên hệ thống có thể đặt **ngưỡng**: đủ tự tin thì tự động xử lý, không thì chuyển người duyệt.
- Nhiều câu hỏi về cùng một ngữ cảnh gửi trong **một request** và trả về cùng lúc.

Cơ chế bên trong của Jev chưa được công bố. **Laya** (Convai Innovations, mã nguồn mở, tôi đã đọc code) dùng cùng giao thức, nên cho thấy cách một model kiểu này hoạt động: một encoder (mmBERT-base, 322 triệu tham số) đọc toàn bộ câu hỏi, các phương án và ngữ cảnh trong **một lượt**, rồi chấm điểm từng phương án và chuẩn hóa bằng softmax. Không có vòng lặp sinh token.

### 1.2 Cấu trúc một request

```json
{
  "model": "jev-latest",
  "state": "<ngữ cảnh là một chuỗi văn bản>",
  "questions": {
    "<id câu hỏi>": { "type": "choice | score | noul", "instructions": "<câu hỏi>", "criteria": "<phương án>" }
  }
}
```

Phản hồi có `answers` (một mục cho mỗi câu hỏi) và `usage` (số token vào, token ra). Có ba kiểu câu hỏi, tương ứng ba bài toán.

### 1.3 Bài toán `choice`: chọn một trong nhiều phương án

Dùng khi đáp án là một nhãn trong tập đã biết: phân loại ý định, định tuyến, chọn quan hệ, chọn người xử lý. `criteria` là các phương án (khóa và mô tả). Kết quả là phương án được chọn cùng xác suất từng phương án, tổng bằng 1. Trường `confidence` đo mức nghiêng về một phương án: `(n·p_max − 1)/(n − 1)`, với n là số phương án; bằng 0 khi các phương án ngang nhau, bằng 1 khi chắc chắn (kiểm chứng trên mẫu `T15-001`: p_max = 0.72, n = 3 cho 0.58, đúng bằng giá trị phản hồi).

**Demo thật** (bài P1, mẫu `CR-001`, nhãn đúng `and`; request và phản hồi lấy từ lần chạy với `jev-1.13.0`):

```json
// Request
{
  "model": "jev-latest",
  "state": "Câu điều khoản: Là tài khoản có trạng thái hoạt động, không bị khóa ghi nợ, không đồng sở hữu và không có người giám hộ.\nVế 1: có trạng thái hoạt động\nVế 2: không bị khóa ghi nợ",
  "questions": {
    "relation": {
      "type": "choice",
      "instructions": "Trong câu điều khoản, vế 1 và vế 2 có quan hệ logic gì với nhau?",
      "criteria": {
        "and": "cả hai vế phải được thỏa đồng thời (và, đồng thời, liệt kê cùng cấp bằng dấu phẩy)",
        "or": "chỉ cần thỏa một trong hai vế (hoặc)",
        "insufficient_evidence": "câu không nêu rõ cách kết hợp hai vế, không đủ căn cứ để kết luận"
      }
    }
  }
}

// Phản hồi
{
  "model": "jev-1.13.0",
  "answers": {
    "relation": {
      "type": "choice",
      "choice": "and",
      "confidence": 1.0,
      "probabilities": { "and": 1.0, "or": 0.0, "insufficient_evidence": 0.0 }
    }
  },
  "usage": { "input_tokens": 459, "output_tokens": 44 }
}
```

Cách đọc: câu liệt kê các điều kiện cùng cấp bằng dấu phẩy, nên model chọn `and` với xác suất 1.0, `confidence` 1.0, tự động xử lý được.

### 1.4 Bài toán `noul`: trả lời có/không

Dùng khi đáp án là đúng/sai: kiểm duyệt, phát hiện vi phạm, kiểm tra điều kiện. `criteria` có đúng hai khóa `true` và `false`. Kết quả là một số từ 0 đến 1 là xác suất đáp án là "có". Đặt ngưỡng 0.5 để đọc thành đúng/sai; số càng gần 0.5 càng không chắc.

**Demo thật** (bài P2, mẫu `T15-006`, nhãn đúng `false`). Trong lần chạy thật, câu này được gửi cùng hai câu `choice` trong một request; phản hồi `noul` là số thật của lần đó. Để dễ đọc, request dưới đây chỉ giữ câu `noul`:

```json
// Request
{
  "model": "jev-latest",
  "state": "Dòng mô tả bước: Mở webview ID Safe\nChủ thể: Hệ thống\nBước con cần xác định: Mở webview ID Safe",
  "questions": {
    "mixed_lanes": {
      "type": "noul",
      "instructions": "Bước này có đồng thời chứa việc của phía client (giao diện) và phía server (xử lý nghiệp vụ) không?",
      "criteria": {
        "true": "bước trộn lẫn việc của nhiều tier (client và server)",
        "false": "bước chỉ thuộc một tier duy nhất"
      }
    }
  }
}

// Phản hồi (phần của câu này)
{ "answers": { "mixed_lanes": { "type": "noul", "noul": 0.29 } } }
```

Cách đọc: 0.29 nhỏ hơn 0.5, nên kết luận `false` (bước "Mở webview" chỉ là việc ở phía giao diện), đúng với nhãn. Số 0.29 chưa quá xa 0.5, nên nếu đặt ngưỡng chặt thì mẫu này vẫn bị chuyển người duyệt.

### 1.5 Bài toán `score`: xếp vào một mức trên thang điểm

Dùng khi đáp án là một mức có thứ tự: mức khẩn cấp, mức rủi ro, mức hài lòng. `criteria` là danh sách các mức theo thứ tự tăng dần (mức 0, 1, 2, ...). Kết quả là xác suất của từng mức và một **điểm kỳ vọng** Σ i·pᵢ, có thể nằm giữa hai mức (ví dụ 2.05 nghĩa là sát mức 2 nhưng hơi nghiêng về mức 3). Khác với `choice`, các mức có thứ tự nên "đoán lệch một mức" nhẹ hơn "đoán lệch ba mức".

**Demo tự dựng** (hai bài toán thử nghiệm không dùng kiểu này, nên đây là ví dụ minh họa, không phải kết quả đo):

```json
// Request
{
  "model": "jev-latest",
  "state": "Khách hàng: Tôi chuyển tiền cho đối tác lúc 9h sáng nay nhưng tiền đã bị trừ mà đối tác chưa nhận được, chiều nay có hạn thanh toán hợp đồng.",
  "questions": {
    "urgency": {
      "type": "score",
      "instructions": "Mức độ khẩn cấp của yêu cầu hỗ trợ này?",
      "criteria": [
        "bình thường: hỏi thông tin, không có thời hạn",
        "cần chú ý: có vấn đề nhưng chưa có thời hạn gấp",
        "khẩn: có thời hạn trong ngày",
        "rất khẩn: mất tiền hoặc gián đoạn dịch vụ ngay lập tức"
      ]
    }
  }
}

// Phản hồi minh họa
{
  "answers": {
    "urgency": { "type": "score", "probabilities": [0.05, 0.15, 0.50, 0.30], "score": 2.05 }
  }
}
// điểm = 0×0.05 + 1×0.15 + 2×0.50 + 3×0.30 = 2.05
```

### 1.6 Điều kiện để dùng được

- Mọi câu hỏi phải được diễn đạt thành một trong ba kiểu trên và có **tập đáp án đóng**.
- Câu hỏi và các phương án phải đủ rõ trong phần `instructions` và `criteria`; model chỉ đọc đúng chữ ghi ở đó.
- Ngữ cảnh (`state`) phải chứa đủ thông tin để quyết định. Đây là lý do hai bài toán thử nghiệm phải đưa thêm các trường như hai vế điều kiện hay các cấu phần của hệ thống vào `state`.

---

## 2. Hai bài toán thử nghiệm

Cả hai bài đều lấy dữ liệu từ tài liệu nghiệp vụ ngân hàng bằng tiếng Việt, mỗi bài 200 mẫu. Mỗi mẫu gửi thành một request riêng. Mỗi bài trình bày theo cùng thứ tự: bối cảnh, đầu vào, câu hỏi gửi cho model, đầu ra, ví dụ, điểm khó.

### 2.1 P1 Condition Relation: hai điều kiện liên hệ với nhau thế nào

**Bối cảnh.** Quy tắc nghiệp vụ thường viết thành một câu ghép nhiều điều kiện, ví dụ "khách hàng được đăng ký thẻ nếu điều kiện A, điều kiện B, ...". Muốn chuyển câu đó thành luật chạy được, phải biết hai điều kiện đứng cạnh nhau phải **cùng đúng** hay **chỉ cần một đúng**.

**Đầu vào (3 trường).**
- `clause_text`: nguyên câu điều khoản.
- `left_condition`: vế 1, đã được trích sẵn từ câu.
- `right_condition`: vế 2, đã được trích sẵn từ câu.

**Câu hỏi gửi cho model.** Một câu `choice`: "Trong câu điều khoản, vế 1 và vế 2 có quan hệ logic gì với nhau?", ba phương án:
- `and`: cả hai vế phải cùng được thỏa.
- `or`: chỉ cần thỏa một trong hai vế.
- `insufficient_evidence`: câu không nêu rõ cách kết hợp, không đủ căn cứ.

**Đầu ra.** Một nhãn trong ba nhãn trên, kèm xác suất.

**Dữ liệu.** 200 mẫu: `and` 127, `or` 53, `insufficient_evidence` 20. Gồm 155 mẫu tổng hợp (câu ngắn, từ nối rõ ràng) và 45 mẫu quy tắc thật (câu dài tới 1.006 ký tự, nhiều mệnh đề).

**Ví dụ: mẫu `CR-010`.**

```
Câu điều khoản:
  "KH chỉ được phép đăng ký thẻ tín dụng cầm cố tiền gửi nếu
   KH chưa có thẻ tín dụng HOẶC
   đã có thẻ tín dụng nhưng tất cả đã hết hiệu lực (trạng thái thẻ tham số động) và toàn bộ dư nợ <= 0."
Vế 1: "tất cả đã hết hiệu lực (trạng thái thẻ tham số động)"
Vế 2: "toàn bộ dư nợ <= 0"
```

Cấu trúc câu có thể vẽ như sau:

```
  [chưa có thẻ tín dụng]  HOẶC  [ đã có thẻ ... nhưng ( vế 1  VÀ  vế 2 ) ]
                                                        └── hai vế đang hỏi ──┘
```

Hai vế đang hỏi nằm trong cùng một nhánh và nối bằng "và", nên đáp án là **`and`**. Chữ "HOẶC" trong câu nối hai nhánh lớn, không nối hai vế này.

**Điểm khó.** Trong câu dài có thể có nhiều từ nối khác nhau, và chỉ từ nối nằm giữa đúng hai vế đang hỏi mới quyết định đáp án. Cách làm "thấy chữ hoặc thì trả `or`" sẽ trả `or` cho mẫu trên và sai. Với câu ngắn (155 mẫu tổng hợp) thì cách đó đã đủ, nên 45 mẫu quy tắc thật mới là phần đo năng lực thật.

### 2.2 P2 Performer Lane: ai thực hiện bước này

**Bối cảnh.** Tài liệu mô tả một luồng nghiệp vụ thành từng dòng "bước". Để vẽ sơ đồ làn trách nhiệm (swimlane), mỗi bước phải được gán cho đúng cấu phần thực hiện nó. Hệ thống nào cũng có một cấu phần **client** (giao diện, phía người dùng) và một cấu phần **server** (xử lý nghiệp vụ, phía máy chủ). Cả 200 mẫu thuộc ba hệ thống: pmkt (82 mẫu), vcb (83), merchant_app (35), và mỗi mẫu có đúng hai cấu phần: một client, một server.

**Đầu vào (4 trường).**
- `row_text`: nội dung dòng bước (trung bình 226 ký tự, tối đa 715).
- `subject`: chủ thể được ghi trong tài liệu (có khi chỉ là "Hệ thống").
- `substeps`: các bước con cần xét trong dòng đó.
- `members`: hai cấu phần của hệ thống, mỗi cấu phần có `id`, `tier` (client hoặc server) và mô tả.

**Ba câu hỏi gửi cho model** (cùng một ngữ cảnh, trong một request):

1. `performer` (`choice`): "Cấu phần nào trực tiếp thực hiện bước được mô tả?" Phương án là hai cấu phần của mẫu, cộng `insufficient_evidence` (không đủ căn cứ).
2. `evidence` (`choice`): "Căn cứ chính để xác định cấu phần nằm ở đâu trong câu?" Phương án: `object` (tên đối tượng hoặc màn hình được nhắc tới), `verb` (động từ hành động như hiển thị, lưu, kiểm tra), `context` (không có từ khóa trực tiếp, phải suy từ ngữ cảnh).
3. `mixed_lanes` (`noul`): "Bước này có đồng thời chứa việc của phía client và phía server không?" Trả lời có hoặc không.

**Đầu ra.** Ba đáp án, mỗi đáp án kèm xác suất. Câu 1 là kết quả chính; câu 2 và 3 giúp người duyệt biết nên tin đáp án đến mức nào.

**Dữ liệu.** Nhãn `performer`: client 102, server 91, `insufficient_evidence` 7. Nhãn `evidence`: `verb` 189, `context` 9, `object` 2. Nhãn `mixed_lanes`: `false` 155, `true` 45. Nhãn mới ở trạng thái cần duyệt nghiệp vụ (195/200 mẫu), nên một số nhãn có thể chưa chuẩn.

**Ví dụ: mẫu `T15-024`.**

```
row_text : "Kiểm tra thông tin rút và hiển thị màn hình xác nhận giao dịch ;
            Tham chiếu theo Quy tắc nghiệp vụ về Số lượng ký tự của số tiền rút /
            Điều kiện số tiền rút so với dư nợ khả dụng / Hạn mức của số tiền rút /
            Quy định về nội dung giao dịch"
subject  : "Merchant App"
members  : merchant_app_client  (client)  Giao diện ứng dụng Merchant App
           merchant_app_server  (server)  Xử lý giao dịch và điều phối các hệ thống phía máy chủ
```

Đáp án đúng:
- `performer = merchant_app_server`: phần kiểm tra theo các quy tắc nghiệp vụ là việc xử lý ở máy chủ.
- `evidence = verb`: căn cứ là động từ "kiểm tra".
- `mixed_lanes = true`: cùng một dòng có cả việc kiểm tra (server) lẫn việc hiển thị màn hình (client).

Để so sánh, mẫu đơn giản `T15-006` có `row_text` "Mở webview ID Safe", chủ thể "Hệ thống". Đáp án: `performer = pmkt_frontend`, `evidence = verb`, `mixed_lanes = false`.

**Điểm khó.**
- Nhiều dòng dài và gộp nhiều hành động (83/200 mẫu dài hơn 200 ký tự), nên khó chỉ ra một cấu phần duy nhất.
- Chủ thể thường chỉ ghi chung ("Hệ thống"), không cho biết client hay server; model phải đoán từ động từ và đối tượng trong câu.
- Client và server của cùng một hệ thống có mô tả gần nhau, nên lỗi hay gặp là nhầm hai cấu phần này với nhau.
- Nhãn `evidence` lệch nặng (`verb` 94.5%), nên một model luôn trả `verb` cũng đã đúng gần hết.

---

## 3. Kết quả thử nghiệm

Ba model chạy qua cùng một API, cùng prompt, mỗi mẫu một request, mỗi bộ 200 mẫu, chạy một lần, không mẫu nào lỗi.

| Model | Bài | Đúng (200 mẫu) | Tốc độ TB mỗi lần gọi | Chi phí 200 mẫu |
|---|---|---|---|---|
| **TypeSafe Jev** | P1 | **198 (99.0%)** | 261 ms | ≈ 0.0040 USD |
| **TypeSafe Jev** | P2 (đúng cả 3 trường) | 113 (56.5%) | 262 ms | ≈ 0.0062 USD |
| OpenRouter miễn phí | P1 | 66 (33.0%) | 2.170 ms | 0 USD |
| OpenRouter miễn phí | P2 | 0 (0%) | 1.802 ms | 0 USD |
| Laya (CPU cục bộ) | P1 | 59 (29.5%) | 256 ms | 0 USD (tự host) |
| Laya (CPU cục bộ) | P2 | 1 (0.5%) | 857 ms | 0 USD (tự host) |

**Độ chính xác.** TypeSafe đạt 99.0% ở P1 so với 63.5% khi luôn đoán `and`. Ở 45 mẫu quy tắc thật nó đúng 44 mẫu (97.8%), trong khi một luật từ khóa 3 dòng chỉ đúng 40 mẫu (88.9%). Ở P2, `performer` đạt 174/200 (87.0%, so với 51.0% khi luôn đoán client). Hai trường còn lại chưa đạt: `evidence` 92.5% so với mốc 94.5% (gần như chỉ trả `verb`), `mixed_lanes` 69.5% so với mốc 77.5% (báo `true` thừa nhiều). Tổng 600 quyết định của P2 đúng 83.0%, so với 74.3% của mốc. Nếu chỉ nhận kết quả có độ tin cậy từ 0.8, P1 tự động xử lý được 95.0% mẫu với độ chính xác 99.5%, và `performer` 66.5% mẫu với 96.2%. Laya (P1 29.5%, P2 21.7%) và OpenRouter (P1 33.0%, P2 47.0%) đều thấp hơn mốc nên không dùng được.

**Tốc độ.** TypeSafe khoảng 260 ms cho cả hai bài, ổn định (p95 dưới 320 ms). Laya chạy trên CPU cục bộ: 256 ms ở P1 nhưng 857 ms ở P2 vì phải xử lý ba câu hỏi. OpenRouter chậm nhất (trung bình 1,8 đến 2,2 giây, p95 tới 6,7 giây) và hay bị giới hạn tốc độ nên phải giãn cách 4 giây giữa các request. Tốc độ đo trên 20 mẫu đầu mỗi bài, gửi tuần tự.

**Chi phí.** TypeSafe tính theo token vào: 244.046 token cho 400 mẫu, tương đương khoảng 0.0103 USD, tức khoảng 0.02 USD cho 1.000 mẫu P1 (giá 0.042 USD cho 1 triệu token vào, token ra tính 0, lấy từ Vercel AI Gateway; giá gọi trực tiếp `api.typesafe.ai` chưa xác nhận). OpenRouter miễn phí và Laya không tính phí gọi, nhưng Laya cần máy chủ tự vận hành.

---

## 4. Ưu điểm, nhược điểm và phạm vi áp dụng

### 4.1 Ưu điểm

- **Đầu ra có cấu trúc và có xác suất.** Không cần phân tích văn bản, không sợ sai định dạng, và đặt được ngưỡng tự tin để chỉ chuyển người duyệt những ca khó. Trong thử nghiệm, nhóm kết quả từ 0.8 trở lên đúng 96% đến 99.5%.
- **Nhanh và rẻ.** Khoảng 260 ms mỗi lần gọi, chi phí chỉ tính theo token vào, cỡ 0.02 USD cho 1.000 mẫu. Một request gồm nhiều câu hỏi về cùng một ngữ cảnh.
- **Hiểu cấu trúc câu dài tốt hơn luật từ khóa.** Ở P1, các mẫu quy tắc thật có nhiều từ nối mà luật từ khóa sai, Jev vẫn đúng 97.8%.
- **Hoạt động tốt với tiếng Việt** trong thử nghiệm này (khác với Laya `multilingual` chưa tinh chỉnh).

### 4.2 Nhược điểm

- **Không phải bài nào cũng đạt.** `evidence` và `mixed_lanes` thấp hơn cả mốc luôn đoán nhãn phổ biến. Với nhãn lệch nặng (`verb` chiếm 94.5%), model có xu hướng trả nhãn phổ biến và không nhận ra nhãn hiếm.
- **Còn nhầm ở chỗ cần ngữ cảnh sâu.** `performer`: 18/26 lỗi là nhầm client với server của cùng hệ thống.
- **Phụ thuộc chất lượng mô tả** trong `instructions`, `criteria` và `state`; model chỉ biết những gì được viết ra.
- **Chưa biết rõ bên trong.** TypeSafe chưa công bố kiến trúc; kết quả công bố chủ yếu là số liệu của chính hãng hoặc bên thứ ba. Giá gọi trực tiếp chưa xác nhận.
- **Không giải thích được lý do** (không có đoạn văn lập luận), chỉ có xác suất.
- **Bản thay thế không dùng ngay được:** Laya cần tinh chỉnh bằng dữ liệu riêng, model miễn phí OpenRouter chỉ nhận `noul` và yếu ở `choice`.
- **Giới hạn của thử nghiệm:** mỗi bộ chạy một lần; P1 có 155/200 mẫu tổng hợp dễ; nhãn P2 chưa duyệt xong.

### 4.3 Các bài toán khác có thể áp dụng

Đây là gợi ý theo đặc tính của từng kiểu câu hỏi, chưa được thử nghiệm trong báo cáo này; trước khi dùng cần đo trên dữ liệu thật như đã làm ở đây.

- **`choice`:** phân loại ý định khách hàng và định tuyến yêu cầu về đúng bộ phận; phân loại loại giao dịch hoặc loại tài liệu; chọn đúng mục lục điều khoản liên quan; gán hạng mục cho khiếu nại.
- **`noul`:** kiểm tra một văn bản có vi phạm chính sách hay không; phát hiện yêu cầu có nhắc tới thông tin nhạy cảm; xác nhận hồ sơ có đủ một điều kiện cụ thể; sàng lọc trước khi chuyển cho người duyệt.
- **`score`:** xếp mức độ khẩn cấp hoặc mức rủi ro của một yêu cầu; chấm mức độ hài lòng; ưu tiên hàng đợi xử lý.
- **Kết hợp:** dùng Jev làm bộ lọc đầu (nhanh, rẻ), chỉ ca dưới ngưỡng tự tin mới chuyển cho người duyệt hoặc cho model lớn hơn; dùng luật từ khóa làm lớp kiểm tra chéo cho P1.

**Điều kiện chung:** đáp án phải là tập đóng, ngữ cảnh phải đủ thông tin, và cần một tập nhãn đã duyệt để đo độ chính xác và chọn ngưỡng trước khi triển khai.

**Việc nên làm tiếp:** chạy lại với `laya-typed-decisions`, thử Jev qua Vercel AI Gateway, thử đổi cách mô tả lựa chọn của `evidence` và `mixed_lanes`, và duyệt lại nhãn P2.
