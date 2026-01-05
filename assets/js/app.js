(() => {
  "use strict";

  // 旧保存値の影響を避けるため v2 に変更
  // 設定構造が変わったため v3 に移行し初期化を促す
  const KEY_X = "suzukoPanX_v3";
  const KEY_Y = "suzukoPanY_v3";
  const KEY_Z = "suzukoZoom_v3";

  const clamp = (n, min, max) => Math.min(max, Math.max(min, n));

  const root = document.documentElement;

  const panX = document.getElementById("panX");
  const panY = document.getElementById("panY");
  const zoom = document.getElementById("zoom");

  const panXOut = document.getElementById("panXOut");
  const panYOut = document.getElementById("panYOut");
  const zoomOut = document.getElementById("zoomOut");

  const buttons = document.querySelectorAll("[data-nudge]");

  if (!panX || !panY || !zoom || !panXOut || !panYOut || !zoomOut) return;

  // index.html 側で指定した min/max をそのまま使う
  const getLimits = (el, fallbackMin, fallbackMax) => {
    const min = Number(el.min);
    const max = Number(el.max);
    const okMin = Number.isFinite(min) ? min : fallbackMin;
    const okMax = Number.isFinite(max) ? max : fallbackMax;
    return { min: okMin, max: okMax };
  };

  const limitsX = () => getLimits(panX, -40, 40);
  const limitsY = () => getLimits(panY, -150, 150);
  const limitsZ = () => getLimits(zoom, 30, 150);

  // 頭が入るように初期値は 0 (上端)、zoom 100
  const DEFAULT = { x: 0, y: 0, z: 100 };

  const setVars = (xVal, yVal, zVal) => {
    const lx = limitsX();
    const ly = limitsY();
    const lz = limitsZ();

    const xv = clamp(Number(xVal), lx.min, lx.max);
    const yv = clamp(Number(yVal), ly.min, ly.max);
    const zv = clamp(Number(zVal), lz.min, lz.max);

    // CSS 側が % 前提の想定のまま。数値レンジだけ広げる
    root.style.setProperty("--pan-x", `${xv}%`);
    root.style.setProperty("--pan-y", `${yv}%`);
    root.style.setProperty("--zoom", String(zv / 100));

    panX.value = String(xv);
    panY.value = String(yv);
    zoom.value = String(zv);

    panXOut.textContent = String(xv);
    panYOut.textContent = String(yv);
    zoomOut.textContent = String(zv);

    try {
      localStorage.setItem(KEY_X, String(xv));
      localStorage.setItem(KEY_Y, String(yv));
      localStorage.setItem(KEY_Z, String(zv));
    } catch (_) {}
  };

  const load = () => {
    let x = DEFAULT.x;
    let y = DEFAULT.y;
    let z = DEFAULT.z;

    try {
      const lx = localStorage.getItem(KEY_X);
      const ly = localStorage.getItem(KEY_Y);
      const lz = localStorage.getItem(KEY_Z);

      if (lx !== null && !Number.isNaN(Number(lx))) x = Number(lx);
      if (ly !== null && !Number.isNaN(Number(ly))) y = Number(ly);
      if (lz !== null && !Number.isNaN(Number(lz))) z = Number(lz);
    } catch (_) {}

    setVars(x, y, z);
  };

  const sync = () => setVars(panX.value, panY.value, zoom.value);

  panX.addEventListener("input", sync);
  panY.addEventListener("input", sync);
  zoom.addEventListener("input", sync);

  buttons.forEach((b) => {
    b.addEventListener("click", () => {
      const mode = b.getAttribute("data-nudge");
      const step = 5;

      const curX = Number(panX.value);
      const curY = Number(panY.value);
      const curZ = Number(zoom.value);

      if (mode === "reset") return setVars(DEFAULT.x, DEFAULT.y, DEFAULT.z);
      if (mode === "up") return setVars(curX, curY - step, curZ);
      if (mode === "down") return setVars(curX, curY + step, curZ);
      if (mode === "left") return setVars(curX - step, curY, curZ);
      if (mode === "right") return setVars(curX + step, curY, curZ);
    });
  });

  load();
})();
