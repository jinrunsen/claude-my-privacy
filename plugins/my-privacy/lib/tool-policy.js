// This adapter translates configured names; it does not approve, parse or
// restrict commands. Native Claude Code permissions remain responsible for
// execution. Object keys and the host's routing metadata are never translated.
const PATH_KEYS = ['file_path', 'path', 'notebook_path'];
const HOST_KEYS = new Set(['tool', 'tool_use_id', 'agentId']);
const MODEL_TOOLS = new Set(['Agent', 'Task', 'Skill']);

function translateString(value, translate) {
  try { return translate(value); }
  catch { return value; }
}

function translateValues(value, translate, seen = new WeakMap()) {
  if (typeof value === 'string') return translateString(value, translate);
  if (!value || typeof value !== 'object') return value;
  if (seen.has(value)) return seen.get(value);
  const prototype = Object.getPrototypeOf(value);
  if (!Array.isArray(value) && prototype !== Object.prototype && prototype !== null) return value;
  const copy = Array.isArray(value) ? [] : Object.create(prototype);
  seen.set(value, copy);
  for (const key of Object.keys(value)) {
    const descriptor = Object.getOwnPropertyDescriptor(value, key);
    if (!descriptor || !Object.hasOwn(descriptor, 'value')) continue;
    Object.defineProperty(copy, key, { ...descriptor, value: translateValues(descriptor.value, translate, seen) });
  }
  return copy;
}

function translateArguments(event, translate) {
  const copy = { ...event };
  for (const key of Object.keys(copy)) {
    if (!HOST_KEYS.has(key)) copy[key] = translateValues(copy[key], translate);
  }
  return copy;
}

export async function resolvePath(path, privacy, exists, _allowCreate = false, _realPath) {
  if (typeof path !== 'string') return path;
  const restored = translateString(path, value => privacy.restore(value));
  if (restored === path) return path;
  // A usable literal alias is the user's selected target, even when the
  // original spelling also exists elsewhere. Missing/unavailable checks never
  // prevent the native tool from trying the deterministically restored path.
  if (typeof exists === 'function') {
    try { if (await exists(path)) return path; }
    catch { /* Best effort only: native tools report filesystem errors. */ }
  }
  return restored;
}

export async function prepareBash(event, privacy, _exists, _realPath) {
  // Translate the complete string. Do not parse or requote shell text: its
  // quoting, separators, heredocs, variables and program syntax stay intact.
  return translateArguments(event, value => privacy.restore(value));
}

export async function prepareTool(event, privacy, exists, realPath) {
  if (MODEL_TOOLS.has(event.tool)) {
    // These arguments enter another model context, so keep them pseudonymous.
    return translateArguments(event, value => privacy.redact(value));
  }
  if (event.tool === 'Bash') return prepareBash(event, privacy);
  const copy = translateArguments(event, value => privacy.restore(value));
  if (event.tool === 'WebFetch' && typeof event.prompt === 'string') {
    // Fetch destinations are execution arguments; its summary instructions
    // are another model's input and keep the same pseudonymous vocabulary.
    copy.prompt = translateString(event.prompt, value => privacy.redact(value));
  }
  for (const key of PATH_KEYS) {
    if (typeof event[key] === 'string') copy[key] = await resolvePath(event[key], privacy, exists, false, realPath);
  }
  return copy;
}
