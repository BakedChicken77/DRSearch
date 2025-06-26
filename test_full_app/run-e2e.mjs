import { spawn } from "child_process";
import { createWriteStream, existsSync } from "fs";
import { dirname, resolve } from "path";
import { fileURLToPath } from "url";
import net from "net";

const __dirname = dirname(fileURLToPath(import.meta.url));
const rootDir = resolve(__dirname, "..");
const backendDir = resolve(rootDir, "drsearch_backend");
const frontendDir = resolve(rootDir, "drsearch_frontend");
const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
const outputDir = resolve(__dirname, "output", timestamp);
const logDir = resolve(outputDir, "logs");
import { mkdirSync } from "fs";
mkdirSync(outputDir, { recursive: true });
mkdirSync(logDir, { recursive: true });

const YARN = process.platform === "win32" ? "yarn.cmd" : "yarn";
const NPX = process.platform === "win32" ? "npx.cmd" : "npx";

// Add verbose logging function
function log(message, level = "INFO") {
  const timestamp = new Date().toISOString();
  console.log(`[${timestamp}] [${level}] ${message}`);
}

function getPort() {
  return new Promise((resolve) => {
    const srv = net.createServer();
    srv.listen(0, () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

function waitFor(url, timeout = 60000) {
  const deadline = Date.now() + timeout;
  return new Promise((resolve, reject) => {
    const check = async () => {
      try {
        const res = await fetch(url);
        if (res.ok) return resolve();
      } catch {}
      if (Date.now() > deadline)
        return reject(new Error("Timeout waiting for " + url));
      setTimeout(check, 500);
    };
    check();
  });
}

function spawnLogged(cmd, args, options, outPath, errPath) {
  log(`Spawning process: ${cmd} ${args.join(" ")}`);
  const proc = spawn(cmd, args, {
    ...options,
    stdio: ["ignore", "pipe", "pipe"],
  });
  if (outPath) proc.stdout.pipe(createWriteStream(outPath));
  if (errPath) proc.stderr.pipe(createWriteStream(errPath));
  return proc;
}

let simProc;
let frontProc;

function cleanup() {
  if (frontProc && !frontProc.killed) frontProc.kill("SIGTERM");
  if (simProc && !simProc.killed) simProc.kill("SIGTERM");
}

process.on("SIGINT", () => {
  cleanup();
  process.exit(1);
});
process.on("SIGTERM", () => {
  cleanup();
  process.exit(1);
});
process.on("exit", cleanup);

(async () => {
  log("Starting end-to-end test execution");
  log(`Environment: COLLECT_COVERAGE=${process.env.COLLECT_COVERAGE}`);
  log(`Working directory: ${process.cwd()}`);
  
  const backendPort = await getPort();
  const frontendPort = await getPort();
  log(`Allocated ports - Backend: ${backendPort}, Frontend: ${frontendPort}`);

  const commonEnv = {
    ...process.env,
    AUTH_ENABLED: "False",
    NEXT_PUBLIC_AUTH_ENABLED: "False",
  };

  log("Starting backend simulator...");
  simProc = spawnLogged(
    "poetry",
    [
      "run",
      "uvicorn",
      "testing_full_app.simulator:app",
      "--port",
      String(backendPort),
    ],
    { cwd: backendDir, env: commonEnv, shell: process.platform === "win32" },
    resolve(logDir, "simulator1.out.log"),
    resolve(logDir, "simulator1.err.log"),
  );

  log(`Waiting for backend to be ready at http://localhost:${backendPort}/index-options`);
  await waitFor(`http://localhost:${backendPort}/index-options`);
  log("Backend simulator is ready");

  if (!existsSync(resolve(frontendDir, "node_modules"))) {
    log("Node modules not found, installing dependencies...");
    await new Promise((res, rej) => {
      const inst = spawn(YARN, ["install", "--silent"], {
        cwd: frontendDir,
        shell: process.platform === "win32",
        stdio: "inherit",
      });
      inst.on("exit", (c) =>
        c === 0 ? res() : rej(new Error("yarn install failed")),
      );
    });
    log("Dependencies installed successfully");
  } else {
    log("Node modules already exist, skipping installation");
  }

  log("Starting frontend development server...");
  frontProc = spawnLogged(
    YARN,
    ["dev", "--port", String(frontendPort)],
    {
      cwd: frontendDir,
      env: {
      ...commonEnv,
      API_BASE_URL: `http://localhost:${backendPort}`,
      NEXT_PUBLIC_API_BASE_URL: `http://localhost:${backendPort}`,
      PORT: String(frontendPort)
    },
      shell: process.platform === "win32",
    },
    resolve(logDir, "frontend1.out.log"),
    resolve(logDir, "frontend1.err.log"),
  );

  log(`Waiting for frontend to be ready at http://localhost:${frontendPort}`);
  await waitFor(`http://localhost:${frontendPort}`);
  log("Frontend is ready");

  const env = {
    ...commonEnv,
    API_BASE_URL: `http://localhost:${backendPort}`,
    FRONTEND_BASE_URL: `http://localhost:${frontendPort}`,
  };
  if (process.env.COLLECT_COVERAGE === "1") {
    env.PW_TEST_COVERAGE = "1";
    log("Coverage collection enabled");
  }

  log("Starting Playwright tests...");
  const testResultsDir = resolve(outputDir, "playwright-results");
  mkdirSync(testResultsDir, { recursive: true });
  log(`Test command: ${NPX} playwright test testing_full_app --output ${testResultsDir}`);
  log(`Test environment: ${JSON.stringify(env, null, 2)}`);

  const testProc = spawn(NPX, ["playwright", "test", "testing_full_app", "--reporter=list", "--output", testResultsDir], {
    cwd: frontendDir,
    env,
    stdio: "inherit",
    shell: process.platform === "win32",
  });

  const code = await new Promise((resolve) => testProc.on("exit", resolve));
  log(`Test execution completed with exit code: ${code}`);
  cleanup();
  process.exitCode = code;
})();
