'use strict';

importScripts('./gif-encoder.js');

let encoder = null;
let exportToken = '';

function reply(requestId, payload, transfer = []) {
  self.postMessage({ requestId, ...payload }, transfer);
}

self.addEventListener('message', (event) => {
  const message = event.data || {};
  const requestId = message.requestId;

  try {
    if (message.action === 'start') {
      exportToken = String(message.token || '');
      encoder = new self.GifEncoder(message.width, message.height, {
        loop: 0,
        transparent: Boolean(message.transparent),
      });
      reply(requestId, { type: 'started' });
      return;
    }

    if (!encoder || String(message.token || '') !== exportToken) {
      throw new Error('GIF export session is not active');
    }

    if (message.action === 'frame') {
      const rgba = new Uint8ClampedArray(message.rgbaBuffer);
      const indexes = self.GifEncoder.quantizeRgba(rgba);
      encoder.addFrame(indexes, message.delayCentiseconds);
      reply(requestId, { type: 'frame-added', frameIndex: message.frameIndex });
      return;
    }

    if (message.action === 'finish') {
      const bytes = encoder.finish();
      encoder = null;
      exportToken = '';
      reply(requestId, { type: 'finished', bytesBuffer: bytes.buffer }, [bytes.buffer]);
      return;
    }

    if (message.action === 'cancel') {
      encoder = null;
      exportToken = '';
      reply(requestId, { type: 'cancelled' });
      return;
    }

    throw new Error('Unknown GIF worker action');
  } catch (error) {
    encoder = null;
    exportToken = '';
    reply(requestId, {
      type: 'error',
      message: error instanceof Error ? error.message : 'GIF worker failed',
    });
  }
});
