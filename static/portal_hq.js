async function logout() {
  await fetch("/api/auth/logout", { method: "POST", credentials: "same-origin" });
  location.href = "/";
}

async function loadPolicy() {
  const msg = document.getElementById("policy-msg");
  const view = document.getElementById("policy-view");
  msg.textContent = "Đang tải...";
  const res = await fetch("/api/hq/policy", { credentials: "same-origin" });
  const data = await res.json();
  if (!res.ok) {
    msg.textContent = data.message || "Không tải được";
    return;
  }
  msg.textContent = "";
  const base = data.policy.base_spread || {};
  const maxm = data.policy.max_branch_margin || {};
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
  const res = await fetch("/api/hq/policy/base-spread", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify(body),
  });
  const data = await res.json();
  document.getElementById("update-msg").textContent = res.ok ? "Đã lưu base_spread" : (data.message || "Lỗi");
  if (res.ok) loadPolicy();
}

async function updateMax() {
  const body = {
    tier: document.getElementById("tier2").value,
    currency: document.getElementById("currency2").value,
    value: document.getElementById("maxm").value,
  };
  const res = await fetch("/api/hq/policy/max-branch-margin", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify(body),
  });
  const data = await res.json();
  document.getElementById("update-msg").textContent = res.ok ? "Đã lưu trần margin" : (data.message || "Lỗi");
  if (res.ok) loadPolicy();
}

async function loadCifs() {
  const res = await fetch("/api/customers/permitted", { credentials: "same-origin" });
  const data = await res.json();
  const sel = document.getElementById("cif-select");
  sel.innerHTML = "";
  (data.customers || []).forEach((c) => {
    const o = document.createElement("option");
    o.value = c.customer_id;
    o.textContent = `${c.cif} – ${c.customer_name} (${c.pricing_tier})`;
    sel.appendChild(o);
  });
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
      box.innerHTML = `<p class="error-text">${data.message || "Lỗi"}</p>`;
      return;
    }
    const q = data.quote;
    box.innerHTML = `
      <p><strong>Final:</strong> ${q.price}</p>
      <p>Market: ${q.market_rate || "—"}</p>
      <p>HQ base: ${q.hq_base_spread || "—"}</p>
      <p>Margin CN: ${q.branch_margin || "0"}</p>
      <p>Total spread: ${q.total_spread || "—"} · Tier: ${q.pricing_tier || "—"}</p>
    `;
  } catch (e) {
    box.innerHTML = `<p class="error-text">${e.message}</p>`;
  }
}
