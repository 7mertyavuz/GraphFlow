/**
 * Capture live high-DPI screenshots of the running GraphFlow web UI.
 *
 * Uses pure Node 24 built-ins (fetch + WebSocket CDP + child_process) with zero
 * third-party npm dependencies against headless Chrome + live Next.js + FastAPI.
 *
 * Outputs:
 *   - docs/assets/ui-showcase.png     (/backtest in EN with preset query + matches)
 *   - docs/assets/ui-showcase-tr.png  (/backtest in TR with preset query + matches)
 *   - docs/assets/ui-findings.png     (/bulgular in EN showing elimination chain)
 *
 * Usage:
 *   node tools/capture_ui_screenshots.mjs
 */

import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const UI_ORIGIN = process.env.GRAPHFLOW_UI_URL || "http://localhost:3000";
const ASSETS_DIR = path.resolve("docs/assets");
const CDP_PORT = 9229;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

class CdpClient {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl);
    this.nextId = 1;
    this.pending = new Map();
    this.openPromise = new Promise((resolve, reject) => {
      this.ws.addEventListener("open", () => resolve());
      this.ws.addEventListener("error", (err) => reject(err));
    });
    this.ws.addEventListener("message", (event) => {
      const msg = JSON.parse(event.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        if (msg.error) reject(new Error(JSON.stringify(msg.error)));
        else resolve(msg.result);
      }
    });
  }

  async connect() {
    await this.openPromise;
  }

  call(method, params = {}) {
    const id = this.nextId++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  async eval(expression) {
    const res = await this.call("Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    if (res.exceptionDetails) {
      throw new Error(`Eval exception: ${JSON.stringify(res.exceptionDetails)}`);
    }
    return res.result?.value;
  }

  async waitUntil(predicateExpr, timeoutMs = 45000, pollMs = 250) {
    const deadline = Date.now() + timeoutMs;
    while (Date.now() < deadline) {
      const ok = await this.eval(`Boolean(${predicateExpr})`);
      if (ok) return;
      await sleep(pollMs);
    }
    throw new Error(`Timed out waiting for: ${predicateExpr}`);
  }

  close() {
    try {
      this.ws.close();
    } catch {
      // ignore
    }
  }
}

