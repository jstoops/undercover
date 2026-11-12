import { defineConfig } from "@playwright/test";
import os from "node:os";
import path from "node:path";

// The end-to-end tests change claims, so they run on a backend and dashboard
// of their own, with a freshly seeded database, apart from npm run dev.
const database = path.join(os.tmpdir(), "undercover-e2e.db");

export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/test-results",
  reporter: "list",
  use: { baseURL: "http://localhost:5174" },
  webServer: [
    {
      command:
        "uv run -m backend.seed && uv run -m uvicorn backend.main:app --port 8001",
      url: "http://127.0.0.1:8001/api/health",
      env: { UNDERCOVER_DB: database },
      reuseExistingServer: false,
    },
    {
      command: "npx vite dashboard --port 5174 --strictPort",
      url: "http://localhost:5174",
      env: { UNDERCOVER_API: "http://127.0.0.1:8001" },
      reuseExistingServer: false,
    },
  ],
});
