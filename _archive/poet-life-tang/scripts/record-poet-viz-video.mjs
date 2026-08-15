#!/usr/bin/env node
/**
 * 用 Playwright 录制竖屏 MP4（1080×1920）。请先在本机启动静态服，例如：
 *   cd viz && python3 -m http.server 8765
 * 然后安装浏览器内核并录制：
 *   npm install
 *   npx playwright install chromium
 *   npm run record:viz-video -- --seconds 120
 *
 * 默认打开：http://127.0.0.1:8765/index.html?video=1&autoplay=1
 * 输出目录：./output/ （每次运行一个带时间戳的子目录）
 */
import fs from "node:fs";
import path from "node:path";

const DEFAULT_URL = "http://127.0.0.1:8765/index.html?video=1&autoplay=1";

function arg(name, def) {
  const i = process.argv.indexOf(name);
  if (i === -1 || !process.argv[i + 1]) return def;
  return process.argv[i + 1];
}

const seconds = Math.max(5, Math.min(3600, +arg("--seconds", "90") || 90));
const outDir = arg("--out", path.join(process.cwd(), "output", `viz-${Date.now()}`));
const pageUrl = arg("--url", DEFAULT_URL);
const proofName = arg("--proof", "overlay-proof.png");
const waitDone = arg("--wait-done", "0") === "1";

let chromium;
try {
  ({ chromium } = await import("playwright"));
} catch {
  console.error("缺少 playwright。请在仓库根目录执行: npm install");
  process.exit(1);
}

fs.mkdirSync(outDir, { recursive: true });

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
const context = await browser.newContext({
  viewport: { width: 1080, height: 1920 },
  deviceScaleFactor: 1,
  recordVideo: { dir: outDir, size: { width: 1080, height: 1920 } },
});
const page = await context.newPage();

try {
  page.on("console", (msg) => {
    const t = msg.type();
    const txt = msg.text();
    if (t === "warning" || t === "error") console.log(`[console.${t}]`, txt);
  });
  page.on("pageerror", (err) => console.log("[pageerror]", err?.message || String(err)));

  await page.goto(pageUrl, { waitUntil: "domcontentloaded", timeout: 120000 });
  await Promise.race([
    page.waitForSelector(".leaflet-container", { timeout: 90000 }),
    page.waitForSelector("#map canvas", { timeout: 90000 }),
  ]);
} catch (e) {
  console.error("无法打开页面:", pageUrl);
  console.error(e.message || e);
  console.error("\n请先启动: cd viz && python3 -m http.server 8765");
  await context.close();
  await browser.close();
  process.exit(1);
}

await new Promise((r) => setTimeout(r, 3500));

function captureOverlayProof() {
  return (async () => {
    try {
      await page.waitForFunction(() => {
        const deed = document.getElementById("dkPop");
        const poem = document.getElementById("pmCard");
        if (!deed || !poem) return false;
        return deed.classList.contains("show") && poem.classList.contains("visible");
      }, null, { timeout: 120000 });
      const proofPath = path.join(outDir, proofName);
      await page.screenshot({ path: proofPath, fullPage: true });
      console.log("已保存重叠校验截图:", proofPath);
    } catch {
      // Not all pages have both elements visible within 2 min; ignore.
    }
  })();
}

// Fire-and-forget: don't block recording duration on proof capture.
const proofPromise = captureOverlayProof();

if (waitDone) {
  await page.waitForFunction(() => !!window.__POET_VIZ_DONE__, null, { timeout: seconds * 1000 });
} else {
  await new Promise((r) => setTimeout(r, seconds * 1000));
}
await proofPromise;
await context.close();
await browser.close();

const files = fs.readdirSync(outDir).filter((f) => f.endsWith(".webm"));
const webm = files.length ? path.join(outDir, files[0]) : null;
console.log("录制完成:", outDir);
if (webm) {
  console.log("原始文件:", webm);
  console.log(
    "可再用 ffmpeg 转 MP4，例如:\n  ffmpeg -y -i " +
      JSON.stringify(webm) +
      " -c:v libx264 -pix_fmt yuv420p -movflags +faststart out.mp4"
  );
}
