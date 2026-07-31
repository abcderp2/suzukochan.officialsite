import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const encoderPath = new URL('../tools/character-animator/gif-encoder.js', import.meta.url);
vm.runInThisContext(fs.readFileSync(encoderPath, 'utf8'), { filename: encoderPath.pathname });

assert.equal(typeof globalThis.GifEncoder, 'function');

const width = 32;
const height = 24;
const expectedFrames = [];
const encoder = new globalThis.GifEncoder(width, height, { loop: 0, transparent: true });

for (let frameNumber = 0; frameNumber < 3; frameNumber += 1) {
  const rgba = new Uint8ClampedArray(width * height * 4);
  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const offset = (y * width + x) * 4;
      rgba[offset] = (x * 17 + frameNumber * 41) % 256;
      rgba[offset + 1] = (y * 23 + frameNumber * 19) % 256;
      rgba[offset + 2] = ((x + y) * 11 + frameNumber * 29) % 256;
      rgba[offset + 3] = (x + y + frameNumber) % 9 === 0 ? 0 : 255;
    }
  }
  const indexes = globalThis.GifEncoder.quantizeRgba(rgba);
  expectedFrames.push(indexes);
  encoder.addFrame(indexes, 7);
}

const bytes = encoder.finish();
assert.equal(new TextDecoder().decode(bytes.subarray(0, 6)), 'GIF89a');
assert.equal(bytes.at(-1), 0x3b);
assert.ok(bytes.length > 1000);

function readUint16(data, offset) {
  return data[offset] | (data[offset + 1] << 8);
}

function readSubBlocks(data, state) {
  const parts = [];
  let total = 0;
  while (true) {
    const size = data[state.offset];
    state.offset += 1;
    if (size === 0) break;
    const part = data.subarray(state.offset, state.offset + size);
    state.offset += size;
    parts.push(part);
    total += part.length;
  }
  const result = new Uint8Array(total);
  let target = 0;
  for (const part of parts) {
    result.set(part, target);
    target += part.length;
  }
  return result;
}

function lzwDecode(data, minimumCodeSize, pixelCount) {
  const clearCode = 1 << minimumCodeSize;
  const endCode = clearCode + 1;
  let codeSize = minimumCodeSize + 1;
  let nextCode = endCode + 1;
  let bitOffset = 0;
  let dictionary = [];

  const reset = () => {
    dictionary = Array.from({ length: clearCode }, (_, index) => Uint8Array.of(index));
    dictionary[clearCode] = null;
    dictionary[endCode] = null;
    codeSize = minimumCodeSize + 1;
    nextCode = endCode + 1;
  };

  const readCode = () => {
    let value = 0;
    for (let bit = 0; bit < codeSize; bit += 1) {
      const absoluteBit = bitOffset + bit;
      value |= ((data[absoluteBit >>> 3] >>> (absoluteBit & 7)) & 1) << bit;
    }
    bitOffset += codeSize;
    return value;
  };

  reset();
  const output = [];
  let previous = null;

  while (bitOffset + codeSize <= data.length * 8) {
    const code = readCode();
    if (code === clearCode) {
      reset();
      previous = null;
      continue;
    }
    if (code === endCode) break;

    let entry;
    if (code < dictionary.length && dictionary[code]) {
      entry = dictionary[code];
    } else if (code === nextCode && previous) {
      entry = new Uint8Array(previous.length + 1);
      entry.set(previous);
      entry[entry.length - 1] = previous[0];
    } else {
      throw new Error(`Invalid LZW code ${code} at dictionary size ${nextCode}`);
    }

    for (const value of entry) output.push(value);

    if (previous && nextCode < 4096) {
      const addition = new Uint8Array(previous.length + 1);
      addition.set(previous);
      addition[addition.length - 1] = entry[0];
      dictionary[nextCode] = addition;
      nextCode += 1;
      if (nextCode === 1 << codeSize && codeSize < 12) codeSize += 1;
    }

    previous = entry;
    if (output.length >= pixelCount) break;
  }

  return Uint8Array.from(output.slice(0, pixelCount));
}

const state = { offset: 6 };
assert.equal(readUint16(bytes, state.offset), width);
state.offset += 2;
assert.equal(readUint16(bytes, state.offset), height);
state.offset += 2;
const packed = bytes[state.offset];
state.offset += 3;
if (packed & 0x80) {
  state.offset += 3 * (1 << ((packed & 0x07) + 1));
}

const decodedFrames = [];
while (state.offset < bytes.length) {
  const introducer = bytes[state.offset];
  state.offset += 1;
  if (introducer === 0x3b) break;
  if (introducer === 0x21) {
    state.offset += 1;
    readSubBlocks(bytes, state);
    continue;
  }
  assert.equal(introducer, 0x2c);
  state.offset += 8;
  const imagePacked = bytes[state.offset];
  state.offset += 1;
  if (imagePacked & 0x80) {
    state.offset += 3 * (1 << ((imagePacked & 0x07) + 1));
  }
  const minimumCodeSize = bytes[state.offset];
  state.offset += 1;
  const compressed = readSubBlocks(bytes, state);
  decodedFrames.push(lzwDecode(compressed, minimumCodeSize, width * height));
}

assert.equal(decodedFrames.length, expectedFrames.length);
for (let index = 0; index < decodedFrames.length; index += 1) {
  assert.deepEqual(decodedFrames[index], expectedFrames[index]);
}

fs.writeFileSync('/tmp/gif-encoder-test.gif', bytes);
console.log(`GIF encoder test passed: ${decodedFrames.length} frames, ${bytes.length} bytes`);
