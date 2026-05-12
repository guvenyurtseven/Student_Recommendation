import React, {useEffect, useMemo, useState} from "react";
import {createRoot} from "react-dom/client";
import "./styles.css";

const ELECTIVE_CATEGORIES = [
  {key: "technical_elective", label: "Technical Elective", hint: "Bolum veya teknik uzmanlasma"},
  {key: "restricted_elective", label: "Restricted Elective", hint: "Bolumun sinirladigi secim havuzu"},
  {key: "nontechnical_elective", label: "Non-Technical Elective", hint: "Sosyal, beseri veya idari alan"},
  {key: "free_elective", label: "Free Elective", hint: "Mufredatin serbest secim alani"},
];

const DIFFICULTY_OPTIONS = [
  {value: "easy", label: "Rahat"},
  {value: "balanced", label: "Dengeli"},
  {value: "hard", label: "Yogun"},
];

function App() {
  if (window.location.pathname.startsWith("/admin")) {
    return <AdminApp />;
  }
  return <PlannerApp />;
}

function PlannerApp() {
  const [operationSemester, setOperationSemester] = useState(null);
  const [difficulty, setDifficulty] = useState("balanced");
  const [pdfFile, setPdfFile] = useState(null);
  const [electives, setElectives] = useState(defaultElectives());
  const [response, setResponse] = useState(null);
  const [status, setStatus] = useState({kind: "idle", text: "Transcript PDF bekleniyor."});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedbackOpen, setFeedbackOpen] = useState(false);
  const [feedbackText, setFeedbackText] = useState("");
  const [feedbackStatus, setFeedbackStatus] = useState({kind: "idle", text: ""});
  const [isFeedbackSubmitting, setIsFeedbackSubmitting] = useState(false);

  const selectedElectiveCount = useMemo(() => electives.filter((item) => item.selected).length, [electives]);

  useEffect(() => {
    loadOperationSemester(setOperationSemester);
  }, []);

  async function submit(event) {
    event.preventDefault();
    if (isSubmitting) return;
    setIsSubmitting(true);
    setStatus({kind: "loading", text: "Plan hazirlaniyor..."});
    setResponse(null);
    try {
      const data = await postJson("/api/recommendations/from-transcript", await buildTranscriptPayload());
      setResponse(data);
      const activeLabel = data.operation_semester?.active_semester_label || data.target_semester_no;
      setStatus({kind: "success", text: `${data.program_abbr} icin ${activeLabel} rotalari hazir.`});
    } catch (error) {
      setStatus({kind: "error", text: error.message});
    } finally {
      setIsSubmitting(false);
    }
  }

  async function buildTranscriptPayload() {
    if (!pdfFile) {
      throw new Error("Transcript PDF secmelisin.");
    }
    return {
      file_name: pdfFile.name,
      file_base64: await fileToBase64(pdfFile),
      goal: {
        difficulty_preference: difficulty,
      },
      elective_intents: selectedElectiveIntents(electives),
    };
  }

  return (
    <main className="app">
      <section className="control-surface">
        <header className="brand-block">
          <div className="brand-mark">M</div>
          <div>
            <p className="eyebrow">METU Student Planner</p>
            <h1>Semester planlayici</h1>
          </div>
        </header>

        <form onSubmit={submit} className="planner-form">
          <section className="form-section">
            <div className="section-heading">
              <h2>Hedef</h2>
              <span>{operationSemester?.active_semester_no || "..."}</span>
            </div>
            <div className="operation-banner">
              <strong>{operationSemester?.active_semester_label || "Aktif donem yukleniyor"}</strong>
              <small>Hedef donem sistem tarafindan otomatik belirlenir.</small>
            </div>
            <div className="segmented" aria-label="Zorluk tercihi">
              {DIFFICULTY_OPTIONS.map((option) => (
                <label key={option.value} className={difficulty === option.value ? "active" : ""}>
                  <input
                    type="radio"
                    name="difficulty"
                    value={option.value}
                    checked={difficulty === option.value}
                    onChange={(event) => setDifficulty(event.target.value)}
                  />
                  {option.label}
                </label>
              ))}
            </div>
          </section>

          <section className="form-section">
            <div className="section-heading">
              <h2>Transcript</h2>
            </div>
            <div className={pdfFile ? "upload-box has-file" : "upload-box"}>
              <input
                id="pdf"
                type="file"
                accept="application/pdf"
                onChange={(event) => setPdfFile(event.target.files?.[0] || null)}
              />
              <label htmlFor="pdf">
                <strong>{pdfFile ? pdfFile.name : "PDF sec"}</strong>
                <span>Bolum, ders gecmisi ve status otomatik okunur.</span>
              </label>
            </div>
          </section>

          <section className="form-section">
            <div className="section-heading">
              <h2>Elective tercihleri</h2>
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
                      <small>{item.hint}</small>
                    </span>
                  </label>
                  <input
                    className="course-entry"
                    value={item.courseCode}
                    onChange={(event) => updateElectiveCourse(item.category, event.target.value)}
                    placeholder="CENG495"
                    disabled={!item.selected}
                    autoCapitalize="characters"
                  />
                </article>
              ))}
            </div>
          </section>

          <button className="primary" type="submit" disabled={isSubmitting || !pdfFile}>
            {isSubmitting ? "Hazirlaniyor..." : "Plan olustur"}
          </button>
        </form>

        <FeedbackPanel
          isOpen={feedbackOpen}
          text={feedbackText}
          status={feedbackStatus}
          isSubmitting={isFeedbackSubmitting}
          onToggle={() => setFeedbackOpen((current) => !current)}
          onTextChange={setFeedbackText}
          onSubmit={submitFeedback}
        />
      </section>

      <section className="report-surface">
        <header className="report-toolbar">
          <div>
            <p className={`status ${status.kind}`}>{status.text}</p>
            <h2>Onerilen rotalar</h2>
          </div>
          {response && <span className="pill">{response.program_abbr}</span>}
        </header>

        {response ? <Report response={response} /> : <EmptyState />}
      </section>
    </main>
  );

  function toggleElective(category) {
    setElectives((current) => (
      current.map((item) => (item.category === category ? {...item, selected: !item.selected} : item))
    ));
  }

  function updateElectiveCourse(category, courseCode) {
    setElectives((current) => (
      current.map((item) => (
        item.category === category
          ? {...item, courseCode: courseCode.toUpperCase().replace(/\s+/g, "")}
          : item
      ))
    ));
  }

  async function submitFeedback(event) {
    event.preventDefault();
    if (isFeedbackSubmitting) return;
    setIsFeedbackSubmitting(true);
    setFeedbackStatus({kind: "loading", text: "Feedback kaydediliyor..."});
    try {
      await postJson("/api/feedback", {text: feedbackText});
      setFeedbackText("");
      setFeedbackStatus({kind: "success", text: "Tesekkurler, feedback kaydedildi."});
      setFeedbackOpen(false);
    } catch (error) {
      setFeedbackStatus({kind: "error", text: error.message});
    } finally {
      setIsFeedbackSubmitting(false);
    }
  }
}

