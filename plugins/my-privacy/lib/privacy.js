/* Pure, local-only fixed substitutions. Fixed aliases are reserved protocol words:
 * an unrelated person with an alias name cannot be distinguished automatically.
 * Callers may restore executable tool arguments and display-only assistant reply
 * text, never model-facing messages or persisted session data. No generic PII
 * detection, short-name replacement, or session-dependent token mapping occurs.
 */

// Configuration is injected by the caller; a fresh installation is an identity
// transform and carries no implicit names, organizations, or pseudonyms.
const DEFAULT_MAPPINGS = [];
const LIMITS = { maxChars: 8_000_000, maxNodes: 200_000, maxDepth: 80, maxMappings: 20_000 };
// Legacy placeholders are opaque text. They are neither newly generated nor
// resolved, and matching fixed terms inside a token must not corrupt it.
const LEGACY_TOKEN_PATTERN = /(<PII_[A-Z][A-Z0-9_]*_[0-9]+>)/g;

function fail(code) {
  // Error messages deliberately contain no original input or configuration.
  const error = new Error(`Privacy protection: ${code}`);
  error.code = code;
  throw error;
}
function escapeRegExp(value) { return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }
function caseLike(source, target) {
  if (!/[A-Za-z]/.test(source)) return target;
  if (source === source.toUpperCase()) return target.toUpperCase();
  if (source === source.toLowerCase()) return target.toLowerCase();
  if (source[0] === source[0].toUpperCase() && source.slice(1) === source.slice(1).toLowerCase()) {
    return target[0].toUpperCase() + target.slice(1).toLowerCase();
  }
  return [...target].map((char, index) => /[A-Z]/.test(source[index] || "") ? char.toUpperCase() : char.toLowerCase()).join("");
}

function dataRecord(value, allowedKeys) {
  if (!value || typeof value !== "object" || Array.isArray(value)) fail("INVALID_CONFIG");
  const proto = Object.getPrototypeOf(value);
  if (proto !== Object.prototype && proto !== null) fail("INVALID_CONFIG");
  const result = {};
  for (const key of Object.keys(value)) {
    if (!allowedKeys.includes(key)) fail("INVALID_CONFIG");
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if (!descriptor || !Object.prototype.hasOwnProperty.call(descriptor, "value")) fail("INVALID_CONFIG");
    Object.defineProperty(result, key, { value: descriptor.value, enumerable: true });
  }
  return result;
}

function normalizeMapping(value) {
  const entry = dataRecord(value, ["from", "to", "casePairs"]);
  if (typeof entry.from !== "string" || typeof entry.to !== "string" || !entry.from.trim() || !entry.to.trim() ||
      entry.from.length > 500 || entry.to.length > 500 || entry.from.toLowerCase() === entry.to.toLowerCase() ||
      /<PII_/.test(entry.from + entry.to)) fail("INVALID_CONFIG");
  if (entry.casePairs !== undefined && !Array.isArray(entry.casePairs)) fail("INVALID_CONFIG");
  if ((entry.casePairs || []).length > 32) fail("MAPPING_LIMIT");
  const fromLower = entry.from.toLowerCase(), toLower = entry.to.toLowerCase();
  const forwardCases = new Map(), reverseCases = new Map();
  for (const value of entry.casePairs || []) {
    const pair = dataRecord(value, ["from", "to"]);
    if (typeof pair.from !== "string" || typeof pair.to !== "string" || pair.from.length > 500 || pair.to.length > 500 ||
        pair.from.toLowerCase() !== fromLower || pair.to.toLowerCase() !== toLower) fail("INVALID_CONFIG");
    if (forwardCases.has(pair.from) || reverseCases.has(pair.to)) fail("AMBIGUOUS_CONFIG");
    forwardCases.set(pair.from, pair.to);
    reverseCases.set(pair.to, pair.from);
  }
  return { from: entry.from, to: entry.to, fromLower, toLower, forwardCases, reverseCases };
}

