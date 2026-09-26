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

/* ========== Chính sách HQ (spread + margin + TGDH) ========== */
async function loadPolicy() {
  const msg = document.getElementById("policy-msg");
  const view = document.getElementById("policy-view");
  msg.textContent = "Đang tải...";
  const r = await safeJson(await fetch("/api/hq/policy", { credentials: "same-origin" }));
  if (!r.ok) { msg.textContent = friendlyErr(r.data, r.status); return; }
  msg.textContent = "";
  const base = r.data.policy.base_spread || {};
  const maxm = r.data.policy.max_branch_margin || {};
  const tgdh = r.data.policy.tgdh_points || {};
  let html = "<table class='data'><thead><tr><th>Tier</th><th>CCY</th><th>BUY (NH mua)</th><th>SELL (NH bán)</th><th>Max margin CN</th></tr></thead><tbody>";
  for (const tier of Object.keys(base)) {
    for (const ccy of Object.keys(base[tier])) {
      html += `<tr><td>${tier}</td><td>${ccy}</td><td>${base[tier][ccy].BUY}</td><td>${base[tier][ccy].SELL}</td><td>${(maxm[tier]||{})[ccy]||"-"}</td></tr>`;
    }
  }
  html += "</tbody></table>";
  html += "<p class='muted' style='margin-top:0.75rem'><strong>TGDH (điểm điều hòa):</strong> ";
  html += Object.keys(tgdh).map(c => c + "=" + tgdh[c]).join(" · ");
  html += "</p>";
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
async function updateTgdh() {
  const body = {
    currency: document.getElementById("tgdh-ccy").value,
    value: document.getElementById("tgdh-pts").value,
  };
  const r = await safeJson(await fetch("/api/hq/policy/tgdh-points", {
    method: "POST", headers: { "Content-Type": "application/json" },
    credentials: "same-origin", body: JSON.stringify(body),
  }));
  document.getElementById("update-msg").textContent = r.ok
    ? "Đã lưu TGDH points (cộng/trừ vào final → ra TGDH)"
    : friendlyErr(r.data, r.status);
  if (r.ok) loadPolicy();
}

/* ========== Base TSC – auto 20s / manual ========== */
async function loadMarket() {
  const box = document.getElementById("market-box");
  const r = await safeJson(await fetch("/api/hq/market-rate", { credentials: "same-origin" }));
  if (!r.ok) { box.innerHTML = "<p class='error-text'>" + friendlyErr(r.data, r.status) + "</p>"; return; }
  const m = r.data.market;
  const rates = m.rates || {};
  let html = `<p><strong>Mode:</strong> ${m.mode} · Interval auto: ${m.auto_interval_seconds}s · Updated: ${m.updated_at}</p>`;
  html += "<table class='data'><thead><tr><th>CCY</th><th>Base TSC</th></tr></thead><tbody>";
  for (const c of Object.keys(rates)) {
    html += `<tr><td>${c}</td><td>${rates[c]}</td></tr>`;
  }
  html += "</tbody></table>";
  box.innerHTML = html;
  const modeSel = document.getElementById("m-mode");
  if (modeSel) modeSel.value = m.mode || "auto";
}
async function setMarketMode() {
  const mode = document.getElementById("m-mode").value;
  const r = await safeJson(await fetch("/api/hq/market-rate/mode", {
    method: "POST", headers: { "Content-Type": "application/json" },
    credentials: "same-origin", body: JSON.stringify({ mode }),
  }));
  document.getElementById("market-msg").textContent = r.ok
    ? "Đã set mode = " + mode
    : friendlyErr(r.data, r.status);
  if (r.ok) loadMarket();
}
async function setManualRate() {
  const body = {
    currency: document.getElementById("m-ccy").value,
    rate: document.getElementById("m-rate").value,
  };
  const r = await safeJson(await fetch("/api/hq/market-rate/set", {
    method: "POST", headers: { "Content-Type": "application/json" },
    credentials: "same-origin", body: JSON.stringify(body),
  }));
  document.getElementById("market-msg").textContent = r.ok
    ? "Đã set base manual " + body.currency + " = " + body.rate
    : friendlyErr(r.data, r.status);
  if (r.ok) loadMarket();
}

/* ========== CIF + Quote ========== */
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
  // HQ: side = chiều NH (BUY = NH mua, SELL = NH bán)
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
    const sideLabel = q.side === "BUY" ? "NH mua (KH bán)" : "NH bán (KH mua)";
    box.innerHTML = `
      <p><strong>Base TSC:</strong> ${q.base_price || "—"} · Side: ${sideLabel}</p>
      <p>HQ spread: ${q.hq_base_spread || "—"} · Margin CN: ${q.branch_margin || "0"} · Total: ${q.total_spread || "—"}</p>
      <p>TGDH points: ${q.tgdh_points || "0"}</p>
      <p class="price-line highlight"><span>Final (KH thấy)</span><strong>${q.price}</strong></p>
      <p class="price-line"><span>TGDH (NSDH)</span><strong>${q.tgdh || q.price}</strong></p>
    `;
  } catch (e) {
    box.innerHTML = "<p class='error-text'>" + e.message + "</p>";
  }
}
async function loadHistory() {
  const box = document.getElementById("history-box");
  const r = await safeJson(await fetch("/api/transaction/history", { credentials: "same-origin" }));
  if (!r.ok) { box.innerHTML = "<p class='error-text'>" + friendlyErr(r.data, r.status) + "</p>"; return; }
  const rows = (r.data.transactions || []).map(
    (t) => "<div class='price-line'><span>" + t.transaction_id + "</span><span>" + t.currency + " " + t.side + " · " + t.price + "</span></div>"
  );
  box.innerHTML = rows.length ? rows.join("") : "<p class='muted'>Chưa có giao dịch</p>";
}

// Auto refresh base TSC view mỗi 20s khi mode auto
setInterval(() => {
  const box = document.getElementById("market-box");
  if (box && box.innerHTML) loadMarket();
}, 20000);