function FeedbackPanel({isOpen, text, status, isSubmitting, onToggle, onTextChange, onSubmit}) {
  return (
    <section className="feedback-widget">
      <button className="secondary" type="button" onClick={onToggle}>
        Feedback gonder
      </button>
      {isOpen && (
        <form className="feedback-form" onSubmit={onSubmit}>
          <label>
            Feedback
            <textarea
              value={text}
              onChange={(event) => onTextChange(event.target.value)}
              placeholder="Eksik, hatali veya gelistirilebilir gordugun noktayi yaz."
              maxLength={4000}
              required
            />
          </label>
          {status.text && <p className={`status ${status.kind}`}>{status.text}</p>}
          <button className="primary" type="submit" disabled={isSubmitting || !text.trim()}>
            {isSubmitting ? "Gonderiliyor..." : "Submit"}
          </button>
        </form>
      )}
      {!isOpen && status.text && <p className={`status ${status.kind}`}>{status.text}</p>}
    </section>
  );
}

function AdminApp() {
  const [token, setToken] = useState(() => window.localStorage.getItem("metu_planner_admin_token") || "");

  if (!token) {
    return <AdminSignIn onSignedIn={setToken} />;
  }

  return <AdminDashboard token={token} onSignOut={() => {
    window.localStorage.removeItem("metu_planner_admin_token");
    setToken("");
  }} />;
}

