import express from "express";
import {spawn} from "node:child_process";
import path from "node:path";
import {fileURLToPath} from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const webRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(webRoot, "..");
const clientDist = path.join(webRoot, "client", "dist");
const bridgePath = path.join(repoRoot, "scripts", "recommendation_api_bridge.py");
const dbPath = process.env.STUDENT_PLANNER_DB || path.join(repoRoot, "data", "db", "student_planner.sqlite");
const pythonBin = process.env.PYTHON || "python";
const port = Number(process.env.PORT || 3000);
const host = process.env.HOST || "127.0.0.1";

const app = express();
app.use(express.json({limit: "9mb"}));

app.get("/api/health", (_request, response) => {
  response.json({ok: true, service: "student-planner-node-web"});
});

app.post("/api/recommendations/from-json", async (request, response) => {
  await handleBridgeRequest(response, "json", request.body);
});

app.post("/api/recommendations/from-transcript", async (request, response) => {
  await handleBridgeRequest(response, "transcript", request.body);
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

app.listen(port, host, () => {
  console.log(`METU Student Planner web server running at http://${host}:${port}/`);
});
