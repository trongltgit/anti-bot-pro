let lastQuoteId = null;
let quoteExpireAt = 0;

function friendlyErr(data, status) {
  if (!data) return "Hệ thống hiện không truy cập được. Vui lòng thử lại sau.";
  if (typeof data === "string" && data.trim().startsWith("<"))
    return "Hệ thống hiện không truy cập được. Vui lòng thử lại sau.";
  if (data.error === "WAITING_CN_SETUP")
    return data.message || "Chưa có báo giá từ chi nhánh. Vui lòng liên hệ chi nhánh.";
  return data.message || data.error || "Hệ thống hiện không truy cập được. Vui lòng thử lại sau.";
}
async function safeJson(res) {
  const text = await res.text();
  try { return { ok: res.ok, status: res.status, data: JSON.parse(text) }; }
  catch {
    return { ok: false, status: res.status, data: { message: "Hệ thống hiện không truy cập được. Vui lòng thử lại sau." } };
  }
}
async function logout() {
  await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
  location.href = "/";
}
function clearPrice(msg) {
  lastQuoteId = null;
  quoteExpireAt = 0;
  document.getElementById("final-price").textContent = "—";
  document.getElementById("price-meta").textContent = "";
  document.getElementById("trade-msg").textContent = "";
  document.getElementById("price-card").style.display = "none";
  document.getElementById("msg").textContent = msg || "";
}
async function signed(method, path, bodyObj) {
  const body = JSON.stringify(bodyObj);
  const r = await safeJson(await fetch("/api/sign-helper", {
    method: "POST", headers: { "Content-Type": "application/json" },
    credentials: "same-origin", body: JSON.stringify({ method, path, body }),
  }));
  if (!r.ok) throw new Error(friendlyErr(r.data, r.status));
  return { headers: r.data.headers, body };
}
async function getQuote() {
  clearPrice("Đang lấy giá...");
  // UI: chiều KH; API: chiều NH (đảo)
  const khSide = document.getElementById("side").value;
  const bankSide = khSide === "BUY" ? "SELL" : "BUY";
  const bodyObj = {
    currency: document.getElementById("currency").value,
    side: bankSide,
    amount: Number(document.getElementById("amount").value),
  };
  try {
    const { headers, body } = await signed("POST", "/api/transaction/quote", bodyObj);
    const r = await safeJson(await fetch("/api/transaction/quote", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Timestamp": headers["X-Timestamp"],
        "X-Nonce": headers["X-Nonce"],
        "X-Signature": headers["X-Signature"],
      },
      credentials: "same-origin", body,
    }));
    if (!r.ok) {
      clearPrice(friendlyErr(r.data, r.status));
      return;
    }
    const q = r.data.quote;
    lastQuoteId = q.quote_id;
    quoteExpireAt = (q.issued_at || Math.floor(Date.now() / 1000)) + (q.valid_for_seconds || 30);
    document.getElementById("msg").textContent = "";
    document.getElementById("price-card").style.display = "block";
    document.getElementById("final-price").textContent = q.price;
    document.getElementById("price-meta").textContent =
      q.currency + " · Bạn " + (khSide === "BUY" ? "mua" : "bán") +
      " · Hiệu lực " + q.valid_for_seconds + " giây";
  } catch (e) {
    clearPrice(e.message || "Hệ thống hiện không truy cập được. Vui lòng thử lại sau.");
  }
}
async function executeTrade() {
  if (!lastQuoteId) {
    document.getElementById("trade-msg").textContent = "Vui lòng xem giá trước.";
    return;
  }
  if (quoteExpireAt && Date.now() / 1000 > quoteExpireAt) {
    clearPrice("Giá đã hết hiệu lực. Vui lòng xem giá lại.");
    return;
  }
  const tm = document.getElementById("trade-msg");
  tm.textContent = "Đang xử lý...";
  try {
    const { headers, body } = await signed("POST", "/api/transaction/execute", { quote_id: lastQuoteId });
    const r = await safeJson(await fetch("/api/transaction/execute", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Timestamp": headers["X-Timestamp"],
        "X-Nonce": headers["X-Nonce"],
        "X-Signature": headers["X-Signature"],
      },
      credentials: "same-origin", body,
    }));
    if (!r.ok) {
      clearPrice(friendlyErr(r.data, r.status));
      return;
    }
    tm.textContent = "Giao dịch thành công · Mã " + r.data.transaction.transaction_id;
    lastQuoteId = null;
  } catch (e) {
    clearPrice(e.message || "Hệ thống hiện không truy cập được. Vui lòng thử lại sau.");
  }
}
async function loadHistory() {
  const box = document.getElementById("history-box");
  const r = await safeJson(await fetch("/api/transaction/history", { credentials: "same-origin" }));
  if (!r.ok) {
    box.innerHTML = "<p class='error-text'>" + friendlyErr(r.data, r.status) + "</p>";
    return;
  }
  const rows = (r.data.transactions || []).map(
    (t) => "<div class='price-line'><span>" + t.transaction_id + "</span><span>" +
      t.currency + " · " + t.price + "</span></div>"
  );
  box.innerHTML = rows.length ? rows.join("") : "<p class='muted'>Chưa có giao dịch</p>";
}
