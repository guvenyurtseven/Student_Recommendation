import React, {useMemo, useState} from "react";
import {createRoot} from "react-dom/client";
import "./styles.css";

const ELECTIVE_CATEGORIES = [
  {key: "technical_elective", label: "Technical Elective", ects: "6.5", detail: "En yüksek workload varsayımı"},
  {key: "restricted_elective", label: "Restricted Elective", ects: "6", detail: "Teknik seçmeliye yakın"},
  {key: "nontechnical_elective", label: "Non-Technical Elective", ects: "5.5", detail: "Daha esnek workload"},
  {key: "free_elective", label: "Free Elective", ects: "5", detail: "En esnek kategori"},
];

const INITIAL_JSON = `{
  "program_abbr": "CENG",
  "completed_courses": [
    {"course_code": "MATH 119", "grade": "DD", "completed_semester_no": "20241"}
  ],
  "goal": {
    "target_semester_no": "20252",
    "difficulty_preference": "balanced"
  }
}`;

function App() {
  const [mode, setMode] = useState("pdf");
  const [targetSemester, setTargetSemester] = useState("20252");
  const [difficulty, setDifficulty] = useState("balanced");
  const [pdfFile, setPdfFile] = useState(null);
  const [jsonInput, setJsonInput] = useState(INITIAL_JSON);
  const [electives, setElectives] = useState(defaultElectives());
  const [response, setResponse] = useState(null);
  const [status, setStatus] = useState({kind: "idle", text: "Transcript PDF veya planner JSON ile başlayabilirsin."});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const selectedElectiveCount = useMemo(() => electives.filter((item) => item.selected).length, [electives]);

  async function submit(event) {
    event.preventDefault();
    if (isSubmitting) return;
    setIsSubmitting(true);
    setStatus({kind: "loading", text: "Deterministik plan hazırlanıyor..."});
    setResponse(null);
    try {
      const payload = mode === "pdf" ? await buildTranscriptPayload() : buildJsonPayload();
      const data = await postJson(
        mode === "pdf" ? "/api/recommendations/from-transcript" : "/api/recommendations/from-json",
        payload,
      );
      setResponse(data);
      setStatus({kind: "success", text: `${data.program_abbr} için ${data.target_semester_no} raporu hazır.`});
    } catch (error) {
      setStatus({kind: "error", text: error.message});
    } finally {
      setIsSubmitting(false);
    }
  }

  async function buildTranscriptPayload() {
    if (!pdfFile) {
      throw new Error("Transcript PDF seçmelisin.");
    }
    return {
      file_name: pdfFile.name,
      file_base64: await fileToBase64(pdfFile),
      goal: buildGoal(),
      elective_intents: selectedElectiveIntents(electives),
    };
  }

  function buildJsonPayload() {
    let payload;
    try {
      payload = JSON.parse(jsonInput);
    } catch {
      throw new Error("JSON input geçerli değil.");
    }
    payload.goal = {
      ...(payload.goal || {}),
      target_semester_no: payload.goal?.target_semester_no || payload.goal?.target_semester || targetSemester,
      difficulty_preference: payload.goal?.difficulty_preference || difficulty,
    };
    const intents = selectedElectiveIntents(electives);
    if (intents.length) {
      payload.elective_intents = intents;
    }
    return payload;
  }

  function buildGoal() {
    return {
      target_semester_no: targetSemester,
      difficulty_preference: difficulty,
    };
  }

  return (
    <main className="app">
      <aside className="control-surface">
        <header className="brand-block">
          <div className="brand-mark">M</div>
          <div>
            <p className="eyebrow">METU Student Planner</p>
            <h1>Next semester karar destek aracı</h1>
          </div>
        </header>

        <form onSubmit={submit} className="planner-form">
          <section className="form-section">
            <div className="section-heading">
              <h2>Hedef</h2>
              <span>1</span>
            </div>
            <div className="target-card">
              <div>
                <strong>Bölüm transcript'ten okunur</strong>
                <p>PDF modunda department/program alanını otomatik kullanıyoruz.</p>
              </div>
              <label>
                Hedef dönem
                <input value={targetSemester} onChange={(event) => setTargetSemester(event.target.value)} />
              </label>
            </div>

            <div className="segmented">
              {["easy", "balanced", "hard"].map((value) => (
                <label key={value} className={difficulty === value ? "active" : ""}>
                  <input
                    type="radio"
                    name="difficulty"
                    value={value}
                    checked={difficulty === value}
                    onChange={(event) => setDifficulty(event.target.value)}
                  />
                  {difficultyLabel(value)}
                </label>
              ))}
            </div>
          </section>

          <section className="form-section">
            <div className="section-heading">
              <h2>Akademik Geçmiş</h2>
              <span>2</span>
            </div>
            <div className="mode-tabs">
              <button type="button" className={mode === "pdf" ? "active" : ""} onClick={() => setMode("pdf")}>
                Transcript PDF
              </button>
              <button type="button" className={mode === "json" ? "active" : ""} onClick={() => setMode("json")}>
                JSON
              </button>
            </div>

            {mode === "pdf" ? (
              <div className="upload-box">
                <input
                  id="pdf"
                  type="file"
                  accept="application/pdf"
                  onChange={(event) => setPdfFile(event.target.files?.[0] || null)}
                />
                <label htmlFor="pdf">
                  <strong>{pdfFile ? pdfFile.name : "PDF seç"}</strong>
                  <span>Dosya bellekte parse edilir, bölüm ve ders geçmişi çıkarılır, saklanmaz.</span>
                </label>
              </div>
            ) : (
              <label>
                Planner JSON
                <textarea value={jsonInput} onChange={(event) => setJsonInput(event.target.value)} spellCheck="false" />
              </label>
            )}
          </section>

          <section className="form-section">
            <div className="section-heading">
              <h2>Elective Tercihleri</h2>
              <span>{selectedElectiveCount}</span>
            </div>
            <div className="elective-list">
              {electives.map((item) => (
                <article className={item.selected ? "elective-row selected" : "elective-row"} key={item.category}>
                  <label className="check-line">
                    <input
                      type="checkbox"
                      checked={item.selected}
                      onChange={() => toggleElective(item.category)}
                    />
                    <span>
                      <strong>{item.label}</strong>
                      <small>{item.detail} · varsayılan {item.ects} ECTS</small>
                    </span>
                  </label>
                  <input
                    className="course-entry"
                    value={item.courseCode}
                    onChange={(event) => updateElectiveCourse(item.category, event.target.value)}
                    placeholder="Opsiyonel: CENG495"
                    disabled={!item.selected}
                  />
                </article>
              ))}
            </div>
          </section>

          <button className="primary" type="submit" disabled={isSubmitting}>
            {isSubmitting ? "Plan hazırlanıyor..." : "Planı oluştur"}
          </button>
        </form>
      </aside>

      <section className="report-surface">
        <header className="report-toolbar">
          <div>
            <p className={`status ${status.kind}`}>{status.text}</p>
            <h2>Deterministik Rapor</h2>
          </div>
          {response && <span className="pill">{response.summary?.preferred_scenario_kind || "balanced"}</span>}
        </header>

        {response ? <Report response={response} /> : <EmptyState />}
      </section>
    </main>
  );

  function toggleElective(category) {
    setElectives((current) => current.map((item) => (
      item.category === category ? {...item, selected: !item.selected} : item
    )));
  }

  function updateElectiveCourse(category, courseCode) {
    setElectives((current) => current.map((item) => (
      item.category === category ? {...item, courseCode} : item
    )));
  }
}