function AdminSignIn({onSignedIn}) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [captcha, setCaptcha] = useState(null);
  const [captchaAnswer, setCaptchaAnswer] = useState("");
  const [status, setStatus] = useState({kind: "idle", text: "Admin girisi gerekli."});
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    refreshCaptcha();
  }, []);

  async function refreshCaptcha() {
    try {
      const data = await fetchJson("/api/admin/captcha");
      setCaptcha(data.captcha);
      setCaptchaAnswer("");
    } catch (error) {
      setStatus({kind: "error", text: error.message});
    }
  }

  async function signIn(event) {
    event.preventDefault();
    setIsSubmitting(true);
    setStatus({kind: "loading", text: "Giris kontrol ediliyor..."});
    try {
      const data = await postJson("/api/admin/sign-in", {
        username,
        password,
        captcha_id: captcha?.id,
        captcha_answer: captchaAnswer,
      });
      window.localStorage.setItem("metu_planner_admin_token", data.token);
      onSignedIn(data.token);
    } catch (error) {
      setStatus({kind: "error", text: error.message});
      refreshCaptcha();
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="admin-app">
      <section className="admin-shell narrow">
        <header className="admin-header">
          <div className="brand-mark">M</div>
          <div>
            <p className="eyebrow">Admin</p>
            <h1>Sign in</h1>
          </div>
        </header>
        <form className="admin-panel admin-form" onSubmit={signIn}>
          <p className={`status ${status.kind}`}>{status.text}</p>
          <label>
            Kullanici adi
            <input value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" />
          </label>
          <label>
            Sifre
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
            />
          </label>
          <label>
            Captcha: {captcha?.question || "yukleniyor"}
            <input value={captchaAnswer} onChange={(event) => setCaptchaAnswer(event.target.value)} />
          </label>
          <button className="primary" type="submit" disabled={isSubmitting || !captcha}>
            {isSubmitting ? "Kontrol ediliyor..." : "Sign in"}
          </button>
        </form>
      </section>
    </main>
  );
}

function AdminDashboard({token, onSignOut}) {
  const [operationSemester, setOperationSemester] = useState(null);
  const [semesterNo, setSemesterNo] = useState("20252");
  const [job, setJob] = useState(null);
  const [feedbacks, setFeedbacks] = useState([]);
  const [status, setStatus] = useState({kind: "idle", text: "Admin panel hazir."});

  useEffect(() => {
    loadOperationSemester((operation) => {
      setOperationSemester(operation);
      setSemesterNo(operation?.active_semester_no || "20252");
    });
    loadAdminJob(setJob, token, onAuthExpired);
    loadFeedbacks();
  }, [token]);

  useEffect(() => {
    if (!job || job.status !== "running") return undefined;
    const id = window.setInterval(() => loadAdminJob(setJob, token, onAuthExpired), 2500);
    return () => window.clearInterval(id);
  }, [job, token]);

  async function startRefresh(event) {
    event.preventDefault();
    setStatus({kind: "loading", text: "Guncelleme isi baslatiliyor..."});
    try {
      const data = await postJson("/api/admin/refresh-operation-semester", {semester_no: semesterNo}, token);
      setJob(data.job);
      setStatus({kind: "success", text: "Offering guncelleme isi baslatildi."});
    } catch (error) {
      setStatus({kind: "error", text: error.message});
      if (error.status === 401) onAuthExpired();
    }
  }

  async function loadFeedbacks() {
    try {
      const data = await fetchJson("/api/admin/feedbacks", token);
      setFeedbacks(data.feedbacks || []);
    } catch (error) {
      setStatus({kind: "error", text: error.message});
      if (error.status === 401) onAuthExpired();
    }
  }

  async function toggleFavorite(feedback) {
    try {
      await patchJson(`/api/admin/feedbacks/${feedback.id}/favorite`, {
        is_favorite: !feedback.is_favorite,
      }, token);
      await loadFeedbacks();
    } catch (error) {
      setStatus({kind: "error", text: error.message});
    }
  }

  async function removeFeedback(feedback) {
    try {
      await deleteJson(`/api/admin/feedbacks/${feedback.id}`, token);
      setFeedbacks((current) => current.filter((item) => item.id !== feedback.id));
    } catch (error) {
      setStatus({kind: "error", text: error.message});
    }
  }

  function onAuthExpired() {
    window.localStorage.removeItem("metu_planner_admin_token");
    onSignOut();
  }

  async function signOut() {
    try {
      await postJson("/api/admin/sign-out", {}, token);
    } finally {
      onAuthExpired();
    }
  }

  const isRunning = job?.status === "running";

  return (
    <main className="admin-app">
      <section className="admin-shell">
        <header className="admin-header">
          <div className="brand-mark">M</div>
          <div>
            <p className="eyebrow">Admin</p>
            <h1>Operasyon donemi</h1>
          </div>
          <button className="secondary compact" type="button" onClick={signOut}>Sign out</button>
        </header>

        <section className="admin-panel">
          <p className={`status ${status.kind}`}>{status.text}</p>
          <div className="operation-banner">
            <strong>{operationSemester?.active_semester_label || "Aktif donem bilinmiyor"}</strong>
            <small>Aktif kod: {operationSemester?.active_semester_no || "-"}</small>
          </div>

          <form className="admin-form" onSubmit={startRefresh}>
            <label>
              Yeni operasyon donemi
              <input value={semesterNo} onChange={(event) => setSemesterNo(event.target.value.trim())} />
            </label>
            <button className="primary" type="submit" disabled={isRunning}>
              {isRunning
                ? "Guncelleme calisiyor..."
                : "SAIS'ten guncel offering ve saat bilgilerini cek"}
            </button>
          </form>
        </section>

        {job && (
          <section className="admin-panel">
            <header className="job-header">
              <h2>Son is</h2>
              <span className={`job-pill ${job.status}`}>{job.status}</span>
            </header>
            <p className="scenario-note">Donem: {job.semester_no}</p>
            <pre className="job-log">{(job.logs || []).slice(-40).join("\n") || "Log bekleniyor..."}</pre>
          </section>
        )}

        <section className="admin-panel">
          <header className="job-header">
            <h2>Feedbackler</h2>
            <span className="job-pill">{feedbacks.length}</span>
          </header>
          <div className="feedback-list">
            {feedbacks.length === 0 && <p className="scenario-note">Henuz feedback yok.</p>}
            {feedbacks.map((feedback) => (
              <article className={feedback.is_favorite ? "feedback-card favorite" : "feedback-card"} key={feedback.id}>
                <p>{feedback.text}</p>
                <footer>
                  <span>{formatDate(feedback.created_at_utc)}</span>
                  <div>
                    <button className="secondary compact" type="button" onClick={() => toggleFavorite(feedback)}>
                      {feedback.is_favorite ? "Favoriden cikar" : "Favori"}
                    </button>
                    <button className="danger compact" type="button" onClick={() => removeFeedback(feedback)}>
                      Remove
                    </button>
                  </div>
                </footer>
              </article>
            ))}
          </div>
        </section>
      </section>
    </main>
  );
}

