function friendlyErr(data, status) {
  if (!data) return "Hệ thống hiện không truy cập được.";
  if (typeof data === "string" && data.trim().startsWith("<"))
    return "Hệ thống hiện không truy cập được.";
  return data.message || data.error || ("Lỗi " + status);
}
async function safeJson(res) {
  const text = await res.text();
  try { return { ok: res.ok, status: res.status, data: JSON.parse(text) }; }
  catch { return { ok: false, status: res.status, data: { message: "Hệ thống hiện không truy cập được." } }; }
}
async function logout() {
  await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
  location.href = "/";
}
async function loadPolicy() {
  const msg = document.getElementById("policy-msg");
  const view = document.getElementById("policy-view");
  msg.textContent = "Đang tải...";
  const r = await safeJson(await fetch("/api/hq/policy", { credentials: "same-origin" }));
  if (!r.ok) { msg.textContent = friendlyErr(r.data, r.status); return; }
  msg.textContent = "";
  const base = r.data.policy.base_spread || {};
  const maxm = r.data.policy.max_branch_margin || {};
  let html = "<table class='data'><thead><tr><th>Tier</th><th>CCY</th><th>BUY</th><th>SELL</th><th>Max margin CN</th></tr></thead><tbody>";
  for (const tier of Object.keys(base)) {
    for (const ccy of Object.keys(base[tier])) {
      html += `<tr><td>${tier}</td><td>${ccy}</td><td>${base[tier][ccy].BUY}</td><td>${base[tier][ccy].SELL}</td><td>${(maxm[tier]||{})[ccy]||"-"}</td></tr>`;
    }
  }
  html += "</tbody></table>";
  view.innerHTML = html;
}
async function updateSpread() {
  const body = {
    tier: document.getElementById("tier").value,
    currency: document.getElementById("currency").value,
    side: document.getElementById("side").value,
    value: document.getElementById("spread").value,
  };
  const r = await safeJson(await fetch("/api/hq/policy/base-spread", {
    method: "POST", headers: { "Content-Type": "application/json" },
    credentials: "same-origin", body: JSON.stringify(body),
  }));
  document.getElementById("update-msg").textContent = r.ok ? "Đã lưu base_spread" : friendlyErr(r.data, r.status);
  if (r.ok) loadPolicy();
}
async function updateMax() {
  const body = {
    tier: document.getElementById("tier2").value,
    currency: document.getElementById("currency2").value,
    value: document.getElementById("maxm").value,
  };
  const r = await safeJson(await fetch("/api/hq/policy/max-branch-margin", {
    method: "POST", headers: { "Content-Type": "application/json" },
    credentials: "same-origin", body: JSON.stringify(body),
  }));
  document.getElementById("update-msg").textContent = r.ok ? "Đã lưu trần margin" : friendlyErr(r.data, r.status);
  if (r.ok) loadPolicy();
}
async function loadCifs() {
  const r = await safeJson(await fetch("/api/customers/permitted", { credentials: "same-origin" }));
  const sel = document.getElementById("cif-select");
  sel.innerHTML = "";
  if (!r.ok) return;
  (r.data.customers || []).forEach((c) => {
    const o = document.createElement("option");
    o.value = c.customer_id;
    o.textContent = c.cif + " – " + c.customer_name + " (" + (c.pricing_tier||"") + ")";
    sel.appendChild(o);
  });
}
async function selectCif(id) {
  await fetch("/api/auth/select-customer", {
    method: "POST", headers: { "Content-Type": "application/json" },
    credentials: "same-origin", body: JSON.stringify({ customer_id: id }),
  });
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
async function quote() {
  const box = document.getElementById("quote-box");
  const cid = document.getElementById("cif-select").value;
  if (cid) await selectCif(cid);
  const bodyObj = {
    currency: document.getElementById("q-cur").value,
    side: document.getElementById("q-side").value,
    amount: Number(document.getElementById("q-amt").value),
    branch_margin: Number(document.getElementById("q-margin").value || 0),
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
    if (!r.ok) { box.innerHTML = "<p class='error-text'>" + friendlyErr(r.data, r.status) + "</p>"; return; }
    const q = r.data.quote;
    box.innerHTML = `
      <p><strong>Base price HQ:</strong> ${q.base_price || "—"}</p>
      <p>HQ spread: ${q.hq_base_spread || "—"} · Margin CN: ${q.branch_margin || "0"} · Total: ${q.total_spread || "—"}</p>
      <p class="price-line highlight"><span>Final (KH thấy)</span><strong>${q.price}</strong></p>
    `;
  } catch (e) {
    box.innerHTML = "<p class='error-text'>" + e.message + "</p>";
  }
}
async function loadHistory() {
  const box = document.getElementById("history-box");
  const r = await safeJson(await fetch("/api/transaction/history", { credentials: "same-origin" }));
  if (!r.ok) { box.innerHTML = "<p class='error-text'>" + friendlyErr(r.data, r.status) + "</p>"; return; }
  // HQ: show all if we expand history later; currently filtered by user
  const rows = (r.data.transactions || []).map(
    (t) => "<div class='price-line'><span>" + t.transaction_id + "</span><span>" + t.currency + " " + t.side + " · " + t.price + "</span></div>"
  );
  box.innerHTML = rows.length ? rows.join("") : "<p class='muted'>Chưa có giao dịch</p>";
}
