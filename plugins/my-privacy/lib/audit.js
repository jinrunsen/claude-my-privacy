// Audit storage deliberately contains structural metadata only. Redaction is
// insufficient here: unknown credentials and company names must never reach it.
export const VERSION = '0.5.0';
export const MAX_AUDIT_EVENTS = 300;
export const AUDIT_PREFIX = 'privacy.audit.v1.';

const VERSIONS = new Set(['0.1.1', '0.1.2', '0.1.3', '0.1.4', '0.1.5', '0.1.6', '0.1.7', '0.1.8', '0.2.0', '0.3.0', '0.4.0', VERSION]);
const KINDS = new Set(['privacy_block', 'tool_error', 'plugin_error', 'recovery', 'filter_fallback']);
const STAGES = new Set([
  'arguments', 'prepare', 'path-check', 'preflight', 'execute', 'result', 'hook',
  'input', 'context', 'skill', 'session', 'request', 'history', 'recovery', 'configuration',
  'prompt.submit', 'prompt.context', 'prompt.section', 'prompt.attachment',
  'skill.prompt', 'session.start', 'session.append', 'session.compact',
  'session.send', 'turn.step', 'ui.render', 'classic.SessionStart',
]);
const CODES = new Set([
  'INVALID_JSON', 'CYCLIC_JSON', 'KEY_COLLISION', 'SIZE_LIMIT', 'DEPTH_LIMIT',
  'NODE_LIMIT', 'MAPPING_LIMIT', 'AMBIGUOUS_ALIAS_CASE', 'UNKNOWN_PII_TOKEN',
  'AMBIGUOUS_PATH', 'AMBIGUOUS_NEW_PATH', 'PATH_NOT_FOUND', 'SHELL_PII_TOKEN',
  'COMPLEX_ALIAS_COMMAND', 'UNSUPPORTED_ALIAS_COMMAND', 'EXTERNAL_COMMAND_OPTION',
  'RELATIVE_ALIAS_AFTER_CD', 'PATH_LOOKUP_LIMIT', 'SHORT_IDENTIFIER_COLLISION',
  'EDIT_MATCH_AMBIGUOUS', 'EDIT_MATCH_NOT_FOUND', 'RAW_PRIVATE_ARGUMENTS',
  'TOOL_ERROR', 'DOWNSTREAM_DENIED', 'NON_TEXT_RESULT', 'RESUMED_SESSION',
  'NON_TEXT_INPUT', 'REQUEST_UNFILTERED', 'HISTORY_LIMIT', 'REQUEST_CHECK_FAILED',
  'FILTER_FAILED', 'OUTPUT_SHAPE', 'INTERNAL_ERROR', 'RECOVERY_SUCCEEDED', 'RECOVERY_FAILED', 'CONFIG_UNAVAILABLE', 'CONFIG_INVALID',
]);
const TOOLS = new Set([
  'Bash', 'Read', 'Write', 'Edit', 'MultiEdit', 'Glob', 'Grep', 'WebFetch',
  'WebSearch', 'NotebookEdit', 'Task', 'Agent', 'Skill', 'ToolSearch', 'TodoWrite',
  'AskUserQuestion', 'LSP', 'ExitPlanMode', 'EnterPlanMode',
]);
const TYPES = new Set(['missing', 'null', 'array', 'object', 'string', 'number', 'boolean', 'other']);
const LENGTHS = new Set(['none', '1-80', '81-400', '401-2000', '2001+']);
const CD_STYLES = new Set(['none', '&&', ';']);
const EXECUTIONS = new Set(['ran', 'not_run', 'unknown']);

// Avoid invoking persisted getters or methods, even when given malformed rows.
function field(object, name) {
  if (!object || typeof object !== 'object') return undefined;
  try {
    const descriptor = Object.getOwnPropertyDescriptor(object, name);
    return descriptor && 'value' in descriptor ? descriptor.value : undefined;
  } catch { return undefined; }
}

function allowed(value, values, fallback = 'OTHER') {
  return typeof value === 'string' && values.has(value) ? value : fallback;
}

function valueType(value) {
  if (value === undefined) return 'missing';
  if (value === null) return 'null';
  try { if (Array.isArray(value)) return 'array'; } catch { return 'other'; }
  return TYPES.has(typeof value) ? typeof value : 'other';
}

function auditTime(value) {
  let milliseconds;
  if (typeof value === 'number' && Number.isFinite(value)) milliseconds = value;
  else if (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(value)) {
    milliseconds = Date.parse(value);
  }
  // Do not copy arbitrary strings or numbers into the log under a date label.
  if (!Number.isFinite(milliseconds) || milliseconds < 946684800000 || milliseconds >= 4102444800000) return null;
  return new Date(milliseconds).toISOString();
}

function commandLength(command) {
  if (!command.length) return 'none';
  if (command.length <= 80) return '1-80';
  if (command.length <= 400) return '81-400';
  return command.length <= 2000 ? '401-2000' : '2001+';
}

function leadingCd(command) {
  // This is diagnostic classification only, not command approval or parsing.
  // This never controls whether a shell command may execute.
  const match = /^[ \t]*cd[ \t]+(?:--[ \t]+)?(?:'\/[^'\r\n]*'|"\/[^"\r\n]*"|\/[^\s;&|]+)[ \t]*(&&(?![&|])|;(?![;&]))/.exec(command);
  return match ? match[1] : 'none';
}

