import test from 'node:test';
import assert from 'node:assert/strict';
import {
  VERSION, MAX_AUDIT_EVENTS, AUDIT_PREFIX, buildAuditEvent, acceptEvents, formatAuditSummary,
} from '../lib/audit.js';

const TIME = Date.UTC(2026, 9, 4, 12, 30, 0);
const SECRET = 'synthetic-secret-token-Zqx487';
const EMAIL = 'private.person@company-fixture.example';
const PATH = '/synthetic/private-company/private-person/secrets.txt';
const PII = '<PII_SYNTHETIC_EMAIL_000001>';
const secrets = [SECRET, EMAIL, PATH, PII];
const event = overrides => buildAuditEvent({
  time: TIME, kind: 'privacy_block', stage: 'prepare', code: 'AMBIGUOUS_PATH',
  tool: 'Read', executed: false, args: { file_path: PATH }, ...overrides,
});
const noSecrets = value => {
  const text = typeof value === 'string' ? value : JSON.stringify(value);
  for (const secret of secrets) assert.equal(text.includes(secret), false, `Unexpected private value in audit output`);
};

test('audit event projects only fixed structural metadata, including shell command shape', () => {
  const row = event({
    tool: 'Bash', args: {
      command: `cd "${PATH}"; source .dev.vars && curl -H "Authorization: Bearer $SYNTHETIC_TOKEN" example.invalid\ncat <<'END'\n${SECRET} ${EMAIL} ${PII}\nEND`,
      description: SECRET, file_path: PATH, [EMAIL]: PII,
    },
    answer: { isError: true, text: secrets.join(' '), ref: SECRET, result: { stdout: secrets.join(' '), stderr: SECRET } },
    message: SECRET, error: new Error(secrets.join(' ')), session: EMAIL,
  });
  assert.equal(row.version, VERSION);
  assert.equal(row.schema, 1);
  assert.equal(row.time, '2026-10-04T12:30:00.000Z');
  assert.deepEqual(row.input, { type: 'object', commandLength: '81-400', leadingCd: ';', multiline: true, heredoc: true, shellVariable: true });
  assert.deepEqual(row.output, { type: 'object', resultType: 'object', isError: true, hasDenial: false });
  assert.deepEqual(Object.keys(row).sort(), ['schema', 'version', 'time', 'kind', 'stage', 'code', 'tool', 'execution', 'input', 'output'].sort());
  noSecrets(row);
  noSecrets(formatAuditSummary([row]));
});

test('unknown event enums, timestamps, and tool names cannot become free-text log channels', () => {
  const row = buildAuditEvent({ time: EMAIL, kind: SECRET, stage: PATH, code: PII, tool: EMAIL, executed: SECRET,
    args: { command: SECRET }, answer: { result: PII, deny: EMAIL }, extra: SECRET });
  assert.equal(row.time, null);
  assert.equal(row.kind, 'OTHER');
  assert.equal(row.stage, 'OTHER');
  assert.equal(row.code, 'INTERNAL_ERROR');
  assert.equal(row.tool, 'OTHER');
  assert.equal(row.execution, 'unknown');
  assert.equal(row.output.resultType, 'string');
  assert.equal(row.output.hasDenial, true);
  noSecrets(row);
  noSecrets(formatAuditSummary([row], { writeFailures: SECRET }));
});

test('audit input classification observes separators without recording or interpreting shell text', () => {
  for (const [command, leadingCd] of [
    [`cd /synthetic/alias && printf '${SECRET}'`, '&&'],
    [`cd -- '/synthetic/alias space'; printf '${SECRET}'`, ';'],
    [`cd /synthetic/alias;; printf '${SECRET}'`, 'none'],
    [`cd /synthetic/alias;& printf '${SECRET}'`, 'none'],
    [`cd /synthetic/alias;;& printf '${SECRET}'`, 'none'],
    [`cd /synthetic/alias || printf '${SECRET}'`, 'none'],
    [`printf '${SECRET}'`, 'none'],
  ]) {
    const row = event({ tool: 'Bash', args: { command } });
    assert.equal(row.input.leadingCd, leadingCd);
    noSecrets(row);
  }
  for (const [length, bucket] of [[0, 'none'], [80, '1-80'], [81, '81-400'], [400, '81-400'], [401, '401-2000'], [2000, '401-2000'], [2001, '2001+']]) {
    assert.equal(event({ args: { command: 'x'.repeat(length) } }).input.commandLength, bucket);
  }
});

test('persisted data is reprojected, including nested fields and old versions', () => {
  const contaminated = { ...event(), version: SECRET, kind: EMAIL, stage: PATH, code: PII, tool: SECRET,
    time: PATH, execution: SECRET, command: SECRET, error: EMAIL,
    input: { type: SECRET, commandLength: EMAIL, leadingCd: PATH, multiline: SECRET, heredoc: PII, shellVariable: EMAIL, command: SECRET },
    output: { type: SECRET, resultType: EMAIL, isError: SECRET, hasDenial: PII, result: SECRET },
  };
  const accepted = acceptEvents([contaminated, { ...event(), version: '0.1.6', secret: SECRET }]);
  assert.equal(accepted.length, 2);
  assert.equal(accepted[0].version, 'OTHER');
  assert.equal(accepted[0].input.multiline, false);
  assert.equal(accepted[0].output.isError, false);
  assert.equal(accepted[1].version, '0.1.6');
  noSecrets(accepted);
  noSecrets(formatAuditSummary([contaminated]));
});