export function createPrivacy(options = {}) {
  options = dataRecord(options, [...Object.keys(LIMITS), "mappings", "extraMappings", "namespace"]);
  const limits = { ...LIMITS };
  for (const key of Object.keys(LIMITS)) {
    if (options[key] !== undefined) {
      if (!Number.isSafeInteger(options[key]) || options[key] < 1 || options[key] > LIMITS[key]) fail("INVALID_CONFIG");
      limits[key] = options[key];
    }
  }
  if (options.mappings !== undefined && !Array.isArray(options.mappings)) fail("INVALID_CONFIG");
  if (options.extraMappings !== undefined && !Array.isArray(options.extraMappings)) fail("INVALID_CONFIG");
  if ((options.mappings || []).length + (options.extraMappings || []).length > 256) fail("MAPPING_LIMIT");
  if (options.namespace !== undefined && (typeof options.namespace !== "string" || !/^[A-Z0-9]{4,32}$/.test(options.namespace))) fail("INVALID_CONFIG");
  // namespace remains an accepted compatibility option; no tokens are created.
  const definitions = [...(options.mappings || DEFAULT_MAPPINGS), ...(options.extraMappings || [])].map(normalizeMapping);
  if (definitions.length > limits.maxMappings) fail("MAPPING_LIMIT");
  for (let left = 0; left < definitions.length; left++) {
    for (let right = 0; right < definitions.length; right++) {
      const a = definitions[left], b = definitions[right];
      if (left !== right && (a.fromLower.includes(b.fromLower) || a.toLower.includes(b.toLower))) fail("AMBIGUOUS_CONFIG");
      if (a.toLower.includes(b.fromLower) || b.fromLower.includes(a.toLower)) fail("AMBIGUOUS_CONFIG");
    }
  }
  const originals = new Map(definitions.map(item => [item.fromLower, item]));
  const aliases = new Map(definitions.map(item => [item.toLower, item]));
  const forwardPattern = definitions.length ? new RegExp(definitions.map(item => escapeRegExp(item.from)).sort((a, b) => b.length - a.length).join("|"), "gi") : null;
  const reversePattern = definitions.length ? new RegExp(definitions.map(item => escapeRegExp(item.to)).sort((a, b) => b.length - a.length).join("|"), "gi") : null;
  function fixed(text, reverse = false, detectOnly = false) {
    if (!definitions.length) return detectOnly ? false : text;
    let detected = false;
    const pattern = reverse ? reversePattern : forwardPattern;
    const lookup = reverse ? aliases : originals;
    const result = text.split(LEGACY_TOKEN_PATTERN).map((segment, index) => {
      if (index % 2 === 1) return segment;
      return segment.replace(pattern, match => {
        detected = true;
        if (detectOnly) return match;
        const definition = lookup.get(match.toLowerCase());
        const casePairs = reverse ? definition.reverseCases : definition.forwardCases;
        return casePairs.get(match) || caseLike(match, reverse ? definition.from : definition.to);
      });
    }).join("");
    return detectOnly ? detected : result;
  }
  function walk(value, transform, inspect = false) {
    let nodes = 0, chars = 0, outputChars = 0, found = false;
    const ancestors = new Set();
    const visitString = input => {
      chars += input.length;
      if (chars > limits.maxChars) fail("SIZE_LIMIT");
      const output = transform(input);
      if (inspect) { found = found || output; return input; }
      outputChars += output.length;
      if (outputChars > limits.maxChars) fail("SIZE_LIMIT");
      return output;
    };
    const visit = (input, depth) => {
      if (++nodes > limits.maxNodes) fail("NODE_LIMIT");
      if (depth > limits.maxDepth) fail("DEPTH_LIMIT");
      if (typeof input === "string") return visitString(input);
      if (input === null || typeof input === "boolean" || (typeof input === "number" && Number.isFinite(input))) return input;
      if (!input || typeof input !== "object") fail("INVALID_JSON");
      if (ancestors.has(input)) fail("CYCLIC_JSON");
      const proto = Object.getPrototypeOf(input);
      if (!Array.isArray(input) && proto !== Object.prototype && proto !== null) fail("INVALID_JSON");
      ancestors.add(input);
      let output;
      if (Array.isArray(input)) {
        if (input.length + nodes > limits.maxNodes) fail("NODE_LIMIT");
        output = [];
        for (let index = 0; index < input.length; index++) {
          const descriptor = Object.getOwnPropertyDescriptor(input, String(index));
          if (!descriptor || !Object.prototype.hasOwnProperty.call(descriptor, "value")) fail("INVALID_JSON");
          output.push(visit(descriptor.value, depth + 1));
        }
      } else {
        output = {};
        for (const key of Object.keys(input)) {
          const descriptor = Object.getOwnPropertyDescriptor(input, key);
          if (!descriptor || !Object.prototype.hasOwnProperty.call(descriptor, "value")) fail("INVALID_JSON");
          // Host tool events can carry optional own data fields as undefined.
          // Match JSON object serialization without evaluating accessors or
          // relaxing validation for root values and array entries.
          if (descriptor.value === undefined) continue;
          const nextKey = visitString(key);
          if (Object.prototype.hasOwnProperty.call(output, nextKey)) fail("KEY_COLLISION");
          Object.defineProperty(output, nextKey, { value: visit(descriptor.value, depth + 1), enumerable: true, configurable: true, writable: true });
        }
      }
      ancestors.delete(input);
      return output;
    };
    const output = visit(value, 0);
    return inspect ? Boolean(found) : output;
  }
  function aliasOption(options) {
    if (!options || typeof options !== "object" || Array.isArray(options) || Object.keys(options).some(key => key !== "shortAliases") || (options.shortAliases !== undefined && typeof options.shortAliases !== "boolean")) fail("INVALID_CONFIG");
    return options.shortAliases === true;
  }
  return Object.freeze({
    redact(value) { return walk(value, text => fixed(text)); },
    restore(value, restoreOptions = {}) {
      aliasOption(restoreOptions);
      return walk(value, text => fixed(text, true));
    },
    containsProtected(value) { return walk(value, text => fixed(text, false, true), true); },
    hasAliases(value, aliasOptions = {}) {
      aliasOption(aliasOptions);
      return walk(value, text => fixed(text, true, true), true);
    },
    hasUnknownTokens(value) {
      // Validate the same supported JSON shapes, but legacy tokens never deny.
      return walk(value, () => false, true);
    },
    stats() { return { tokens: 0, fixedCaseVariants: 0, types: { EMAIL: 0, PHONE: 0, ID: 0, CARD: 0 } }; },
  });
}
