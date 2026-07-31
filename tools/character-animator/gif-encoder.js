(function attachGifEncoder(globalScope) {
  'use strict';

  const MAX_GIF_SIDE = 512;
  const MAX_GIF_PIXELS = MAX_GIF_SIDE * MAX_GIF_SIDE;

  function assertInteger(value, name, minimum, maximum) {
    if (!Number.isInteger(value) || value < minimum || value > maximum) {
      throw new RangeError(`${name} must be an integer from ${minimum} to ${maximum}`);
    }
  }

  function pushUint16(target, value) {
    target.push(value & 0xff, (value >>> 8) & 0xff);
  }

  function createPalette() {
    const palette = new Uint8Array(256 * 3);
    let index = 1;

    for (let red = 0; red < 6; red += 1) {
      for (let green = 0; green < 6; green += 1) {
        for (let blue = 0; blue < 6; blue += 1) {
          const offset = index * 3;
          palette[offset] = red * 51;
          palette[offset + 1] = green * 51;
          palette[offset + 2] = blue * 51;
          index += 1;
        }
      }
    }

    for (let gray = 0; gray < 39; gray += 1) {
      const value = Math.round((gray * 255) / 38);
      const offset = (217 + gray) * 3;
      palette[offset] = value;
      palette[offset + 1] = value;
      palette[offset + 2] = value;
    }

    return palette;
  }

  const GLOBAL_PALETTE = createPalette();

  class BitWriter {
    constructor() {
      this.bytes = [];
      this.buffer = 0;
      this.bitCount = 0;
    }

    write(code, width) {
      this.buffer |= code << this.bitCount;
      this.bitCount += width;

      while (this.bitCount >= 8) {
        this.bytes.push(this.buffer & 0xff);
        this.buffer >>>= 8;
        this.bitCount -= 8;
      }
    }

    finish() {
      if (this.bitCount > 0) {
        this.bytes.push(this.buffer & 0xff);
      }
      return Uint8Array.from(this.bytes);
    }
  }

  function lzwEncode(indexes, minimumCodeSize) {
    const clearCode = 1 << minimumCodeSize;
    const endCode = clearCode + 1;
    const codeSize = minimumCodeSize + 1;
    const writer = new BitWriter();
    const literalsPerBlock = 250;

    writer.write(clearCode, codeSize);
    let literalsSinceClear = 0;

    for (let position = 0; position < indexes.length; position += 1) {
      writer.write(indexes[position], codeSize);
      literalsSinceClear += 1;

      if (literalsSinceClear === literalsPerBlock && position + 1 < indexes.length) {
        writer.write(clearCode, codeSize);
        literalsSinceClear = 0;
      }
    }

    writer.write(endCode, codeSize);
    return writer.finish();
  }

  function quantizeRgba(rgba) {
    if (!(rgba instanceof Uint8ClampedArray) && !(rgba instanceof Uint8Array)) {
      throw new TypeError('RGBA data must be a Uint8ClampedArray or Uint8Array');
    }
    if (rgba.length % 4 !== 0) {
      throw new RangeError('RGBA data length must be divisible by 4');
    }

    const indexes = new Uint8Array(rgba.length / 4);

    for (let source = 0, target = 0; source < rgba.length; source += 4, target += 1) {
      const alpha = rgba[source + 3];
      if (alpha < 128) {
        indexes[target] = 0;
        continue;
      }

      const red = rgba[source];
      const green = rgba[source + 1];
      const blue = rgba[source + 2];
      const maximum = Math.max(red, green, blue);
      const minimum = Math.min(red, green, blue);

      if (maximum - minimum <= 18) {
        const luminance = Math.round(red * 0.2126 + green * 0.7152 + blue * 0.0722);
        indexes[target] = 217 + Math.round((luminance * 38) / 255);
      } else {
        const redLevel = Math.round(red / 51);
        const greenLevel = Math.round(green / 51);
        const blueLevel = Math.round(blue / 51);
        indexes[target] = 1 + redLevel * 36 + greenLevel * 6 + blueLevel;
      }
    }

    return indexes;
  }

  class GifEncoder {
    constructor(width, height, options = {}) {
      assertInteger(width, 'width', 1, MAX_GIF_SIDE);
      assertInteger(height, 'height', 1, MAX_GIF_SIDE);
      if (width * height > MAX_GIF_PIXELS) {
        throw new RangeError('GIF frame exceeds the pixel budget');
      }

      this.width = width;
      this.height = height;
      this.loop = options.loop === undefined ? 0 : options.loop;
      this.transparent = options.transparent !== false;
      assertInteger(this.loop, 'loop', 0, 65535);
      this.chunks = [];
      this.frameCount = 0;
      this.finished = false;
      this.writeHeader();
    }

    writeHeader() {
      const bytes = [];
      for (const character of 'GIF89a') {
        bytes.push(character.charCodeAt(0));
      }
      pushUint16(bytes, this.width);
      pushUint16(bytes, this.height);
      bytes.push(0xf7, 0x00, 0x00);
      this.chunks.push(Uint8Array.from(bytes), GLOBAL_PALETTE);

      const loop = [];
      loop.push(0x21, 0xff, 0x0b);
      for (const character of 'NETSCAPE2.0') {
        loop.push(character.charCodeAt(0));
      }
      loop.push(0x03, 0x01);
      pushUint16(loop, this.loop);
      loop.push(0x00);
      this.chunks.push(Uint8Array.from(loop));
    }

    addFrame(indexes, delayCentiseconds) {
      if (this.finished) {
        throw new Error('Cannot add a frame after finish');
      }
      if (!(indexes instanceof Uint8Array)) {
        throw new TypeError('Frame indexes must be a Uint8Array');
      }
      if (indexes.length !== this.width * this.height) {
        throw new RangeError('Frame index count does not match GIF dimensions');
      }
      assertInteger(delayCentiseconds, 'delayCentiseconds', 1, 65535);

      const control = [0x21, 0xf9, 0x04, this.transparent ? 0x09 : 0x08];
      pushUint16(control, delayCentiseconds);
      control.push(0x00, 0x00);
      this.chunks.push(Uint8Array.from(control));

      const descriptor = [0x2c, 0x00, 0x00, 0x00, 0x00];
      pushUint16(descriptor, this.width);
      pushUint16(descriptor, this.height);
      descriptor.push(0x00);
      this.chunks.push(Uint8Array.from(descriptor));

      const compressed = lzwEncode(indexes, 8);
      this.chunks.push(Uint8Array.of(0x08));
      for (let offset = 0; offset < compressed.length; offset += 255) {
        const block = compressed.subarray(offset, Math.min(offset + 255, compressed.length));
        this.chunks.push(Uint8Array.of(block.length), block);
      }
      this.chunks.push(Uint8Array.of(0x00));
      this.frameCount += 1;
    }

    finish() {
      if (this.finished) {
        throw new Error('GIF has already been finished');
      }
      if (this.frameCount === 0) {
        throw new Error('GIF must contain at least one frame');
      }
      this.finished = true;
      this.chunks.push(Uint8Array.of(0x3b));

      const length = this.chunks.reduce((total, chunk) => total + chunk.length, 0);
      const result = new Uint8Array(length);
      let offset = 0;
      for (const chunk of this.chunks) {
        result.set(chunk, offset);
        offset += chunk.length;
      }
      return result;
    }

    static quantizeRgba(rgba) {
      return quantizeRgba(rgba);
    }
  }

  globalScope.GifEncoder = GifEncoder;
})(typeof self !== 'undefined' ? self : globalThis);
