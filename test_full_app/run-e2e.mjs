import { spawn } from "child_process";
import { createWriteStream, existsSync } from "fs";
import { dirname, resolve } from "path";
import { fileURLToPath } from "url";
import net from "net";

const __dirname = dirname(fileURLToPath(import.meta.url));
const rootDir = resolve(__dirname, "..");
const backendDir = resolve(rootDir, "drsearch_backend");
const frontendDir = resolve(rootDir, "drsearch_frontend");
const logDir = resolve(__dirname, "logs");
import { mkdirSync } from "fs";
mkdirSync(logDir, { recursive: true });

const YARN = process.platform === "win32" ? "yarn.cmd" : "yarn";
const NPX = process.platform === "win32" ? "npx.cmd" : "npx";

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
  const backendPort = await getPort();
  const frontendPort = await getPort();

  const commonEnv = {
    ...process.env,
    AUTH_ENABLED: "False",
    NEXT_PUBLIC_AUTH_ENABLED: "False",
  };

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

  await waitFor(`http://localhost:${backendPort}/index-options`);

  if (!existsSync(resolve(frontendDir, "node_modules"))) {
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
  }

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

  await waitFor(`http://localhost:${frontendPort}`);

  const env = {
    ...commonEnv,
    API_BASE_URL: `http://localhost:${backendPort}`,
    FRONTEND_BASE_URL: `http://localhost:${frontendPort}`,
  };
  if (process.env.COLLECT_COVERAGE === "1") {
    env.PW_TEST_COVERAGE = "1";
  }

  const testProc = spawn(NPX, ["playwright", "test", "testing_full_app"], {
    cwd: frontendDir,
    env,
    stdio: "inherit",
    shell: process.platform === "win32",
  });

  const code = await new Promise((resolve) => testProc.on("exit", resolve));
  cleanup();
  process.exitCode = code;
})();
