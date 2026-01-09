document.addEventListener('DOMContentLoaded', () => {
  const img = document.querySelector('.gallery-img');
  const container = document.querySelector('.gallery-container');
  const inputPanX = document.getElementById('panX');
  const inputPanY = document.getElementById('panY');
  const inputZoom = document.getElementById('zoom');
  const outPanX = document.getElementById('panXOut');
  const outPanY = document.getElementById('panYOut');
  const outZoom = document.getElementById('zoomOut');
  const resetBtn = document.getElementById('resetBtn');

  // Versioning for localStorage to force reset on update
  const CURRENT_VERSION = '2';

  // Default state will be calculated on load
  let state = {
    x: 0,
    y: 0,
    zoom: 1.0
  };

  function getAutoFitState() {
    if (!img || !container) return { x: 0, y: 0, zoom: 0.6 };

    // We need natural dimensions, but img might not be loaded yet.
    // However, if we run this when naturalWidth is available...
    const nW = img.naturalWidth || 5504; // Fallback to known size
    const nH = img.naturalHeight || 3072;
    const cW = container.clientWidth;
    const cH = container.clientHeight;

    if (cW === 0 || cH === 0) return { x: 0, y: 0, zoom: 0.6 };

    // Calculate scale to "contain"
    const scaleX = cW / nW;
    const scaleY = cH / nH;

    // Use the larger scale to "cover" or smaller to "contain"?
    // "Display properly" -> Contain means see everything.
    // Cover means fills box but crops.
    // User complaint was "cropped". So "Contain" is safer.
    // BUT contain might leave whitespace.
    // Let's try Contain.
    let fitZoom = Math.min(scaleX, scaleY);

    // Add a little padding? e.g. 95%
    fitZoom = fitZoom * 0.95;

    // Minimum zoom constraint
    fitZoom = Math.max(fitZoom, 0.1);

    return {
      x: 0,
      y: 0,
      zoom: fitZoom
    };
  }

  function loadState() {
    let loaded = false;
    try {
      const version = localStorage.getItem('suzukoGalleryVersion');
      if (version === CURRENT_VERSION) {
        const storedX = localStorage.getItem('suzukoPanX');
        const storedY = localStorage.getItem('suzukoPanY');
        const storedZoom = localStorage.getItem('suzukoZoom');

        if (storedX !== null && storedY !== null && storedZoom !== null) {
          state.x = parseFloat(storedX);
          state.y = parseFloat(storedY);
          state.zoom = parseFloat(storedZoom);
          loaded = true;
        }
      } else {
        // Version mismatch, force defaults
        console.log('Gallery version mismatch or new. Resetting to auto-fit.');
        localStorage.clear(); // Or just clear specific keys
        localStorage.setItem('suzukoGalleryVersion', CURRENT_VERSION);
      }
    } catch (e) {
      console.error('Failed to load gallery state', e);
    }

    if (!loaded) {
      // Calculate defaults
      // Wait for image load if needed
      if (img.naturalWidth) {
        state = getAutoFitState();
        updateView();
      } else {
        img.onload = () => {
          state = getAutoFitState();
          updateView();
        };
      }
    } else {
      validateState();
      updateView();
    }
  }

  function validateState() {
    // Sanitize
    if (isNaN(state.x)) state.x = 0;
    if (isNaN(state.y)) state.y = 0;
    if (isNaN(state.zoom)) state.zoom = 1.0;

    // Clamp
    // Zoom: 0.1 to 3.0
    state.zoom = Math.max(0.1, Math.min(state.zoom, 3.0));

    // Pan: -100 to 100
    state.x = Math.max(-100, Math.min(state.x, 100));
    state.y = Math.max(-100, Math.min(state.y, 100));
  }

  function updateView() {
    if (!img) return;

    const translateX = -50 + state.x;
    const translateY = -50 + state.y;

    img.style.transform = `translate(${translateX}%, ${translateY}%) scale(${state.zoom})`;

    // Update UI
    if (inputPanX) inputPanX.value = state.x;
    if (outPanX) outPanX.textContent = state.x.toFixed(1);

    if (inputPanY) inputPanY.value = state.y;
    if (outPanY) outPanY.textContent = state.y.toFixed(1);

    if (inputZoom) inputZoom.value = state.zoom;
    if (outZoom) outZoom.textContent = state.zoom.toFixed(3); // More precision for small scales

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
      // Reset to Auto Fit
      state = getAutoFitState();
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

  // Handle window resize (optional: re-fit if user hasn't touched it?
  // For now, keep state as is to avoid jumping)
});
