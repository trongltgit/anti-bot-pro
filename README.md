# Anti-Bot Pro – TSC / CN / KH Pricing + Anti-bot

## Demo accounts

| User | Pass | Role |
|------|------|------|
| hq01 | demo123 | TSC – quản user, policy, blocked, log |
| admin_cn01 | demo123 | Admin CN Q1 – gán CIF staff |
| admin_cn02 | demo123 | Admin CN Q3 |
| staff01 | demo123 | NV CN1 – CIF 001,003 |
| staff02 | demo123 | NV CN1 – CIF 004,005,008 |
| staff03 | demo123 | NV CN2 – CIF 002,006 |
| cust001 / cust002 / cust003 | demo123 | KH online |

10 CIF demo: CUST001–CUST010 (CN001 / CN002).

## Logic giá

- CN chỉ thấy: **final + margin CN + TGDH** (nếu chọn NSDH)
- KH chỉ thấy giá đã set (TGDH nếu CN bật NSDH, không thì final)
- TSC thấy hết; **margin CN chỉ sau deal done**
- Cùng CIF + cùng lúc: **KH mua > KH bán**

## Quote / Anti-spam KH

- Giá online **hiệu lực 60 giây**
- Cùng currency + side + amount bấm liên tục → **cooldown 1 phút**:  
  *“Hiện tại hệ thống không cập nhật giá được, xin vui lòng thử lại sau.”*
- Đổi bất kỳ yếu tố (ccy / side / amount) → hỏi lại được
- CN đổi margin/NSDH → **interrupt** mọi quote CIF đó

## Bot / Crawl

- Flood quote (≥20/phút) → **block user** (TSC mở khóa)
- Crawling không login / UA bot → log `crawl_attempt` + từ chối rõ
- TSC: danh sách blocked + unlock / lock tay để test

## Log

- Mọi hỏi giá + giao dịch + crawl/bot
- TSC / Admin CN: xem + **xuất CSV (Excel)** / text

## Chạy

```bash
pip install -r requirements.txt
export SECRET_KEY=dev API_SIGNING_SECRET=dev SESSION_COOKIE_SECURE=0
python app.py
# hoặc gunicorn run:app
```
