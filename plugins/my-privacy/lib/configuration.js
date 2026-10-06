import { createPrivacy } from './privacy.js';

export const MAX_CONFIG_CHARS = 262144;

function fail(code) {
  const error = new Error(`Privacy configuration: ${code}`);
  error.code = code;
  throw error;
}

// Pure parser: filesystem location, permissions, and missing-file behavior are
// owned by the host integration. Validation errors never echo input contents.
export function parseMappings(text, options = {}) {
  if (!options || typeof options !== 'object' || Array.isArray(options) ||
      Object.keys(options).some(key => key !== 'maxChars')) fail('INVALID_CONFIG');
  const limit = options.maxChars === undefined ? MAX_CONFIG_CHARS : options.maxChars;
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > MAX_CONFIG_CHARS || typeof text !== 'string') fail('INVALID_CONFIG');
  if (text.length > limit) fail('SIZE_LIMIT');
  let value;
  try { value = JSON.parse(text); }
  catch { fail('INVALID_JSON'); }
  if (!value || typeof value !== 'object' || Array.isArray(value) ||
      Object.keys(value).some(key => key !== 'mappings') || !Array.isArray(value.mappings)) fail('INVALID_CONFIG');
  createPrivacy({ mappings: value.mappings });
  // Reproject to this documented schema instead of exporting arbitrary JSON.
  return value.mappings.map(entry => ({
    from: entry.from, to: entry.to,
    ...(entry.casePairs === undefined ? {} : { casePairs: entry.casePairs.map(pair => ({ from: pair.from, to: pair.to })) }),
  }));
}
