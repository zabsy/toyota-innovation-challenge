const API_BASE = window.location.origin;

// Mirrors the backend's VALID_STATUSES in DB/DB_server.py — keep in sync.
const STATUS_OPTIONS = [
  { value: "good", label: "Good", color: "#2d6a4f" },
  { value: "defective", label: "Defective", color: "#eb0a1e" },
];

const ROUTING = {
  good: "Accept — Good Bin",
  defective: "Reject — Defect Bin",
};

const $ = (id) => document.getElementById(id);

const els = {
  connection: $("connection-status"),
  statusMsg: $("status-message"),
  refreshBtn: $("refresh-btn"),
  addForm: $("add-form"),
  newQr: $("new-qr"),
  newStatus: $("new-status"),
  notice: $("notice"),
  gaugeFill: $("gauge-fill"),
  qualityRate: $("quality-rate"),
  overviewBars: $("overview-bars"),
  overviewTable: $("overview-table-body"),
  pctTable: $("pct-table-body"),
  reportTable: $("report-table-body"),
  registryTable: $("registry-table-body"),
  donutChart: $("donut-chart"),
  donutLegend: $("donut-legend"),
  donutTotal: $("donut-total"),
  kpiTotal: $("kpi-total"),
  kpiGood: $("kpi-good"),
  kpiBad: $("kpi-bad"),
  kpiGoodPct: $("kpi-good-pct"),
  kpiBadPct: $("kpi-bad-pct"),
};

let parts = {};
let lastUpdated = null;
let noticeTimer = null;

const GAUGE_ARC = 157;

function qrNumber(qrCode) {
  const m = qrCode.match(/(\d+)$/);
  return m ? Number(m[1]) : qrCode;
}

function sortedEntries(items) {
  return Object.entries(items).sort((a, b) => qrNumber(a[0]) - qrNumber(b[0]));
}

function statusOf(part) {
  return part.status || part;
}

function labelFor(status) {
  return STATUS_OPTIONS.find((o) => o.value === status)?.label || status;
}

function showNotice(msg) {
  els.notice.textContent = msg;
  els.notice.classList.add("show");
  clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => els.notice.classList.remove("show"), 3200);
}

function computeMetrics(items) {
  const counts = { good: 0, defective: 0 };
  const entries = Object.values(items);

  entries.forEach((part) => {
    const s = statusOf(part);
    if (counts[s] !== undefined) counts[s] += 1;
  });

  const total = entries.length || 0;
  const good = counts.good;
  const bad = counts.defective;
  const pct = (n) => (total ? ((n / total) * 100).toFixed(1) : "0.0");

  return { counts, total, good, bad, pct };
}

function tagHtml(status) {
  return `<span class="tag ${status}">${labelFor(status)}</span>`;
}

function buildSelect(status, qrCode) {
  const opts = STATUS_OPTIONS.map(
    (o) =>
      `<option value="${o.value}" ${o.value === status ? "selected" : ""}>${o.label}</option>`
  ).join("");
  return `<select data-qr="${qrCode}" aria-label="Classification for ${qrCode}">${opts}</select>`;
}

function renderKpis(m) {
  els.kpiTotal.textContent = m.total;
  els.kpiGood.textContent = m.good;
  els.kpiBad.textContent = m.bad;
  els.kpiGoodPct.textContent = `${m.pct(m.good)}% of total`;
  els.kpiBadPct.textContent = `${m.pct(m.bad)}% of total`;

  const rate = m.total ? (m.good / m.total) * 100 : 0;
  els.qualityRate.textContent = `${rate.toFixed(1)}%`;
  const offset = GAUGE_ARC - (rate / 100) * GAUGE_ARC;
  els.gaugeFill.style.strokeDashoffset = offset;
}

function renderBarChart(container, counts, total) {
  container.innerHTML = STATUS_OPTIONS.map((opt) => {
    const n = counts[opt.value] || 0;
    const w = total ? (n / total) * 100 : 0;
    return `
      <div class="bar-row">
        <span class="bar-label">${opt.label}</span>
        <div class="bar-track">
          <div class="bar-fill ${opt.value}" style="width:${w}%"></div>
        </div>
        <span class="bar-count">${n}</span>
      </div>`;
  }).join("");
}

