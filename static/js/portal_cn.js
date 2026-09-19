let lastQuoteId = null;
let quoteTimer = null;
let quoteExpireAt = 0;

function friendlyErr(data, status) {
  if (!data) return "Hệ thống hiện không truy cập được. Vui lòng thử lại sau.";
  if (typeof data === "string" && data.trim().startsWith("<"))
    return "Hệ thống hiện không truy cập được. Vui lòng thử lại sau.";
  return data.message || data.error || ("Lỗi " + status);
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
function fillCifSelects(customers) {
  ["cif-select", "preset-cif"].forEach((id) => {
    const sel = document.getElementById(id);
    sel.innerHTML = "";
    if (!customers || !customers.length) {
      const o = document.createElement("option");
      o.value = ""; o.textContent = "-- Chưa có CIF --";
      sel.appendChild(o);
      return;
    }
    customers.forEach((c) => {
      const o = document.createElement("option");
      o.value = c.customer_id;
      o.textContent = (c.cif || c.customer_id) + " – " + (c.customer_name || "");
      sel.appendChild(o);
    });
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
  (r.data.branches || []).forEach((b) => {
    const o = document.createElement("option");
    o.value = b.branch_id;
    o.textContent = b.branch_name + " (" + b.branch_id + ")";
    sel.appendChild(o);
  });
  sel.onchange = loadCifs;
  if (sel.value) loadCifs();
}
async function loadCifs() {
  const bid = document.getElementById("branch-select").value;
  const msg = document.getElementById("cif-msg");
  if (!bid) { fillCifSelects([]); msg.textContent = "Chọn chi nhánh"; return; }
  const r = await safeJson(await fetch("/api/branches/" + encodeURIComponent(bid) + "/customers", { credentials: "same-origin" }));
  if (!r.ok) { fillCifSelects([]); msg.textContent = friendlyErr(r.data, r.status); return; }
  const list = r.data.customers || [];
  fillCifSelects(list);
  msg.textContent = list.length + " CIF";
  const sel = document.getElementById("cif-select");
  sel.onchange = () => {
    if (sel.value) selectCif(sel.value);
    document.getElementById("preset-cif").value = sel.value;
  };
  if (sel.value) { selectCif(sel.value); document.getElementById("preset-cif").value = sel.value; }
  loadPresets();
}
async function selectCif(id) {
  if (!id) return;
  await fetch("/api/auth/select-customer", {
    method: "POST", headers: { "Content-Type": "application/json" },
    credentials: "same-origin", body: JSON.stringify({ customer_id: id }),
  });
}
async function savePreset() {
  const cid = document.getElementById("preset-cif").value || document.getElementById("cif-select").value;
  if (!cid) { document.getElementById("preset-msg").textContent = "Chọn CIF trước"; return; }
  await selectCif(cid);
  const body = {
    customer_id: cid,
    currency: document.getElementById("p-cur").value,
    side: document.getElementById("p-side").value,
    margin: Number(document.getElementById("p-margin").value || 0),
  };
  const r = await safeJson(await fetch("/api/cn/margin-preset", {
    method: "POST", headers: { "Content-Type": "application/json" },
    credentials: "same-origin", body: JSON.stringify(body),
  }));
  document.getElementById("preset-msg").textContent = r.ok ? "Đã lưu margin CIF " + cid : friendlyErr(r.data, r.status);
  if (r.ok) loadPresets();
}
async function loadPresets() {
  const box = document.getElementById("preset-list");
  const r = await safeJson(await fetch("/api/cn/margin-preset", { credentials: "same-origin" }));
  if (!r.ok) { box.innerHTML = "<p class='error-text'>" + friendlyErr(r.data, r.status) + "</p>"; return; }
  const items = r.data.presets || [];
  if (!items.length) { box.innerHTML = "<p class='muted'>Chưa lưu margin nào</p>"; return; }
  box.innerHTML = items.map((p) =>
    "<div class='price-line'><span>" + p.customer_id + " · " + p.currency + " " + p.side +
    "</span><span>margin " + p.margin +
    " <button type='button' class='secondary' data-c='" + p.customer_id + "' data-cur='" + p.currency +
    "' data-s='" + p.side + "' onclick='delPreset(this)'>Xóa</button></span></div>"
  ).join("");
}
async function delPreset(btn) {
  const r = await safeJson(await fetch("/api/cn/margin-preset/delete", {
    method: "POST", headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify({
      customer_id: btn.getAttribute("data-c"),
      currency: btn.getAttribute("data-cur"),
      side: btn.getAttribute("data-s"),
    }),
  }));
  document.getElementById("preset-msg").textContent = r.ok ? "Đã xóa margin" : friendlyErr(r.data, r.status);
  loadPresets();
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
function clearQuoteUI(msg) {
  document.getElementById("final-px").textContent = "—";
  document.getElementById("quote-meta").textContent = msg || "";
  document.getElementById("btn-exec").disabled = true;
  lastQuoteId = null;
  quoteExpireAt = 0;
}
async function fetchQuoteOnce() {
  if (quoteExpireAt && Date.now() / 1000 > quoteExpireAt) {
    clearQuoteUI("Giá đã hết hiệu lực. Đang lấy giá mới...");
  }
  const cid = document.getElementById("cif-select").value;
  if (!cid) { clearQuoteUI("Chọn CIF trước"); return; }
  await selectCif(cid);
  const bodyObj = {
    currency: document.getElementById("currency").value,
    side: document.getElementById("side").value,
    amount: Number(document.getElementById("amount").value),
    branch_margin: Number(document.getElementById("margin").value || 0),
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
      clearQuoteUI(friendlyErr(r.data, r.status));
      return;
    }
    const q = r.data.quote;
    lastQuoteId = q.quote_id;
    quoteExpireAt = (q.issued_at || Math.floor(Date.now() / 1000)) + (q.valid_for_seconds || 30);
    document.getElementById("final-px").textContent = q.price;
    document.getElementById("quote-meta").textContent =
      "Margin CN: " + (q.branch_margin || "0") + " · Hiệu lực " + q.valid_for_seconds + "s (HQ cấu hình)";
    document.getElementById("btn-exec").disabled = false;
  } catch (e) {
    clearQuoteUI(e.message || "Hệ thống hiện không truy cập được. Vui lòng thử lại sau.");
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
  if (quoteExpireAt && Date.now() / 1000 > quoteExpireAt) {
    clearQuoteUI("Giá đã hết hiệu lực. Lấy giá mới trước khi giao dịch.");
    return;
  }
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
      credentials: "same-origin", body,
    }));
    if (!r.ok) {
      box.innerHTML = "<p class='error-text'>" + friendlyErr(r.data, r.status) + "</p>";
      return;
    }
    box.innerHTML = "<p>Đã thực hiện · Mã <strong>" + r.data.transaction.transaction_id +
      "</strong> · Giá " + r.data.transaction.price + "</p>";
    clearQuoteUI("Đã giao dịch");
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
    (t) => "<div class='price-line'><span>" + t.transaction_id + "</span><span>" +
      t.currency + " " + t.side + " · " + t.price + "</span></div>"
  );
  box.innerHTML = rows.length ? rows.join("") : "<p class='muted'>Chưa có giao dịch</p>";
}
loadBranches();
