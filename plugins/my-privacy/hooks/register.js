import { createPrivacy } from '../lib/privacy.js';
import { redactAppend, rewriteToolResult, compactMessages } from '../lib/content.js';
import { prepareTool } from '../lib/tool-policy.js';
import { CONFIG_RELATIVE_PATH } from '../config.js';
import { parseMappings } from '../lib/configuration.js';
import { VERSION, AUDIT_PREFIX, MAX_AUDIT_EVENTS, buildAuditEvent, acceptEvents, formatAuditSummary } from '../lib/audit.js';

let privacy = createPrivacy();
let configurationState = 'not_loaded';
let mappingCount = 0;
let configurationLoading;
let auditWriteFailures = 0;
let auditSequence = 0;
const auditInstance = Math.random().toString(36).slice(2, 12) || '0';
const auditKeyPattern = /^privacy\.audit\.v1\.\d{16}\.[a-z0-9]+\.\d{8}$/;

// Personal mappings live outside the source, installed plugin and Git history.
// Load once per Mod instance; /reload-plugins picks up configuration changes.
async function loadConfiguration($) {
  let text;
  try {
    const configuredPath = await $.env.get('CLAUDE_MY_PRIVACY_CONFIG');
    const home = configuredPath ? undefined : await $.env.get('HOME');
    const path = configuredPath || (home ? home.replace(/\/+$/, '') + '/' + CONFIG_RELATIVE_PATH : undefined);
    if (!path || !path.startsWith('/') || /[\u0000\r\n]/.test(path)) throw new Error('Configuration unavailable');
    text = await $.fs.read(path);
  } catch {
    configurationState = 'unavailable';
    await recordAudit($, { kind: 'filter_fallback', stage: 'configuration', code: 'CONFIG_UNAVAILABLE', executed: false });
    return;
  }
  try {
    const mappings = parseMappings(text);
    const configured = createPrivacy({ mappings });
    privacy = configured;
    mappingCount = mappings.length;
    configurationState = 'loaded';
  } catch {
    configurationState = 'invalid';
    await recordAudit($, { kind: 'filter_fallback', stage: 'configuration', code: 'CONFIG_INVALID', executed: false });
  }
}

async function ensurePrivacy($) {
  if (configurationLoading) return configurationLoading;
  configurationLoading = loadConfiguration($);
  return configurationLoading;
}

// Keep only bounded structural metadata, never arguments, content or errors.
async function recordAudit($, details) {
  try {
    const time = await $.clock.now();
    const row = buildAuditEvent({ ...details, time });
    const key = AUDIT_PREFIX + String(Math.floor(time)).padStart(16, '0') + '.' + auditInstance + '.' + String(++auditSequence).padStart(8, '0');
    await $.store.set(key, row);
    const keys = (await $.store.keys()).filter(key => auditKeyPattern.test(key)).sort();
    for (const expired of keys.slice(0, Math.max(0, keys.length - MAX_AUDIT_EVENTS))) await $.store.delete(expired);
  } catch { auditWriteFailures += 1; }
}

async function auditSummary($) {
  try {
    const keys = (await $.store.keys()).filter(key => auditKeyPattern.test(key)).sort().slice(-MAX_AUDIT_EVENTS);
    const rows = [];
    for (const key of keys) rows.push(await $.store.get(key));
    return { text: formatAuditSummary(acceptEvents(rows), { writeFailures: auditWriteFailures }) };
  } catch {
    return { text: 'MyPrivacy audit is unavailable: local storage could not be read. Targeted replacement remains best effort.' };
  }
}

// Filtering failures are diagnostic events, not permission decisions. Passing
// the original preserves operation, but can leave a listed term unfiltered.
async function redact($, value, stage) {
  await ensurePrivacy($);
  try { return privacy.redact(value); }
  catch {
    await recordAudit($, { kind: 'filter_fallback', stage, code: 'FILTER_FAILED', executed: 'unknown' });
    return value;
  }
}