function renderDonut(counts, total) {
  els.donutTotal.textContent = total;

  if (!total) {
    els.donutChart.innerHTML =
      '<circle cx="50" cy="50" r="40" fill="none" stroke="#e0e0e0" stroke-width="14"/>';
    els.donutLegend.innerHTML = "<li>No data registered</li>";
    return;
  }

  const r = 40;
  const c = 2 * Math.PI * r;
  let offset = 0;
  let segments = "";
  let legend = "";

  STATUS_OPTIONS.forEach((opt) => {
    const n = counts[opt.value] || 0;
    if (!n) return;
    const frac = n / total;
    const len = frac * c;
    segments += `<circle cx="50" cy="50" r="${r}" fill="none" stroke="${opt.color}"
      stroke-width="14" stroke-dasharray="${len} ${c - len}" stroke-dashoffset="${-offset}"/>`;
    offset += len;
    legend += `<li>
      <span class="legend-swatch" style="background:${opt.color}"></span>
      ${opt.label}
      <span class="legend-pct">${((n / total) * 100).toFixed(1)}% (${n})</span>
    </li>`;
  });

  els.donutChart.innerHTML = segments;
  els.donutLegend.innerHTML = legend;
}

function renderPctTable(counts, total) {
  els.pctTable.innerHTML = STATUS_OPTIONS.map((opt) => {
    const n = counts[opt.value] || 0;
    const p = total ? (n / total) * 100 : 0;
    return `<tr>
      <td>${opt.label}</td>
      <td>${n}</td>
      <td>${p.toFixed(1)}%</td>
      <td class="pct-bar-cell">
        <div class="pct-bar"><div class="pct-bar-inner" style="width:${p}%;background:${opt.color}"></div></div>
      </td>
    </tr>`;
  }).join("");
}

function renderOverviewTable(items) {
  const rows = sortedEntries(items);
  if (!rows.length) {
    els.overviewTable.innerHTML = `<tr><td colspan="4">No QR codes registered</td></tr>`;
    return;
  }
  els.overviewTable.innerHTML = rows
    .map(([code, part]) => {
      const s = statusOf(part);
      return `<tr>
        <td>${qrNumber(code)}</td>
        <td>${code}</td>
        <td>${tagHtml(s)}</td>
        <td>${ROUTING[s] || "—"}</td>
      </tr>`;
    })
    .join("");
}

function renderReportTable(items) {
  const rows = sortedEntries(items);
  const ts = lastUpdated ? new Date(lastUpdated).toLocaleString() : "—";

  if (!rows.length) {
    els.reportTable.innerHTML = `<tr><td colspan="6">No data</td></tr>`;
    return;
  }

  els.reportTable.innerHTML = rows
    .map(([code, part]) => {
      const s = statusOf(part);
      return `<tr>
        <td>${qrNumber(code)}</td>
        <td>${code}</td>
        <td>${tagHtml(s)}</td>
        <td>${s === "good" ? "Yes" : "—"}</td>
        <td>${s === "defective" ? "Yes" : "—"}</td>
        <td>${ts}</td>
      </tr>`;
    })
    .join("");
}

function renderRegistryTable(items) {
  const rows = sortedEntries(items);
  if (!rows.length) {
    els.registryTable.innerHTML = `<tr><td colspan="5">No mappings configured</td></tr>`;
    return;
  }

  els.registryTable.innerHTML = rows
    .map(([code, part]) => {
      const s = statusOf(part);
      return `<tr data-qr="${code}">
        <td>${qrNumber(code)}</td>
        <td>${code}</td>
        <td>${tagHtml(s)}</td>
        <td>${buildSelect(s, code)}</td>
        <td class="cell-actions">
          <button class="btn btn-primary btn-sm save-btn" type="button" data-qr="${code}">Save</button>
          <button class="btn btn-secondary btn-sm delete-btn" type="button" data-qr="${code}">Delete</button>
        </td>
      </tr>`;
    })
    .join("");
}

