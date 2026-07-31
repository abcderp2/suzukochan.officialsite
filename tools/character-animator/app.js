'use strict';

(() => {
  const STORAGE_KEY = 'suzuko-character-animator-settings-v1';
  const SETTINGS_VERSION = 1;
  const MAX_FILE_BYTES = 15 * 1024 * 1024;
  const MAX_SOURCE_PIXELS = 32_000_000;
  const MAX_SOURCE_SIDE = 8192;
  const ALLOWED_IMAGE_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp']);
  const EXPORT_FRAME_BUDGET = 21_000_000;

  const defaults = Object.freeze({
    preset: 'float',
    amplitude: 18,
    speed: 0.75,
    rotation: 4,
    pulse: 4,
    zoom: 88,
    outputSize: 360,
    duration: 3,
    fps: 12,
    backgroundMode: 'transparent',
    backgroundColor: '#ffffff',
    flip: false,
    offsetX: 0,
    offsetY: 0,
  });

  const settings = { ...defaults };
  const state = {
    image: null,
    imageWidth: 0,
    imageHeight: 0,
    sourceName: 'character',
    playing: true,
    animationStartedAt: performance.now(),
    pausedSeconds: 0,
    animationFrameId: 0,
    exporting: false,
    exportCancelled: false,
    pointer: null,
    resumeAfterVisibility: false,
  };

  const elements = {
    imageInput: document.getElementById('imageInput'),
    canvas: document.getElementById('previewCanvas'),
    status: document.getElementById('status'),
    progress: document.getElementById('exportProgress'),
    playButton: document.getElementById('playButton'),
    centerButton: document.getElementById('centerButton'),
    flipButton: document.getElementById('flipButton'),
    resetButton: document.getElementById('resetButton'),
    exportGifButton: document.getElementById('exportGifButton'),
    exportPngButton: document.getElementById('exportPngButton'),
    cancelExportButton: document.getElementById('cancelExportButton'),
    exportSettingsButton: document.getElementById('exportSettingsButton'),
    importSettingsInput: document.getElementById('importSettingsInput'),
    preset: document.getElementById('preset'),
    amplitude: document.getElementById('amplitude'),
    speed: document.getElementById('speed'),
    rotation: document.getElementById('rotation'),
    pulse: document.getElementById('pulse'),
    zoom: document.getElementById('zoom'),
    outputSize: document.getElementById('outputSize'),
    duration: document.getElementById('duration'),
    fps: document.getElementById('fps'),
    backgroundMode: document.getElementById('backgroundMode'),
    backgroundColor: document.getElementById('backgroundColor'),
    amplitudeValue: document.getElementById('amplitudeValue'),
    speedValue: document.getElementById('speedValue'),
    rotationValue: document.getElementById('rotationValue'),
    pulseValue: document.getElementById('pulseValue'),
    zoomValue: document.getElementById('zoomValue'),
    frameEstimate: document.getElementById('frameEstimate'),
  };

  const previewContext = elements.canvas.getContext('2d', { alpha: true });
  if (!previewContext) {
    announce('このブラウザではCanvasを利用できません。');
    return;
  }

  function clampNumber(value, minimum, maximum, fallback) {
    const number = Number(value);
    if (!Number.isFinite(number)) return fallback;
    return Math.min(maximum, Math.max(minimum, number));
  }

  function normalizeSettings(candidate) {
    const normalized = {
      preset: ['float', 'bounce', 'shake', 'sway', 'orbit', 'breathe'].includes(candidate.preset)
        ? candidate.preset
        : defaults.preset,
      amplitude: clampNumber(candidate.amplitude, 0, 60, defaults.amplitude),
      speed: clampNumber(candidate.speed, 0.2, 2, defaults.speed),
      rotation: clampNumber(candidate.rotation, 0, 18, defaults.rotation),
      pulse: clampNumber(candidate.pulse, 0, 12, defaults.pulse),
      zoom: clampNumber(candidate.zoom, 40, 140, defaults.zoom),
      outputSize: [256, 360, 480].includes(Number(candidate.outputSize))
        ? Number(candidate.outputSize)
        : defaults.outputSize,
      duration: [2, 3, 4, 5, 6].includes(Number(candidate.duration))
        ? Number(candidate.duration)
        : defaults.duration,
      fps: [10, 12, 15].includes(Number(candidate.fps))
        ? Number(candidate.fps)
        : defaults.fps,
      backgroundMode: ['transparent', 'white', 'black', 'green', 'custom'].includes(candidate.backgroundMode)
        ? candidate.backgroundMode
        : defaults.backgroundMode,
      backgroundColor: /^#[0-9a-f]{6}$/i.test(String(candidate.backgroundColor || ''))
        ? String(candidate.backgroundColor)
        : defaults.backgroundColor,
      flip: Boolean(candidate.flip),
      offsetX: clampNumber(candidate.offsetX, -480, 480, 0),
      offsetY: clampNumber(candidate.offsetY, -480, 480, 0),
    };
    return normalized;
  }

  function loadSavedSettings() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return false;
      const parsed = JSON.parse(raw);
      if (parsed.version !== SETTINGS_VERSION || typeof parsed.settings !== 'object') return false;
      Object.assign(settings, normalizeSettings(parsed.settings));
      return true;
    } catch {
      return false;
    }
  }

  function saveSettings() {
    try {
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({ version: SETTINGS_VERSION, settings: { ...settings } }),
      );
    } catch {
      // Storage can be unavailable in private browsing or local-file mode.
    }
  }

  function applySettingsToControls() {
    elements.preset.value = settings.preset;
    elements.amplitude.value = String(settings.amplitude);
    elements.speed.value = String(settings.speed);
    elements.rotation.value = String(settings.rotation);
    elements.pulse.value = String(settings.pulse);
    elements.zoom.value = String(settings.zoom);
    elements.outputSize.value = String(settings.outputSize);
    elements.duration.value = String(settings.duration);
    elements.fps.value = String(settings.fps);
    elements.backgroundMode.value = settings.backgroundMode;
    elements.backgroundColor.value = settings.backgroundColor;
    elements.backgroundColor.disabled = settings.backgroundMode !== 'custom';
    elements.flipButton.setAttribute('aria-pressed', String(settings.flip));
    elements.flipButton.textContent = settings.flip ? '左右反転を戻す' : '左右反転';
    updateValueLabels();
    resizePreviewCanvas();
  }

  function readControlsIntoSettings() {
    Object.assign(
      settings,
      normalizeSettings({
        ...settings,
        preset: elements.preset.value,
        amplitude: elements.amplitude.value,
        speed: elements.speed.value,
        rotation: elements.rotation.value,
        pulse: elements.pulse.value,
        zoom: elements.zoom.value,
        outputSize: elements.outputSize.value,
        duration: elements.duration.value,
        fps: elements.fps.value,
        backgroundMode: elements.backgroundMode.value,
        backgroundColor: elements.backgroundColor.value,
      }),
    );
    elements.backgroundColor.disabled = settings.backgroundMode !== 'custom';
    updateValueLabels();
    resizePreviewCanvas();
    saveSettings();
    renderPreview();
  }

  function updateValueLabels() {
    elements.amplitudeValue.textContent = `${Math.round(settings.amplitude)} px`;
    elements.speedValue.textContent = `${settings.speed.toFixed(2)} 回毎秒`;
    elements.rotationValue.textContent = `${Math.round(settings.rotation)} 度`;
    elements.pulseValue.textContent = `${Math.round(settings.pulse)} パーセント`;
    elements.zoomValue.textContent = `${Math.round(settings.zoom)} パーセント`;
    const frames = settings.duration * settings.fps;
    const megapixels = (settings.outputSize * settings.outputSize * frames) / 1_000_000;
    elements.frameEstimate.textContent = `${frames} フレーム、処理量の目安 ${megapixels.toFixed(1)} メガピクセル`;
  }

  function announce(message) {
    elements.status.textContent = message;
  }

  function setProgress(value, message) {
    elements.progress.value = value;
    elements.progress.textContent = `${Math.round(value)}%`;
    elements.progress.setAttribute('aria-valuenow', String(Math.round(value)));
    if (message) announce(message);
  }

  function resizePreviewCanvas() {
    const size = settings.outputSize;
    if (elements.canvas.width !== size || elements.canvas.height !== size) {
      elements.canvas.width = size;
      elements.canvas.height = size;
    }
  }

  function backgroundColor() {
    switch (settings.backgroundMode) {
      case 'white':
        return '#ffffff';
      case 'black':
        return '#000000';
      case 'green':
        return '#00b140';
      case 'custom':
        return settings.backgroundColor;
      default:
        return null;
    }
  }

  function motionAt(seconds) {
    const phase = seconds * settings.speed * Math.PI * 2;
    const amplitude = settings.amplitude;
    const rotationRadians = (settings.rotation * Math.PI) / 180;
    const pulse = settings.pulse / 100;
    const motion = { x: 0, y: 0, rotation: 0, scale: 1 };

    switch (settings.preset) {
      case 'bounce':
        motion.y = -Math.abs(Math.sin(phase)) * amplitude;
        motion.rotation = Math.sin(phase) * rotationRadians * 0.2;
        break;
      case 'shake':
        motion.x = Math.sin(phase * 4) * amplitude * 0.55;
        motion.y = Math.cos(phase * 3) * amplitude * 0.12;
        motion.rotation = Math.sin(phase * 4) * rotationRadians;
        break;
      case 'sway':
        motion.x = Math.sin(phase) * amplitude * 0.25;
        motion.rotation = Math.sin(phase) * rotationRadians;
        break;
      case 'orbit':
        motion.x = Math.cos(phase) * amplitude;
        motion.y = Math.sin(phase) * amplitude;
        motion.rotation = Math.sin(phase) * rotationRadians * 0.35;
        break;
      case 'breathe':
        motion.y = -Math.sin(phase) * amplitude * 0.12;
        motion.scale = 1 + ((Math.sin(phase) + 1) / 2) * pulse;
        break;
      case 'float':
      default:
        motion.y = Math.sin(phase) * amplitude;
        motion.rotation = Math.sin(phase * 0.5) * rotationRadians * 0.35;
        motion.scale = 1 + ((Math.sin(phase) + 1) / 2) * pulse * 0.35;
        break;
    }

    return motion;
  }

  function drawPlaceholder(context, size) {
    context.save();
    context.fillStyle = '#f4f7fb';
    context.fillRect(0, 0, size, size);
    context.strokeStyle = '#a8b3c2';
    context.lineWidth = Math.max(2, size / 180);
    context.setLineDash([size / 24, size / 36]);
    context.strokeRect(size * 0.12, size * 0.12, size * 0.76, size * 0.76);
    context.setLineDash([]);
    context.fillStyle = '#354052';
    context.textAlign = 'center';
    context.textBaseline = 'middle';
    context.font = `600 ${Math.max(16, size / 18)}px sans-serif`;
    context.fillText('画像を選んでください', size / 2, size / 2);
    context.restore();
  }

  function drawFrame(context, size, seconds) {
    context.save();
    context.clearRect(0, 0, size, size);
    const fill = backgroundColor();
    if (fill) {
      context.fillStyle = fill;
      context.fillRect(0, 0, size, size);
    }

    if (!state.image) {
      drawPlaceholder(context, size);
      context.restore();
      return;
    }

    const motion = motionAt(seconds);
    const fitScale = Math.min(size / state.imageWidth, size / state.imageHeight) * 0.78;
    const scale = fitScale * (settings.zoom / 100) * motion.scale;
    const offsetScale = size / settings.outputSize;
    const centerX = size / 2 + settings.offsetX * offsetScale + motion.x * offsetScale;
    const centerY = size / 2 + settings.offsetY * offsetScale + motion.y * offsetScale;

    context.imageSmoothingEnabled = true;
    context.imageSmoothingQuality = 'high';
    context.translate(centerX, centerY);
    context.rotate(motion.rotation);
    context.scale(settings.flip ? -scale : scale, scale);
    context.drawImage(
      state.image,
      -state.imageWidth / 2,
      -state.imageHeight / 2,
      state.imageWidth,
      state.imageHeight,
    );
    context.restore();
  }

  function currentSeconds() {
    if (!state.playing) return state.pausedSeconds;
    return (performance.now() - state.animationStartedAt) / 1000;
  }

  function renderPreview() {
    drawFrame(previewContext, elements.canvas.width, currentSeconds());
  }

  function previewLoop() {
    if (!state.playing || document.hidden || state.exporting) return;
    renderPreview();
    state.animationFrameId = requestAnimationFrame(previewLoop);
  }

  function startPreview() {
    cancelAnimationFrame(state.animationFrameId);
    if (state.playing && !document.hidden && !state.exporting) {
      state.animationFrameId = requestAnimationFrame(previewLoop);
    } else {
      renderPreview();
    }
  }

  function setPlaying(playing) {
    if (playing === state.playing) return;
    if (playing) {
      state.animationStartedAt = performance.now() - state.pausedSeconds * 1000;
      state.playing = true;
    } else {
      state.pausedSeconds = currentSeconds();
      state.playing = false;
    }
    elements.playButton.textContent = state.playing ? '一時停止' : '再生';
    elements.playButton.setAttribute('aria-pressed', String(!state.playing));
    startPreview();
  }

  async function decodeImage(file) {
    if ('createImageBitmap' in window) {
      try {
        return await createImageBitmap(file, { imageOrientation: 'from-image' });
      } catch {
        // Some browsers reject the optional orientation argument.
        return createImageBitmap(file);
      }
    }

    const objectUrl = URL.createObjectURL(file);
    try {
      const image = new Image();
      image.decoding = 'async';
      image.src = objectUrl;
      if (typeof image.decode === 'function') {
        await image.decode();
      } else {
        await new Promise((resolve, reject) => {
          image.addEventListener('load', resolve, { once: true });
          image.addEventListener('error', reject, { once: true });
        });
      }
      return image;
    } finally {
      URL.revokeObjectURL(objectUrl);
    }
  }

  async function handleImageSelection() {
    const file = elements.imageInput.files && elements.imageInput.files[0];
    elements.imageInput.value = '';
    if (!file) return;

    if (!ALLOWED_IMAGE_TYPES.has(file.type)) {
      announce('PNG、JPEG、WebPだけを選べます。SVGと動画は読み込みません。');
      return;
    }
    if (file.size <= 0 || file.size > MAX_FILE_BYTES) {
      announce('画像は15MB以下にしてください。');
      return;
    }

    announce('画像を端末内で読み込んでいます。');
    try {
      const decoded = await decodeImage(file);
      const width = decoded.width || decoded.naturalWidth;
      const height = decoded.height || decoded.naturalHeight;
      if (
        !Number.isInteger(width)
        || !Number.isInteger(height)
        || width < 1
        || height < 1
        || width > MAX_SOURCE_SIDE
        || height > MAX_SOURCE_SIDE
        || width * height > MAX_SOURCE_PIXELS
      ) {
        if (typeof decoded.close === 'function') decoded.close();
        announce('画像が大きすぎます。縦横8192px以内、合計3200万画素以内にしてください。');
        return;
      }

      if (state.image && typeof state.image.close === 'function') state.image.close();
      state.image = decoded;
      state.imageWidth = width;
      state.imageHeight = height;
      state.sourceName = safeBaseName(file.name);
      settings.offsetX = 0;
      settings.offsetY = 0;
      saveSettings();
      renderPreview();
      announce(`${width}×${height}pxの画像を読み込みました。画像は外部へ送信されません。`);
    } catch {
      announce('画像を読み込めませんでした。別のPNG、JPEG、WebPを試してください。');
    }
  }

  function safeBaseName(fileName) {
    const withoutExtension = String(fileName || 'character').replace(/\.[^.]+$/, '');
    const safe = withoutExtension
      .normalize('NFKC')
      .replace(/[^a-zA-Z0-9_-]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 40);
    return safe || 'character';
  }

  function downloadBlob(blob, fileName) {
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = fileName;
    link.rel = 'noopener';
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
  }

  function canvasToBlob(canvas, type) {
    return new Promise((resolve, reject) => {
      canvas.toBlob((blob) => {
        if (blob) resolve(blob);
        else reject(new Error('Canvas export failed'));
      }, type);
    });
  }

  async function exportPng() {
    if (!state.image || state.exporting) {
      announce('先に画像を選んでください。');
      return;
    }
    try {
      const canvas = document.createElement('canvas');
      canvas.width = settings.outputSize;
      canvas.height = settings.outputSize;
      const context = canvas.getContext('2d', { alpha: true });
      if (!context) throw new Error('Canvas unavailable');
      drawFrame(context, settings.outputSize, currentSeconds());
      const blob = await canvasToBlob(canvas, 'image/png');
      downloadBlob(blob, `${state.sourceName}-frame.png`);
      announce('現在のフレームをPNGで保存しました。');
    } catch {
      announce('PNGを書き出せませんでした。ブラウザの空き容量を確認してください。');
    }
  }

  class WorkerClient {
    constructor() {
      this.worker = new Worker('./gif-worker.js');
      this.sequence = 0;
      this.pending = new Map();
      this.worker.addEventListener('message', (event) => {
        const message = event.data || {};
        const pending = this.pending.get(message.requestId);
        if (!pending) return;
        this.pending.delete(message.requestId);
        if (message.type === 'error') pending.reject(new Error(message.message));
        else pending.resolve(message);
      });
      this.worker.addEventListener('error', () => {
        for (const pending of this.pending.values()) {
          pending.reject(new Error('GIF worker failed'));
        }
        this.pending.clear();
      });
    }

    request(payload, transfer = []) {
      const requestId = ++this.sequence;
      return new Promise((resolve, reject) => {
        this.pending.set(requestId, { resolve, reject });
        this.worker.postMessage({ requestId, ...payload }, transfer);
      });
    }

    terminate() {
      this.worker.terminate();
      for (const pending of this.pending.values()) {
        pending.reject(new Error('GIF worker terminated'));
      }
      this.pending.clear();
    }
  }

  function nextPaint() {
    return new Promise((resolve) => requestAnimationFrame(() => resolve()));
  }

  async function encodeGifInWorker(exportCanvas, context, frameCount, delayCentiseconds, transparent) {
    const client = new WorkerClient();
    const token = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    try {
      await client.request({
        action: 'start',
        token,
        width: exportCanvas.width,
        height: exportCanvas.height,
        transparent,
      });

      for (let frameIndex = 0; frameIndex < frameCount; frameIndex += 1) {
        if (state.exportCancelled) throw new DOMException('Export cancelled', 'AbortError');
        drawFrame(context, exportCanvas.width, frameIndex / settings.fps);
        const rgba = context.getImageData(0, 0, exportCanvas.width, exportCanvas.height).data;
        await client.request(
          {
            action: 'frame',
            token,
            frameIndex,
            delayCentiseconds,
            rgbaBuffer: rgba.buffer,
          },
          [rgba.buffer],
        );
        setProgress(((frameIndex + 1) / frameCount) * 92, `GIFを生成中です。${frameIndex + 1}/${frameCount}フレーム`);
      }

      const result = await client.request({ action: 'finish', token });
      return new Uint8Array(result.bytesBuffer);
    } finally {
      client.terminate();
    }
  }

  async function encodeGifOnMainThread(exportCanvas, context, frameCount, delayCentiseconds, transparent) {
    const encoder = new window.GifEncoder(exportCanvas.width, exportCanvas.height, {
      loop: 0,
      transparent,
    });

    for (let frameIndex = 0; frameIndex < frameCount; frameIndex += 1) {
      if (state.exportCancelled) throw new DOMException('Export cancelled', 'AbortError');
      drawFrame(context, exportCanvas.width, frameIndex / settings.fps);
      const rgba = context.getImageData(0, 0, exportCanvas.width, exportCanvas.height).data;
      encoder.addFrame(window.GifEncoder.quantizeRgba(rgba), delayCentiseconds);
      setProgress(((frameIndex + 1) / frameCount) * 92, `互換モードでGIFを生成中です。${frameIndex + 1}/${frameCount}フレーム`);
      if (frameIndex % 2 === 1) await nextPaint();
    }

    return encoder.finish();
  }

  function setExporting(exporting) {
    state.exporting = exporting;
    const controls = document.querySelectorAll('button, input, select');
    for (const control of controls) {
      if (control === elements.cancelExportButton) continue;
      control.disabled = exporting;
    }
    elements.cancelExportButton.hidden = !exporting;
    elements.cancelExportButton.disabled = false;
    if (!exporting) {
      elements.backgroundColor.disabled = settings.backgroundMode !== 'custom';
    }
    startPreview();
  }

  async function exportGif() {
    if (!state.image || state.exporting) {
      announce('先に画像を選んでください。');
      return;
    }

    const frameCount = settings.duration * settings.fps;
    const pixelBudget = settings.outputSize * settings.outputSize * frameCount;
    if (pixelBudget > EXPORT_FRAME_BUDGET) {
      announce('この設定は端末への負荷が高すぎます。サイズ、時間、フレーム数を下げてください。');
      return;
    }

    state.exportCancelled = false;
    setExporting(true);
    setProgress(0, 'GIFの準備をしています。');

    const exportCanvas = document.createElement('canvas');
    exportCanvas.width = settings.outputSize;
    exportCanvas.height = settings.outputSize;
    const context = exportCanvas.getContext('2d', { alpha: true, willReadFrequently: true });
    if (!context) {
      setExporting(false);
      announce('このブラウザではGIFを書き出せません。');
      return;
    }

    const delayCentiseconds = Math.max(1, Math.round(100 / settings.fps));
    const transparent = settings.backgroundMode === 'transparent';

    try {
      let bytes;
      if (typeof Worker === 'function' && location.protocol !== 'file:') {
        try {
          bytes = await encodeGifInWorker(
            exportCanvas,
            context,
            frameCount,
            delayCentiseconds,
            transparent,
          );
        } catch (error) {
          if (error instanceof DOMException && error.name === 'AbortError') throw error;
          setProgress(0, '省メモリ互換モードに切り替えています。');
          await nextPaint();
          bytes = await encodeGifOnMainThread(
            exportCanvas,
            context,
            frameCount,
            delayCentiseconds,
            transparent,
          );
        }
      } else {
        bytes = await encodeGifOnMainThread(
          exportCanvas,
          context,
          frameCount,
          delayCentiseconds,
          transparent,
        );
      }

      if (state.exportCancelled) throw new DOMException('Export cancelled', 'AbortError');
      setProgress(98, 'GIFファイルをまとめています。');
      const blob = new Blob([bytes], { type: 'image/gif' });
      downloadBlob(blob, `${state.sourceName}-${settings.preset}.gif`);
      setProgress(100, `GIFを保存しました。ファイルサイズは約${(blob.size / 1024 / 1024).toFixed(1)}MBです。`);
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        setProgress(0, 'GIF生成を中止しました。設定と画像は残っています。');
      } else {
        setProgress(0, 'GIFを生成できませんでした。サイズか時間を下げて再度試してください。');
      }
    } finally {
      setExporting(false);
    }
  }

  function exportSettings() {
    const payload = {
      tool: 'Suzuko Character Animator',
      version: SETTINGS_VERSION,
      settings: { ...settings },
    };
    const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], { type: 'application/json' });
    downloadBlob(blob, 'character-animation-settings.json');
    announce('設定ファイルを保存しました。画像データは含まれません。');
  }

  async function importSettings() {
    const file = elements.importSettingsInput.files && elements.importSettingsInput.files[0];
    elements.importSettingsInput.value = '';
    if (!file) return;
    if (file.size <= 0 || file.size > 64 * 1024) {
      announce('設定ファイルは64KB以下のJSONを選んでください。');
      return;
    }
    try {
      const parsed = JSON.parse(await file.text());
      if (parsed.version !== SETTINGS_VERSION || typeof parsed.settings !== 'object') {
        throw new Error('Unsupported settings');
      }
      Object.assign(settings, normalizeSettings(parsed.settings));
      applySettingsToControls();
      saveSettings();
      renderPreview();
      announce('設定を読み込みました。画像はもう一度選んでください。');
    } catch {
      announce('設定ファイルを読み込めませんでした。書き出したJSONか確認してください。');
    }
  }

  function resetSettings() {
    Object.assign(settings, defaults);
    state.pausedSeconds = 0;
    state.animationStartedAt = performance.now();
    applySettingsToControls();
    saveSettings();
    renderPreview();
    announce('設定を初期値へ戻しました。読み込んだ画像は残っています。');
  }

  function centerImage() {
    settings.offsetX = 0;
    settings.offsetY = 0;
    saveSettings();
    renderPreview();
    announce('画像を中央へ戻しました。');
  }

  function toggleFlip() {
    settings.flip = !settings.flip;
    elements.flipButton.setAttribute('aria-pressed', String(settings.flip));
    elements.flipButton.textContent = settings.flip ? '左右反転を戻す' : '左右反転';
    saveSettings();
    renderPreview();
  }

  function pointerCoordinates(event) {
    const rectangle = elements.canvas.getBoundingClientRect();
    return {
      x: (event.clientX - rectangle.left) * (elements.canvas.width / rectangle.width),
      y: (event.clientY - rectangle.top) * (elements.canvas.height / rectangle.height),
    };
  }

  function handlePointerDown(event) {
    if (!state.image || state.exporting || event.button !== 0) return;
    const point = pointerCoordinates(event);
    state.pointer = {
      id: event.pointerId,
      x: point.x,
      y: point.y,
      offsetX: settings.offsetX,
      offsetY: settings.offsetY,
    };
    elements.canvas.setPointerCapture(event.pointerId);
  }

  function handlePointerMove(event) {
    if (!state.pointer || state.pointer.id !== event.pointerId) return;
    const point = pointerCoordinates(event);
    settings.offsetX = clampNumber(
      state.pointer.offsetX + point.x - state.pointer.x,
      -settings.outputSize,
      settings.outputSize,
      0,
    );
    settings.offsetY = clampNumber(
      state.pointer.offsetY + point.y - state.pointer.y,
      -settings.outputSize,
      settings.outputSize,
      0,
    );
    renderPreview();
  }

  function handlePointerUp(event) {
    if (!state.pointer || state.pointer.id !== event.pointerId) return;
    state.pointer = null;
    saveSettings();
  }

  function handleCanvasKeydown(event) {
    if (!state.image || state.exporting) return;
    const step = event.shiftKey ? 10 : 2;
    let handled = true;
    switch (event.key) {
      case 'ArrowLeft':
        settings.offsetX -= step;
        break;
      case 'ArrowRight':
        settings.offsetX += step;
        break;
      case 'ArrowUp':
        settings.offsetY -= step;
        break;
      case 'ArrowDown':
        settings.offsetY += step;
        break;
      default:
        handled = false;
    }
    if (!handled) return;
    event.preventDefault();
    settings.offsetX = clampNumber(settings.offsetX, -settings.outputSize, settings.outputSize, 0);
    settings.offsetY = clampNumber(settings.offsetY, -settings.outputSize, settings.outputSize, 0);
    saveSettings();
    renderPreview();
  }

  function bindEvents() {
    elements.imageInput.addEventListener('change', handleImageSelection);
    for (const control of [
      elements.preset,
      elements.amplitude,
      elements.speed,
      elements.rotation,
      elements.pulse,
      elements.zoom,
      elements.outputSize,
      elements.duration,
      elements.fps,
      elements.backgroundMode,
      elements.backgroundColor,
    ]) {
      control.addEventListener('input', readControlsIntoSettings);
      control.addEventListener('change', readControlsIntoSettings);
    }

    elements.playButton.addEventListener('click', () => setPlaying(!state.playing));
    elements.centerButton.addEventListener('click', centerImage);
    elements.flipButton.addEventListener('click', toggleFlip);
    elements.resetButton.addEventListener('click', resetSettings);
    elements.exportGifButton.addEventListener('click', exportGif);
    elements.exportPngButton.addEventListener('click', exportPng);
    elements.cancelExportButton.addEventListener('click', () => {
      state.exportCancelled = true;
      elements.cancelExportButton.disabled = true;
      announce('中止処理を行っています。');
    });
    elements.exportSettingsButton.addEventListener('click', exportSettings);
    elements.importSettingsInput.addEventListener('change', importSettings);

    elements.canvas.addEventListener('pointerdown', handlePointerDown);
    elements.canvas.addEventListener('pointermove', handlePointerMove);
    elements.canvas.addEventListener('pointerup', handlePointerUp);
    elements.canvas.addEventListener('pointercancel', handlePointerUp);
    elements.canvas.addEventListener('keydown', handleCanvasKeydown);

    document.addEventListener('visibilitychange', () => {
      if (document.hidden) {
        state.resumeAfterVisibility = state.playing;
        cancelAnimationFrame(state.animationFrameId);
      } else if (state.resumeAfterVisibility) {
        state.animationStartedAt = performance.now() - state.pausedSeconds * 1000;
        startPreview();
      }
    });
  }

  function registerServiceWorker() {
    if (!('serviceWorker' in navigator)) return;
    if (!['https:', 'http:'].includes(location.protocol)) return;
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('./sw.js').catch(() => {
        // The tool remains usable online when offline installation is unavailable.
      });
    });
  }

  const hadSavedSettings = loadSavedSettings();
  if (!hadSavedSettings && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    state.playing = false;
  }
  applySettingsToControls();
  elements.playButton.textContent = state.playing ? '一時停止' : '再生';
  elements.playButton.setAttribute('aria-pressed', String(!state.playing));
  bindEvents();
  renderPreview();
  startPreview();
  registerServiceWorker();

  if (location.protocol === 'file:') {
    announce('ローカルモードです。GIFは互換モードで処理します。画像は端末外へ送信されません。');
  } else if (!state.playing) {
    announce('端末の動きを減らす設定に合わせ、プレビューを停止しています。');
  }
})();
