const state = {
  activeTab: "pdf",
};

const form = document.querySelector("#planner-form");
const statusEl = document.querySelector("#result-status");
const reportEl = document.querySelector("#report-output");
const summaryGrid = document.querySelector("#summary-grid");
const parseSummary = document.querySelector("#parse-summary");
const clearButton = document.querySelector("#clear-result");

document.querySelectorAll(".tab-button").forEach((button) => {
  button.addEventListener("click", () => {
    state.activeTab = button.dataset.tab;
    document.querySelectorAll(".tab-button").forEach((item) => item.classList.toggle("active", item === button));
    document.querySelectorAll(".tab-panel").forEach((panel) => {
      panel.classList.toggle("active", panel.id === `${state.activeTab}-panel`);
    });
  });
});

clearButton.addEventListener("click", () => {
  statusEl.textContent = "Henüz rapor üretilmedi.";
  summaryGrid.hidden = true;
  parseSummary.hidden = true;
  reportEl.className = "report-output empty";
  reportEl.textContent = "Rapor burada görünecek.";
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  setLoading(true);
  try {
    const response = state.activeTab === "pdf" ? await submitTranscript() : await submitJson();
    renderResponse(response);
  } catch (error) {
    renderError(error);
  } finally {
    setLoading(false);
  }
});

function setLoading(isLoading) {
  form.querySelector(".primary-action").disabled = isLoading;
  statusEl.textContent = isLoading ? "Rapor hazırlanıyor..." : statusEl.textContent;
}

async function submitTranscript() {
  const fileInput = document.querySelector("#transcript-file");
  const file = fileInput.files[0];
  if (!file) {
    throw new Error("Transcript PDF seçilmedi.");
  }
  if (file.type && file.type !== "application/pdf") {
    throw new Error("Lütfen PDF dosyası seçin.");
  }
  const fileBase64 = await readFileAsBase64(file);
  const payload = {
    program_abbr: document.querySelector("#program").value,
    file_name: file.name,
    file_base64: fileBase64,
    goal: buildGoal(),
    elective_intents: selectedElectiveIntents(),
  };
  return postJson("/api/recommendations/from-transcript", payload);
}

async function submitJson() {
  const text = document.querySelector("#json-input").value;
  let payload;
  try {
    payload = JSON.parse(text);
  } catch {
    throw new Error("JSON input geçerli değil.");
  }
  payload.program_abbr = payload.program_abbr || payload.program || document.querySelector("#program").value;
  payload.goal = {
    ...(payload.goal || {}),
    target_semester_no: payload.goal?.target_semester_no || payload.goal?.target_semester || document.querySelector("#target-semester").value,
    difficulty_preference: payload.goal?.difficulty_preference || selectedDifficulty(),
  };
  const electiveIntents = selectedElectiveIntents();
  if (electiveIntents.length) {
    payload.elective_intents = electiveIntents;
  }
  return postJson("/api/recommendations/from-json", payload);
}

function buildGoal() {
  return {
    target_semester_no: document.querySelector("#target-semester").value.trim(),
    difficulty_preference: selectedDifficulty(),
  };
}

function selectedDifficulty() {
  return document.querySelector("input[name='difficulty']:checked").value;
}

function selectedElectiveIntents() {
  return Array.from(document.querySelectorAll("[data-elective-category]"))
    .filter((checkbox) => checkbox.checked)
    .map((checkbox) => {
      const category = checkbox.dataset.electiveCategory;
      const courseInput = document.querySelector(`[data-elective-course="${category}"]`);
      const courseCode = courseInput?.value.trim();
      return {
        category,
        wants_to_take: true,
        ...(courseCode ? {course_code: courseCode} : {}),
      };
    });
}

function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1]);
    reader.onerror = () => reject(new Error("PDF dosyası okunamadı."));
    reader.readAsDataURL(file);
  });
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw new Error(data.error || "İstek başarısız oldu.");
  }
  return data;
}

function renderResponse(data) {
  statusEl.textContent = `${data.program_abbr} için ${data.target_semester_no} raporu hazır.`;
  renderSummary(data.summary);
  renderParseSummary(data.transcript_parse);
  reportEl.className = "report-output";
  reportEl.innerHTML = renderMarkdown(data.report_markdown || "");
}

function renderSummary(summary) {
  const items = [
    ["Senaryo", summary.scenario_count],
    ["Alınabilir", summary.eligible_course_count],
    ["Bloklu", summary.blocked_course_count],
    ["Uyarı", summary.warning_count],
  ];
  summaryGrid.innerHTML = items.map(([label, value]) => (
    `<div class="summary-item"><strong>${escapeHtml(String(value))}</strong><span>${escapeHtml(label)}</span></div>`
  )).join("");
  summaryGrid.hidden = false;
}

function renderParseSummary(transcriptParse) {
  if (!transcriptParse) {
    parseSummary.hidden = true;
    return;
  }
  const metadata = transcriptParse.metadata || {};
  const warnings = transcriptParse.warnings || [];
  parseSummary.textContent = [
    `Transcript parse: ${metadata.completed_course_count || 0} tamamlanmış ders, ${metadata.in_progress_course_count || 0} devam eden ders.`,
    `Raw transcript retained: ${metadata.raw_transcript_retained === false ? "false" : "unknown"}.`,
    warnings.length ? `${warnings.length} parse uyarısı var.` : "Parse uyarısı yok.",
  ].join(" ");
  parseSummary.hidden = false;
}

function renderError(error) {
  statusEl.innerHTML = `<span class="error">${escapeHtml(error.message)}</span>`;
  reportEl.className = "report-output empty";
  reportEl.textContent = "Rapor üretilemedi.";
}

function renderMarkdown(markdown) {
  const lines = markdown.split(/\r?\n/);
  const html = [];
  let table = [];
  let listOpen = false;

  const flushList = () => {
    if (listOpen) {
      html.push("</ul>");
      listOpen = false;
    }
  };
  const flushTable = () => {
    if (!table.length) return;
    const rows = table.filter((row) => !/^\|\s*-+/.test(row));
    if (rows.length) {
      html.push("<table>");
      rows.forEach((row, index) => {
        const cells = row.split("|").slice(1, -1).map((cell) => escapeHtml(cell.trim()));
        html.push(index === 0 ? "<thead><tr>" : "<tr>");
        cells.forEach((cell) => html.push(index === 0 ? `<th>${cell}</th>` : `<td>${cell}</td>`));
        html.push(index === 0 ? "</tr></thead><tbody>" : "</tr>");
      });
      html.push("</tbody></table>");
    }
    table = [];
  };

  lines.forEach((line) => {
    if (line.startsWith("|")) {
      flushList();
      table.push(line);
      return;
    }
    flushTable();
    if (!line.trim()) {
      flushList();
      return;
    }
    if (line.startsWith("# ")) {
      flushList();
      html.push(`<h2>${escapeHtml(line.slice(2))}</h2>`);
    } else if (line.startsWith("## ")) {
      flushList();
      html.push(`<h3>${escapeHtml(line.slice(3))}</h3>`);
    } else if (line.startsWith("### ")) {
      flushList();
      html.push(`<h3>${escapeHtml(line.slice(4))}</h3>`);
    } else if (line.startsWith("- ")) {
      if (!listOpen) {
        html.push("<ul>");
        listOpen = true;
      }
      html.push(`<li>${escapeHtml(line.slice(2))}</li>`);
    } else {
      flushList();
      html.push(`<p>${escapeHtml(line)}</p>`);
    }
  });
  flushTable();
  flushList();
  return html.join("");
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

clearButton.click();
