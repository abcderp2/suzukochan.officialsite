"use strict";

(() => {
  const input = document.getElementById("image-file");
  const button = document.getElementById("process-button");
  const status = document.getElementById("status");
  const download = document.getElementById("download-link");
  const maxBytes = 30 * 1024 * 1024;
  const maxPixels = 40_000_000;
  const supportedTypes = new Map([
    ["image/jpeg", "image/jpeg"],
    ["image/png", "image/png"],
    ["image/webp", "image/webp"]
  ]);
  let downloadUrl = "";

  function setStatus(message, isError = false) {
    status.textContent = message;
    status.dataset.state = isError ? "error" : "normal";
  }

  function fileType(file) {
    if (supportedTypes.has(file.type)) {
      return supportedTypes.get(file.type);
    }

    const name = file.name.toLowerCase();
    if (name.endsWith(".jpg") || name.endsWith(".jpeg")) {
      return "image/jpeg";
    }
    if (name.endsWith(".png")) {
      return "image/png";
    }
    if (name.endsWith(".webp")) {
      return "image/webp";
    }
    return "";
  }

  function loadWithImage(file) {
    const sourceUrl = URL.createObjectURL(file);
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.decoding = "async";
      image.onload = () => {
        URL.revokeObjectURL(sourceUrl);
        resolve(image);
      };
      image.onerror = () => {
        URL.revokeObjectURL(sourceUrl);
        reject(new Error("画像を読み込めませんでした。"));
      };
      image.src = sourceUrl;
    });
  }

  async function loadImage(file) {
    if (typeof window.createImageBitmap === "function") {
      try {
        return await window.createImageBitmap(file, { imageOrientation: "from-image" });
      } catch (error) {
        return loadWithImage(file);
      }
    }
    return loadWithImage(file);
  }

  function canvasBlob(canvas, type) {
    return new Promise((resolve, reject) => {
      canvas.toBlob((blob) => {
        if (blob) {
          resolve(blob);
        } else {
          reject(new Error("処理済み画像を作成できませんでした。"));
        }
      }, type, type === "image/png" ? undefined : 0.92);
    });
  }

  async function processImage() {
    const file = input.files && input.files[0];
    if (!file) {
      setStatus("先に画像を選択してください。", true);
      return;
    }

    const type = fileType(file);
    if (!type) {
      setStatus("JPEG、PNG、WebPだけを使用してください。GIF、動画、HEIC、AVIFは対象外です。", true);
      return;
    }
    if (file.size > maxBytes) {
      setStatus("画像が大きすぎます。30MB以下の画像を使用してください。", true);
      return;
    }

    button.disabled = true;
    download.hidden = true;
    setStatus("端末内で処理しています。しばらくお待ちください。");

    let image;
    try {
      image = await loadImage(file);
      const width = image.width || image.naturalWidth;
      const height = image.height || image.naturalHeight;
      if (!width || !height || width * height > maxPixels) {
        throw new Error("画像の画素数が大きすぎます。4,000万画素以下の画像を使用してください。");
      }

      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const context = canvas.getContext("2d");
      if (!context) {
        throw new Error("画像処理に必要な機能を利用できません。");
      }
      context.drawImage(image, 0, 0, width, height);
      if (typeof image.close === "function") {
        image.close();
      }

      const blob = await canvasBlob(canvas, type);
      if (downloadUrl) {
        URL.revokeObjectURL(downloadUrl);
      }
      downloadUrl = URL.createObjectURL(blob);
      download.href = downloadUrl;
      download.download = file.name;
      download.hidden = false;
      setStatus("処理が完了しました。処理済み画像をダウンロードしてからアップロードしてください。");
    } catch (error) {
      if (image && typeof image.close === "function") {
        image.close();
      }
      setStatus(error instanceof Error ? error.message : "画像を処理できませんでした。", true);
    } finally {
      button.disabled = false;
    }
  }

  input.addEventListener("change", () => {
    download.hidden = true;
    setStatus(input.files && input.files[0]
      ? "画像を選択しました。ボタンを押して個人情報を削除してください。"
      : "画像はまだ選択されていません。");
  });
  button.addEventListener("click", processImage);
  window.addEventListener("pagehide", () => {
    if (downloadUrl) {
      URL.revokeObjectURL(downloadUrl);
    }
  });
})();
