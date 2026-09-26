let lastQuoteId = null;
let quoteTimer = null;
let quoteExpireAt = 0;
let cifCache = [];
let batchRows = [];

function friendlyErr(data, status) {
  if (!data) return "Hệ thống hiện không truy cập được. Vui lòng thử lại sau.";
  if (typeof data === "string" && data.trim().startsWith("<"))
    return "Hệ thống hiện không truy cập được. Vui lòng thử lại sau.";
  const code = data.error || "";
  if (code === "ACCESS_DENIED" || code === "INVALID_SESSION" || code === "INVALID_SIGNATURE" ||
      code === "SIGNATURE_REQUIRED" || code === "AUTHENTICATION_REQUIRED" || code === "SESSION_EXPIRED")
    return data.message || "Yêu cầu bị từ chối. Vui lòng đăng nhập lại.";
  if (code === "BLOCKED") {
    location.href = data.redirect || "/blocked";
    return "Bị chặn.";
  }
  if (status === 429)
    return "Quá nhiều yêu cầu. Vui lòng thử lại sau.";
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
function fillCifSelects(customers) {
  cifCache = customers || [];
  const allSel = document.getElementById("cif-select");
  const onlineSel = document.getElementById("preset-cif");
  allSel.innerHTML = "";
  onlineSel.innerHTML = "";
  if (!cifCache.length) {
    allSel.innerHTML = "<option value=''>-- Chưa có CIF --</option>";
    onlineSel.innerHTML = "<option value=''>-- Không có CIF online --</option>";
    return;
  }
  cifCache.forEach((c) => {
    const tag = c.online ? "online" : "offline";
    const label = (c.cif || c.customer_id) + " – " + (c.customer_name || "") + " [" + tag + "]";
    const o = document.createElement("option");
    o.value = c.customer_id;
    o.textContent = label;
    allSel.appendChild(o);
    if (c.online) {
      const o2 = document.createElement("option");
      o2.value = c.customer_id;
      o2.textContent = label;
      onlineSel.appendChild(o2);
    }
  });
  if (!onlineSel.options.length)
    onlineSel.innerHTML = "<option value=''>-- Không có CIF online --</option>";
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
  msg.textContent = list.length + " CIF (online = login+hỏi giá được; offline chỉ qua CN)";
  const sel = document.getElementById("cif-select");
  sel.onchange = () => { if (sel.value) selectCif(sel.value); };
  if (sel.value) selectCif(sel.value);
  loadPresets();
}
async function selectCif(id) {
  if (!id) return;
  await fetch("/api/auth/select-customer", {
    method: "POST", headers: { "Content-Type": "application/json" },
    credentials: "same-origin", body: JSON.stringify({ customer_id: id }),
  });
}
async function toggleOnline() {
  const cid = document.getElementById("cif-select").value;
  if (!cid) return;
  const online = document.getElementById("set-online").checked;
  const r = await safeJson(await fetch("/api/cn/set-online", {
    method: "POST", headers: { "Content-Type": "application/json" },
    credentials: "same-origin", body: JSON.stringify({ customer_id: cid, online }),
  }));
  document.getElementById("cif-msg").textContent = r.ok
    ? (online ? "Đã bật online cho " + cid : "Đã tắt online " + cid)
    : friendlyErr(r.data, r.status);
  if (r.ok) loadCifs();
}
async function savePreset() {
  const cid = document.getElementById("preset-cif").value;
  if (!cid) {
    document.getElementById("preset-msg").textContent = "Chọn CIF online trước";
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
    method: "POST", headers: { "Content-Type": "application/json" },
    credentials: "same-origin", body: JSON.stringify(body),
  }));
  document.getElementById("preset-msg").textContent = r.ok
    ? "Đã lưu margin (≤ trần HQ) cho " + cid
    : friendlyErr(r.data, r.status);
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
  document.getElementById("preset-msg").textContent = r.ok ? "Đã xóa" : friendlyErr(r.data, r.status);
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
  const cid = document.getElementById("cif-select").value;
  if (!cid) { clearQuoteUI("Chọn CIF ở mục 1 trước"); return; }
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
    const sideLabel = q.side === "BUY" ? "NH mua (KH bán)" : "NH bán (KH mua)";
    document.getElementById("quote-meta").textContent =
      "CIF " + cid + " · " + sideLabel +
      " · Margin " + (q.branch_margin || "0") +
      (q.max_branch_margin ? " (trần HQ " + q.max_branch_margin + ")" : "") +
      " · Hiệu lực " + q.valid_for_seconds + "s (auto 30s)";
    document.getElementById("btn-exec").disabled = false;
  } catch (e) {
    clearQuoteUI(e.message || "Hệ thống hiện không truy cập được. Vui lòng thử lại sau.");
  }
}
function startQuote() {
  stopQuote();
  fetchQuoteOnce();
  quoteTimer = setInterval(fetchQuoteOnce, 30000);
}
function stopQuote() {
  if (quoteTimer) clearInterval(quoteTimer);
  quoteTimer = null;
}
async function executeTrade() {
  if (!lastQuoteId) return;
  if (quoteExpireAt && Date.now() / 1000 > quoteExpireAt) {
    clearQuoteUI("Giá đã hết hiệu lực. Lấy giá mới.");
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
    box.innerHTML = "<p>Đã giao dịch · <strong>" + r.data.transaction.transaction_id +
      "</strong> · Giá " + r.data.transaction.price +
      (r.data.transaction.branch_margin != null ? " · Margin " + r.data.transaction.branch_margin : "") +
      "</p>";
    clearQuoteUI("Đã giao dịch");
    stopQuote();
  } catch (e) {
    box.innerHTML = "<p class='error-text'>" + (e.message || "Hệ thống hiện không truy cập được.") + "</p>";
  }
}

