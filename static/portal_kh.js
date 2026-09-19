let lastQuoteId = null;

async function logout() {
  await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
  location.href = "/";
}

async function signed(method, path, bodyObj) {
  const body = JSON.stringify(bodyObj);
  const res = await fetch("/api/sign-helper", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify({ method, path, body }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.message || "Sign failed");
  return { headers: data.headers, body };
}

async function getQuote() {
  const card = document.getElementById("price-card");
  const bodyObj = {
    currency: document.getElementById("currency").value,
    side: document.getElementById("side").value,
    amount: Number(document.getElementById("amount").value),
  };
  document.getElementById("final-price").textContent = "...";
  card.style.display = "block";
  try {
    const { headers, body } = await signed("POST", "/api/transaction/quote", bodyObj);
    const res = await fetch("/api/transaction/quote", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Timestamp": headers["X-Timestamp"],
        "X-Nonce": headers["X-Nonce"],
        "X-Signature": headers["X-Signature"],
      },
      credentials: "same-origin",
      body,
    });
    const data = await res.json();
    if (!res.ok) {
      document.getElementById("final-price").textContent = "—";
      document.getElementById("price-meta").textContent = data.message || "Không lấy được giá";
      lastQuoteId = null;
      return;
    }
    const q = data.quote;
    lastQuoteId = q.quote_id;
    document.getElementById("final-price").textContent = q.price;
    document.getElementById("price-meta").textContent =
      q.currency + " · " + q.side + " · hiệu lực " + q.valid_for_seconds + " giây";
    document.getElementById("trade-msg").textContent = "";
  } catch (e) {
    document.getElementById("price-meta").textContent = e.message;
  }
}

async function executeTrade() {
  if (!lastQuoteId) return;
  const msg = document.getElementById("trade-msg");
  msg.textContent = "Đang xử lý...";
  try {
    const { headers, body } = await signed("POST", "/api/transaction/execute", { quote_id: lastQuoteId });
    const res = await fetch("/api/transaction/execute", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Timestamp": headers["X-Timestamp"],
        "X-Nonce": headers["X-Nonce"],
        "X-Signature": headers["X-Signature"],
      },
      credentials: "same-origin",
      body,
    });
    const data = await res.json();
    if (!res.ok) {
      msg.textContent = data.message || "Giao dịch thất bại";
      return;
    }
    msg.textContent = "Thành công · Mã " + data.transaction.transaction_id;
    lastQuoteId = null;
  } catch (e) {
    msg.textContent = e.message;
  }
}
