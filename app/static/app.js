const askForm = document.getElementById("askForm");
const questionInput = document.getElementById("questionInput");
const askBtn = document.getElementById("askBtn");
const clearBtn = document.getElementById("clearBtn");
const errorBox = document.getElementById("error");
const resultBox = document.getElementById("result");
const answerText = document.getElementById("answerText");
const intentTag = document.getElementById("intentTag");
const sourceTag = document.getElementById("sourceTag");
const tableWrap = document.getElementById("tableWrap");
const sqlText = document.getElementById("sqlText");
const chartBox = document.getElementById("chart");
const statusBadge = document.getElementById("statusBadge");
const statsList = document.getElementById("datasetStats");
const exampleChips = document.getElementById("exampleChips");

const COLUMN_LABELS = {
  product: "Product",
  region: "Region",
  category: "Category",
  sales_channel: "Channel",
  month: "Month",
  transactions: "Transactions",
  units: "Units",
  revenue: "Revenue",
  metric: "Metric",
  value: "Value",
};

const CURRENCY_COLUMNS = new Set(["revenue", "value", "change", "change_pct"]);
const currency = new Intl.NumberFormat("en-IN", {
  style: "currency",
  currency: "INR",
  maximumFractionDigits: 2,
});
const number = new Intl.NumberFormat("en-IN");

function showError(message) {
  errorBox.textContent = message;
  errorBox.classList.remove("hidden");
  resultBox.classList.add("hidden");
}

function hideError() {
  errorBox.classList.add("hidden");
}

async function loadHealth() {
  try {
    const res = await fetch("/api/health");
    const body = await res.json();
    const d = body.dataset;
    statusBadge.textContent = `${d.transactions_loaded} rows loaded`;
    statusBadge.classList.add("ok");
    const rows = [
      ["Transactions", number.format(d.transactions_loaded)],
      ["Completed", number.format(d.completed_transactions)],
      ["Returned", number.format(d.returned_transactions)],
      ["Rejected rows", number.format(d.rejected_rows)],
      ["Total revenue", currency.format(d.total_revenue)],
      ["From", d.date_range.start],
      ["To", d.date_range.end],
    ];
    statsList.innerHTML = rows
      .map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`)
      .join("");
  } catch (err) {
    statusBadge.textContent = "dataset unavailable";
    statusBadge.classList.remove("ok");
  }
}

async function loadExamples() {
  try {
    const res = await fetch("/api/examples");
    const { examples } = await res.json();
    exampleChips.innerHTML = "";
    examples.forEach((text) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "chip";
      chip.textContent = text;
      chip.addEventListener("click", () => {
        questionInput.value = text;
        questionInput.focus();
      });
      exampleChips.appendChild(chip);
    });
  } catch (err) {
    /* examples are a convenience; ignore failures */
  }
}

function formatCell(key, value) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") {
    if (key === "change_pct") return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
    if (CURRENCY_COLUMNS.has(key)) return currency.format(value);
    return number.format(value);
  }
  return String(value);
}

function renderTable(rows) {
  if (!rows || rows.length === 0) {
    tableWrap.innerHTML = '<p class="note">No supporting rows returned.</p>';
    return;
  }
  const columns = [];
  rows.forEach((row) => {
    Object.keys(row).forEach((key) => {
      if (!columns.includes(key)) columns.push(key);
    });
  });
  const head = columns
    .map((c) => `<th>${COLUMN_LABELS[c] || c}</th>`)
    .join("");
  const body = rows
    .map((row) => {
      const cells = columns
        .map((c) => {
          const value = row[c];
          const isNum = typeof value === "number";
          return `<td class="${isNum ? "num" : ""}">${formatCell(c, value)}</td>`;
        })
        .join("");
      return `<tr>${cells}</tr>`;
    })
    .join("");
  tableWrap.innerHTML = `<table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table>`;
}

function renderChart(chart) {
  chartBox.innerHTML = "";
  if (!chart || !chart.x || chart.x.length < 2) return;

  const width = 640;
  const height = 220;
  const pad = { top: 16, right: 16, bottom: 32, left: 56 };
  const values = chart.y.map(Number);
  const max = Math.max(...values);
  const min = Math.min(...values, 0);
  const span = max - min || 1;
  const innerW = width - pad.left - pad.right;
  const innerH = height - pad.top - pad.bottom;

  const points = values.map((v, i) => {
    const x = pad.left + (innerW * i) / (values.length - 1);
    const y = pad.top + innerH - ((v - min) / span) * innerH;
    return { x, y, v, label: chart.x[i] };
  });

  const line = points.map((p, i) => `${i === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");
  const area = `${line} L${points[points.length - 1].x},${pad.top + innerH} L${points[0].x},${pad.top + innerH} Z`;

  const dots = points
    .map((p) => `<circle cx="${p.x}" cy="${p.y}" r="3.5" fill="#4f8cff" />`)
    .join("");
  const labels = points
    .map(
      (p, i) =>
        i % Math.ceil(points.length / 7) === 0
          ? `<text x="${p.x}" y="${height - 10}" fill="#9fb0c9" font-size="10" text-anchor="middle">${p.label}</text>`
          : ""
    )
    .join("");

  chartBox.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" role="img" aria-label="Revenue chart" width="100%">
      <defs>
        <linearGradient id="areaFill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stop-color="#4f8cff" stop-opacity="0.35" />
          <stop offset="100%" stop-color="#4f8cff" stop-opacity="0" />
        </linearGradient>
      </defs>
      <line x1="${pad.left}" y1="${pad.top + innerH}" x2="${width - pad.right}" y2="${pad.top + innerH}" stroke="#263a63" />
      <path d="${area}" fill="url(#areaFill)" />
      <path d="${line}" fill="none" stroke="#4f8cff" stroke-width="2.5" />
      ${dots}
      ${labels}
    </svg>`;
}

function renderResult(payload) {
  hideError();
  resultBox.classList.remove("hidden");
  answerText.textContent = payload.answer;
  intentTag.textContent = payload.intent.replace(/_/g, " ");
  sourceTag.textContent = payload.interpreted_by === "llm" ? "LLM interpreted" : "rule-based";
  renderChart(payload.chart);
  renderTable(payload.data);
  sqlText.textContent = payload.sql;
}

async function ask(question) {
  askBtn.disabled = true;
  askBtn.innerHTML = '<span class="spinner"></span>Thinking';
  hideError();
  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    });
    const body = await res.json();
    if (!res.ok) {
      const detail = body.detail || body.error || "Could not answer that question.";
      showError(typeof detail === "string" ? detail : JSON.stringify(detail));
      return;
    }
    renderResult(body);
  } catch (err) {
    showError("Network error. Is the server still running?");
  } finally {
    askBtn.disabled = false;
    askBtn.textContent = "Ask";
  }
}

askForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  if (!question) {
    showError("Please type a question first.");
    return;
  }
  ask(question);
});

clearBtn.addEventListener("click", () => {
  questionInput.value = "";
  questionInput.focus();
  hideError();
  resultBox.classList.add("hidden");
});

loadHealth();
loadExamples();