function Report({response}) {
  const view = response.student_view || legacyStudentView(response);
  const routes = view.routes || [];
  const priorityWarnings = view.notices || [];

  return (
    <div className="report-content">
      {priorityWarnings.length > 0 && (
        <div className="notice">
          <strong>Kontrol edilmesi gereken nokta var.</strong>
          <span>{priorityWarnings[0].message}</span>
        </div>
      )}

      <div className="route-stack">
        {routes.map((route) => (
          <ScenarioCard key={route.id} route={route} />
        ))}
      </div>

      {(view.blocked_courses || []).length > 0 && <BlockedPanel courses={view.blocked_courses} />}
    </div>
  );
}

function ScenarioCard({route}) {
  const courses = route.courses || [];
  const creditCourseCount = route.credit_course_count ?? 0;
  const zeroCreditCount = route.zero_credit_course_count ?? 0;

  return (
    <article className="scenario-card">
      <section className="scenario-main">
        <header>
          <div>
            <p>{routeLabel(route.tempo_label || route.id)}</p>
            <h3>{route.title}</h3>
          </div>
          <span>{creditCourseCount} kredili ders</span>
        </header>
        {zeroCreditCount > 0 && <p className="scenario-note">+ {zeroCreditCount} kredisiz ders</p>}
        <div className="course-list">
          {courses.map((course) => (
            <CoursePill course={course} key={`${route.id}-${course.code}`} />
          ))}
        </div>
      </section>
    </article>
  );
}

function CoursePill({course}) {
  const tags = courseTags(course.flags || []);
  return (
    <div className="course-pill" style={{"--course-color": course.color || "#f97316"}}>
      <div>
        <strong>{course.code}</strong>
        {course.summary && <small>{course.summary}</small>}
      </div>
      {tags.length > 0 && <span>{tags.join(" / ")}</span>}
    </div>
  );
}

function EmptyState() {
  return (
    <div className="empty-state">
      <h3>Rotalar burada gorunecek</h3>
      <p>Transcript PDF yukledikten sonra uc farkli semester rotasi olusturulur.</p>
    </div>
  );
}

