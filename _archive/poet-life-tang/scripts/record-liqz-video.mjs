#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";

const OUT_DIR = path.join(process.cwd(), "output", `liqz-viz-${Date.now()}`);
const PAGE_URL = "http://127.0.0.1:8765/liqz-cinematic.html?video=1&autoplay=1";
const MAX_WAIT_S = 900; // 15 min safety net

fs.mkdirSync(OUT_DIR, { recursive: true });

let chromium;
try {
  ({ chromium } = await import("playwright"));
} catch {
  console.error("Missing playwright. Run: npm install");
  process.exit(1);
}

const browser = await chromium.launch({
  headless: true,
  args: [
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--disable-gpu-sandbox",
    "--disable-software-rasterizer",
    "--enable-webgl",
    "--ignore-gpu-blocklist",
    "--disable-features=VizDisplayCompositor",
    "--disable-gpu-watchdog",
  ],
});

const context = await browser.newContext({
  viewport: { width: 1080, height: 1920 },
  deviceScaleFactor: 2,
  recordVideo: {
    dir: OUT_DIR,
    size: { width: 1080, height: 1920 },
  },
});

const page = await context.newPage();

page.on("console", (msg) => {
  const t = msg.type();
  if (t === "error" || t === "warning") console.log(`[${t}]`, msg.text());
});
page.on("pageerror", (err) => console.log("[page]", err?.message || String(err)));

try {
  await page.goto(PAGE_URL, { waitUntil: "networkidle", timeout: 120000 });
} catch (e) {
  console.error("Cannot open page:", PAGE_URL);
  console.error(e.message || e);
  await context.close();
  await browser.close();
  process.exit(1);
}

// Wait for the animation to finish
try {
  await page.waitForFunction(
    () => !!window.__POET_VIZ_DONE__,
    null,
    { timeout: MAX_WAIT_S * 1000, polling: 2000 }
  );
  console.log("Animation completed!");
} catch {
  console.warn("Timed out waiting for __POET_VIZ_DONE__");
}

// Extra 5s to catch final panorama
await new Promise((r) => setTimeout(r, 6000));

await context.close();
await browser.close();

const files = fs.readdirSync(OUT_DIR).filter((f) => f.endsWith(".webm"));
if (files.length === 0) {
  console.error("No webm file found in", OUT_DIR);
  process.exit(1);
}

const webm = path.join(OUT_DIR, files[0]);
const mp4 = path.join(process.cwd(), "output", "liqz-final.mov");

console.log("Converting to MP4...");
execSync(
  `ffmpeg -y -i ${JSON.stringify(webm)} -c:v libx264 -pix_fmt yuv420p -movflags +faststart -preset veryslow -crf 18 ${JSON.stringify(mp4)}`,
  { stdio: "inherit", timeout: 300000 }
);

const stat = fs.statSync(mp4);
console.log(`Done! ${(stat.size / 1024 / 1024).toFixed(1)}MB → ${mp4}`);

// Cleanup raw webm
fs.rmSync(OUT_DIR, { recursive: true, force: true });
