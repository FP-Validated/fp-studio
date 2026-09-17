import { createHash } from 'node:crypto';
export const MAX_PIXELS = 16_000_000;
export function validateInput(value, depth = 0) {
  if (depth > 64) throw Error('JSON nesting exceeds 64');
  if (typeof value === 'number' && (!Number.isFinite(value) || Math.abs(value) > Number.MAX_SAFE_INTEGER)) throw Error('Unsafe number');
  if (Array.isArray(value)) {
    if (value.length > 10000) throw Error('Too many items');
    value.forEach(v => validateInput(v, depth + 1));
  } else if (value && typeof value === 'object') {
    for (const [k,v] of Object.entries(value)) {
      if (['__proto__','constructor','prototype'].includes(k)) throw Error('Unsafe key');
      validateInput(v, depth + 1);
    }
  } else if (!['string','number','boolean'].includes(typeof value) && value !== null) throw Error('Not JSON');
}
// Recursively sort ALL object keys. An array replacer silently omits nested keys and
// cannot be used for a content hash. This representation is local to the JS worker.
export function stableStringify(value) {
  validateInput(value);
  function emit(v) {
    if (Array.isArray(v)) return '[' + v.map(emit).join(',') + ']';
    if (v && typeof v === 'object') return '{' + Object.keys(v).sort().map(k => JSON.stringify(k) + ':' + emit(v[k])).join(',') + '}';
    return JSON.stringify(v);
  }
  return emit(value);
}
export const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
export function validateFrame(frame) {
  const { width, height } = frame || {};
  if (!Number.isInteger(width) || !Number.isInteger(height) || width <= 0 || height <= 0 || width > 8192 || height > 16384 || width * height > MAX_PIXELS) {
    throw Error('Frame exceeds the 16-million-pixel budget or has invalid dimensions');
  }
}
export function validateRequest(req) {
  if (!req || !req.input || typeof req.input !== 'object' || Array.isArray(req.input)) throw Error('input must be an object');
  validateInput(req.input);
  if (req.input.theme !== undefined && !/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$/.test(req.input.theme)) throw Error('Invalid theme ID');
}
export function ensureStatic(svg) {
  if (/<(?:script|foreignObject|iframe|image)\b/i.test(svg) || /<!DOCTYPE|<!ENTITY/i.test(svg) || /\bon[a-z]+\s*=/i.test(svg)) throw Error('Active/external SVG is not supported');
  for (const m of svg.matchAll(/(?:href|src)\s*=\s*["']([^"']*)["']/gi)) if (!m[1].startsWith('#')) throw Error('External SVG URL refused');
}
