import '@testing-library/jest-dom';
import { randomUUID } from 'crypto';
import { TextDecoder, TextEncoder } from 'util';

// Polyfill ResizeObserver for jsdom test environment
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
};

// Polyfill crypto.randomUUID for jsdom test environment
if (!global.crypto) {
  (global as any).crypto = {};
}
if (!(global.crypto as any).randomUUID) {
  (global.crypto as any).randomUUID = randomUUID;
}

// jsdom does not expose TextEncoder/TextDecoder, but the `docx` package
// used by the Word-export utility needs them to pack a Document into a Blob.
// Polyfill from Node's built-in `util` module.
if (typeof (globalThis as any).TextEncoder === 'undefined') {
  (globalThis as any).TextEncoder = TextEncoder;
}
if (typeof (globalThis as any).TextDecoder === 'undefined') {
  (globalThis as any).TextDecoder = TextDecoder;
}

// jsdom 16 ships a Blob without .arrayBuffer() — polyfill via FileReader so
// JSZip (and any other binary consumer) can read docx Blobs in tests.
if (typeof Blob !== 'undefined' && typeof Blob.prototype.arrayBuffer !== 'function') {
  (Blob.prototype as any).arrayBuffer = function arrayBuffer(this: Blob): Promise<ArrayBuffer> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result as ArrayBuffer);
      reader.onerror = () => reject(reader.error);
      reader.readAsArrayBuffer(this);
    });
  };
}