function BlockedPanel({courses}) {
  return (
    <section className="blocked-panel">
      <header>
        <h3>Simdilik kapali dersler</h3>
        <span>{courses.length}</span>
      </header>
      <div className="blocked-list">
        {courses.slice(0, 6).map((course) => (
          <div className="blocked-row" key={course.code}>
            <strong>{course.code}</strong>
            <span>{blockedReason(course)}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function defaultElectives() {
  return ELECTIVE_CATEGORIES.map((item) => ({
    category: item.key,
    label: item.label,
    hint: item.hint,
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

function routeLabel(kind) {
  return {
    easy: "Rahat rota",
    balanced: "Standart rota",
    aggressive: "Hizli rota",
    low_tempo: "Rahat rota",
    standard_tempo: "Standart rota",
    fast_tempo: "Hizli rota",
  }[kind] || "Alternatif rota";
}

function courseTags(flags) {
  const labels = {
    zero_credit: "kredisiz",
    repeat_priority: "tekrar",
    placeholder: "secimli",
    needs_course_selection: "ders secimi gerekli",
    priority_elective: "oncelikli elective",
    student_requested: "tercihin",
  };
  return flags.map((flag) => labels[flag]).filter(Boolean);
}

function blockedReason(course) {
  if (course.missing_prerequisites?.length) {
    return `Eksik: ${course.missing_prerequisites.join(", ")}`;
  }
  return course.explanation || "Kosul saglanmiyor.";
}

function legacyStudentView(response) {
  const scenarios = response.report?.scenarios || [];
  return {
    routes: scenarios.map((scenario) => {
      const courses = scenario.courses || [];
      return {
        id: scenario.kind,
        title: scenario.name,
        tempo_label: scenario.kind,
        credit_course_count: courses.filter((course) => (
          course.estimated_credits === null || course.estimated_credits === undefined || course.estimated_credits > 0
        )).length,
        zero_credit_course_count: courses.filter((course) => course.estimated_credits === 0).length,
        courses: courses.map((course) => ({
          code: course.course_code,
          summary: "Mufredatindaki siradaki alinabilir derslerden biri.",
          flags: [
            ...(course.estimated_credits === 0 ? ["zero_credit"] : []),
            ...(course.is_repeat_priority ? ["repeat_priority"] : []),
            ...(course.is_placeholder ? ["placeholder"] : []),
            ...(course.requires_course_selection || course.is_placeholder ? ["needs_course_selection"] : []),
            ...(course.is_easy_priority_elective ? ["priority_elective"] : []),
            ...(course.is_user_requested ? ["student_requested"] : []),
          ],
        })),
      };
    }),
    notices: (response.report?.warnings || []).filter((warning) => (
      warning.severity === "blocker" || warning.severity === "warning"
    )),
    blocked_courses: (response.report?.blocked_courses || []).map((course) => ({
      code: course.course_code,
      missing_prerequisites: course.missing_prerequisite_codes || [],
      explanation: course.explanation,
    })),
  };
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result).split(",", 2)[1]);
    reader.onerror = () => reject(new Error("PDF okunamadi."));
    reader.readAsDataURL(file);
  });
}

function loadOperationSemester(setter) {
  fetchJson("/api/admin/operation-semester")
    .then((data) => setter(data.operation_semester))
    .catch(() => setter(null));
}

function loadAdminJob(setter, token, onAuthExpired) {
  fetchJson("/api/admin/refresh-job", token)
    .then((data) => setter(data.job))
    .catch((error) => {
      setter(null);
      if (error.status === 401 && onAuthExpired) onAuthExpired();
    });
}

async function fetchJson(url, token = "") {
  const response = await fetch(url, {
    headers: authHeaders(token),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw httpError(data.error || "Istek basarisiz oldu.", response.status);
  }
  return data;
}

async function postJson(url, payload, token = "") {
  const response = await fetch(url, {
    method: "POST",
    headers: {"Content-Type": "application/json", ...authHeaders(token)},
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw httpError(data.error || "Istek basarisiz oldu.", response.status);
  }
  return data;
}

async function patchJson(url, payload, token = "") {
  const response = await fetch(url, {
    method: "PATCH",
    headers: {"Content-Type": "application/json", ...authHeaders(token)},
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw httpError(data.error || "Istek basarisiz oldu.", response.status);
  }
  return data;
}

async function deleteJson(url, token = "") {
  const response = await fetch(url, {
    method: "DELETE",
    headers: authHeaders(token),
  });
  const data = await response.json();
  if (!response.ok || !data.ok) {
    throw httpError(data.error || "Istek basarisiz oldu.", response.status);
  }
  return data;
}

function authHeaders(token) {
  return token ? {Authorization: `Bearer ${token}`} : {};
}

function httpError(message, status) {
  const error = new Error(message);
  error.status = status;
  return error;
}

function formatDate(value) {
  if (!value) return "";
  return value.replace("T", " ").replace("Z", "");
}

createRoot(document.getElementById("root")).render(<App />);