async function privateContext($, event) {
  const blocks = [];
  for (const block of event.blocks) blocks.push({ ...block, text: await redact($, block.text, 'prompt.context') });
  const copy = { ...event, blocks };
  if (event.instructionFiles) copy.instructionFiles = await redact($, event.instructionFiles, 'prompt.context');
  return copy;
}

async function localTool($, event, next) {
  await ensurePrivacy($);
  let ready = event;
  try {
    // The host's static analyzer requires host APIs to be called directly.
    // Existence is an optional preference, never an execution prerequisite.
    const existing = new Map();
    if (event.tool !== 'Bash') {
      for (const key of ['file_path', 'path', 'notebook_path']) {
        if (typeof event[key] === 'string' && privacy.hasAliases(event[key])) {
          try { existing.set(event[key], await $.fs.exists(event[key])); }
          catch {
            await recordAudit($, { kind: 'filter_fallback', stage: 'path-check', code: 'FILTER_FAILED', tool: event.tool, executed: false });
          }
        }
      }
    }
    let translationFailed = false;
    const toolPrivacy = {
      restore(value) {
        try { return privacy.restore(value); }
        catch { translationFailed = true; return value; }
      },
      redact(value) {
        try { return privacy.redact(value); }
        catch { translationFailed = true; return value; }
      },
    };
    ready = await prepareTool(event, toolPrivacy, async path => existing.get(path) === true);
    if (translationFailed) await recordAudit($, { kind: 'filter_fallback', stage: 'prepare', code: 'FILTER_FAILED', tool: event.tool, executed: false, args: event });
  } catch {
    await recordAudit($, { kind: 'filter_fallback', stage: 'prepare', code: 'FILTER_FAILED', tool: event.tool, executed: false, args: event });
  }

  // Exactly one execution attempt. Never rerun a tool after an output/filter
  // error; its side effects may already have occurred.
  let answer;
  try { answer = await next(ready); }
  catch (error) {
    await recordAudit($, { kind: 'tool_error', stage: 'execute', code: 'TOOL_ERROR', tool: event.tool, executed: 'unknown', args: event });
    const message = typeof error?.message === 'string' ? error.message : 'The tool failed without an error message.';
    return { deny: 'Underlying tool failed (execution may have occurred): ' + await redact($, message, 'result') };
  }
  if (answer?.deny !== undefined || answer?.isError === true) {
    await recordAudit($, { kind: 'tool_error', stage: 'result', code: answer?.deny !== undefined ? 'DOWNSTREAM_DENIED' : 'TOOL_ERROR',
      tool: event.tool, executed: 'unknown', args: event, answer });
  }
  try { return rewriteToolResult(answer, value => privacy.redact(value)); }
  catch {
    await recordAudit($, { kind: 'filter_fallback', stage: 'result', code: 'FILTER_FAILED', tool: event.tool, executed: 'unknown', args: event, answer });
    return answer;
  }
}

