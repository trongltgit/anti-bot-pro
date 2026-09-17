# Anti-Bot Pro – Mô hình Web chống Bot / Crawling chuyên nghiệp

Phiên bản nâng cao, thiết kế rõ ràng, sẵn sàng triển khai lên Render hoặc bất kỳ PaaS nào.

## Các lớp bảo vệ đã tích hợp

1. **Rate Limiting** nhiều mức (theo IP, theo endpoint)
2. **Browser Fingerprint** + gắn vào session
3. **Phát hiện User-Agent bot** phổ biến
4. **Chữ ký HMAC + chống Replay Attack** cho API nhạy cảm
5. **Phân tách endpoint** theo mức độ nhạy cảm
6. **Sẵn sàng** kết nối Redis + Cloudflare

## Cấu trúc thư mục

```
anti-bot-pro/
├── app/
│   ├── __init__.py          # Khởi tạo Flask + Limiter
│   └── routes.py            # Các route chính + API
├── utils/
│   ├── security.py          # Fingerprint, HMAC, UA check
│   └── rate_limit.py        # Decorator rate limit
├── templates/               # HTML
├── static/                  # CSS + JS
├── app.py                   # Entry point
├── requirements.txt
└── README.md
```

## Chạy local

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
export SECRET_KEY="your-very-long-secret-key-here"
export API_SIGNING_SECRET="another-secret-for-hmac"
python app.py
```

Mở http://localhost:5000

## Deploy lên Render (khuyến nghị)

1. Đẩy code lên GitHub
2. Tạo **New Web Service** trên Render
3. Kết nối repo
4. Cấu hình:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
5. Thêm Environment Variables:
   - `SECRET_KEY` = chuỗi dài ngẫu nhiên
   - `API_SIGNING_SECRET` = chuỗi dài ngẫu nhiên khác
   - (Tùy chọn) `REDIS_URL` nếu dùng Redis

## Cách mở rộng chuyên nghiệp hơn

- Thêm **Cloudflare Turnstile** (CAPTCHA hiện đại)
- Dùng **FingerprintJS** phía client để fingerprint mạnh hơn
- Chuyển rate limit sang **Redis** (thêm `REDIS_URL`)
- Thêm **JWT + MFA** cho phần đăng nhập
- Ghi **Audit Log** mọi truy cập dữ liệu nhạy cảm
- Kết hợp **Cloudflare WAF Bot Management** phía trước

## Lưu ý bảo mật

- Đổi toàn bộ secret trước khi lên production
- Không bao giờ để secret HMAC nằm ở phía client
- Endpoint `/api/user-data` và `/api/sensitive` phải yêu cầu đăng nhập thật trong hệ thống thật
- Nên đặt Cloudflare hoặc WAF phía trước toàn bộ traffic

---
Tạo bởi Grok – phục vụ mục đích bảo vệ hệ thống giao dịch / dữ liệu khách hàng.
