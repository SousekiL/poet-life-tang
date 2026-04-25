/* global L */
(function () {
  const VIZ_VIDEO_EXPORT =
    typeof document !== "undefined" &&
    document.documentElement.classList.contains("viz-video-export");

  const T0 = 618;
  const T1 = 1279;

  /**
   * 播放：`currentY += (dt * speed * span) / PLAYBACK_DIVISOR`（仅 playing 时）
   * 整段时长 ≈ PLAYBACK_DIVISOR / rngSpeed（秒）。rngSpeed=1 时约等于本常数秒。
   * 270 → 年速最慢时全程约 4 分 30 秒（rngSpeed=1）。
   */
  const PLAYBACK_DIVISOR = 270;

  /** 与 rngSpeed 对应：从 T0 播到 T1 的预估秒数（近似，不含结尾渐隐） */
  function playbackEtaSeconds(speed) {
    const s = +speed;
    if (!s || s < 1) return NaN;
    return PLAYBACK_DIVISOR / s;
  }

  function formatPlaybackEta(sec) {
    if (!Number.isFinite(sec) || sec <= 0) return "";
    const rounded = Math.round(sec);
    if (rounded < 60) return `全程约 ${rounded} 秒`;
    const m = Math.floor(rounded / 60);
    const r = rounded % 60;
    if (r === 0) return `全程约 ${m} 分钟`;
    return `全程约 ${m} 分 ${r} 秒`;
  }

  function updateSpeedEta() {
    const el = document.getElementById("speedEta");
    const rng = document.getElementById("rngSpeed");
    if (!el || !rng) return;
    el.textContent = formatPlaybackEta(playbackEtaSeconds(rng.value));
  }

  const CHINA_GEOJSON_URL = "https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json";
  /** 白陆 + 蓝海（无标注、无地形晕渲） */
  const BASEMAP_TILES =
    "https://{s}.basemaps.cartocdn.com/rastertiles/light_nolabels/{z}/{x}/{y}{r}.png";
  /** 略透让海色更统一，中国省界矢量再叠纯白 */
  const BASEMAP_TILE_OPACITY = 0.72;
  const BASEMAP_ATTR = '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; CARTO';
  /** 浅色国界（失败则仅底图） */
  const WORLD_COUNTRIES_URL =
    "https://cdn.jsdelivr.net/gh/nvkelso/natural-earth-vector@v5.1.2/geojson/ne_110m_admin_0_countries.geojson";

  /** 轨迹仅保留最近若干「模拟年」的线段，头淡尾实，滑过即消散 */
  const TRAIL_YEAR_WINDOW = 2.15;
  const VIP_TRAIL_YEAR_WINDOW = 3.4;

  /** 名人轨迹 / 动点 / 图例同色（顺序即图例顺序；下列为生年序） */
  const VIP_PALETTE = [
    ["范仲淹", "#1565c0"],
    ["欧阳修", "#0d47a1"],
    ["苏洵", "#00838f"],
    ["周敦颐", "#2e7d32"],
    ["王安石", "#ef6c00"],
    ["苏轼", "#c62828"],
    ["周邦彦", "#6a1b9a"],
    ["李清照", "#ad1457"],
    ["岳飞", "#1b5e20"],
    ["陆游", "#283593"],
    ["朱熹", "#5d4037"],
    ["辛弃疾", "#e65100"],
    ["文天祥", "#37474f"],
    ["陆秀夫", "#01579b"],
  ];
  const VIP_COLOR_BY_NAME = new Map(VIP_PALETTE);
  const VIP_POETS = new Set(VIP_COLOR_BY_NAME.keys());

  const TRAIL_COLOR = "#bdbdbd";
  const MOVER_FILL_SUBTLE = "#cfd8dc";
  const MOVER_STROKE_SUBTLE = "#eceff1";

  /** 播放到末年后白幕渐隐时长（毫秒） */
  /** 结尾雾感渐隐略拉长，更易体会「朦胧消散」 */
  const OUTRO_MS = 7800;
  /** 名人出生/卒地说明在地图上停留时长（毫秒） */
  const VIP_CAPTION_MS = 5600;
  /** 同年多位 VIP 右侧卡片错开间隔（毫秒），仅延迟 DOM 不动画年份 */
  const VIP_CAPTION_STAGGER_MS = 120;

  /** 地图红/蓝脉冲点图例：淡出动画（毫秒）；完整展示时长在 startMarkerDotGuide 内取 4.8–6.8 秒随机 */
  const MARKER_DOT_GUIDE_FADE_MS = 420;
  /** 播放开场标题停留时长：3.2–4.4 秒随机；淡出时长固定 */
  const INTRO_TITLE_FADE_MS = 420;
  /** 结尾制作信息从后段开始浮现 */
  const OUTRO_CREDITS_START = 0.56;
  const OUTRO_CREDITS_PEAK_OPACITY = 0.88;
  let markerGuideTimerFade = 0;
  let markerGuideTimerRemove = 0;
  let introTitleTimerFade = 0;
  let introTitleTimerRemove = 0;

  /** 分时段重点城市（label 为当时常用地名，浅色 tooltip） */
  const CITY_ERAS = [
    {
      from: 618,
      to: 650,
      cities: [
        { name: "长安·大兴城", lat: 34.27, lng: 108.95 },
        { name: "洛阳", lat: 34.62, lng: 112.45 },
        { name: "晋阳", lat: 37.87, lng: 112.55 },
        { name: "江都", lat: 32.4, lng: 119.45 },
      ],
    },
    {
      from: 650,
      to: 712,
      cities: [
        { name: "长安", lat: 34.27, lng: 108.95 },
        { name: "洛阳", lat: 34.62, lng: 112.45 },
        { name: "幽州", lat: 39.9, lng: 116.4 },
        { name: "益州", lat: 30.67, lng: 104.07 },
        { name: "凉州", lat: 37.93, lng: 102.64 },
      ],
    },
    {
      from: 712,
      to: 756,
      cities: [
        { name: "长安", lat: 34.27, lng: 108.95 },
        { name: "洛阳", lat: 34.62, lng: 112.45 },
        { name: "扬州", lat: 32.4, lng: 119.45 },
        { name: "广州", lat: 23.13, lng: 113.27 },
        { name: "益州", lat: 30.67, lng: 104.07 },
        { name: "洪州", lat: 28.68, lng: 115.88 },
      ],
    },
    {
      from: 756,
      to: 820,
      cities: [
        { name: "长安", lat: 34.27, lng: 108.95 },
        { name: "凤翔", lat: 34.52, lng: 107.38 },
        { name: "洛阳", lat: 34.62, lng: 112.45 },
        { name: "襄阳", lat: 32.04, lng: 112.12 },
        { name: "江陵", lat: 30.33, lng: 112.2 },
        { name: "金陵", lat: 32.05, lng: 118.78 },
      ],
    },
    {
      from: 820,
      to: 860,
      cities: [
        { name: "长安", lat: 34.27, lng: 108.95 },
        { name: "洛阳", lat: 34.62, lng: 112.45 },
        { name: "扬州", lat: 32.4, lng: 119.45 },
        { name: "杭州", lat: 30.25, lng: 120.17 },
        { name: "越州", lat: 30.0, lng: 120.58 },
      ],
    },
    {
      from: 860,
      to: 908,
      cities: [
        { name: "长安", lat: 34.27, lng: 108.95 },
        { name: "洛阳", lat: 34.62, lng: 112.45 },
        { name: "汴州", lat: 34.8, lng: 114.35 },
        { name: "扬州", lat: 32.4, lng: 119.45 },
        { name: "成都", lat: 30.67, lng: 104.07 },
      ],
    },
    {
      from: 908,
      to: 960,
      cities: [
        { name: "开封", lat: 34.8, lng: 114.35 },
        { name: "洛阳", lat: 34.62, lng: 112.45 },
        { name: "扬州", lat: 32.4, lng: 119.45 },
        { name: "太原", lat: 37.87, lng: 112.55 },
        { name: "金陵", lat: 32.05, lng: 118.78 },
      ],
    },
    {
      from: 960,
      to: 1127,
      cities: [
        { name: "东京开封", lat: 34.8, lng: 114.35 },
        { name: "洛阳", lat: 34.62, lng: 112.45 },
        { name: "大名", lat: 36.28, lng: 115.15 },
        { name: "杭州", lat: 30.25, lng: 120.17 },
        { name: "升州", lat: 32.05, lng: 118.78 },
      ],
    },
    {
      from: 1127,
      to: 1280,
      cities: [
        { name: "临安", lat: 30.25, lng: 120.17 },
        { name: "建康", lat: 32.05, lng: 118.78 },
        { name: "平江府", lat: 31.3, lng: 120.62 },
        { name: "福州", lat: 26.08, lng: 119.3 },
        { name: "赣州", lat: 25.83, lng: 114.93 },
      ],
    },
  ];

  /** 用户选定的大事记文本（保持原文） */
  const HIST_EVENTS = [
    { year: 618, text: "618年 李渊称帝，建立唐朝" },
    { year: 622, text: "622年 初唐完成统一" },
    { year: 626, text: "626年 玄武门之变，李世民即位" },
    { year: 640, text: "640年 文成公主入藏，唐蕃和亲" },
    { year: 660, text: "660年 唐灭百济" },
    { year: 683, text: "683年 徐敬业起兵反武" },
    { year: 690, text: "690年 武则天登基，改国号为周" },
    { year: 705, text: "705年 神龙政变，中宗复位" },
    { year: 713, text: "713年 唐玄宗亲政" },
    { year: 730, text: "730年 开元盛世" },
    { year: 755, text: "755年 安禄山起兵，安史之乱爆发" },
    { year: 783, text: "783年 泾原兵变" },
    { year: 787, text: "787年 平凉劫盟，唐蕃关系破裂" },
    { year: 805, text: "805年 永贞革新" },
    { year: 845, text: "845年 会昌法难，唐武宗灭佛" },
    { year: 878, text: "878年 黄巢起义" },
    { year: 907, text: "907年 朱温篡唐，唐朝灭亡" },
    { year: 960, text: "960年 陈桥兵变，赵匡胤建宋" },
    { year: 975, text: "975年 宋师平南唐，李煜降" },
    { year: 979, text: "979年 宋灭北汉，五代分裂结束" },
    { year: 1004, text: "1004年 澶渊之盟，宋辽休战" },
    {
      year: 1038,
      text: "1038年 元昊于兴庆府（今宁夏银川一带）称帝，国号大夏，史称西夏",
    },
    { year: 1043, text: "1043年 庆历新政起" },
    { year: 1067, text: "1067年 宋神宗即位" },
    { year: 1069, text: "1069年 熙宁变法，王安石主政" },
    { year: 1085, text: "1085年 元祐更化，反新法派抬头" },
    { year: 1120, text: "1120年 方腊起义" },
    { year: 1122, text: "1122年 宋金海上之盟" },
    { year: 1125, text: "1125年 金军南下，徽宗传位钦宗" },
    { year: 1127, text: "1127年 靖康之变，北宋亡，高宗南渡" },
    { year: 1129, text: "1129年 高宗驻跸东南，行在渐定于临安一带" },
    { year: 1141, text: "1141年 绍兴和议，宋金对峙固化" },
    { year: 1161, text: "1161年 采石之战，挫败完颜亮南侵" },
    { year: 1194, text: "1194年 庆元党禁" },
    { year: 1206, text: "1206年 开禧北伐" },
    { year: 1234, text: "1234年 宋蒙灭金" },
    { year: 1259, text: "1259年 蒙哥攻蜀，战于钓鱼城" },
    { year: 1273, text: "1273年 襄樊陷落" },
    { year: 1276, text: "1276年 元军入临安，谢太后降" },
    { year: 1279, text: "1279年 崖山海战，南宋亡" },
  ];

  function isVipName(name) {
    return VIP_POETS.has(name);
  }

  function vipColor(name) {
    return VIP_COLOR_BY_NAME.get(name) || "#37474f";
  }

  function mixVipHex(name, grayR, grayG, grayB, t) {
    const c = vipColor(name);
    const h = c.replace("#", "");
    const r = parseInt(h.slice(0, 2), 16);
    const g = parseInt(h.slice(2, 4), 16);
    const b = parseInt(h.slice(4, 6), 16);
    const mix = (a, b0) => Math.round(a + (b0 - a) * t);
    const toHex = (x) => Math.max(0, Math.min(255, x)).toString(16).padStart(2, "0");
    return `#${toHex(mix(r, grayR))}${toHex(mix(g, grayG))}${toHex(mix(b, grayB))}`;
  }

  /** 地图上名人动点：明显降饱和，弱化存在感 */
  function vipMoverFill(name) {
    return mixVipHex(name, 236, 239, 241, 0.62);
  }

  /** VIP 轨迹线：略降饱和，仍能与灰底普通轨迹区分 */
  function vipTrailColor(name) {
    return mixVipHex(name, 232, 234, 240, 0.38);
  }

  function cityEraIndex(Y) {
    for (let i = 0; i < CITY_ERAS.length; i++) {
      const e = CITY_ERAS[i];
      if (Y >= e.from && Y < e.to) return i;
    }
    return CITY_ERAS.length - 1;
  }

  /** 都城长安：单独常驻，与时段层叠区分开 */
  const CHANGAN_CENTER = { lat: 34.27, lng: 108.95, label: "长安" };

  function isChanganCity(c) {
    if (/^长安/.test(c.name)) return true;
    const dlat = Math.abs(c.lat - CHANGAN_CENTER.lat);
    const dlng = Math.abs(c.lng - CHANGAN_CENTER.lng);
    return dlat < 0.08 && dlng < 0.15;
  }

  function easeInOutCubic(t) {
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  }

  function hashStr(s) {
    let h = 0;
    for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
    return Math.abs(h);
  }

  function posAtYear(poet, Y) {
    const wps = poet.waypoints;
    if (!wps || !wps.length) {
      if (poet.birth && poet.birth.lat != null) {
        return { lat: poet.birth.lat, lng: poet.birth.lng };
      }
      return { lat: 34.5, lng: 108.5 };
    }
    if (Y <= wps[0].yearStart) {
      return { lat: wps[0].lat, lng: wps[0].lng };
    }
    const last = wps[wps.length - 1];
    if (Y >= last.yearEnd) {
      return { lat: last.lat, lng: last.lng };
    }
    for (let i = 0; i < wps.length; i++) {
      const w = wps[i];
      if (Y >= w.yearStart && Y <= w.yearEnd) {
        return { lat: w.lat, lng: w.lng };
      }
    }
    for (let i = 0; i < wps.length - 1; i++) {
      const a = wps[i];
      const b = wps[i + 1];
      if (Y > a.yearEnd && Y < b.yearStart) {
        const t0 = a.yearEnd;
        const t1 = b.yearStart;
        let u = (Y - t0) / (t1 - t0);
        u = easeInOutCubic(Math.min(1, Math.max(0, u)));
        return {
          lat: a.lat + (b.lat - a.lat) * u,
          lng: a.lng + (b.lng - a.lng) * u,
        };
      }
    }
    let best = wps[0];
    let bestd = Math.abs(Y - (best.yearStart + best.yearEnd) / 2);
    for (const w of wps) {
      const c = (w.yearStart + w.yearEnd) / 2;
      const d = Math.abs(Y - c);
      if (d < bestd) {
        bestd = d;
        best = w;
      }
    }
    return { lat: best.lat, lng: best.lng };
  }

  function buildSmoothedPath(poet, stepYears) {
    const pts = [];
    const y0 = poet.birthYear;
    const y1 = poet.deathYear;
    for (let y = y0; y <= y1 + 1e-9; y += stepYears) {
      const p = posAtYear(poet, y);
      pts.push({ y, lat: p.lat, lng: p.lng });
    }
    if (pts.length < 5) return pts;
    return pts.map((row, i) => {
      const i0 = Math.max(0, i - 1);
      const i2 = Math.min(pts.length - 1, i + 1);
      const a = pts[i0];
      const b = row;
      const c = pts[i2];
      return {
        y: b.y,
        lat: (a.lat + b.lat + c.lat) / 3,
        lng: (a.lng + b.lng + c.lng) / 3,
      };
    });
  }

  function buildEventsByYear(events) {
    const m = new Map();
    for (const ev of events) {
      const y = ev.year;
      if (!m.has(y)) m.set(y, []);
      m.get(y).push(ev);
    }
    for (const [, arr] of m) {
      arr.sort((a, b) => {
        if (a.kind !== b.kind) return a.kind === "birth" ? -1 : 1;
        return (a.poet_id || "").localeCompare(b.poet_id || "");
      });
    }
    return m;
  }

  function pulseParams(kind, prefixCount, emphasis) {
    const em = emphasis / 100;
    const n = Math.max(1, prefixCount || 1);
    const logn = Math.log(1 + n);
    if (kind === "birth") {
      return {
        durationMs: (380 + 340 * logn) * em,
        peakR: (9 + Math.min(38, 6.2 * logn)) * em,
        peakOpacity: Math.min(0.995, 0.68 + 0.14 * logn),
        fadeOpacity: Math.max(0.04, 0.16 - 0.01 * n),
      };
    }
    return {
      durationMs: (340 + 240 * logn) * em,
      peakR: (8 + Math.min(34, 5.4 * logn)) * em,
      peakOpacity: Math.min(0.99, 0.62 + 0.13 * logn),
      fadeOpacity: Math.max(0.045, 0.15 - 0.009 * n),
    };
  }

  const state = {
    data: null,
    map: null,
    tileLayer: null,
    worldLayer: null,
    chinaLayer: null,
    cityLayer: null,
    changanLayer: null,
    trailsLayer: null,
    vipTrailsLayer: null,
    moversLayer: null,
    pulseLayer: null,
    /** Hartwell 朝代外轮廓（按年切换）；无数据或未加载时为 null */
    dynastyLayer: null,
    dynastyBundle: null,
    /** 当前已渲染的 snapshot id，避免每帧重复建层 */
    dynastySnapshotId: null,
    poetMarkers: new Map(),
    trailSegs: new Map(),
    vipTrailSegs: new Map(),
    pathCache: new Map(),
    cityEraIndex: -1,
    outroActive: false,
    outroT0: 0,
    shouldStartOutro: false,
    pulses: [],
    currentY: T0,
    lastFiredYear: T0 - 2,
    playing: false,
    introActive: false,
    lastTs: 0,
    raf: 0,
    eventsByYear: new Map(),
    vipCaptionFired: new Set(),
    vipCaptionTimers: new Map(),
  };

  function clearSegGroup(segMap, layer, id) {
    const arr = segMap.get(id);
    if (!arr) return;
    arr.forEach((ln) => layer.removeLayer(ln));
    segMap.delete(id);
  }

  function clearAllTrailSegs() {
    state.trailSegs.forEach((arr, id) => {
      arr.forEach((ln) => state.trailsLayer.removeLayer(ln));
    });
    state.trailSegs.clear();
    state.vipTrailSegs.forEach((arr, id) => {
      arr.forEach((ln) => state.vipTrailsLayer.removeLayer(ln));
    });
    state.vipTrailSegs.clear();
  }

  /** 滑动年窗 + 分段透明度：近「当前年」一侧更实，早段渐隐 */
  function updateFadingTrail(Y, p, layer, segMap, isVip) {
    const path = state.pathCache.get(p.id);
    if (!path || !path.length || Y < p.birthYear) {
      clearSegGroup(segMap, layer, p.id);
      return;
    }
    const W = isVip ? VIP_TRAIL_YEAR_WINDOW : TRAIL_YEAR_WINDOW;
    const yLo = Y - W;
    const pts = path.filter((pt) => pt.y <= Y && pt.y >= yLo);
    if (pts.length < 2) {
      clearSegGroup(segMap, layer, p.id);
      return;
    }
    clearSegGroup(segMap, layer, p.id);
    const color = isVip ? vipTrailColor(p.name) : TRAIL_COLOR;
    const weight = isVip ? 2.5 : 2.1;
    const segs = [];
    for (let i = 0; i < pts.length - 1; i++) {
      const mid = (pts[i].y + pts[i + 1].y) / 2;
      let u = (mid - yLo) / W;
      u = Math.max(0, Math.min(1, u));
      const op = isVip ? 0.05 + 0.48 * Math.pow(u, 1.4) : 0.06 + 0.58 * Math.pow(u, 1.4);
      const ln = L.polyline(
        [
          [pts[i].lat, pts[i].lng],
          [pts[i + 1].lat, pts[i + 1].lng],
        ],
        {
          color,
          opacity: op,
          weight,
          lineCap: "round",
          lineJoin: "round",
          smoothFactor: 1.12,
        }
      ).addTo(layer);
      segs.push(ln);
    }
    segMap.set(p.id, segs);
  }

  function updateTrails(Y) {
    for (const p of state.data.poets) {
      if (isVipName(p.name)) continue;
      updateFadingTrail(Y, p, state.trailsLayer, state.trailSegs, false);
    }
    for (const p of state.data.poets) {
      if (!isVipName(p.name)) continue;
      updateFadingTrail(Y, p, state.vipTrailsLayer, state.vipTrailSegs, true);
    }
  }

  function spawnPulse(ev, emphasis, staggerMs) {
    const kind = ev.kind;
    const col = kind === "birth" ? "#d32f2f" : "#1565c0";
    const fillCol = kind === "birth" ? "#ff5252" : "#2196f3";
    const vipEv = ev.name && isVipName(ev.name);
    const p0 = pulseParams(kind, ev.prefix_count || 1, emphasis);
    const p = vipEv
      ? {
          durationMs: p0.durationMs * 1.22,
          peakR: p0.peakR * 1.18,
          peakOpacity: Math.min(0.995, p0.peakOpacity + 0.04),
          fadeOpacity: p0.fadeOpacity,
        }
      : p0;
    const delay = (hashStr(ev.poet_id || ev.name || "") % 40) * (staggerMs / 40);
    const start = performance.now() + delay;
    const mk = L.circleMarker([ev.lat, ev.lng], {
      radius: 4,
      color: col,
      weight: 2.6,
      fillColor: fillCol,
      fillOpacity: 0.32,
      opacity: 0.9,
    }).addTo(state.pulseLayer);
    state.pulses.push({
      mk,
      start,
      duration: p.durationMs,
      peakR: p.peakR,
      peakOpacity: p.peakOpacity,
      fadeOpacity: p.fadeOpacity,
    });
  }

  function fireYearEvents(y, emphasis, staggerMs) {
    const list = state.eventsByYear.get(y) || [];
    for (const ev of list) {
      spawnPulse(ev, emphasis, staggerMs);
    }
  }

  function fireEventsUpTo(yInt, emphasis, staggerMs) {
    if (yInt <= state.lastFiredYear) return;
    for (let y = state.lastFiredYear + 1; y <= yInt; y++) {
      fireYearEvents(y, emphasis, staggerMs);
      maybeVipMilestoneCaptions(y);
    }
    state.lastFiredYear = yInt;
  }

  function cleanPlaceLabel(s) {
    return String(s || "")
      .replace(/\s*\(出生地\)\s*/g, "")
      .replace(/\s+/g, " ")
      .trim() || "某地";
  }

  function startMarkerDotGuide() {
    const el = document.getElementById("markerDotGuide");
    if (!el) return;
    clearTimeout(markerGuideTimerFade);
    clearTimeout(markerGuideTimerRemove);
    el.classList.remove("marker-dot-guide--gone");
    el.removeAttribute("hidden");
    const holdMs = 4800 + Math.floor(Math.random() * 2001);
    markerGuideTimerFade = window.setTimeout(() => {
      if (!el.isConnected) return;
      el.classList.add("marker-dot-guide--gone");
    }, holdMs);
    markerGuideTimerRemove = window.setTimeout(() => {
      if (!el.isConnected) return;
      el.setAttribute("hidden", "");
    }, holdMs + MARKER_DOT_GUIDE_FADE_MS);
  }

  function hideMarkerDotGuideImmediately() {
    clearTimeout(markerGuideTimerFade);
    clearTimeout(markerGuideTimerRemove);
    const el = document.getElementById("markerDotGuide");
    if (!el) return;
    el.classList.remove("marker-dot-guide--gone");
    el.setAttribute("hidden", "");
  }

  function startIntroTitleCard(onDone) {
    const el = document.getElementById("introTitleCard");
    const creditsEl = document.getElementById("introCredits");
    if (!el) {
      onDone();
      return;
    }
    clearTimeout(introTitleTimerFade);
    clearTimeout(introTitleTimerRemove);
    el.classList.remove("intro-title-card--gone");
    el.removeAttribute("hidden");
    if (creditsEl) {
      creditsEl.classList.remove("intro-credits--gone");
      creditsEl.removeAttribute("hidden");
    }
    const holdMs = 3200 + Math.floor(Math.random() * 1201);
    introTitleTimerFade = window.setTimeout(() => {
      if (!el.isConnected) return;
      el.classList.add("intro-title-card--gone");
      if (creditsEl && creditsEl.isConnected) creditsEl.classList.add("intro-credits--gone");
    }, holdMs);
    introTitleTimerRemove = window.setTimeout(() => {
      if (!el.isConnected) return;
      el.setAttribute("hidden", "");
      if (creditsEl && creditsEl.isConnected) creditsEl.setAttribute("hidden", "");
      onDone();
    }, holdMs + INTRO_TITLE_FADE_MS);
  }

  function hideIntroTitleCardImmediately() {
    clearTimeout(introTitleTimerFade);
    clearTimeout(introTitleTimerRemove);
    const el = document.getElementById("introTitleCard");
    const creditsEl = document.getElementById("introCredits");
    if (!el) return;
    el.classList.remove("intro-title-card--gone");
    el.setAttribute("hidden", "");
    if (creditsEl) {
      creditsEl.classList.remove("intro-credits--gone");
      creditsEl.setAttribute("hidden", "");
    }
  }

  function startPlayPrelude() {
    state.introActive = true;
    state.playing = false;
    state.lastTs = 0;
    setTimeUiVisible(false);
    document.getElementById("btnPlay").textContent = "暂停";
    hideMarkerDotGuideImmediately();
    startIntroTitleCard(() => {
      if (!state.introActive) return;
      startMarkerDotGuide();
      state.introActive = false;
      state.playing = true;
      setTimeUiVisible(true);
      state.lastTs = 0;
      document.getElementById("btnPlay").textContent = "暂停";
    });
  }

  function cancelPlayPrelude() {
    state.introActive = false;
    hideIntroTitleCardImmediately();
    hideMarkerDotGuideImmediately();
    document.getElementById("btnPlay").textContent = "播放";
  }

  function vipCaptionTimerKey(name, zone) {
    return `${name}:${zone}`;
  }

  function vipPaletteOrderIndex(name) {
    const i = VIP_PALETTE.findIndex(([n]) => n === name);
    return i === -1 ? 9999 : i;
  }

  function forEachVipDockRoot(fn) {
    ["vipDockBirth", "vipDockDeath"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) fn(el, id);
    });
  }

  function ensureVipDockSlots() {
    function mountSlots(container) {
      if (!container || container.children.length > 0) return;
      const n = VIP_PALETTE.length;
      VIP_PALETTE.forEach(([name], i) => {
        const slot = document.createElement("div");
        slot.className = "vip-dock-slot";
        const topPct = n <= 1 ? 50 : 8 + (i * 84) / Math.max(1, n - 1);
        slot.style.top = `${topPct.toFixed(2)}%`;
        slot.dataset.vipName = name;
        container.appendChild(slot);
      });
    }
    mountSlots(document.getElementById("vipDockBirth"));
    mountSlots(document.getElementById("vipDockDeath"));
  }

  function pushVipDockCard(name, accent, lineMain, zone) {
    const rootId = zone === "death" ? "vipDockDeath" : "vipDockBirth";
    const dock = document.getElementById(rootId);
    if (!dock) return;
    const slot = dock.querySelector(`[data-vip-name="${name}"]`);
    if (!slot) return;

    const tkey = vipCaptionTimerKey(name, zone);
    const oldTimer = state.vipCaptionTimers.get(tkey);
    if (oldTimer) clearTimeout(oldTimer);
    const oldCard = slot.querySelector(".vip-dock-card");
    if (oldCard) oldCard.remove();

    const card = document.createElement("div");
    card.className = "vip-dock-card";
    card.style.borderLeft = `4px solid ${accent}`;
    const nm = document.createElement("div");
    nm.className = "vip-cap-name";
    nm.textContent = name;
    const l1 = document.createElement("div");
    l1.className = "vip-cap-line";
    l1.textContent = lineMain;
    card.appendChild(nm);
    card.appendChild(l1);
    slot.appendChild(card);
    requestAnimationFrame(() => {
      card.classList.add("vip-dock-card--in");
    });
    const timer = setTimeout(() => {
      card.classList.remove("vip-dock-card--in");
      card.classList.add("vip-dock-card--out");
      setTimeout(() => card.remove(), 520);
      state.vipCaptionTimers.delete(tkey);
    }, VIP_CAPTION_MS);
    state.vipCaptionTimers.set(tkey, timer);
  }

  function maybeVipMilestoneCaptions(y) {
    if (!state.data) return;
    const items = [];
    for (const p of state.data.poets) {
      if (!isVipName(p.name)) continue;
      const col = vipColor(p.name);
      const ord = vipPaletteOrderIndex(p.name);
      if (y === p.birthYear) {
        const key = `${p.id}-birth`;
        if (state.vipCaptionFired.has(key)) continue;
        state.vipCaptionFired.add(key);
        const pl = p.birth && p.birth.place ? cleanPlaceLabel(p.birth.place) : "某地";
        items.push({
          sort: ord * 2,
          name: p.name,
          col,
          zone: "birth",
          line: `${p.name}于${p.birthYear}年在${pl}出生`,
        });
      }
      if (y === p.deathYear) {
        const key2 = `${p.id}-death`;
        if (state.vipCaptionFired.has(key2)) continue;
        state.vipCaptionFired.add(key2);
        const pl2 = p.death && p.death.place ? cleanPlaceLabel(p.death.place) : "卒地未载";
        items.push({
          sort: ord * 2 + 1,
          name: p.name,
          col,
          zone: "death",
          line: `${p.name}于${p.deathYear}年在${pl2}卒`,
        });
      }
    }
    items.sort((a, b) => a.sort - b.sort);
    items.forEach((it, i) => {
      window.setTimeout(() => {
        pushVipDockCard(it.name, it.col, it.line, it.zone);
      }, i * VIP_CAPTION_STAGGER_MS);
    });
  }

  function clearAllVipCaptions() {
    forEachVipDockRoot((dock) => {
      dock.querySelectorAll(".vip-dock-card").forEach((n) => n.remove());
    });
    state.vipCaptionTimers.forEach((t) => clearTimeout(t));
    state.vipCaptionTimers.clear();
  }

  function tickPulses(now) {
    const keep = [];
    for (const p of state.pulses) {
      const t = (now - p.start) / p.duration;
      if (t <= 0) {
        keep.push(p);
        continue;
      }
      if (t >= 1) {
        state.pulseLayer.removeLayer(p.mk);
        continue;
      }
      const wave = Math.sin(Math.PI * t);
      const r = 4 + (p.peakR - 4) * wave;
      const op = p.fadeOpacity + (p.peakOpacity - p.fadeOpacity) * wave;
      p.mk.setRadius(r);
      p.mk.setStyle({
        fillOpacity: Math.min(0.98, op * 1.02 + 0.14 * wave),
        opacity: Math.min(1, op + 0.42 * wave),
        weight: 2.2 + 1.35 * wave,
      });
      keep.push(p);
    }
    state.pulses = keep;
  }

  function pickMovers(alive, maxPoets) {
    if (alive.length <= maxPoets) return alive;
    const vips = alive.filter((p) => isVipName(p.name));
    if (vips.length >= maxPoets) return vips.slice(0, maxPoets);
    const rest = alive.filter((p) => !isVipName(p.name));
    const restCap = Math.max(0, maxPoets - vips.length);
    const step = Math.max(1, Math.ceil(rest.length / Math.max(1, restCap)));
    const pickedRest = rest.filter((_, i) => i % step === 0);
    const seen = new Set(vips.map((x) => x.id));
    const out = [...vips];
    for (const p of pickedRest) {
      if (seen.has(p.id)) continue;
      seen.add(p.id);
      out.push(p);
      if (out.length >= maxPoets) break;
    }
    return out;
  }

  function updateMovers(Y, maxPoets) {
    state.moversLayer.clearLayers();
    const alive = state.data.poets.filter((p) => Y >= p.birthYear && Y <= p.deathYear);
    const list = pickMovers(alive, maxPoets);
    for (const p of list) {
      const { lat, lng } = posAtYear(p, Y);
      let mk = state.poetMarkers.get(p.id);
      const vip = isVipName(p.name);
      const radius = vip ? 4.1 : 2.9;
      const weight = vip ? 1.25 : 0.75;
      const fillCol = vip ? vipMoverFill(p.name) : MOVER_FILL_SUBTLE;
      const strokeCol = vip ? "#cfd8dc" : MOVER_STROKE_SUBTLE;
      const fillOp = vip ? 0.66 : 0.32;
      if (!mk) {
        mk = L.circleMarker([lat, lng], {
          radius,
          color: strokeCol,
          weight,
          fillColor: fillCol,
          fillOpacity: fillOp,
        });
        state.poetMarkers.set(p.id, mk);
      } else {
        mk.setLatLng([lat, lng]);
        mk.setStyle({
          radius,
          color: strokeCol,
          weight,
          fillColor: fillCol,
          fillOpacity: fillOp,
        });
      }
      mk.addTo(state.moversLayer);
    }
  }

  function addPermanentChangan() {
    if (state.changanLayer) return;
    state.changanLayer = L.layerGroup().addTo(state.map);
    const mk = L.circleMarker([CHANGAN_CENTER.lat, CHANGAN_CENTER.lng], {
      radius: 4.2,
      color: "#b0bec5",
      weight: 1.1,
      fillColor: "#f5f5f5",
      fillOpacity: 0.96,
      opacity: 0.98,
    }).addTo(state.changanLayer);
    mk.bindTooltip(CHANGAN_CENTER.label, {
      permanent: true,
      direction: "top",
      offset: [0, -5],
      className: "city-lbl city-lbl--changan",
    });
  }

  function updateKeyCities(Y) {
    if (!state.cityLayer) return;
    const idx = cityEraIndex(Y);
    if (idx === state.cityEraIndex && state.cityLayer.getLayers().length > 0) return;
    state.cityEraIndex = idx;
    state.cityLayer.clearLayers();
    const era = CITY_ERAS[idx];
    for (const c of era.cities) {
      if (isChanganCity(c)) continue;
      const mk = L.circleMarker([c.lat, c.lng], {
        radius: 3.6,
        color: "#cfd8dc",
        weight: 1,
        fillColor: "#eceff1",
        fillOpacity: 0.9,
        opacity: 0.92,
      }).addTo(state.cityLayer);
      mk.bindTooltip(c.name, {
        permanent: true,
        direction: "top",
        offset: [0, -4],
        className: "city-lbl",
      });
    }
  }

  function updateHistHud(Y) {
    const el = document.getElementById("histHud");
    if (!el) return;
    const yf = Math.floor(Y);
    const chip = `<div class="hist-year-chip">${yf}年</div>`;
    let cur = null;
    for (const ev of HIST_EVENTS) {
      if (ev.year <= yf) cur = ev;
    }
    if (!cur) {
      el.innerHTML = `${chip}<div class="hist-event-body"><span class="hist-placeholder">大事记随年推进</span></div>`;
      return;
    }
    el.innerHTML = `${chip}<div class="hist-event-body"><strong>${cur.text}</strong></div>`;
  }

  function setTimeUiVisible(visible) {
    const year = document.getElementById("yearLabel");
    const hud = document.getElementById("histHud");
    if (year) {
      year.style.opacity = visible ? "1" : "0";
      year.style.transition = "opacity 0.28s ease";
    }
    if (hud) hud.style.opacity = visible ? "1" : "0";
  }

  function resetOutroVisual() {
    const cover = document.getElementById("mapOutroCover");
    const mist = document.getElementById("mapOutroMist");
    const hud = document.getElementById("histHud");
    const credits = document.getElementById("outroCredits");
    const mapc = state.map && state.map.getContainer();
    if (cover) cover.style.opacity = "0";
    if (mist) {
      mist.style.opacity = "0";
      mist.style.backdropFilter = "blur(0px)";
      mist.style.webkitBackdropFilter = "blur(0px)";
    }
    if (hud) hud.style.opacity = "1";
    forEachVipDockRoot((dock) => {
      dock.style.opacity = "1";
    });
    if (credits) credits.style.opacity = "0";
    if (mapc) {
      mapc.style.filter = "";
      mapc.style.opacity = "";
    }
    const stage = document.getElementById("mapStage");
    if (stage) stage.classList.remove("map-stage--outro");
    state.outroActive = false;
    state.shouldStartOutro = false;
  }

  function tickOutro(ts) {
    const cover = document.getElementById("mapOutroCover");
    const mist = document.getElementById("mapOutroMist");
    const hud = document.getElementById("histHud");
    const credits = document.getElementById("outroCredits");
    const mapc = state.map && state.map.getContainer();
    const stage = document.getElementById("mapStage");
    if (!state.outroActive || !cover) return;
    const t = Math.min(1, (ts - state.outroT0) / OUTRO_MS);
    if (stage) stage.classList.add("map-stage--outro");
    const soft = t * t * (3 - 2 * t);
    const easeOut = 1 - Math.pow(1 - t, 2.35);
    if (mapc) {
      const blur = 2.5 + 11 * easeOut;
      const sat = 1 - 0.42 * easeOut;
      const br = 1 - 0.18 * easeOut;
      mapc.style.filter = `blur(${blur}px) saturate(${sat}) brightness(${br})`;
      mapc.style.opacity = String(1 - 0.14 * easeOut);
    }
    if (mist) {
      mist.style.opacity = String(0.12 + 0.68 * soft);
      const mb = 10 * soft;
      mist.style.backdropFilter = `blur(${mb}px)`;
      mist.style.webkitBackdropFilter = `blur(${mb}px)`;
    }
    cover.style.opacity = String(0.08 + 0.82 * Math.pow(t, 1.25));
    if (hud) hud.style.opacity = String(1 - 0.88 * soft);
    forEachVipDockRoot((dock) => {
      dock.style.opacity = String(1 - 0.9 * soft);
    });
    if (credits) {
      const u = Math.max(0, Math.min(1, (t - OUTRO_CREDITS_START) / (1 - OUTRO_CREDITS_START)));
      const e = u * u * (3 - 2 * u);
      credits.style.opacity = String(OUTRO_CREDITS_PEAK_OPACITY * e);
    }
    if (t >= 1) state.outroActive = false;
  }

  function frame(ts) {
    const speed = +document.getElementById("rngSpeed").value;
    const emphasis = +document.getElementById("rngEmphasis").value;
    const maxPoets = +document.getElementById("rngMaxPoets").value;
    const stagger = +document.getElementById("rngStagger").value;
    if (!state.lastTs) state.lastTs = ts;
    const dt = (ts - state.lastTs) / 1000;
    state.lastTs = ts;

    if (state.playing) {
      const span = T1 - T0;
      state.currentY += (dt * speed * span) / PLAYBACK_DIVISOR;
      if (state.currentY > T1) {
        state.currentY = T1;
        state.playing = false;
        document.getElementById("btnPlay").textContent = "播放";
        state.shouldStartOutro = true;
      }
      const pr = document.getElementById("rngProgress");
      pr.value = String(Math.round(((state.currentY - T0) / span) * 1000));
    }

    if (state.shouldStartOutro) {
      state.shouldStartOutro = false;
      state.outroActive = true;
      state.outroT0 = ts;
    }
    tickOutro(ts);

    const yInt = Math.floor(state.currentY);
    document.getElementById("yearLabel").textContent = `${yInt} 年`;
    fireEventsUpTo(yInt, emphasis, stagger);
    tickPulses(ts);
    updateTrails(state.currentY);
    updateMovers(state.currentY, maxPoets);
    updateKeyCities(state.currentY);
    updateHistHud(state.currentY);
    refreshDynastyOverlays(yInt);
    state.raf = requestAnimationFrame(frame);
  }

  async function loadChinaOutline() {
    try {
      const res = await fetch(CHINA_GEOJSON_URL);
      if (!res.ok) throw new Error(String(res.status));
      return await res.json();
    } catch {
      return {
        type: "FeatureCollection",
        features: [
          {
            type: "Feature",
            properties: { name: "示意" },
            geometry: {
              type: "Polygon",
              coordinates: [
                [
                  [73.4, 18.1],
                  [135.1, 18.1],
                  [135.1, 53.7],
                  [73.4, 53.7],
                  [73.4, 18.1],
                ],
              ],
            },
          },
        ],
      };
    }
  }

  function addBasemap() {
    state.tileLayer = L.tileLayer(BASEMAP_TILES, {
      attribution: BASEMAP_ATTR,
      subdomains: "abcd",
      maxZoom: 19,
      opacity: BASEMAP_TILE_OPACITY,
    }).addTo(state.map);
  }

  async function tryAddWorldCountries() {
    try {
      const res = await fetch(WORLD_COUNTRIES_URL);
      if (!res.ok) return;
      const geo = await res.json();
      state.worldLayer = L.geoJSON(geo, {
        interactive: false,
        style() {
          return {
            color: "#e0e0e0",
            weight: 0.45,
            fillColor: "#fafafa",
            fillOpacity: 0.32,
            opacity: 0.75,
          };
        },
      }).addTo(state.map);
    } catch {
      /* 忽略：无外网或大文件失败 */
    }
  }

  function addChinaLayers(geo) {
    const gj = L.geoJSON(geo, {
      style() {
        return {
          color: "#bdbdbd",
          weight: 0.75,
          fillColor: "#ffffff",
          fillOpacity: 0.96,
          opacity: 1,
        };
      },
    }).addTo(state.map);
    state.chinaLayer = gj;
    try {
      const b = gj.getBounds();
      if (VIZ_VIDEO_EXPORT) {
        state.map.fitBounds(b, { padding: [56, 72], maxZoom: 5.35 });
      } else {
        state.map.fitBounds(b, { padding: [20, 20], maxZoom: 6 });
      }
    } catch {
      state.map.setView([34.5, 105], 5);
    }
  }

  /**
   * Hartwell v5 朝代外轮廓切片（与 scripts/build_hartwell_dynasty_outlines.py 一致）。
   * 907–959 五代十国无对应切片 → 不叠层。
   */
  function resolveDynastySnapshotKey(yf) {
    if (yf >= 618 && yf <= 907) return "tang741";
    if (yf >= 960 && yf <= 1126) return "chin1080";
    if (yf >= 1127 && yf <= 1279) return "chin1200";
    return null;
  }

  function refreshDynastyOverlays(yf) {
    const sid = resolveDynastySnapshotKey(yf);
    if (sid === state.dynastySnapshotId) return;
    state.dynastySnapshotId = sid;
    if (!state.dynastyLayer) return;
    state.dynastyLayer.clearLayers();
    if (!sid || !state.dynastyBundle || !state.dynastyBundle.snapshots) return;
    const snap = state.dynastyBundle.snapshots[sid];
    if (!snap || !snap.geo || !snap.geo.features || !snap.geo.features.length) return;
    L.geoJSON(snap.geo, {
      interactive: false,
      style(feature) {
        const p = feature.properties || {};
        return {
          color: p.stroke || "#546e7a",
          weight: Number.isFinite(p.weight) ? p.weight : 1.25,
          fillColor: p.fill || "#90a4ae",
          fillOpacity: Number.isFinite(p.fillOpacity) ? p.fillOpacity : 0.08,
          opacity: 0.92,
        };
      },
    }).addTo(state.dynastyLayer);
  }

  function initCityLayer() {
    state.cityLayer = L.layerGroup().addTo(state.map);
    state.cityEraIndex = -1;
    addPermanentChangan();
  }

  function precomputePaths() {
    state.pathCache.clear();
    const step = 0.32;
    for (const p of state.data.poets) {
      state.pathCache.set(p.id, buildSmoothedPath(p, step));
    }
  }

  async function init() {
    const res = await fetch("data/trajectories.json");
    if (!res.ok) {
      throw new Error("无法加载 data/trajectories.json — 请在 viz 目录运行 python3 -m http.server 8765");
    }
    state.data = await res.json();
    state.eventsByYear = buildEventsByYear(state.data.events || []);

    let dynastyBundle = null;
    try {
      const dRes = await fetch("data/hartwell_dynasty_outlines.json");
      if (dRes.ok) dynastyBundle = await dRes.json();
    } catch {
      dynastyBundle = null;
    }
    state.dynastyBundle = dynastyBundle;

    state.map = L.map("map", {
      worldCopyJump: true,
      zoomControl: !VIZ_VIDEO_EXPORT,
      attributionControl: true,
      preferCanvas: true,
    }).setView([34.5, 108.5], 5);

    addBasemap();
    await tryAddWorldCountries();
    const china = await loadChinaOutline();
    addChinaLayers(china);
    state.dynastyLayer = L.layerGroup().addTo(state.map);
    state.trailsLayer = L.layerGroup().addTo(state.map);
    state.vipTrailsLayer = L.layerGroup().addTo(state.map);
    initCityLayer();
    state.pulseLayer = L.layerGroup().addTo(state.map);
    state.moversLayer = L.layerGroup().addTo(state.map);

    precomputePaths();
    ensureVipDockSlots();
    resetOutroVisual();

    const rngSpeed = document.getElementById("rngSpeed");
    if (rngSpeed) {
      rngSpeed.addEventListener("input", updateSpeedEta);
      rngSpeed.addEventListener("change", updateSpeedEta);
    }
    updateSpeedEta();

    document.getElementById("btnPlay").onclick = () => {
      if (state.introActive) {
        cancelPlayPrelude();
        return;
      }
      if (state.playing) {
        state.playing = false;
        document.getElementById("btnPlay").textContent = "播放";
        state.lastTs = 0;
        return;
      }
      if (state.currentY <= T0 + 0.001) {
        startPlayPrelude();
        return;
      }
      state.playing = true;
      setTimeUiVisible(true);
      document.getElementById("btnPlay").textContent = "暂停";
      state.lastTs = 0;
    };
    document.getElementById("btnReset").onclick = () => {
      state.pulses.forEach((p) => state.pulseLayer.removeLayer(p.mk));
      state.pulses = [];
      clearAllTrailSegs();
      state.currentY = T0;
      state.lastTs = 0;
      state.playing = false;
      state.introActive = false;
      document.getElementById("btnPlay").textContent = "播放";
      document.getElementById("rngProgress").value = "0";
      state.lastFiredYear = Math.floor(state.currentY) - 1;
      state.cityEraIndex = -1;
      state.vipCaptionFired = new Set();
      clearAllVipCaptions();
      hideIntroTitleCardImmediately();
      hideMarkerDotGuideImmediately();
      state.dynastySnapshotId = null;
      refreshDynastyOverlays(Math.floor(state.currentY));
      resetOutroVisual();
      setTimeUiVisible(false);
    };

    document.getElementById("rngProgress").oninput = (e) => {
      const u = +e.target.value / 1000;
      state.currentY = T0 + u * (T1 - T0);
      const yInt = Math.floor(state.currentY);
      state.lastFiredYear = yInt - 1;
      state.pulses.forEach((p) => state.pulseLayer.removeLayer(p.mk));
      state.pulses = [];
      clearAllTrailSegs();
      state.introActive = false;
      state.cityEraIndex = -1;
      state.vipCaptionFired = new Set();
      clearAllVipCaptions();
      hideIntroTitleCardImmediately();
      hideMarkerDotGuideImmediately();
      document.getElementById("btnPlay").textContent = "播放";
      state.dynastySnapshotId = null;
      refreshDynastyOverlays(yInt);
      setTimeUiVisible(false);
      if (state.currentY < T1 - 0.05) resetOutroVisual();
    };

    state.currentY = T0;
    state.lastFiredYear = Math.floor(state.currentY) - 1;
    setTimeUiVisible(false);
    state.raf = requestAnimationFrame(frame);

    if (VIZ_VIDEO_EXPORT && new URLSearchParams(location.search).get("autoplay") === "1") {
      window.setTimeout(() => {
        state.playing = true;
        setTimeUiVisible(false);
        const bp = document.getElementById("btnPlay");
        if (bp) bp.textContent = "暂停";
        state.lastTs = 0;
      }, 1600);
    }
  }

  init().catch((err) => {
    document.getElementById("yearLabel").textContent = "加载失败";
    alert(err.message || String(err));
  });
})();