export function register(on) {
  on('session.start', async ($, event, next) => {
    await ensurePrivacy($);
    await $.command.register({ name: 'my-privacy-status', description: 'Show targeted local replacement policy and its limits.' });
    await $.command.register({ name: 'my-privacy-audit', description: 'Summarize local replacement fallbacks and native tool errors without private content.' });
    await $.command.register({ name: 'my-privacy-recover', description: 'Show migration guidance for the older history guard.' });
    $.ui.status(undefined);
    return next(event);
  });

  on('command.run', { command: 'my-privacy-status' }, async ($) => {
    await ensurePrivacy($);
    return {
      text: 'MyPrivacy v' + VERSION + ': targeted replacement, best effort. Configuration: ' + configurationState + '; mappings: ' + mappingCount + '. Configured terms are pseudonymized in supported text; aliases are restored in executable tool arguments and local assistant reply display. Display restoration changes only rendered reply text, not model context or stored session messages. No personal mappings are built into the plugin. Missing or invalid configuration leaves text unchanged; reload plugins after fixing it. Ordinary emails, phones, short identifiers and old PII placeholders pass unchanged. Model-facing Agent/Task/Skill arguments remain pseudonymized. No command whitelist, format-based denial, media denial, resumed-session denial or history lock. Shell syntax is preserved by literal substitution; native permissions still apply. Listed aliases are reserved vocabulary. Images, signed thinking, pinned tool-use history, saved system snapshots, raw queue records and file snapshots may remain unfiltered. Filtering failures pass the original and record metadata. Local audit retains up to ' + MAX_AUDIT_EVENTS + ' events; use /my-privacy-audit. Audit write failures in this instance: ' + auditWriteFailures + '.',
    };
  });

  on('command.run', { command: 'my-privacy-audit' }, async ($) => auditSummary($));
  on('command.run', { command: 'my-privacy-recover' }, async () => ({
    text: 'Targeted replacement mode has no history lock. Continue normally; no history was rewritten and no tool was retried. Older placeholders may require re-reading their source.',
  }));

  on('ui.render', { component: 'AssistantMessage' }, async ($, event, next) => {
    await ensurePrivacy($);
    let ready = event;
    try {
      // Restore each visible block independently. The host keeps its native
      // renderer and pinned onScreen viewport metadata. Session/model data
      // remains untouched.
      if (typeof event.props?.text === 'string') {
        ready = { ...event, props: { ...event.props, text: privacy.restore(event.props.text) } };
      }
    } catch {
      await recordAudit($, { kind: 'filter_fallback', stage: 'ui.render', code: 'FILTER_FAILED', executed: false });
    }
    // Downstream rendering is attempted once, outside the restoration catch.
    return next(ready);
  });

  on('prompt.submit', async ($, event, next) => next({
    ...event, text: await redact($, event.text, 'prompt.submit'),
    ...(event.context ? { context: await redact($, event.context, 'prompt.submit') } : {}),
  }));

  on('prompt.context', async ($, event, next) => {
    const answer = await next(await privateContext($, event));
    return privateContext($, answer);
  });

  on('prompt.section', async ($, event, next) => {
    const answer = await next({ ...event, text: await redact($, event.text, 'prompt.section') });
    return { ...answer, text: await redact($, answer.text, 'prompt.section') };
  });

  on('prompt.attachment', async ($, event, next) => {
    const answer = await next({ ...event, text: await redact($, event.text, 'prompt.attachment') });
    return { ...answer, text: await redact($, answer.text, 'prompt.attachment') };
  });

  on('skill.prompt', async ($, event, next) => {
    const answer = await next({ ...event, text: await redact($, event.text, 'skill.prompt') });
    return { ...answer, text: await redact($, answer.text, 'skill.prompt') };
  });

  on('tool.call', async ($, event, next) => localTool($, event, next));

  on('session.append', async ($, event, next) => {
    await ensurePrivacy($);
    let ready = event;
    try { ready = redactAppend(event, value => privacy.redact(value)); }
    catch {
      await recordAudit($, { kind: 'filter_fallback', stage: 'session.append', code: 'FILTER_FAILED', executed: 'unknown' });
    }
    return next(ready);
  });

  on('session.compact', async ($, event, next) => {
    await ensurePrivacy($);
    let ready = event;
    try {
      ready = { ...event, messages: compactMessages(event.messages, value => privacy.redact(value)),
        ...(event.instructions ? { instructions: privacy.redact(event.instructions) } : {}) };
    } catch {
      await recordAudit($, { kind: 'filter_fallback', stage: 'session.compact', code: 'FILTER_FAILED', executed: 'unknown' });
    }
    return next(ready);
  });

  on('session.send', async ($, event, next) => next({ ...event, text: await redact($, event.text, 'session.send') }));
  // Intentionally no turn.step guard: immutable old content never locks turns.
}
