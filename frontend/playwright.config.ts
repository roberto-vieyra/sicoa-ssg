import { defineConfig } from "@playwright/test";
import { networkInterfaces } from "node:os";
import { resolve } from "node:path";

const host = process.env.E2E_LAN_IP || "127.0.0.1";
const local = Object.values(networkInterfaces())
  .flat()
  .some((address) => address?.address === host && address.family === "IPv4");
if (!local) throw new Error("E2E_LAN_IP debe ser una IPv4 de este equipo.");
const port = Number(process.env.E2E_PORT || 5183);
if (!Number.isInteger(port) || port < 1 || port > 65535)
  throw new Error("Puerto E2E inválido.");
const baseURL = `http://${host}:${port}`;
const root = resolve(import.meta.dirname, "..");
const python = resolve(
  root,
  process.platform === "win32"
    ? ".venv/Scripts/python.exe"
    : ".venv/bin/python",
);

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 180_000,
  reporter: [["list"], ["html", { open: "never" }]],
  webServer: {
    command: `"${python}" -m scripts.qa_artifacts --host ${host} --serve ${port}`,
    cwd: root,
    url: `${baseURL}/api/health`,
    reuseExistingServer: false,
    timeout: 180_000,
  },
  use: {
    baseURL,
    browserName: "chromium",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { viewport: { width: 1440, height: 900 } } },
    {
      name: "mobile",
      use: {
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
      },
    },
  ],
});
