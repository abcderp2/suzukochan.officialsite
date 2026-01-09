document.addEventListener('DOMContentLoaded', () => {
  const img = document.querySelector('.gallery-img');
  const inputPanX = document.getElementById('panX');
  const inputPanY = document.getElementById('panY');
  const inputZoom = document.getElementById('zoom');
  const outPanX = document.getElementById('panXOut');
  const outPanY = document.getElementById('panYOut');
  const outZoom = document.getElementById('zoomOut');
  const resetBtn = document.getElementById('resetBtn');

  // Default state (shows face/head)
  // Image is 5504x3072. Centered shows torso.
  // Shift Y positive to show top.
  const DEFAULTS = {
    x: 0,
    y: 20, // Shift down to show head
    zoom: 0.6 // Initial zoom to fit width reasonably
  };

  let state = { ...DEFAULTS };

  function loadState() {
    try {
      const storedX = localStorage.getItem('suzukoPanX');
      const storedY = localStorage.getItem('suzukoPanY');
      const storedZoom = localStorage.getItem('suzukoZoom');

      if (storedX !== null) state.x = parseFloat(storedX);
      if (storedY !== null) state.y = parseFloat(storedY);
      if (storedZoom !== null) state.zoom = parseFloat(storedZoom);
    } catch (e) {
      console.error('Failed to load gallery state', e);
    }
    validateState();
    updateView();
  }

  function validateState() {
    // Sanitize
    if (isNaN(state.x)) state.x = DEFAULTS.x;
    if (isNaN(state.y)) state.y = DEFAULTS.y;
    if (isNaN(state.zoom)) state.zoom = DEFAULTS.zoom;

    // Clamp
    // Zoom: 0.1 to 3.0
    state.zoom = Math.max(0.1, Math.min(state.zoom, 3.0));

    // Pan: -100 to 100 (percentage offset)
    state.x = Math.max(-100, Math.min(state.x, 100));
    state.y = Math.max(-100, Math.min(state.y, 100));
  }

  function updateView() {
    if (!img) return;

    // Use translate(-50%, -50%) for centering, then add state offsets
    // state.x/y are percentages of the image size added to the position
    const translateX = -50 + state.x;
    const translateY = -50 + state.y;

    img.style.transform = `translate(${translateX}%, ${translateY}%) scale(${state.zoom})`;

    // Update UI
    if (inputPanX) inputPanX.value = state.x;
    if (outPanX) outPanX.textContent = state.x.toFixed(1);

    if (inputPanY) inputPanY.value = state.y;
    if (outPanY) outPanY.textContent = state.y.toFixed(1);

    if (inputZoom) inputZoom.value = state.zoom;
    if (outZoom) outZoom.textContent = state.zoom.toFixed(2);

    // Save
    try {
      localStorage.setItem('suzukoPanX', state.x);
      localStorage.setItem('suzukoPanY', state.y);
      localStorage.setItem('suzukoZoom', state.zoom);
    } catch (e) {
      // ignore
    }
  }

  // Event Listeners
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      state = { ...DEFAULTS };
      validateState();
      updateView();
    });
  }

  // Inputs
  const inputs = [
    { el: inputPanX, key: 'x' },
    { el: inputPanY, key: 'y' },
    { el: inputZoom, key: 'zoom' }
  ];

  inputs.forEach(({ el, key }) => {
    if (el) {
      el.addEventListener('input', (e) => {
        state[key] = parseFloat(e.target.value);
        // Do not validate immediately on input to allow smooth sliding?
        // Or validate to prevent out of bounds?
        // Let's validate.
        // validateState(); // Maybe skip clamping during slide if range inputs are clamped?
        // But range inputs have min/max.
        updateView();
      });
      el.addEventListener('change', () => {
        validateState();
        updateView();
      });
    }
  });

  // Nudge Buttons
  document.querySelectorAll('[data-nudge]').forEach(btn => {
    btn.addEventListener('click', () => {
      const type = btn.dataset.type;
      const amount = parseFloat(btn.dataset.nudge);

      if (type === 'x') state.x += amount;
      if (type === 'y') state.y += amount;
      if (type === 'zoom') state.zoom += amount;

      validateState();
      updateView();
    });
  });

  // Initial Load
  loadState();
});