function Report({response}) {
  return (
    <>
      <div className="metric-grid">
        <Metric label="Senaryo" value={response.summary?.scenario_count ?? 0} />
        <Metric label="Alınabilir" value={response.summary?.eligible_course_count ?? 0} />
        <Metric label="Bloklu" value={response.summary?.blocked_course_count ?? 0} />
        <Metric label="Uyarı" value={response.summary?.warning_count ?? 0} />
      </div>

      {response.transcript_parse && (
        <div className="parse-band">
          <strong>Transcript parse:</strong>{" "}
          {response.transcript_parse.metadata.completed_course_count} completed course,{" "}
          {response.transcript_parse.metadata.in_progress_course_count} in-progress course. Raw transcript retained:{" "}
          {String(response.transcript_parse.metadata.raw_transcript_retained)}.
        </div>
      )}

      <article className="markdown-report" dangerouslySetInnerHTML={{__html: renderMarkdown(response.report_markdown || "")}} />
    </>
  );
}

function Metric({label, value}) {
  return (
    <div className="metric">
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="empty-state">
      <h3>Rapor burada oluşacak</h3>
      <p>Transcript PDF yükleyebilir veya mevcut planner JSON formatını kullanabilirsin.</p>
    </div>
  );
}

function defaultElectives() {
  return ELECTIVE_CATEGORIES.map((item) => ({
    category: item.key,
    label: item.label,
    ects: item.ects,
    detail: item.detail,
    selected: false,
    courseCode: "",
  }));
}

function selectedElectiveIntents(electives) {
  return electives
    .filter((item) => item.selected)
    .map((item) => ({...item, compactCourseCode: item.courseCode.trim().replace(/\s+/g, "")}))
    .map((item) => ({
      category: item.category,
      wants_to_take: true,
      ...(item.compactCourseCode ? {course_code: item.compactCourseCode} : {}),
    }));
}

function difficultyLabel(value) {
  return {
    easy: "Kolay",
    balanced: "Dengeli",
    hard: "Zor",
  }[value];
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1]);
    reader.onerror = () => reject(new Error("PDF okunamadı."));
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

function renderMarkdown(markdown) {
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
    html.push("<table>");
    rows.forEach((row, index) => {
      const cells = row.split("|").slice(1, -1).map((cell) => escapeHtml(cell.trim()));
      html.push(index === 0 ? "<thead><tr>" : "<tr>");
      cells.forEach((cell) => html.push(index === 0 ? `<th>${cell}</th>` : `<td>${cell}</td>`));
      html.push(index === 0 ? "</tr></thead><tbody>" : "</tr>");
    });
    html.push("</tbody></table>");
    table = [];
  };

  markdown.split(/\r?\n/).forEach((line) => {
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
      html.push(`<h2>${escapeHtml(line.slice(2))}</h2>`);
    } else if (line.startsWith("## ")) {
      html.push(`<h3>${escapeHtml(line.slice(3))}</h3>`);
    } else if (line.startsWith("### ")) {
      html.push(`<h4>${escapeHtml(line.slice(4))}</h4>`);
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

createRoot(document.getElementById("root")).render(<App />);
