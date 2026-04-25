/* global L */
(function () {
  const DATA_URL = "data/trajectories.json";
  const DYNASTY_URL = "data/hartwell_dynasty_outlines.json";
  const CHINA_GEOJSON_URL = "https://geo.datav.aliyun.com/areas_v3/bound/100000_full.json";
  const BASEMAP_TILES =
    "https://{s}.basemaps.cartocdn.com/rastertiles/light_nolabels/{z}/{x}/{y}{r}.png";
  const BASEMAP_ATTR = '&copy; OSM &copy; CARTO';
  const BASEMAP_OPACITY = 0.72;

  /** 与主图同量级：playU 0→1 约 PLAYBACK_DIVISOR / speed 秒 */
  const PLAYBACK_DIVISOR = 200;
  const TRAIL_YEAR_WINDOW = 3.15;

  const ACT_DEF = [
    { key: "libai", name: "李白", match: "李白", y0: 701, y1: 762, line: "#1565c0", stroke: "#0d47a1", mover: "#42a5f5" },
    { key: "sushi", name: "苏轼", match: "苏轼", y0: 1036, y1: 1101, line: "#c62828", stroke: "#b71c1c", mover: "#ef5350" },
    { key: "liqz", name: "李清照", match: "李清照", y0: 1084, y1: 1156, line: "#ad1457", stroke: "#880e4f", mover: "#f48fb1" },
  ];

  /** 李清照：跨越该历法年触发；依次入队，每首展示 3–5s，期间冻结时间轴 */
  const LIQZ_POETRY_TRIGGERS = [
    {
      id: "t1099",
      year: 1099,
      items: [
        {
          title: "如梦令·常记溪亭日暮",
          eraLabel: "约 1099 年",
          anchorYear: 1099.5,
          body:
            "常记溪亭日暮，沉醉不知归路。兴尽晚回舟，误入藕花深处。争渡，争渡，惊起一滩鸥鹭。",
        },
        {
          title: "如梦令·昨夜雨疏风骤",
          eraLabel: "约 1099 年",
          anchorYear: 1099.5,
          body:
            "昨夜雨疏风骤，浓睡不消残酒。试问卷帘人，却道海棠依旧。知否，知否？应是绿肥红瘦。",
        },
      ],
    },
    {
      id: "t1101",
      year: 1101,
      items: [
        {
          title: "醉花阴·薄雾浓云愁永昼",
          eraLabel: "约 1101—1120 年",
          anchorYear: 1105,
          body:
            "薄雾浓云愁永昼，瑞脑销金兽。佳节又重阳，玉枕纱厨，半夜凉初透。\n" +
            "东篱把酒黄昏后，有暗香盈袖。莫道不销魂，帘卷西风，人比黄花瘦。",
        },
      ],
    },
    {
      id: "t1127",
      year: 1127,
      items: [
        {
          title: "夏日绝句",
          eraLabel: "1127 年",
          anchorYear: 1127.5,
          body: "生当作人杰，死亦为鬼雄。\n至今思项羽，不肯过江东。",
        },
      ],
    },
    {
      id: "t1132",
      year: 1132,
      items: [
        {
          title: "声声慢·寻寻觅觅",
          eraLabel: "约 1129—1132 年",
          anchorYear: 1130.5,
          body:
            "寻寻觅觅，冷冷清清，凄凄惨惨戚戚。乍暖还寒时候，最难将息。三杯两盏淡酒，怎敌他、晚来风急？雁过也，正伤心，却是旧时相识。\n" +
            "满地黄花堆积。憔悴损，如今有谁堪摘？守着窗儿，独自怎生得黑？梧桐更兼细雨，到黄昏、点点滴滴。这次第，怎一个愁字了得！",
        },
      ],
    },
    {
      id: "t1135",
      year: 1135,
      items: [
        {
          title: "武陵春·春晚",
          eraLabel: "1135 年",
          anchorYear: 1135.5,
          body:
            "风住尘香花已尽，日晚倦梳头。物是人非事事休，欲语泪先流。\n" +
            "闻说双溪春尚好，也拟泛轻舟。只恐双溪舴艋舟，载不动许多愁。",
        },
      ],
    },
  ];

  const state = {
    acts: [],
    totalSpan: 0,
    pathCache: new Map(),
    map: null,
    chinaLayer: null,
    tileLayer: null,
    trailLayer: null,
    dynastyLayer: null,
    dynastyBundle: null,
    dynastySnapshotId: null,
    moverLayer: null,
    trailSegs: new Map(),
    moverMk: null,
    playU: 0,
    playing: false,
    lastTs: 0,
    raf: 0,
    /** null 表示尚未定段，避免首帧误清轨迹 */
    lastActKey: null,
    soloId: "solo",
    framePrevActKey: null,
    liqzPrevYf: null,
    poetryFired: new Set(),
    poetry: {
      queue: [],
      timerId: null,
      /** 任一首诗词在屏上（含定时器等待） */
      sessionActive: false,
      /** 仅当「当前首之后队列里还有下一首」时为 true，用于暂停 playU */
      freezeTimeline: false,
      /** 本段展示中曾进入过冻结（用于从多首末首恢复播放） */
      wasFrozenInBurst: false,
      resumePlaying: false,
    },
  };

  function showErr(msg) {
    const el = document.getElementById("err");
    el.style.display = "block";
    el.textContent = msg;
  }

  function span(a) {
    return a.y1 - a.y0;
  }

  function easeInOutCubic(t) {
    return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
  }

  function posAtYear(poet, Y) {
    const wps = poet.waypoints;
    if (!wps || !wps.length) {
      if (poet.birth && poet.birth.lat != null) return { lat: poet.birth.lat, lng: poet.birth.lng };
      return { lat: 34.5, lng: 108.5 };
    }
    if (Y <= wps[0].yearStart) return { lat: wps[0].lat, lng: wps[0].lng };
    const last = wps[wps.length - 1];
    if (Y >= last.yearEnd) return { lat: last.lat, lng: last.lng };
    for (let i = 0; i < wps.length; i++) {
      const w = wps[i];
      if (Y >= w.yearStart && Y <= w.yearEnd) return { lat: w.lat, lng: w.lng };
    }
    for (let i = 0; i < wps.length - 1; i++) {
      const a = wps[i];
      const b = wps[i + 1];
      if (Y > a.yearEnd && Y < b.yearStart) {
        const t0 = a.yearEnd;
        const t1 = b.yearStart;
        let u = (Y - t0) / (t1 - t0);
        u = easeInOutCubic(Math.min(1, Math.max(0, u)));
        return { lat: a.lat + (b.lat - a.lat) * u, lng: a.lng + (b.lng - a.lng) * u };
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
      return { y: b.y, lat: (a.lat + b.lat + c.lat) / 3, lng: (a.lng + b.lng + c.lng) / 3 };
    });
  }

  function playUToReal(u) {
    const U = Math.max(0, Math.min(1, u));
    let t = U * state.totalSpan;
    let acc = 0;
    for (let ai = 0; ai < state.acts.length; ai++) {
      const a = state.acts[ai];
      const len = span(a);
      if (t < acc + len || ai === state.acts.length - 1) {
        const local = Math.min(len, Math.max(0, t - acc));
        const year = a.y0 + local;
        return { act: a, poet: a.poet, year };
      }
      acc += len;
    }
    const last = state.acts[state.acts.length - 1];
    return { act: last, poet: last.poet, year: last.y1 };
  }

  function trimDetail(t) {
    if (!t) return "";
    return String(t).replace(/^[,，、\s]+/, "").trim();
  }

  function formatEta(sec) {
    if (!Number.isFinite(sec) || sec <= 0) return "";
    const r = Math.round(sec);
    if (r < 60) return `全程约 ${r} 秒`;
    const m = Math.floor(r / 60);
    const s = r % 60;
    if (s === 0) return `全程约 ${m} 分钟`;
    return `全程约 ${m} 分 ${s} 秒`;
  }

  function playbackEtaSeconds(speed) {
    const s = +speed;
    if (!s || s < 1) return NaN;
    return PLAYBACK_DIVISOR / s;
  }

  function liqzPlayUAtYear(y) {
    let acc = 0;
    for (let i = 0; i < state.acts.length; i++) {
      const a = state.acts[i];
      if (a.key === "liqz") {
        const len = span(a);
        const local = Math.max(0, Math.min(len, y - a.y0));
        return (acc + local) / state.totalSpan;
      }
      acc += span(a);
    }
    return 1;
  }

  function syncProgressUi() {
    const rng = document.getElementById("rngProgress");
    if (rng) rng.value = String(Math.round(state.playU * 1000));
  }

  function hidePoemDock() {
    const stage = document.getElementById("mapStage");
    if (stage) stage.classList.remove("has-poem-dock");
    const dock = document.getElementById("poemDock");
    if (!dock) return;
    dock.classList.remove("is-visible");
    dock.textContent = "";
  }

  function renderPoemDock(item) {
    const dock = document.getElementById("poemDock");
    const stage = document.getElementById("mapStage");
    if (!dock) return;
    if (stage) stage.classList.add("has-poem-dock");
    dock.textContent = "";
    const scroll = document.createElement("div");
    scroll.className = "poem-scroll";
    const era = document.createElement("div");
    era.className = "poem-era";
    era.textContent = item.eraLabel || "";
    const tit = document.createElement("div");
    tit.className = "poem-title";
    tit.textContent = item.title || "";
    const body = document.createElement("div");
    body.className = "poem-body";
    body.textContent = item.body || "";
    scroll.appendChild(era);
    scroll.appendChild(tit);
    scroll.appendChild(body);
    dock.appendChild(scroll);
    dock.classList.add("is-visible");
  }

  function clearPoetryTimer() {
    if (state.poetry.timerId != null) {
      clearTimeout(state.poetry.timerId);
      state.poetry.timerId = null;
    }
  }

  function finishPoetrySession() {
    clearPoetryTimer();
    state.poetry.sessionActive = false;
    state.poetry.freezeTimeline = false;
    state.poetry.wasFrozenInBurst = false;
    hidePoemDock();
    state.poetry.resumePlaying = false;
    state.lastTs = 0;
  }

  function showNextPoemOrFinish() {
    clearPoetryTimer();
    if (!state.poetry.queue.length) {
      finishPoetrySession();
      return;
    }
    const item = state.poetry.queue.shift();
    const hasMoreAfterThis = state.poetry.queue.length > 0;

    if (hasMoreAfterThis) {
      if (!state.poetry.freezeTimeline) {
        state.poetry.resumePlaying = state.playing;
        state.playing = false;
        const bp = document.getElementById("btnPlay");
        if (bp) bp.textContent = "播放";
        state.lastTs = 0;
      }
      state.poetry.freezeTimeline = true;
      state.poetry.wasFrozenInBurst = true;
      state.playU = liqzPlayUAtYear(item.anchorYear);
      syncProgressUi();
    } else {
      state.poetry.freezeTimeline = false;
      if (state.poetry.wasFrozenInBurst) {
        state.playing = state.poetry.resumePlaying;
        state.poetry.wasFrozenInBurst = false;
        const bp = document.getElementById("btnPlay");
        if (bp) bp.textContent = state.playing ? "暂停" : "播放";
        state.lastTs = 0;
      }
    }

    renderPoemDock(item);
    const ms = 8000 + Math.random() * 6000;
    state.poetry.timerId = setTimeout(() => {
      state.poetry.timerId = null;
      showNextPoemOrFinish();
    }, ms);
  }

  function tryBeginPoetrySession() {
    if (!state.poetry.queue.length || state.poetry.sessionActive) return;
    state.poetry.sessionActive = true;
    state.poetry.wasFrozenInBurst = false;
    state.poetry.freezeTimeline = false;
    state.poetry.resumePlaying = false;
    showNextPoemOrFinish();
  }

  function enqueueLiQZPoetryCrossing(prevYf, yf) {
    if (prevYf == null || yf <= prevYf) return;
    for (const trig of LIQZ_POETRY_TRIGGERS) {
      if (trig.year > prevYf && trig.year <= yf && !state.poetryFired.has(trig.id)) {
        state.poetryFired.add(trig.id);
        for (const it of trig.items) state.poetry.queue.push(it);
      }
    }
    tryBeginPoetrySession();
  }

  function unfireLiQZPoetryAfterYear(yf) {
    for (const trig of LIQZ_POETRY_TRIGGERS) {
      if (trig.year > yf) state.poetryFired.delete(trig.id);
    }
  }

  function abortPoetryForScrub() {
    const hadFreeze = state.poetry.freezeTimeline;
    const resume = state.poetry.resumePlaying;
    clearPoetryTimer();
    state.poetry.queue.length = 0;
    state.poetry.sessionActive = false;
    state.poetry.freezeTimeline = false;
    state.poetry.wasFrozenInBurst = false;
    hidePoemDock();
    if (hadFreeze && resume) {
      state.playing = true;
      const bp = document.getElementById("btnPlay");
      if (bp) bp.textContent = "暂停";
    }
    state.poetry.resumePlaying = false;
    state.lastTs = 0;
  }

  function updateSpeedEta() {
    const el = document.getElementById("speedEta");
    const rng = document.getElementById("rngSpeed");
    if (!el || !rng) return;
    el.textContent = formatEta(playbackEtaSeconds(rng.value));
  }

  /**
   * 与主图 app.js 一致：按历法年切换 Hartwell 朝代外廓（618–907 / 960–1126 / 1127–1279）。
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

  function clearTrailSegs() {
    const arr = state.trailSegs.get(state.soloId);
    if (arr) {
      arr.forEach((ln) => state.trailLayer.removeLayer(ln));
    }
    state.trailSegs.delete(state.soloId);
  }

  function updateSoloTrail(Y, poet, color) {
    const path = state.pathCache.get(poet.id);
    const layer = state.trailLayer;
    const segMap = state.trailSegs;
    const id = state.soloId;
    if (!path || !path.length || Y < poet.birthYear) {
      const arr = segMap.get(id);
      if (arr) {
        arr.forEach((ln) => layer.removeLayer(ln));
      }
      segMap.delete(id);
      return;
    }
    const W = TRAIL_YEAR_WINDOW;
    const yLo = Y - W;
    const pts = path.filter((pt) => pt.y <= Y && pt.y >= yLo);
    if (pts.length < 2) {
      clearTrailSegs();
      return;
    }
    clearTrailSegs();
    const segs = [];
    for (let i = 0; i < pts.length - 1; i++) {
      const mid = (pts[i].y + pts[i + 1].y) / 2;
      let u = (mid - yLo) / W;
      u = Math.max(0, Math.min(1, u));
      const op = 0.08 + 0.52 * Math.pow(u, 1.35);
      const ln = L.polyline(
        [
          [pts[i].lat, pts[i].lng],
          [pts[i + 1].lat, pts[i + 1].lng],
        ],
        {
          color,
          opacity: op,
          weight: 2.65,
          lineCap: "round",
          lineJoin: "round",
          smoothFactor: 1.12,
        }
      ).addTo(layer);
      segs.push(ln);
    }
    segMap.set(id, segs);
  }

  function updatePhaseHud(act, year, poet) {
    const yf = Math.floor(year + 1e-9);
    document.getElementById("yearLabel").textContent = `${yf} 年`;
    document.getElementById("poetBadge").textContent = act.name;
    document.getElementById("poetBadge").style.borderColor = act.line;
    document.getElementById("phaseYearChip").textContent = String(yf);
    document.getElementById("phasePoetTitle").textContent = act.name;
    const wps = poet.waypoints || [];
    let sub = "行迹编年";
    for (let wi = 0; wi < wps.length; wi++) {
      const w = wps[wi];
      if (yf >= w.yearStart && yf <= w.yearEnd) {
        const d = trimDetail(w.detail_text);
        const prev = wi > 0 ? wps[wi - 1] : null;
        const mig =
          prev && (prev.place !== w.place || prev.lat !== w.lat || prev.lng !== w.lng)
            ? `自「${prev.place || ""}」至「${w.place || ""}」`
            : w.place || "";
        const tail = d ? (d.length > 220 ? d.slice(0, 220) + "…" : d) : "";
        sub = tail ? `${mig} · ${tail}` : mig;
        break;
      }
    }
    document.getElementById("phaseSub").textContent = sub;
  }

  function updateMover(poet, year, fill) {
    const { lat, lng } = posAtYear(poet, year);
    if (!state.moverMk) {
      state.moverMk = L.circleMarker([lat, lng], {
        radius: 5.2,
        color: "#eceff1",
        weight: 1.4,
        fillColor: fill,
        fillOpacity: 0.88,
      }).addTo(state.moverLayer);
    } else {
      state.moverMk.setLatLng([lat, lng]);
      state.moverMk.setStyle({ fillColor: fill });
    }
  }

  function frame(ts) {
    const speed = +document.getElementById("rngSpeed").value;
    if (!state.lastTs) state.lastTs = ts;
    const dt = (ts - state.lastTs) / 1000;
    state.lastTs = ts;

    let playUAdvanced = false;
    if (state.playing && !state.poetry.freezeTimeline) {
      const before = state.playU;
      state.playU += (dt * speed) / PLAYBACK_DIVISOR;
      if (state.playU >= 1) {
        state.playU = 1;
        state.playing = false;
        const bp = document.getElementById("btnPlay");
        if (bp) bp.textContent = "播放";
      }
      if (state.playU !== before) playUAdvanced = true;
      syncProgressUi();
    }

    const { act, poet, year } = playUToReal(state.playU);
    const yf = Math.floor(year + 1e-9);

    const actSwitch = act.key !== state.framePrevActKey;
    if (actSwitch) {
      state.framePrevActKey = act.key;
      if (act.key === "liqz") {
        state.liqzPrevYf = yf;
      } else {
        state.liqzPrevYf = null;
        abortPoetryForScrub();
      }
    } else if (act.key === "liqz") {
      if (!state.poetry.sessionActive) {
        if (playUAdvanced && state.liqzPrevYf != null && yf > state.liqzPrevYf) {
          enqueueLiQZPoetryCrossing(state.liqzPrevYf, yf);
        }
        if (playUAdvanced) state.liqzPrevYf = yf;
      } else if (!state.poetry.freezeTimeline && playUAdvanced) {
        state.liqzPrevYf = yf;
      }
    }

    if (state.lastActKey !== null && act.key !== state.lastActKey) {
      clearTrailSegs();
    }
    state.lastActKey = act.key;

    updatePhaseHud(act, year, poet);
    refreshDynastyOverlays(yf);
    updateMover(poet, year, act.mover);
    updateSoloTrail(year, poet, act.line);

    state.raf = requestAnimationFrame(frame);
  }

  async function loadChinaOutline() {
    try {
      const res = await fetch(CHINA_GEOJSON_URL);
      if (!res.ok) throw new Error(String(res.status));
      return await res.json();
    } catch {
      return null;
    }
  }

  async function main() {
    let res;
    try {
      res = await fetch(DATA_URL);
    } catch {
      showErr("无法加载 " + DATA_URL + " — 请在 viz 目录运行 python3 -m http.server 8765");
      return;
    }
    if (!res.ok) {
      showErr("加载失败 HTTP " + res.status);
      return;
    }
    const data = await res.json();
    let dynastyBundle = null;
    try {
      const dr = await fetch(DYNASTY_URL);
      if (dr.ok) dynastyBundle = await dr.json();
    } catch {
      dynastyBundle = null;
    }
    state.dynastyBundle = dynastyBundle;

    const poets = data.poets || [];
    const acts = [];
    for (const d of ACT_DEF) {
      const p = poets.find((x) => x.name === d.match);
      if (!p) {
        showErr("未找到诗人：" + d.match);
        return;
      }
      acts.push({ ...d, poet: p });
    }
    state.acts = acts;
    state.totalSpan = acts.reduce((s, a) => s + span(a), 0);

    for (const a of acts) {
      state.pathCache.set(a.poet.id, buildSmoothedPath(a.poet, 0.28));
    }

    state.map = L.map("map", {
      worldCopyJump: true,
      zoomControl: true,
      attributionControl: true,
      preferCanvas: true,
    }).setView([34.5, 108.5], 5);

    state.tileLayer = L.tileLayer(BASEMAP_TILES, {
      attribution: BASEMAP_ATTR,
      subdomains: "abcd",
      maxZoom: 19,
      opacity: BASEMAP_OPACITY,
    }).addTo(state.map);

    const chinaGeo = await loadChinaOutline();
    if (chinaGeo) {
      state.chinaLayer = L.geoJSON(chinaGeo, {
        interactive: false,
        style() {
          return {
            color: "#bdbdbd",
            weight: 0.75,
            fillColor: "#ffffff",
            fillOpacity: 0.94,
            opacity: 1,
          };
        },
      }).addTo(state.map);
      try {
        state.map.fitBounds(state.chinaLayer.getBounds(), { padding: [18, 18], maxZoom: 5.5 });
      } catch {
        /* */
      }
    }

    const latlngs = [];
    for (const a of acts) {
      for (const w of a.poet.waypoints || []) {
        latlngs.push([w.lat, w.lng]);
      }
    }
    if (latlngs.length) {
      try {
        state.map.fitBounds(L.latLngBounds(latlngs), { padding: [40, 80], maxZoom: 6 });
      } catch {
        /* */
      }
    }

    state.dynastyLayer = L.layerGroup().addTo(state.map);
    state.trailLayer = L.layerGroup().addTo(state.map);
    state.moverLayer = L.layerGroup().addTo(state.map);

    state.playU = 0;
    state.lastActKey = null;
    const rngSpeed = document.getElementById("rngSpeed");
    if (rngSpeed) {
      rngSpeed.addEventListener("input", updateSpeedEta);
      rngSpeed.addEventListener("change", updateSpeedEta);
    }
    updateSpeedEta();

    document.getElementById("btnPlay").onclick = () => {
      if (state.poetry.freezeTimeline) return;
      if (state.playing) {
        state.playing = false;
        document.getElementById("btnPlay").textContent = "播放";
        state.lastTs = 0;
        return;
      }
      state.playing = true;
      document.getElementById("btnPlay").textContent = "暂停";
      state.lastTs = 0;
    };

    document.getElementById("btnReset").onclick = () => {
      abortPoetryForScrub();
      state.poetryFired.clear();
      state.framePrevActKey = null;
      state.liqzPrevYf = null;
      state.playing = false;
      state.playU = 0;
      state.lastTs = 0;
      state.lastActKey = null;
      document.getElementById("rngProgress").value = "0";
      document.getElementById("btnPlay").textContent = "播放";
      clearTrailSegs();
      if (state.moverMk) {
        state.moverLayer.removeLayer(state.moverMk);
        state.moverMk = null;
      }
      state.dynastySnapshotId = null;
      refreshDynastyOverlays(701);
      const { act, poet, year } = playUToReal(0);
      updatePhaseHud(act, year, poet);
    };

    document.getElementById("rngProgress").oninput = (e) => {
      abortPoetryForScrub();
      state.playU = +e.target.value / 1000;
      state.playing = false;
      document.getElementById("btnPlay").textContent = "播放";
      state.lastTs = 0;
      const { act, poet, year } = playUToReal(state.playU);
      const yf = Math.floor(year + 1e-9);
      unfireLiQZPoetryAfterYear(yf);
      if (act.key === "liqz") state.liqzPrevYf = yf;
      else state.liqzPrevYf = null;
      if (state.lastActKey !== null && act.key !== state.lastActKey) {
        clearTrailSegs();
      }
      state.lastActKey = act.key;
      updatePhaseHud(act, year, poet);
      state.dynastySnapshotId = null;
      refreshDynastyOverlays(Math.floor(year + 1e-9));
      updateMover(poet, year, act.mover);
      updateSoloTrail(year, poet, act.line);
    };

    state.dynastySnapshotId = null;
    refreshDynastyOverlays(701);

    state.raf = requestAnimationFrame(frame);
  }

  main();
})();