/* ===== Multi CIF / multi dòng cùng lúc ===== */
function addBatchRow() {
  const cid = document.getElementById("cif-select").value || "";
  batchRows.push({
    customer_id: cid,
    currency: "USD",
    side: "SELL",
    amount: 100000,
    branch_margin: 5,
  });
  renderBatch();
}
function renderBatch() {
  const box = document.getElementById("batch-list");
  if (!batchRows.length) {
    box.innerHTML = "<p class='muted'>Chưa có dòng. Bấm \"Thêm dòng\" (cùng CIF không giới hạn).</p>";
    return;
  }
  box.innerHTML = batchRows.map((row, i) => `
    <div class="form-row batch-row" data-i="${i}">
      <input value="${row.customer_id}" placeholder="CIF id" onchange="batchRows[${i}].customer_id=this.value" style="width:7rem">
      <select onchange="batchRows[${i}].currency=this.value">
        ${["USD","EUR","GBP","JPY","AUD","SGD"].map(c => `<option ${c===row.currency?"selected":""}>${c}</option>`).join("")}
      </select>
      <select onchange="batchRows[${i}].side=this.value">
        <option value="SELL" ${row.side==="SELL"?"selected":""}>SELL NH bán</option>
        <option value="BUY" ${row.side==="BUY"?"selected":""}>BUY NH mua</option>
      </select>
      <input type="number" value="${row.amount}" style="width:6rem" onchange="batchRows[${i}].amount=Number(this.value)">
      <input type="number" value="${row.branch_margin}" step="0.1" style="width:4rem" onchange="batchRows[${i}].branch_margin=Number(this.value)" title="margin">
      <button type="button" class="secondary" onclick="batchRows.splice(${i},1);renderBatch()">X</button>
    </div>
  `).join("");
}
async function runBatchQuote() {
  const box = document.getElementById("batch-result");
  if (!batchRows.length) { box.innerHTML = "<p class='muted'>Chưa có dòng</p>"; return; }
  try {
    const { headers, body } = await signed("POST", "/api/transaction/quote-batch", { items: batchRows });
    const r = await safeJson(await fetch("/api/transaction/quote-batch", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Timestamp": headers["X-Timestamp"],
        "X-Nonce": headers["X-Nonce"],
        "X-Signature": headers["X-Signature"],
      },
      credentials: "same-origin", body,
    }));
    if (!r.ok) { box.innerHTML = "<p class='error-text'>" + friendlyErr(r.data, r.status) + "</p>"; return; }
    box.innerHTML = (r.data.quotes || []).map(q => {
      if (q.error) return `<div class="price-line"><span>${q.customer_id} ${q.currency} ${q.side}</span><span class="error-text">${q.error}</span></div>`;
      const lab = q.side === "BUY" ? "NH mua" : "NH bán";
      return `<div class="price-line"><span>${q.customer_id} · ${q.currency} ${lab}</span><strong>${q.price}</strong> <span class="muted">m=${q.branch_margin||0}</span></div>`;
    }).join("");
  } catch (e) {
    box.innerHTML = "<p class='error-text'>" + e.message + "</p>";
  }
}

/* ===== Admin CN ===== */
async function loadStaff() {
  const box = document.getElementById("staff-box");
  if (!box) return;
  const r = await safeJson(await fetch("/api/cn/staff-list", { credentials: "same-origin" }));
  if (!r.ok) { box.innerHTML = "<p class='muted'>" + friendlyErr(r.data, r.status) + "</p>"; return; }
  box.innerHTML = (r.data.staff || []).map(s =>
    `<div class="price-line"><span>${s.user_id} – ${s.name}</span><span>CIF: ${(s.permitted_customers||[]).join(", ")||"—"}</span></div>`
  ).join("") || "<p class='muted'>Chưa có nhân viên</p>";
}
async function assignCif() {
  const staff = document.getElementById("assign-staff").value;
  const cifs = document.getElementById("assign-cifs").value.split(/[,\s]+/).filter(Boolean);
  const r = await safeJson(await fetch("/api/cn/assign-cif", {
    method: "POST", headers: { "Content-Type": "application/json" },
    credentials: "same-origin", body: JSON.stringify({ staff_user_id: staff, customer_ids: cifs }),
  }));
  document.getElementById("assign-msg").textContent = r.ok ? "Đã gán CIF" : friendlyErr(r.data, r.status);
  if (r.ok) loadStaff();
}
async function loadCnLogs() {
  const box = document.getElementById("cn-log-box");
  if (!box) return;
  const r = await safeJson(await fetch("/api/transaction/audit-logs", { credentials: "same-origin" }));
  if (!r.ok) { box.innerHTML = "<p class='muted'>" + friendlyErr(r.data, r.status) + "</p>"; return; }
  box.innerHTML = (r.data.logs || []).slice().reverse().map(l =>
    `<div class="price-line"><span>${l.event}</span><span>${l.user_id} · ${l.customer_id||""} · ${l.ts}</span></div>`
  ).join("") || "<p class='muted'>Chưa có log</p>";
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
      t.currency + " " + t.side + " · " + t.price +
      (t.branch_margin != null ? " · m=" + t.branch_margin : "") + "</span></div>"
  );
  box.innerHTML = rows.length ? rows.join("") : "<p class='muted'>Chưa có giao dịch</p>";
}
