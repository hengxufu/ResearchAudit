import { defineConfig } from "@playwright/test";
import path from "node:path";
import { randomUUID } from "node:crypto";
const root = path.resolve("..");
const port = Number(process.env.PW_PORT || 8023);
if (!Number.isInteger(port) || port < 1024 || port > 65535)
  throw Error("Invalid PW_PORT");
const python =
  process.env.RESEARCHAUDIT_PYTHON ||
  path.join(
    root,
    ".venv",
    process.platform === "win32" ? "Scripts/python.exe" : "bin/python",
  );
export default defineConfig({
  testDir: "./e2e",
  timeout: 60000,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    headless: true,
    channel: process.env.PW_BROWSER_CHANNEL || undefined,
    viewport: { width: 1440, height: 1000 },
    trace: "retain-on-failure",
  },
  webServer: {
    command: `"${python}" -m uvicorn backend.main:app --host 127.0.0.1 --port ${port}`,
    cwd: root,
    url: `http://127.0.0.1:${port}`,
    reuseExistingServer: false,
    env: {
      RESEARCHAUDIT_HOME: path.join(
        root,
        ".test-runs-" + randomUUID(),
        "e2e-db",
      ),
    },
    timeout: 30000,
  },
});