function inputShape(args) {
  const value = field(args, 'command');
  const command = typeof value === 'string' ? value : '';
  return {
    type: valueType(args), commandLength: commandLength(command), leadingCd: leadingCd(command),
    multiline: /[\r\n]/.test(command), heredoc: command.includes('<<'),
    shellVariable: /\$(?:[A-Za-z_]|\{)/.test(command),
  };
}

function outputShape(answer) {
  return {
    type: valueType(answer), resultType: valueType(field(answer, 'result')),
    isError: field(answer, 'isError') === true,
    hasDenial: typeof field(answer, 'deny') === 'string',
  };
}

export function buildAuditEvent(details = {}) {
  const executed = field(details, 'executed');
  return {
    schema: 1, version: VERSION, time: auditTime(field(details, 'time')),
    kind: allowed(field(details, 'kind'), KINDS),
    stage: allowed(field(details, 'stage'), STAGES),
    code: allowed(field(details, 'code'), CODES, 'INTERNAL_ERROR'),
    tool: allowed(field(details, 'tool'), TOOLS),
    execution: executed === true ? 'ran' : executed === false ? 'not_run' : 'unknown',
    input: inputShape(field(details, 'args')),
    output: outputShape(field(details, 'answer')),
  };
}

function storedEvent(row) {
  if (field(row, 'schema') !== 1) return null;
  const input = field(row, 'input'), output = field(row, 'output');
  return {
    schema: 1, version: allowed(field(row, 'version'), VERSIONS), time: auditTime(field(row, 'time')),
    kind: allowed(field(row, 'kind'), KINDS), stage: allowed(field(row, 'stage'), STAGES),
    code: allowed(field(row, 'code'), CODES, 'INTERNAL_ERROR'), tool: allowed(field(row, 'tool'), TOOLS),
    execution: allowed(field(row, 'execution'), EXECUTIONS, 'unknown'),
    input: {
      type: allowed(field(input, 'type'), TYPES, 'other'),
      commandLength: allowed(field(input, 'commandLength'), LENGTHS, 'none'),
      leadingCd: allowed(field(input, 'leadingCd'), CD_STYLES, 'none'),
      multiline: field(input, 'multiline') === true, heredoc: field(input, 'heredoc') === true,
      shellVariable: field(input, 'shellVariable') === true,
    },
    output: {
      type: allowed(field(output, 'type'), TYPES, 'other'),
      resultType: allowed(field(output, 'resultType'), TYPES, 'other'),
      isError: field(output, 'isError') === true, hasDenial: field(output, 'hasDenial') === true,
    },
  };
}

export function acceptEvents(rows) {
  try {
    if (!Array.isArray(rows)) return [];
    const accepted = [];
    // Each row is reprojected; never stringify or spread storage contents.
    for (let index = Math.max(0, rows.length - MAX_AUDIT_EVENTS); index < rows.length; index += 1) {
      const event = storedEvent(field(rows, String(index)));
      if (event) accepted.push(event);
    }
    return accepted.sort((a, b) => (a.time || '').localeCompare(b.time || ''));
  } catch { return []; }
}

function countLines(events, property) {
  const counts = new Map();
  for (const event of events) counts.set(event[property], (counts.get(event[property]) || 0) + 1);
  return [...counts].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(([name, count]) => `${name}=${count}`).join(', ') || 'none';
}

function recommendations(events) {
  const codes = new Set(events.map(event => event.code));
  const advice = [];
  if (events.some(event => event.kind === 'privacy_block' || event.kind === 'recovery')) advice.push('Retained blocks/recovery events belong to the older policy. Version 0.2.0 uses targeted replacement with no command whitelist or history lock; reload plugins in an older running session.');
  if (events.some(event => event.kind === 'filter_fallback')) advice.push('A replacement could not complete; the original was passed through without retrying a tool. Reproduce with synthetic data to improve replacement coverage.');
  if (events.some(event => event.kind === 'tool_error')) advice.push('Native tool failures are counted separately from privacy blocks retained from older versions. Inspect the native failure; execution may already have occurred.');
  if (events.some(event => event.kind === 'plugin_error') || ['INTERNAL_ERROR', 'OUTPUT_SHAPE', 'FILTER_FAILED', 'REQUEST_CHECK_FAILED'].some(code => codes.has(code))) advice.push('Reproduce the plugin failure using a synthetic fixture and verify the host output schema.');
  if (!advice.length) advice.push('No specific optimization is suggested by the retained metadata.');
  return advice;
}

export function formatAuditSummary(rows, options = {}) {
  const events = acceptEvents(rows);
  const failures = field(options, 'writeFailures');
  const writeFailures = Number.isSafeInteger(failures) && failures >= 0 ? Math.min(failures, 1000000) : 0;
  const recent = events.slice(-10).map(event => {
    const structure = event.tool === 'Bash'
      ? `; command=${event.input.commandLength}, cd=${event.input.leadingCd}, multiline=${event.input.multiline}, heredoc=${event.input.heredoc}` : '';
    return `- ${event.time || 'time unavailable'} ${event.kind} ${event.tool} [${event.stage}:${event.code}] execution=${event.execution}; output=${event.output.type}/${event.output.resultType}${structure}`;
  });
  return [
    `MyPrivacy v${VERSION} audit: ${events.length} retained events (limit ${MAX_AUDIT_EVENTS}).`,
    'Local structural metadata only; no commands, paths, prompts, tool output, credentials, or PII mappings are recorded.',
    `Kinds: ${countLines(events, 'kind')}`,
    `Codes: ${countLines(events, 'code')}`,
    `Stages: ${countLines(events, 'stage')}`,
    `Versions: ${countLines(events, 'version')}`,
    `Execution: ${countLines(events, 'execution')}`,
    `Audit write failures in this process: ${writeFailures}.`,
    'Recent events:', ...(recent.length ? recent : ['- none']),
    'Analysis:', ...recommendations(events).map(advice => `- ${advice}`),
    'Analysis never changes filtering rules or permissions automatically.',
  ].join('\n');
}
