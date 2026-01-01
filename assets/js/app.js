(() => {
  "use strict";

  const KEY_X = "suzukoThumbX";
  const KEY_Y = "suzukoThumbY";

  const clamp = (n, min, max) => Math.min(max, Math.max(min, n));

  const root = document.documentElement;
  const x = document.getElementById("thumbX");
  const y = document.getElementById("thumbY");
  const xOut = document.getElementById("thumbXOut");
  const yOut = document.getElementById("thumbYOut");
  const buttons = document.querySelectorAll("[data-nudge]");

  if (!x || !y || !xOut || !yOut) return;

  const setVars = (xVal, yVal) => {
    const xv = clamp(Number(xVal), 0, 100);
    const yv = clamp(Number(yVal), 0, 100);
    root.style.setProperty("--thumb-x", `${xv}%`);
    root.style.setProperty("--thumb-y", `${yv}%`);
    x.value = String(xv);
    y.value = String(yv);
    xOut.textContent = String(xv);
    yOut.textContent = String(yv);
    try {
      localStorage.setItem(KEY_X, String(xv));
      localStorage.setItem(KEY_Y, String(yv));
    } catch (_) {}
  };

  const load = () => {
    let xv = 50;
    let yv = 92;
    try {
      const lx = localStorage.getItem(KEY_X);
      const ly = localStorage.getItem(KEY_Y);
      if (lx !== null) xv = Number(lx);
      if (ly !== null) yv = Number(ly);
    } catch (_) {}
    setVars(xv, yv);
  };

  x.addEventListener("input", () => setVars(x.value, y.value));
  y.addEventListener("input", () => setVars(x.value, y.value));

  buttons.forEach((b) => {
    b.addEventListener("click", () => {
      const mode = b.getAttribute("data-nudge");
      const step = 2;
      const curX = Number(x.value);
      const curY = Number(y.value);

      if (mode === "reset") return setVars(50, 92);
      if (mode === "up") return setVars(curX, curY - step);
      if (mode === "down") return setVars(curX, curY + step);
      if (mode === "left") return setVars(curX - step, curY);
      if (mode === "right") return setVars(curX + step, curY);
    });
  });

  load();
})();
