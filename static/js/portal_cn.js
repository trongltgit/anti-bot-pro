let lastQuoteId = null;
let quoteTimer = null;

function friendlyErr(data, status) {
  if (!data) return "Hệ thống hiện không truy cập được. Vui lòng thử lại sau.";
  if (typeof data === "string" && data.trim().startsWith("<"))
    return "Hệ thống hiện không truy cập được. Vui lòng thử lại sau.";
  return data.message || data.error || ("Lỗi " + status);
}

async function safeJson(res) {
  const text = await res.text();
  try {
    return { ok: res.ok, status: res.status, data: JSON.parse(text) };
  } catch {
    return { ok: false, status: res.status, data: { message: "Hệ thống hiện không truy cập được. Vui lòng thử lại sau." } };
  }
}

async function logout() {
  await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
  location.href = "/";
}

function fillCifSelects(customers) {
  const sel = document.getElementById("cif-select");
  const preset = document.getElementById("preset-cif");
  sel.innerHTML = "";
  preset.innerHTML = "";
  if (!customers || !customers.length) {
    const o1 = document.createElement("option");
    o1.value = "";
    o1.textContent = "-- Chưa có CIF --";
    sel.appendChild(o1);
    preset.appendChild(o1.cloneNode(true));
    return;
  }
  customers.forEach((c) => {
    const label = (c.cif || c.customer_id) + " – " + (c.customer_name || "");
    const o1 = document.createElement("option");
    o1.value = c.customer_id;
    o1.textContent = label;
    sel.appendChild(o1);
    const o2 = document.createElement("option");
    o2.value = c.customer_id;
    o2.textContent = label;
    preset.appendChild(o2);
  });
}

async function loadBranches() {
  const r = await safeJson(await fetch("/api/branches", { credentials: "same-origin" }));
  const sel = document.getElementById("branch-select");
  sel.innerHTML = "";
  if (!r.ok) {
    document.getElementById("cif-msg").textContent = friendlyErr(r.data, r.status);
    return;
  }
  const branches = r.data.branches || [];
  if (!branches.length) {
    sel.innerHTML = "<option value=''>-- Không có chi nhánh --</option>";
    document.getElementById("cif-msg").textContent = "Không có chi nhánh được gán";
    return;
  }
  branches.forEach((b) => {
    const o = document.createElement("option");
    o.value = b.branch_id;
    o.textContent = b.branch_name + " (" + b.branch_id + ")";
    sel.appendChild(o);
  });
  sel.onchange = loadCifs;
  loadCifs();
}

async function loadCifs() {
  const bid = document.getElementById("branch-select").value;
  const msg = document.getElementById("cif-msg");
  if (!bid) {
    fillCifSelects([]);
    msg.textContent = "Chọn chi nhánh trước";
    return;
  }
  const r = await safeJson(await fetch("/api/branches/" + encodeURIComponent(bid) + "/customers", { credentials: "same-origin" }));
  if (!r.ok) {
    fillCifSelects([]);
    msg.textContent = friendlyErr(r.data, r.status);
    return;
  }
  const list = r.data.customers || [];
  fillCifSelects(list);
  msg.textContent = list.length + " CIF thuộc chi nhánh";
  const sel = document.getElementById("cif-select");
  sel.onchange = () => {
    if (sel.value) selectCif(sel.value);
    document.getElementById("preset-cif").value = sel.value;
  };
  if (sel.value) {
    selectCif(sel.value);
    document.getElementById("preset-cif").value = sel.value;
  }
}

async function selectCif(id) {
  if (!id) return;
  await fetch("/api/auth/select-customer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify({ customer_id: id }),
  });
}

async function savePreset() {
  const cid = document.getElementById("preset-cif").value || document.getElementById("cif-select").value;
  if (!cid) {
    document.getElementById("preset-msg").textContent = "Chọn CIF trước khi lưu margin";
    return;
  }
  await selectCif(cid);
  const body = {
    customer_id: cid,
    currency: document.getElementById("p-cur").value,
    side: document.getElementById("p-side").value,
    margin: Number(document.getElementById("p-margin").value || 0),
  };
  const r = await safeJson(await fetch("/api/cn/margin-preset", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify(body),
  }));
  document.getElementById("preset-msg").textContent = r.ok
    ? "Đã lưu margin cho CIF " + cid
    : friendlyErr(r.data, r.status);
}

async function signed(method, path, bodyObj) {
  const body = JSON.stringify(bodyObj);
  const r = await safeJson(await fetch("/api/sign-helper", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify({ method, path, body }),
  }));
  if (!r.ok) throw new Error(friendlyErr(r.data, r.status));
  return { headers: r.data.headers, body };
}

async function fetchQuoteOnce() {
  const cid = document.getElementById("cif-select").value;
  if (!cid) {
    document.getElementById("quote-meta").textContent = "Chọn CIF trước";
    return;
  }
  await selectCif(cid);
  const bodyObj = {
    currency: document.getElementById("currency").value,
    side: document.getElementById("side").value,
    amount: Number(document.getElementById("amount").value),
    branch_margin: Number(document.getElementById("margin").value || 0),
  };
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
    const r = await safeJson(res);
    if (!r.ok) {
      document.getElementById("final-px").textContent = "—";
      document.getElementById("quote-meta").textContent = friendlyErr(r.data, r.status);
      document.getElementById("btn-exec").disabled = true;
      return;
    }
    const q = r.data.quote;
    lastQuoteId = q.quote_id;
    document.getElementById("final-px").textContent = q.price;
    document.getElementById("quote-meta").textContent =
      "Margin CN: " + (q.branch_margin || "0") + " · Cập nhật lại sau " + q.valid_for_seconds + "s";
    document.getElementById("btn-exec").disabled = false;
  } catch (e) {
    document.getElementById("quote-meta").textContent = e.message || "Hệ thống hiện không truy cập được.";
  }
}

function startQuote() {
  stopQuote();
  fetchQuoteOnce();
  quoteTimer = setInterval(fetchQuoteOnce, 5000);
}

function stopQuote() {
  if (quoteTimer) clearInterval(quoteTimer);
  quoteTimer = null;
}

async function executeTrade() {
  if (!lastQuoteId) return;
  const box = document.getElementById("trade-box");
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
      credentials: "same-origin",
      body,
    }));
    if (!r.ok) {
      box.innerHTML = "<p class='error-text'>" + friendlyErr(r.data, r.status) + "</p>";
      return;
    }
    box.innerHTML = "<p>Đã thực hiện · Mã <strong>" + r.data.transaction.transaction_id + "</strong> · Giá " + r.data.transaction.price + "</p>";
    document.getElementById("btn-exec").disabled = true;
    lastQuoteId = null;
    stopQuote();
  } catch (e) {
    box.innerHTML = "<p class='error-text'>" + (e.message || "Hệ thống hiện không truy cập được.") + "</p>";
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
    (t) => "<div class='price-line'><span>" + t.transaction_id + "</span><span>" + t.currency + " " + t.side + " · " + t.price + "</span></div>"
  );
  box.innerHTML = rows.length ? rows.join("") : "<p class='muted'>Chưa có giao dịch</p>";
}

loadBranches();
