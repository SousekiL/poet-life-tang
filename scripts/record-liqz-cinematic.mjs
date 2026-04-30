#!/usr/bin/env node
/**
 * ── 李清照 Cinematic 竖屏录制定制版 ──
 *
 * 方案: A (headed 真 GPU) + C (降分辨率 720×1280)
 * 自包含: 内置 HTTP 静态服务 → Playwright 录制 → ffmpeg 转 MP4
 *
 * 用法:
 *   node scripts/record-liqz-cinematic.mjs
 *
 * 输出: output/liqz-cinematic-{ts}/liqz.mp4
 */

import fs from "node:fs";
import path from "node:path";
import http from "node:http";

/* ── 配置 ── */
const WIDTH = 720;
const HEIGHT = 1280;
const FPS = 24;
const STATIC_DIR = path.resolve(process.cwd(), "viz");
const PAGE_URL = `/liqz-cinematic.html?video=1&autoplay=1`;
const PORT = 18972;

const ts = Date.now();
const OUT_DIR = path.join(process.cwd(), "output", `liqz-cinematic-${ts}`);
fs.mkdirSync(OUT_DIR, { recursive: true });

/* ── 启动内置 HTTP 静态服 ── */
function startServer(dir, port) {
  const mime = { ".html":"text/html", ".js":"application/javascript", ".css":"text/css",
    ".json":"application/json", ".png":"image/png", ".jpg":"image/jpeg",
    ".svg":"image/svg+xml", ".woff2":"font/woff2", ".webm":"video/webm" };
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const url = new URL(req.url, `http://127.0.0.1:${port}`);
      let filePath = path.join(dir, url.pathname === "/" ? "/index.html" : url.pathname);
      try {
        if (!fs.statSync(filePath).isFile()) { res.writeHead(404); res.end(); return; }
      } catch { res.writeHead(404); res.end(); return; }
      const ext = path.extname(filePath).toLowerCase();
      res.writeHead(200, { "Content-Type": mime[ext] || "application/octet-stream" });
      fs.createReadStream(filePath).pipe(res);
    });
    server.listen(port, "127.0.0.1", () => {
      console.log(`静态服启动: http://127.0.0.1:${port}`);
      resolve(server);
    });
  });
}

const server = await startServer(STATIC_DIR, PORT);

/* ── Playwright 录制 ── */
let chromium;
try {
  ({ chromium } = await import("playwright"));
} catch {
  console.error("缺少 playwright。请在仓库根目录执行: npm install");
  server.close();
  process.exit(1);
}

console.log(`视口: ${WIDTH}x${HEIGHT} @ ${FPS}fps`);
console.log(`输出: ${OUT_DIR}`);

const browser = await chromium.launch({
  headless: false,
  args: [
    `--window-size=${Math.round(WIDTH * 0.55)},${Math.round(HEIGHT * 0.55)}`,
    "--disable-gpu-sandbox",
    "--disable-software-rasterizer",
  ],
});

const context = await browser.newContext({
  viewport: { width: WIDTH, height: HEIGHT },
  deviceScaleFactor: 1,
  recordVideo: { dir: OUT_DIR, size: { width: WIDTH, height: HEIGHT } },
});

const page = await context.newPage();

try {
  const fullUrl = `http://127.0.0.1:${PORT}${PAGE_URL}`;
  console.log("打开:", fullUrl);
  await page.goto(fullUrl, { waitUntil: "domcontentloaded", timeout: 120000 });

  /* 等待 MapLibre canvas 就绪 */
  console.log("等待地图就绪...");
  await page.waitForFunction(() => {
    const c = document.querySelector("canvas");
    return c && c.width > 100 && c.height > 100;
  }, { timeout: 120000 }).catch(() => {});

  /* 等待动画完成 (__POET_VIZ_DONE__ 信号) */
  console.log("录制中 (等待 __POET_VIZ_DONE__)...");
  await page.waitForFunction(
    () => window.__POET_VIZ_DONE__ === true,
    null,
    { timeout: 600000, polling: 500 } /* 最多 10 分钟 */
  );
  console.log("动画完成!");

  /* 额外保持几秒让视频收尾 */
  await new Promise(r => setTimeout(r, 3000));
} catch (e) {
  console.error("录制出错:", e.message || e);
}

await context.close();
await browser.close();
server.close();

/* ── 查找录制的 webm ── */
const files = fs.readdirSync(OUT_DIR).filter(f => f.endsWith(".webm"));
const webm = files.length ? path.join(OUT_DIR, files[0]) : null;

if (!webm) {
  console.error("未找到录制的 webm 文件");
  process.exit(1);
}

console.log(`原始 webm: ${webm}`);

/* ── ffmpeg 转 MP4 ── */
const mp4Out = path.join(OUT_DIR, "liqz.mp4");
const { execSync } = await import("node:child_process");

try {
  console.log("转 MP4...");
  execSync(
    `ffmpeg -y -i "${webm}" -c:v libx264 -pix_fmt yuv420p ` +
    `-preset fast -crf 22 -movflags +faststart "${mp4Out}"`,
    { stdio: "inherit" }
  );
  console.log(`✅ 完成: ${mp4Out}`);

  const stat = fs.statSync(mp4Out);
  console.log(`尺寸: ${(stat.size / 1024 / 1024).toFixed(1)} MB`);
} catch {
  console.error("ffmpeg 转换失败，webm 保留在:", webm);
  process.exit(1);
}