test('MyPrivacy preserves the audit storage namespace and recognizes the previous release', () => {
  const rows = [{ ...event(), version: '0.3.0' }, { ...event(), version: '0.4.0' }, event()];
  assert.equal(AUDIT_PREFIX, 'privacy.audit.v1.');
  assert.deepEqual(acceptEvents(rows).map(row => row.version), ['0.3.0', '0.4.0', VERSION]);
  const summary = formatAuditSummary(rows);
  assert.equal(summary.startsWith(`MyPrivacy v${VERSION} audit:`), true);
  assert.equal(summary.includes(`Versions: 0.3.0=1, 0.4.0=1, ${VERSION}=1`), true);
});

test('malformed storage rows and accessors never leak or execute getters', () => {
  let invoked = 0;
  const badRow = {};
  Object.defineProperty(badRow, 'schema', { get() { invoked += 1; throw new Error(SECRET); } });
  const getterRow = { ...event() };
  Object.defineProperty(getterRow, 'code', { get() { invoked += 1; throw new Error(SECRET); } });
  Object.defineProperty(getterRow, 'input', { get() { invoked += 1; throw new Error(SECRET); } });
  const rows = [null, undefined, SECRET, 3, [], { schema: SECRET, command: SECRET }, badRow, getterRow];
  const result = acceptEvents(rows);
  assert.equal(result.length, 1);
  assert.equal(result[0].code, 'INTERNAL_ERROR');
  assert.equal(invoked, 0);
  noSecrets(result);
  noSecrets(formatAuditSummary(rows));
  assert.deepEqual(acceptEvents({ rows, [SECRET]: EMAIL }), []);
  const revoked = Proxy.revocable([], {});
  revoked.revoke();
  assert.deepEqual(acceptEvents(revoked.proxy), []);
});

test('native tool errors, privacy blocks, and plugin failures remain distinct in analysis', () => {
  const rows = [
    event(),
    event({ kind: 'tool_error', code: 'TOOL_ERROR', stage: 'result', executed: true, answer: { isError: true, result: SECRET } }),
    event({ kind: 'tool_error', code: 'DOWNSTREAM_DENIED', stage: 'execute', executed: false, answer: { deny: SECRET } }),
    event({ kind: 'plugin_error', code: 'OUTPUT_SHAPE', stage: 'result', executed: 'unknown' }),
  ];
  const summary = formatAuditSummary(rows, { writeFailures: 3 });
  assert.match(summary, /Kinds: tool_error=2, plugin_error=1, privacy_block=1/);
  assert.match(summary, /Execution: not_run=2, ran=1, unknown=1/);
  assert.match(summary, /Audit write failures in this process: 3/);
  assert.match(summary, /Native tool failures are counted separately from privacy blocks/);
  assert.match(summary, /verify the host output schema/);
  assert.match(summary, /never changes filtering rules or permissions automatically/);
  noSecrets(summary);
});

test('retention caps events, recent detail caps ten, and dates sort consistently', () => {
  assert.equal(MAX_AUDIT_EVENTS, 300);
  assert.equal(AUDIT_PREFIX, 'privacy.audit.v1.');
  const rows = Array.from({ length: MAX_AUDIT_EVENTS + 20 }, (_, i) => event({ time: TIME + i * 1000 }));
  const accepted = acceptEvents(rows);
  assert.equal(accepted.length, MAX_AUDIT_EVENTS);
  assert.equal(accepted[0].time, new Date(TIME + 20000).toISOString());
  const summary = formatAuditSummary(rows);
  assert.match(summary, /300 retained events \(limit 300\)/);
  assert.equal(summary.split('\n').filter(line => /^- 2026-/.test(line)).length, 10);
  assert.equal(acceptEvents([rows[2], rows[1]])[0].time, rows[1].time);
});

test('missing and malformed inputs produce safe bounded reports', () => {
  const defaultEvent = buildAuditEvent();
  assert.equal(defaultEvent.input.type, 'missing');
  assert.equal(defaultEvent.output.type, 'missing');
  const cycle = {};
  cycle.self = cycle;
  const row = event({ time: Infinity, args: cycle, answer: cycle });
  assert.equal(row.time, null);
  noSecrets(row);
  for (const time of [-1, 0, NaN, Infinity, 5000000000000, SECRET, new Date(TIME), null]) {
    assert.equal(event({ time }).time, null);
  }
  const summary = formatAuditSummary(null, { writeFailures: Number.MAX_SAFE_INTEGER });
  assert.match(summary, /0 retained events/);
  assert.match(summary, /1000000/);
  assert.match(summary, /No specific optimization/);
});
