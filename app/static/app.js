"use strict";

const api = {
  async list() {
    const r = await fetch("/api/invoices");
    return r.json();
  },
  async create(vendor, amount) {
    const r = await fetch("/api/invoices", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ vendor, amount }),
    });
    return { status: r.status, body: await r.json().catch(() => ({})) };
  },
  async approve(id, approver, role) {
    const r = await fetch(`/api/invoices/${id}/approvals`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ approver, role }),
    });
    return { status: r.status, body: await r.json().catch(() => ({})) };
  },
};

function setMsg(el, text, kind) {
  el.textContent = text;
  el.className = "msg " + (kind || "");
}

function fmt(n) {
  return Number(n).toLocaleString("en-US");
}

async function refresh() {
  const tbody = document.querySelector("#invoices tbody");
  const invoices = await api.list();
  tbody.innerHTML = "";
  for (const inv of invoices) {
    const tr = document.createElement("tr");
    const approvals = inv.approvals
      .map((a) => `${a.approver} (${a.role})`)
      .join(", ") || "—";
    tr.innerHTML = `
      <td>${inv.id}</td>
      <td>${escapeHtml(inv.vendor)}</td>
      <td>${fmt(inv.amount)}</td>
      <td><span class="status ${inv.status}">${inv.status}</span></td>
      <td class="approvals">${escapeHtml(approvals)}</td>
      <td><button class="use-btn" data-id="${inv.id}">Use</button></td>`;
    tbody.appendChild(tr);
  }
  tbody.querySelectorAll(".use-btn").forEach((b) => {
    b.addEventListener("click", () => {
      document.querySelector("#inv-id").value = b.dataset.id;
      document.querySelector("#approver").focus();
    });
  });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

document.querySelector("#create-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const vendor = document.querySelector("#vendor").value.trim();
  const amount = parseInt(document.querySelector("#amount").value, 10);
  const { status, body } = await api.create(vendor, amount);
  const msg = document.querySelector("#create-msg");
  if (status === 201) {
    setMsg(msg, `Created invoice #${body.id} (${body.status}).`, "ok");
    document.querySelector("#create-form").reset();
    refresh();
  } else {
    setMsg(msg, "Could not create invoice (amount must be a positive integer).", "err");
  }
});

document.querySelector("#approve-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const id = parseInt(document.querySelector("#inv-id").value, 10);
  const approver = document.querySelector("#approver").value.trim();
  const role = document.querySelector("#role").value;
  const { status, body } = await api.approve(id, approver, role);
  const msg = document.querySelector("#approve-msg");
  if (status === 200) {
    const kind = body.outcome === "approved" ? "ok" : "pending";
    setMsg(msg, body.message, kind);
  } else if (status === 404) {
    setMsg(msg, `Invoice #${id} not found.`, "err");
  } else if (status === 409) {
    const detail = body.detail || {};
    setMsg(msg, "Rejected: " + (detail.message || "not allowed"), "err");
  } else {
    setMsg(msg, "Invalid request.", "err");
  }
  refresh();
});

document.querySelector("#seed-btn").addEventListener("click", async () => {
  const samples = [
    ["Office Supplies Co", 25000],
    ["Logistics Partner", 120000],
    ["Enterprise Software", 600000],
  ];
  for (const [vendor, amount] of samples) {
    await api.create(vendor, amount);
  }
  setMsg(document.querySelector("#create-msg"), "Seeded 3 example invoices.", "ok");
  refresh();
});

document.querySelector("#refresh-btn").addEventListener("click", refresh);

refresh();
