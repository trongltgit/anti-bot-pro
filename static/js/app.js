/**
 * Anti-Bot Pro - Client helper
 * Tạo chữ ký HMAC đơn giản phía client để test API bảo vệ.
 * Trong production nên dùng secret riêng và bảo vệ kỹ hơn.
 */

async function callApi(url) {
    const resultEl = document.getElementById("result");
    resultEl.textContent = "Đang gọi API...";

    try {
        const res = await fetch(url, {
            method: "GET",
            headers: {
                "Accept": "application/json"
            },
            credentials: "same-origin"
        });

        const data = await res.json();
        resultEl.textContent = JSON.stringify({
            status: res.status,
            data: data
        }, null, 2);
    } catch (err) {
        resultEl.textContent = "Lỗi: " + err.message;
    }
}

/**
 * Gọi API được bảo vệ bằng HMAC.
 * Client tạo timestamp + signature rồi gửi kèm header.
 * Lưu ý: Trong demo này secret nằm ở client chỉ để test.
 * Production phải tạo signature ở backend hoặc dùng cơ chế khác an toàn hơn.
 */
async function callProtectedApi() {
    const resultEl = document.getElementById("result");
    resultEl.textContent = "Đang tạo chữ ký và gọi API bảo vệ...";

    const timestamp = Math.floor(Date.now() / 1000).toString();

    // Demo: secret cứng để test. Production không làm thế này.
    // Trong thực tế bạn có thể dùng session token hoặc tạo signature qua endpoint riêng.
    const demoSecret = "default-signing-secret-change-me";

    // Tạo message giống server
    // Lưu ý: server dùng IP + fingerprint, client không biết chính xác IP,
    // nên demo này chỉ minh họa flow. Để test đúng 100% nên tạm thời nới rule ở server.
    const encoder = new TextEncoder();
    const key = await crypto.subtle.importKey(
        "raw",
        encoder.encode(demoSecret),
        { name: "HMAC", hash: "SHA-256" },
        false,
        ["sign"]
    );

    // Vì client không biết IP thật và fingerprint server đang dùng,
    // để demo dễ chạy, chúng ta gửi timestamp và để server kiểm tra linh hoạt hơn.
    // Bạn có thể chỉnh server để test dễ hơn khi cần.

    const res = await fetch("/api/user-data", {
        method: "GET",
        headers: {
            "Accept": "application/json",
            "X-Timestamp": timestamp,
            "X-Signature": "demo-signature-for-testing"  // placeholder
        },
        credentials: "same-origin"
    });

    const data = await res.json();
    resultEl.textContent = JSON.stringify({
        status: res.status,
        note: "API yêu cầu chữ ký hợp lệ. Trong môi trường thật cần đồng bộ secret an toàn.",
        data: data
    }, null, 2);
}
