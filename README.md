# Anti-Bot Pro – Giá 2 cấp + 3 vai trò (HQ / CN / KH)

## Chính sách giá (TSC)

| Thành phần | Mô tả |
|------------|--------|
| **Base TSC** | Tỷ giá gốc do Hội sở quản lý |
| **Mode** | `auto` (dao động real-time mỗi **20 giây**) hoặc `manual` (TSC set tay) |
| **HQ base_spread** | Điểm spread theo tier / currency / side |
| **CN margin** | Margin chi nhánh (≤ trần HQ), gắn theo CIF |
| **Final price** | base ± (HQ spread + CN margin) |
| **TGDH / NSDH** | Final price **± điểm điều hòa** (TSC set) |

### Side – logic nhất quán

API / internal **luôn dùng chiều Ngân hàng (NH)**:

| Side API | Ý nghĩa | Công thức |
|----------|---------|-----------|
| **BUY** | NH mua (KH bán ngoại tệ) | `base − total_spread` → **thấp hơn** |
| **SELL** | NH bán (KH mua ngoại tệ) | `base + total_spread` → **cao hơn** |

Hiển thị theo role:

- **USER TSC (HQ) / CN**: chiều bán = NH bán, chiều mua = NH mua
- **USER KH**: UI "Mua" = KH mua = NH bán (API `SELL`); UI "Bán" = KH bán = NH mua (API `BUY`)

**Ràng buộc cùng thời điểm + cùng CIF:**

- Giá **KH bán** luôn **<** giá **KH mua**
- Tương đương: NH BUY < NH SELL (được đảm bảo bởi công thức ± spread)

### Auto update

- Base TSC (mode auto): đổi mỗi **20 giây**
- CN theo dõi giá / KH quote: hiệu lực **30 giây**, CN auto-refresh mỗi **30 giây**

---

## Ai thấy gì?

| | Base TSC | HQ spread | TGDH points | CN margin | Final / TGDH | Sửa policy |
|--|----------|-----------|-------------|-----------|--------------|------------|
| **HQ** | Có | Có | Có | Có | Có | **Có** |
| **CN** | Không* | Không | Không | Có (của mình) | Có | Không |
| **KH** | Không | Không | Không | Không | **Chỉ final (+ TGDH)** | Không |

*CN có thể xem market công khai nếu cần; base_spread HQ khóa server-side.

---

## Tài khoản demo

| Username | Password | Vai trò |
|----------|----------|---------|
| `hq01` | `demo123` | Hội sở – quản lý chính sách + base TSC |
| `staff01` | `demo123` | Chi nhánh – nhập margin |
| `cust001` | `demo123` | Khách hàng – chỉ final price |

---

## API HQ mới

| Endpoint | Mô tả |
|----------|--------|
| `GET /api/hq/market-rate` | Xem base TSC + mode |
| `POST /api/hq/market-rate/mode` | `{ "mode": "auto" \| "manual" }` |
| `POST /api/hq/market-rate/set` | `{ "currency": "USD", "rate": "26250" }` |
| `POST /api/hq/policy/tgdh-points` | `{ "currency": "USD", "value": "5" }` (dương/âm) |

---

## Chạy local / Render

```bash
pip install -r requirements.txt
export SECRET_KEY=dev-secret
export API_SIGNING_SECRET=dev-signing
export SESSION_COOKIE_SECURE=0
python app.py
```

Render: Start `gunicorn app:app`, env `SECRET_KEY`, `API_SIGNING_SECRET`, `SESSION_COOKIE_SECURE=1`.

Optional env:

- `HQ_BASE_MODE=auto|manual`
- `HQ_BASE_JITTER_PCT=0.08`
- `PRICING_QUOTE_VALID_SECONDS=30`

---

Anti-Bot (Fingerprint + HMAC + Nonce + Rate limit + AuthZ) áp dụng mọi API quote/execute/policy.
