import express from "express";
import {spawn} from "node:child_process";
import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import {fileURLToPath} from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const webRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(webRoot, "..");
const clientDist = path.join(webRoot, "client", "dist");
const bridgePath = path.join(repoRoot, "scripts", "recommendation_api_bridge.py");
const appDataBridgePath = path.join(repoRoot, "scripts", "web_app_api_bridge.py");
const adminRefreshPath = path.join(repoRoot, "scripts", "admin_refresh_operation_semester.py");
const operationConfigPath = path.join(repoRoot, "config", "operation.json");
const dbPath = process.env.STUDENT_PLANNER_DB || path.join(repoRoot, "data", "db", "student_planner.sqlite");
const pythonBin = process.env.PYTHON || "python";
const port = Number(process.env.PORT || 3000);
const host = process.env.HOST || "127.0.0.1";
let adminJob = null;
const captchaChallenges = new Map();
const adminSessions = new Map();
const adminSessionTtlMs = 6 * 60 * 60 * 1000;
const captchaTtlMs = 10 * 60 * 1000;

const app = express();
app.use(express.json({limit: "9mb"}));

app.get("/api/health", (_request, response) => {
  response.json({ok: true, service: "student-planner-node-web"});
});

app.get("/api/admin/operation-semester", async (_request, response) => {
  try {
    response.json({ok: true, operation_semester: await readOperationSemester()});
  } catch (error) {
    response.status(500).json({ok: false, error: error.message});
  }
});

app.post("/api/feedback", async (request, response) => {
  await handleAppDataRequest(response, "submit-feedback", {text: request.body?.text});
});

app.get("/api/admin/captcha", (_request, response) => {
  response.json({ok: true, captcha: createCaptchaChallenge()});
});

app.post("/api/admin/sign-in", async (request, response) => {
  const captchaOk = verifyCaptchaAnswer(request.body?.captcha_id, request.body?.captcha_answer);
  if (!captchaOk) {
    response.status(400).json({ok: false, error: "Captcha verification failed."});
    return;
  }

  try {
    const result = await callAppDataBridge("verify-admin", {
      username: request.body?.username,
      password: request.body?.password,
    });
    if (!result.ok) {
      response.status(401).json(result);
      return;
    }
    const token = crypto.randomBytes(32).toString("hex");
    adminSessions.set(token, {
      username: result.admin.username,
      expiresAt: Date.now() + adminSessionTtlMs,
    });
    response.json({ok: true, token, admin: result.admin, expires_in_seconds: adminSessionTtlMs / 1000});
  } catch (error) {
    response.status(500).json({ok: false, error: error.message});
  }
});

app.post("/api/admin/sign-out", requireAdmin, (request, response) => {
  const token = bearerToken(request);
  if (token) {
    adminSessions.delete(token);
  }
  response.json({ok: true});
});

app.get("/api/admin/session", requireAdmin, (request, response) => {
  response.json({ok: true, admin: {username: request.admin.username}});
});

app.get("/api/admin/feedbacks", requireAdmin, async (_request, response) => {
  await handleAppDataRequest(response, "list-feedback", {});
});

app.patch("/api/admin/feedbacks/:id/favorite", requireAdmin, async (request, response) => {
  await handleAppDataRequest(response, "favorite-feedback", {
    id: request.params.id,
    is_favorite: Boolean(request.body?.is_favorite),
  });
});

app.delete("/api/admin/feedbacks/:id", requireAdmin, async (request, response) => {
  await handleAppDataRequest(response, "delete-feedback", {id: request.params.id});
});

app.get("/api/admin/refresh-job", requireAdmin, (_request, response) => {
  response.json({ok: true, job: adminJob});
});

app.post("/api/admin/refresh-operation-semester", requireAdmin, (request, response) => {
  const semesterNo = String(request.body?.semester_no || "").trim();
  if (!/^\d{5}$/.test(semesterNo)) {
    response.status(400).json({ok: false, error: "semester_no must be a 5-digit METU semester number."});
    return;
  }
  if (adminJob && adminJob.status === "running") {
    response.status(409).json({ok: false, error: "An admin refresh job is already running.", job: adminJob});
    return;
  }

  adminJob = startAdminRefreshJob(semesterNo);
  response.status(202).json({ok: true, job: adminJob});
});

app.post("/api/recommendations/from-json", async (request, response) => {
  await handleBridgeRequest(response, "json", request.body);
});

app.post("/api/recommendations/from-transcript", async (request, response) => {
  await handleBridgeRequest(response, "transcript", request.body);
});

app.use("/api", (_request, response) => {
  response.status(404).json({ok: false, error: "API endpoint not found."});
});

app.use(express.static(clientDist));
app.get("*", (_request, response) => {
  response.sendFile(path.join(clientDist, "index.html"));
});

async function handleBridgeRequest(response, mode, payload) {
  try {
    const result = await callPythonBridge(mode, payload);
    response.status(result.ok ? 200 : 400).json(result);
  } catch (error) {
    response.status(500).json({ok: false, error: error.message});
  }
}

async function handleAppDataRequest(response, mode, payload) {
  try {
    const result = await callAppDataBridge(mode, payload);
    response.status(result.ok ? 200 : 400).json(result);
  } catch (error) {
    response.status(500).json({ok: false, error: error.message});
  }
}

