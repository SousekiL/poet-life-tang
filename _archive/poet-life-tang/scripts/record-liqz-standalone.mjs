#!/usr/bin/env node
/**
 * Combined server + headless recorder for liqz-cinematic.
 * Starts its own static server, opens headless Chromium, records video,
 * waits for `window.__POET_VIZ_DONE__`, converts webm→mp4, cleans up.
 */
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import http from "node:http";
import url from "node:url";

const VIZ_DIR = path.join(process.cwd(), "viz");
const OUT_MOV = path.join(process.cwd(), "output", "liqz.mov");
const MAX_ANIM_S = 900; // 15 min safety
const PORT = 9876;

/* ── Simple static server ── */
const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js":   "text/javascript",
  ".json": "application/json",
  ".css":  "text/css",
  ".png":  "image/png",
  ".svg":  "image/svg+xml",
  ".webp": "image/webp",
};

function serve(req, res) {
  let p = url.parse(req.url).pathname.replace(/\/$/, "/index.html") || "/index.html";
  p = path.join(VIZ_DIR, p);
  if (!p.startsWith(VIZ_DIR)) { res.writeHead(403); res.end(); return; }
  const ext = path.extname(p).toLowerCase();
  fs.readFile(p, (err, data) => {
    if (err) { res.writeHead(404); res.end("404"); return; }
    res.writeHead(200, { "Content-Type": MIME[ext] || "application/octet-stream" });
    res.end(data);
  });
}

const server = http.createServer(serve);
await new Promise((r) => server.listen(PORT, r));
console.log(`Server on :${PORT}`);

/* ── Browser & recording ── */
let chromium;
try {
  ({ chromium } = await import("playwright"));
} catch {
  console.error("Missing playwright. Run: npm install && npx playwright install chromium");
  server.close();
  process.exit(1);
}

const TMP = path.join(process.cwd(), "output", `_liqz-rec-${Date.now()}`);
fs.mkdirSync(TMP, { recursive: true });

const browser = await chromium.launch({
  headless: true,
  args: [
    "--use-gl=angle",
    "--use-angle=swiftshader",
    "--disable-gpu-sandbox",
    "--ignore-gpu-blocklist",
    "--disable-gpu-watchdog",
  ],
});

const ctx = await browser.newContext({
  viewport: { width: 1080, height: 1920 },
  deviceScaleFactor: 2,
  recordVideo: { dir: TMP, size: { width: 1080, height: 1920 } },
});

const page = await ctx.newPage();
page.on("console", (m) => { if (m.type() === "error") console.log("[err]", m.text()); });
page.on("pageerror", (e) => console.log("[page]", e?.message || String(e)));

const PAGE_URL = `http://127.0.0.1:${PORT}/liqz-cinematic.html?video=1&autoplay=1`;
console.log("Opening", PAGE_URL);

try {
  await page.goto(PAGE_URL, { waitUntil: "load", timeout: 120000 });
  console.log("Page loaded, waiting for animation to finish...");
} catch (e) {
  console.error(e.message || e);
  await ctx.close(); await browser.close(); server.close();
  process.exit(1);
}

try {
  await page.waitForFunction(
    () => !!window.__POET_VIZ_DONE__,
    null,
    { timeout: MAX_ANIM_S * 1000, polling: 4000 }
  );
  console.log("✅ Sequence complete!");
} catch {
  console.warn("⚠ Timed out waiting for __POET_VIZ_DONE__");
}

// Extra 6s for final panorama + cleanup
await new Promise((r) => setTimeout(r, 6000));

await ctx.close();
await browser.close();
server.close();

/* ── Find the webm ── */
const webms = fs.readdirSync(TMP).filter((f) => f.endsWith(".webm"));
if (!webms.length) { console.error("❌ No webm found"); process.exit(1); }
const webm = path.join(TMP, webms[0]);

/* ── ffmpeg convert ── */
console.log("Converting to MP4...");
execSync(
  `ffmpeg -y -i ${JSON.stringify(webm)} -c:v libx264 -pix_fmt yuv420p -movflags +faststart -preset fast -crf 20 ${JSON.stringify(OUT_MOV)}`,
  { stdio: "inherit", timeout: 300000 }
);

fs.rmSync(TMP, { recursive: true, force: true });

const st = fs.statSync(OUT_MOV);
console.log(`🎬 Done! ${(st.size / 1024 / 1024).toFixed(1)}MB → ${OUT_MOV}`);