function renderAll() {
  const m = computeMetrics(parts);
  renderKpis(m);
  renderBarChart(els.overviewBars, m.counts, m.total);
  renderDonut(m.counts, m.total);
  renderPctTable(m.counts, m.total);
  renderOverviewTable(parts);
  renderReportTable(parts);
  renderRegistryTable(parts);
}

async function fetchParts() {
  const res = await fetch(`${API_BASE}/parts`);
  if (!res.ok) throw new Error("Unable to load QR database");

  const payload = await res.json();
  parts = payload.parts || payload;
  lastUpdated = payload.last_updated || null;
  renderAll();

  els.connection.textContent = "Connected";
  els.connection.classList.add("online");
  els.statusMsg.textContent = lastUpdated
    ? `Last change: ${new Date(lastUpdated).toLocaleString()} · Pi reads live on each QR scan`
    : "Connected to production server";
}

async function savePart(qrCode, status) {
  const res = await fetch(`${API_BASE}/part`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ qr_code: qrCode, status }),
  });
  const payload = await res.json();
  if (!res.ok) throw new Error(payload.error || "Save failed");

  const key = payload.qr_code || qrCode;
  parts[key] = { status: payload.status };
  lastUpdated = Date.now();
  renderAll();
  showNotice(`${key} set to ${labelFor(payload.status)}. Controller will sync on next poll.`);
}

async function deletePart(qrCode) {
  const res = await fetch(`${API_BASE}/part/${encodeURIComponent(qrCode)}`, {
    method: "DELETE",
  });
  const payload = await res.json();
  if (!res.ok) throw new Error(payload.error || "Delete failed");

  delete parts[qrCode];
  lastUpdated = Date.now();
  renderAll();
  showNotice(`${qrCode} removed from the registry. Controller will sync on next poll.`);
}

/* Navigation */
document.querySelectorAll(".nav-item").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".nav-item").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`view-${btn.dataset.view}`).classList.add("active");
  });
});

els.registryTable.addEventListener("click", async (e) => {
  const saveBtn = e.target.closest(".save-btn");
  const deleteBtn = e.target.closest(".delete-btn");

  if (saveBtn) {
    const qr = saveBtn.dataset.qr;
    const select = els.registryTable.querySelector(`select[data-qr="${qr}"]`);
    if (!select) return;

    saveBtn.disabled = true;
    try {
      await savePart(qr, select.value);
    } catch (err) {
      showNotice(err.message);
    } finally {
      saveBtn.disabled = false;
    }
  } else if (deleteBtn) {
    const qr = deleteBtn.dataset.qr;
    if (
      !confirm(
        `Delete ${qr} from the registry?\nThe robotic arm will no longer have a mapping for this QR code.`
      )
    ) {
      return;
    }

    deleteBtn.disabled = true;
    try {
      await deletePart(qr);
    } catch (err) {
      showNotice(err.message);
      deleteBtn.disabled = false;
    }
  }
});

els.addForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await savePart(els.newQr.value.trim(), els.newStatus.value);
    els.newQr.value = "";
  } catch (err) {
    showNotice(err.message);
  }
});

els.refreshBtn.addEventListener("click", async () => {
  try {
    await fetchParts();
    showNotice("Data refreshed");
  } catch (err) {
    showNotice(err.message);
    els.connection.classList.remove("online");
    els.connection.textContent = "Disconnected";
  }
});

async function bootstrap() {
  try {
    await fetchParts();
  } catch (err) {
    els.statusMsg.textContent = "Server unreachable — ensure DB_server.py is running";
    els.connection.textContent = "Disconnected";
    showNotice(err.message);
  }

  setInterval(async () => {
    try {
      await fetchParts();
    } catch {
      els.connection.classList.remove("online");
      els.connection.textContent = "Disconnected";
    }
  }, 8000);
}

bootstrap();