async function waitForCdpTarget() {
  for (let i = 0; i < 40; i++) {
    try {
      const res = await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`);
      if (res.ok) {
        const list = await res.json();
        const page = list.find((t) => t.type === "page");
        if (page?.webSocketDebuggerUrl) return page.webSocketDebuggerUrl;
      }
    } catch {
      // retry
    }
    await sleep(150);
  }
  throw new Error("Chrome CDP target did not become ready");
}

async function clickButtonByExactText(client, candidates) {
  const clicked = await client.eval(`(() => {
    const targets = ${JSON.stringify(candidates)};
    const buttons = Array.from(document.querySelectorAll('button'));
    for (const label of targets) {
      const btn = buttons.find(b => b.textContent && b.textContent.trim() === label && !b.disabled);
      if (btn) { btn.click(); return label; }
    }
    return null;
  })()`);
  if (!clicked) {
    const avail = await client.eval(
      `Array.from(document.querySelectorAll('button')).map(b => b.textContent?.trim()).filter(Boolean)`
    );
    throw new Error(`Could not find enabled button matching ${JSON.stringify(candidates)}; found: ${JSON.stringify(avail)}`);
  }
  return clicked;
}

async function hideNextDevOverlay(client) {
  await client.eval(`document.querySelectorAll('nextjs-portal').forEach(el => { el.style.display = 'none'; })`);
}

async function captureBacktest(client, lang, outFile) {
  const width = 1560;
  const initialHeight = 1600;
  await client.call("Emulation.setDeviceMetricsOverride", {
    width,
    height: initialHeight,
    deviceScaleFactor: 2,
    mobile: false,
  });

  await client.call("Page.navigate", { url: `${UI_ORIGIN}/backtest` });
  await client.waitUntil(`document.readyState === 'complete' && document.querySelectorAll('canvas').length >= 1`);

  // Force clean deterministic UI language and reload so hydrated DOM + API headers match
  await client.eval(`window.localStorage.setItem('graphflow.lang', ${JSON.stringify(lang)})`);
  await client.call("Page.reload", { ignoreCache: true });
  await client.waitUntil(`document.readyState === 'complete' && document.querySelectorAll('canvas').length >= 1`);
  await sleep(500);

  // Pick Head & Shoulders starter preset (H&S / OBO) and trigger historical search
  const presetLabels = lang === "tr" ? ["OBO"] : ["H&S"];
  const submitLabels = lang === "tr" ? ["Geçmişte tara"] : ["Scan history"];

  await clickButtonByExactText(client, presetLabels);
  await sleep(300);
  await clickButtonByExactText(client, submitLabels);

  // Wait for search + outcome stats + card chart canvases (1 DrawPad + 1 FanChart + MatchCards)
  await client.waitUntil(
    `document.querySelectorAll('.animate-spin').length === 0 && document.querySelectorAll('canvas').length >= 6`,
    60000,
    350
  );
  // Ensure stats endpoint settled cleanly without 500 alert
  const bodyText = await client.eval(`document.body.innerText`);
  if (
    bodyText.includes("Statistics could not be computed") ||
    bodyText.includes("İstatistik hesaplanamadı")
  ) {
    throw new Error(`Outcome stats failed in UI (${lang})`);
  }

  // Size viewport cleanly to the bottom of the first MatchCard row (3 cards across at >=1536px)
  const measuredBottom = await client.eval(`(() => {
    window.scrollTo(0, 0);
    const grid = Array.from(document.querySelectorAll('div')).find(
      (el) => el.className && typeof el.className === 'string' && el.className.includes('2xl:grid-cols-3') && el.children.length >= 3
    );
    if (!grid) return 1960;
    const rowBottom = Math.max(
      grid.children[0].getBoundingClientRect().bottom,
      grid.children[1].getBoundingClientRect().bottom,
      grid.children[2].getBoundingClientRect().bottom
    );
    return Math.min(2300, Math.ceil(rowBottom + 24));
  })()`);

  await client.call("Emulation.setDeviceMetricsOverride", {
    width,
    height: measuredBottom || 1980,
    deviceScaleFactor: 2,
    mobile: false,
  });

  // Allow Lightweight Charts & FanChart canvases to finish painting after resize
  await sleep(1800);

  await hideNextDevOverlay(client);
  await client.eval(`window.scrollTo(0, 0)`);
  await sleep(250);

  const shot = await client.call("Page.captureScreenshot", { format: "png" });
  const dest = path.join(ASSETS_DIR, outFile);
  fs.writeFileSync(dest, Buffer.from(shot.data, "base64"));
  console.log(`wrote ${dest} (${width}x${measuredBottom})`);
}

async function captureFindings(client, outFile) {
  const width = 1280;
  const height = 960;
  await client.call("Emulation.setDeviceMetricsOverride", {
    width,
    height,
    deviceScaleFactor: 2,
    mobile: false,
  });

  await client.call("Page.navigate", { url: `${UI_ORIGIN}/bulgular` });
  await client.waitUntil(`document.readyState === 'complete'`);
  await client.eval(`window.localStorage.setItem('graphflow.lang', 'en')`);
  await client.call("Page.reload", { ignoreCache: true });
  await client.waitUntil(
    `document.readyState === 'complete' && document.querySelectorAll('.animate-spin').length === 0 && document.querySelectorAll('table tr').length >= 10`,
    30000,
    250
  );
  await sleep(600);
  await hideNextDevOverlay(client);
  await client.eval(`window.scrollTo(0, 0)`);
  await sleep(200);

  const shot = await client.call("Page.captureScreenshot", { format: "png" });
  const dest = path.join(ASSETS_DIR, outFile);
  fs.writeFileSync(dest, Buffer.from(shot.data, "base64"));
  console.log(`wrote ${dest}`);
}

async function main() {
  fs.mkdirSync(ASSETS_DIR, { recursive: true });
  const userDataDir = fs.mkdtempSync(path.join(os.tmpdir(), "graphflow_chrome_"));
  const chrome = spawn(
    "google-chrome-stable",
    [
      "--headless=new",
      "--disable-gpu",
      "--no-sandbox",
      "--hide-scrollbars",
      `--remote-debugging-port=${CDP_PORT}`,
      `--user-data-dir=${userDataDir}`,
      "--window-size=1480,1020",
      "about:blank",
    ],
    { stdio: "ignore" }
  );

  let client;
  try {
    const wsUrl = await waitForCdpTarget();
    client = new CdpClient(wsUrl);
    await client.connect();
    await client.call("Page.enable");
    await client.call("Runtime.enable");

    await captureBacktest(client, "en", "ui-showcase.png");
    await captureBacktest(client, "tr", "ui-showcase-tr.png");
    await captureFindings(client, "ui-findings.png");
  } finally {
    if (client) client.close();
    chrome.kill("SIGKILL");
    fs.rmSync(userDataDir, { recursive: true, force: true });
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