function callPythonBridge(mode, payload) {
  return new Promise((resolve, reject) => {
    const child = spawn(pythonBin, [bridgePath, "--mode", mode, "--db", dbPath], {
      cwd: repoRoot,
      stdio: ["pipe", "pipe", "pipe"],
      windowsHide: true,
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString("utf8");
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString("utf8");
    });
    child.on("error", (error) => reject(error));
    child.on("close", () => {
      try {
        const parsed = JSON.parse(stdout || "{}");
        if (parsed.ok === false && stderr.trim()) {
          parsed.server_stderr = stderr.trim().slice(0, 1200);
        }
        resolve(parsed);
      } catch (error) {
        reject(new Error(`Python bridge returned invalid JSON. ${stderr.trim()}`));
      }
    });

    child.stdin.write(JSON.stringify(payload || {}));
    child.stdin.end();
  });
}

function callAppDataBridge(mode, payload) {
  return new Promise((resolve, reject) => {
    const child = spawn(pythonBin, [appDataBridgePath, "--mode", mode, "--db", dbPath], {
      cwd: repoRoot,
      stdio: ["pipe", "pipe", "pipe"],
      windowsHide: true,
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString("utf8");
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString("utf8");
    });
    child.on("error", (error) => reject(error));
    child.on("close", () => {
      try {
        const parsed = JSON.parse(stdout || "{}");
        if (parsed.ok === false && stderr.trim()) {
          parsed.server_stderr = stderr.trim().slice(0, 1200);
        }
        resolve(parsed);
      } catch (error) {
        reject(new Error(`App data bridge returned invalid JSON. ${stderr.trim()}`));
      }
    });

    child.stdin.write(JSON.stringify(payload || {}));
    child.stdin.end();
  });
}

async function readOperationSemester() {
  const raw = await fs.readFile(operationConfigPath, "utf8");
  return JSON.parse(raw);
}

function createCaptchaChallenge() {
  cleanupExpiredMaps();
  const left = crypto.randomInt(2, 10);
  const right = crypto.randomInt(2, 10);
  const captchaId = crypto.randomBytes(16).toString("hex");
  captchaChallenges.set(captchaId, {
    answer: String(left + right),
    expiresAt: Date.now() + captchaTtlMs,
  });
  return {
    id: captchaId,
    question: `${left} + ${right} = ?`,
  };
}

function verifyCaptchaAnswer(captchaId, answer) {
  cleanupExpiredMaps();
  const challenge = captchaChallenges.get(String(captchaId || ""));
  captchaChallenges.delete(String(captchaId || ""));
  if (!challenge) {
    return false;
  }
  return String(answer || "").trim() === challenge.answer;
}

function requireAdmin(request, response, next) {
  cleanupExpiredMaps();
  const token = bearerToken(request);
  const session = token ? adminSessions.get(token) : null;
  if (!session) {
    response.status(401).json({ok: false, error: "Admin sign-in required."});
    return;
  }
  session.expiresAt = Date.now() + adminSessionTtlMs;
  request.admin = {username: session.username};
  next();
}

function bearerToken(request) {
  const header = request.get("authorization") || "";
  if (!header.toLowerCase().startsWith("bearer ")) {
    return null;
  }
  return header.slice(7).trim();
}

function cleanupExpiredMaps() {
  const now = Date.now();
  for (const [key, value] of captchaChallenges.entries()) {
    if (value.expiresAt <= now) {
      captchaChallenges.delete(key);
    }
  }
  for (const [key, value] of adminSessions.entries()) {
    if (value.expiresAt <= now) {
      adminSessions.delete(key);
    }
  }
}

function startAdminRefreshJob(semesterNo) {
  const startedAt = new Date().toISOString();
  const job = {
    id: `${semesterNo}-${startedAt}`,
    semester_no: semesterNo,
    status: "running",
    started_at: startedAt,
    finished_at: null,
    exit_code: null,
    logs: [],
  };
  const child = spawn(pythonBin, [adminRefreshPath, "--semester", semesterNo, "--db", dbPath], {
    cwd: repoRoot,
    stdio: ["ignore", "pipe", "pipe"],
    windowsHide: true,
  });

  child.stdout.on("data", (chunk) => appendJobLog(job, chunk.toString("utf8")));
  child.stderr.on("data", (chunk) => appendJobLog(job, chunk.toString("utf8")));
  child.on("error", (error) => {
    job.status = "failed";
    job.finished_at = new Date().toISOString();
    appendJobLog(job, error.message);
  });
  child.on("close", (code) => {
    job.exit_code = code;
    job.status = code === 0 ? "completed" : "failed";
    job.finished_at = new Date().toISOString();
  });

  return job;
}

function appendJobLog(job, text) {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
  job.logs.push(...lines);
  if (job.logs.length > 200) {
    job.logs = job.logs.slice(job.logs.length - 200);
  }
}

app.listen(port, host, () => {
  console.log(`METU Student Planner web server running at http://${host}:${port}/`);
  callAppDataBridge("ensure", {}).catch((error) => {
    console.error(`Failed to ensure web app tables: ${error.message}`);
  });
});
