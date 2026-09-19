# Anti-Bot Pro – Giá 2 cấp + 3 vai trò (HQ / CN / KH)

## Ai thấy gì?

| | Market price | HQ base_spread | branch_margin | Final price | Sửa chính sách HQ |
|--|--------------|----------------|---------------|-------------|-------------------|
| **HQ** (Hội sở) | Có | Có | Có | Có | **Có** |
| **CN** (Chi nhánh) | Có | **Không** | Có (của mình) | Có | Không |
| **KH** (Khách hàng) | Không | Không | Không | **Chỉ final** | Không |

Market price là giá thị trường công khai → CN được xem.  
Chính sách HQ (base_spread) khóa server-side, chỉ role HQ truy cập API `/api/hq/policy*`.

---

## Tài khoản demo

| Username | Password | Vai trò |
|----------|----------|---------|
| `hq01` | `demo123` | Hội sở – quản lý chính sách |
| `staff01` | `demo123` | Chi nhánh – nhập margin |
| `cust001` | `demo123` | Khách hàng – chỉ final price |

---

## Cách test 3 màn hình

### 1. Hội sở (`hq01`)
1. Login → hiện panel **Quản lý chính sách HQ**
2. Tải chính sách → thấy base_spread + max_branch_margin theo GOLD/SILVER/BRONZE
3. Sửa base_spread USD SELL GOLD = 10 → Lưu
4. Chọn CIF CUST001 → Lấy giá → thấy **market_rate + hq_base_spread + branch_margin + final**

### 2. Chi nhánh (`staff01`)
1. Login → **không** thấy panel HQ
2. Gọi `/api/hq/policy` → **403 HQ_ONLY**
3. Chọn CIF → nhập branch_margin = 5 → Lấy giá
4. Thấy: **market_rate + branch_margin + max_branch_margin + final**
5. **Không** có `hq_base_spread`
6. Thử margin quá trần → lỗi

### 3. Khách hàng (`cust001`)
1. Login → CIF gắn sẵn
2. Lấy giá → response **chỉ** `price` (final)
3. Không market, không margin, không HQ

### 4. Kiểm tra khóa chính sách
- Đổi base_spread ở HQ → CN lấy giá lại thấy final đổi (vì công thức server) nhưng CN vẫn không thấy con số HQ
- CN/KH không sửa được policy

---

## Chạy local / Render

```bash
pip install -r requirements.txt
export SECRET_KEY=dev SECRET_KEY
export API_SIGNING_SECRET=dev-signing
export SESSION_COOKIE_SECURE=0
python app.py
```

Render: Start `gunicorn app:app`, env `SECRET_KEY`, `API_SIGNING_SECRET`, `SESSION_COOKIE_SECURE=1`.

---

Anti-Bot (Fingerprint + HMAC + Nonce + Rate limit + AuthZ) áp dụng mọi API quote/execute/policy.
