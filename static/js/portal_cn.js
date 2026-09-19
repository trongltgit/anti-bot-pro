let lastQuoteId = null;

async function logout() {
  await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
  location.href = "/login/cn";
}

async function loadCifs() {
  const res = await fetch("/api/customers/permitted", { credentials: "same-origin" });
  const data = await res.json();
  const sel = document.getElementById("cif-select");
  const msg = document.getElementById("cif-msg");
  sel.innerHTML = "";
  if (!res.ok) {
    msg.textContent = data.message || "Lỗi";
    return;
  }
  (data.customers || []).forEach((c) => {
    const o = document.createElement("option");
    o.value = c.customer_id;
    o.textContent = `${c.cif} – ${c.customer_name}`;
    sel.appendChild(o);
  });
  msg.textContent = (data.customers || []).length + " khách hàng";
  sel.onchange = () => selectCif(sel.value);
  if (sel.value) selectCif(sel.value);
}

async function selectCif(id) {
  await fetch("/api/auth/select-customer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify({ customer_id: id }),
  });
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
  const box = document.getElementById("quote-box");
  const cid = document.getElementById("cif-select").value;
  if (cid) await selectCif(cid);
  const bodyObj = {
    currency: document.getElementById("currency").value,
    side: document.getElementById("side").value,
    amount: Number(document.getElementById("amount").value),
    branch_margin: Number(document.getElementById("margin").value || 0),
  };
  box.innerHTML = "<p class='muted'>Đang lấy giá...</p>";
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
      box.innerHTML = `<p class="error-text">${data.message || "Không lấy được giá"}</p>`;
      document.getElementById("btn-exec").disabled = true;
      return;
    }
    const q = data.quote;
    lastQuoteId = q.quote_id;
    box.innerHTML = `
      <div class="price-line"><span>Giá thị trường</span><strong>${q.market_rate || "—"}</strong></div>
      <div class="price-line"><span>Margin chi nhánh</span><strong>${q.branch_margin || "0"}</strong></div>
      <div class="price-line highlight"><span>Giá khách hàng</span><strong>${q.price}</strong></div>
      <p class="muted small">Hiệu lực ${q.valid_for_seconds}s · Không hiển thị chính sách Hội sở</p>
    `;
    document.getElementById("btn-exec").disabled = false;
  } catch (e) {
    box.innerHTML = `<p class="error-text">${e.message}</p>`;
  }
}

async function executeTrade() {
  const box = document.getElementById("trade-box");
  if (!lastQuoteId) return;
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
      box.innerHTML = `<p class="error-text">${data.message || "Lỗi"}</p>`;
      return;
    }
    const t = data.transaction;
    box.innerHTML = `<p>Đã giao dịch <strong>${t.transaction_id}</strong> · Giá ${t.price} · ${t.currency} ${t.side}</p>`;
    document.getElementById("btn-exec").disabled = true;
    lastQuoteId = null;
  } catch (e) {
    box.innerHTML = `<p class="error-text">${e.message}</p>`;
  }
}

async function loadHistory() {
  const box = document.getElementById("history-box");
  const res = await fetch("/api/transaction/history", { credentials: "same-origin" });
  const data = await res.json();
  if (!res.ok) {
    box.innerHTML = `<p class="error-text">${data.message || "Lỗi"}</p>`;
    return;
  }
  const rows = (data.transactions || []).map(
    (t) => `<div class="price-line"><span>${t.transaction_id}</span><span>${t.currency} ${t.side} · ${t.price}</span></div>`
  );
  box.innerHTML = rows.length ? rows.join("") : "<p class='muted'>Chưa có giao dịch</p>";
}
