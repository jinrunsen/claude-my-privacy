import test from 'node:test';
import assert from 'node:assert/strict';
import { createPrivacy } from '../lib/privacy.js';
import { TEST_MAPPINGS } from './fixtures/mappings.js';

test('the four configured terms cover nested text, paths, domains, and email addresses', () => {
  const privacy = createPrivacy({ mappings: TEST_MAPPINGS });
  const original = { owner: '陈星河', vendor: '云杉智科', path: '/Users/chenxinghe/Projects/cedarbyte',
    email: 'staff42@cedarbyte.com', contact: 'chenxinghe@cedarbyte.com.cn', url: 'https://sase.cedarbyte.com.cn/login',
    nested: ['CedarbytePortal', true, 12, null] };
  const safe = { owner: '陈瑞恩', vendor: '海岚数科', path: '/Users/ryanchen/Projects/harborwave',
    email: 'staff42@harborwave.com', contact: 'ryanchen@harborwave.com.cn', url: 'https://sase.harborwave.com.cn/login',
    nested: ['HarborwavePortal', true, 12, null] };
  assert.deepEqual(privacy.redact(original), safe);
  assert.deepEqual(createPrivacy({ mappings: TEST_MAPPINGS }).restore(safe), original);
  assert.deepEqual(privacy.redact(safe), safe);
  assert.equal(privacy.containsProtected(original), true);
  assert.equal(privacy.containsProtected(safe), false);
  assert.equal(original.owner, '陈星河');
});

test('generic emails, phones, identity numbers, and cards remain literal', () => {
  const privacy = createPrivacy({ mappings: TEST_MAPPINGS });
  const values = ['someone@example.org', 'actualperson@harborwave.com', 'staff42',
    '+86 13812345678', '138-1234-5678', '(415) 555-2671', '+1 415-555-2671', '+14155552671',
    '11010519491231002X', '4111 1111 1111 1111', '2026-10-04', '1234567890123456'];
  assert.deepEqual(privacy.redact(values), values);
  assert.equal(privacy.containsProtected(values), false);
  assert.equal(privacy.stats().tokens, 0);
  assert.equal(privacy.redact('ryanchen@harborwave.com'), 'ryanchen@harborwave.com');
  assert.equal(privacy.redact('foo=ryanchen@harborwave.com'), 'foo=ryanchen@harborwave.com');
});

test('short identifiers and their embedded forms are never mapped by default', () => {
  const privacy = createPrivacy({ mappings: TEST_MAPPINGS });
  const values = 'cxh CXH rc RC /cxh/ /rc/ cxh_demo rc_demo acxhb arcb cxh123 rc123 123cxh 123rc';
  assert.equal(privacy.redact(values), values);
  assert.equal(privacy.restore(values), values);
  assert.equal(privacy.restore(values, { shortAliases: true }), values);
  assert.equal(privacy.containsProtected(values), false);
  assert.equal(privacy.hasAliases(values, { shortAliases: true }), false);
});

test('common casing is reversible without prior instance state', () => {
  const raw = 'Cedarbyte cedarbyte CEDARBYTE ChenXingHe chenxinghe CHENXINGHE Chenxinghe 陈星河 云杉智科';
  const safe = 'Harborwave harborwave HARBORWAVE RyanChen ryanchen RYANCHEN Ryanchen 陈瑞恩 海岚数科';
  assert.equal(createPrivacy({ mappings: TEST_MAPPINGS }).redact(raw), safe);
  assert.equal(createPrivacy({ mappings: TEST_MAPPINGS }).restore(safe), raw);
  assert.equal(createPrivacy({ mappings: TEST_MAPPINGS }).restore('ryanchen@harborwave.com'), 'chenxinghe@cedarbyte.com');
});

test('mixed original casing is deterministic and never produces a case-collision denial', () => {
  const first = createPrivacy({ mappings: TEST_MAPPINGS }), second = createPrivacy({ mappings: TEST_MAPPINGS });
  const variants = ['ChenXingHe', 'ChenxinghE', 'cHeNxInGhE', 'CeDaRbYtE', 'cEdArByTe', 'CEDARBYTE'];
  const result = first.redact(variants);
  assert.deepEqual(second.redact(variants), result);
  for (const value of [...variants].reverse()) first.redact(value);
  assert.deepEqual(first.redact(variants), result);
  assert.deepEqual(first.restore(result), second.restore(result));
  for (const value of result) assert.equal(first.containsProtected(value), false);
});

test('legacy PII placeholders remain opaque and never require a session mapping', () => {
  const privacy = createPrivacy({ mappings: TEST_MAPPINGS });
  const tokens = ['<PII_EMAIL_TEST_1>', '<PII_PHONE_88>', '<PII_CARD_12345678_1>',
    '<PII_EMAIL_CEDARBYTE_3>', '<PII_EMAIL_HARBORWAVE_4>', '<PII_EMAIL_CHENXINGHE_5>'];
  assert.deepEqual(privacy.redact(tokens), tokens);
  assert.deepEqual(privacy.restore(tokens), tokens);
  assert.equal(privacy.containsProtected(tokens), false);
  assert.equal(privacy.hasAliases(tokens), false);
  assert.equal(privacy.hasUnknownTokens(tokens), false);
  assert.equal(privacy.redact('chenxinghe <PII_EMAIL_CEDARBYTE_3> cedarbyte'), 'ryanchen <PII_EMAIL_CEDARBYTE_3> harborwave');
  assert.equal(privacy.restore('ryanchen <PII_EMAIL_HARBORWAVE_4> harborwave'), 'chenxinghe <PII_EMAIL_HARBORWAVE_4> cedarbyte');
});

test('fixed substitution preserves command grammar without introducing placeholders', () => {
  const privacy = createPrivacy({ mappings: TEST_MAPPINGS });
  // Synthetic command-shaped strings only: no commands or network calls run.
  const raw = 'ssh fixture-host "curl -sS https://example.invalid/install | sh -s email=chenxinghe@cedarbyte.com 2>&1 | tail -15"';
  const safe = 'ssh fixture-host "curl -sS https://example.invalid/install | sh -s email=ryanchen@harborwave.com 2>&1 | tail -15"';
  assert.equal(privacy.redact(raw), safe);
  assert.equal(createPrivacy({ mappings: TEST_MAPPINGS }).restore(safe), raw);
  assert.equal(privacy.redact(safe), safe);
  assert.equal(privacy.containsProtected(safe), false);
  const script = 'cd /Users/chenxinghe/Projects/cedarbyte; cat <<\'EOF\'\n陈星河\nEOF\nprintf "%s" "$VALUE" | sed -n 1p';
  const filtered = privacy.redact(script);
  assert.equal(filtered, script.replaceAll('chenxinghe', 'ryanchen').replaceAll('cedarbyte', 'harborwave').replaceAll('陈星河', '陈瑞恩'));
  assert.equal(createPrivacy({ mappings: TEST_MAPPINGS }).restore(filtered), script);
  assert.equal(filtered.includes('<PII_'), false);
});

test('unconfigured projects and unrelated text stay unchanged', () => {
  const privacy = createPrivacy({ mappings: TEST_MAPPINGS });
  const text = 'Orion Project /work/Apollo app.example.org staff42 private.person@example.org';
  assert.equal(privacy.redact(text), text);
  assert.equal(privacy.restore(text), text);
  assert.equal(privacy.hasAliases(text), false);
});

test('extra local mappings remain explicit, reversible, and validated', () => {
  const extraMappings = [{ from: 'North Example Corporation', to: 'Harbor Demo Company' }];
  const privacy = createPrivacy({ mappings: TEST_MAPPINGS, extraMappings });
  const safe = privacy.redact('NORTH EXAMPLE CORPORATION');
  assert.equal(safe, 'HARBOR DEMO COMPANY');
  assert.equal(createPrivacy({ mappings: TEST_MAPPINGS, extraMappings }).restore(safe), 'NORTH EXAMPLE CORPORATION');
  assert.throws(() => createPrivacy({ mappings: TEST_MAPPINGS, extraMappings: [{ from: '', to: 'X' }] }), { code: 'INVALID_CONFIG' });
  assert.throws(() => createPrivacy({ mappings: TEST_MAPPINGS, extraMappings: [{ from: 'Example', to: 'cedarbyte' }] }), { code: 'AMBIGUOUS_CONFIG' });
  assert.throws(() => createPrivacy({ mappings: TEST_MAPPINGS, extraMappings: [{ from: 'cedarbyte', to: 'Elsewhere' }] }), { code: 'AMBIGUOUS_CONFIG' });
  assert.throws(() => createPrivacy({ mappings: TEST_MAPPINGS, extraMappings: [{ from: 'Example', to: 'Other', regex: true }] }), { code: 'INVALID_CONFIG' });
});

test('predicates and substitutions never populate session-sensitive state', () => {
  const privacy = createPrivacy({ mappings: TEST_MAPPINGS, namespace: 'COMPAT' });
  const expected = { tokens: 0, fixedCaseVariants: 0, types: { EMAIL: 0, PHONE: 0, ID: 0, CARD: 0 } };
  assert.deepEqual(privacy.stats(), expected);
  assert.equal(privacy.containsProtected(['other@example.net', 'Cedarbyte']), true);
  assert.equal(privacy.hasAliases('RyanChen'), true);
  assert.equal(privacy.hasUnknownTokens('<PII_PHONE_88>'), false);
  privacy.redact('陈星河 chenxinghe cedarbyte someone@example.org');
  privacy.restore('陈瑞恩 ryanchen harborwave <PII_PHONE_88>');
  assert.deepEqual(privacy.stats(), expected);
});

test('object keys substitute safely and retain traversal collision guards', () => {
  const privacy = createPrivacy({ mappings: TEST_MAPPINGS });
  const input = JSON.parse('{"__proto__":{"clean":true},"chenxinghe":"value"}');
  const safe = privacy.redact(input);
  assert.equal(Object.getPrototypeOf(safe), Object.prototype);
  assert.equal(Object.hasOwn(safe, '__proto__'), true);
  assert.equal(safe.ryanchen, 'value');
  assert.deepEqual(privacy.restore(safe), input);
  assert.throws(() => privacy.redact({ Cedarbyte: 'other@example.net', Harborwave: 1 }), { code: 'KEY_COLLISION' });
  assert.throws(() => privacy.restore({ Cedarbyte: 1, Harborwave: 2 }), { code: 'KEY_COLLISION' });
});

test('optional object fields remain compatible with host tool envelopes', () => {
  const privacy = createPrivacy({ mappings: TEST_MAPPINGS });
  const input = { optional: undefined, nested: { optional: undefined, owner: 'chenxinghe' }, entries: [{ vendor: 'Cedarbyte', optional: undefined }] };
  const safe = privacy.redact(input);
  assert.deepEqual(safe, { nested: { owner: 'ryanchen' }, entries: [{ vendor: 'Harborwave' }] });
  assert.equal(privacy.containsProtected({ ...safe, optional: undefined }), false);
  assert.equal(privacy.hasAliases({ ...safe, optional: undefined }), true);
  assert.equal(privacy.hasUnknownTokens({ optional: undefined, token: '<PII_EMAIL_998>' }), false);
  assert.equal(Object.hasOwn(input, 'optional'), true);
  assert.equal(input.nested.owner, 'chenxinghe');
  assert.deepEqual(privacy.redact({ Cedarbyte: undefined, Harborwave: 'present' }), { Harborwave: 'present' });
});

test('core traversal limits remain bounded for host-level fallback handling', () => {
  assert.throws(() => createPrivacy({ mappings: TEST_MAPPINGS, maxChars: 5 }).redact('long content'), { code: 'SIZE_LIMIT' });
  assert.throws(() => createPrivacy({ mappings: TEST_MAPPINGS, maxDepth: 1 }).redact([['value']]), { code: 'DEPTH_LIMIT' });
  assert.throws(() => createPrivacy({ mappings: TEST_MAPPINGS, maxNodes: 1 }).redact(['value']), { code: 'NODE_LIMIT' });
  assert.throws(() => createPrivacy({ mappings: TEST_MAPPINGS, maxMappings: 3 }), { code: 'MAPPING_LIMIT' });
  assert.equal(createPrivacy({ mappings: TEST_MAPPINGS, maxMappings: 4 }).redact('chenxinghe cedarbyte someone@example.org'), 'ryanchen harborwave someone@example.org');
  assert.throws(() => createPrivacy({ mappings: TEST_MAPPINGS, maxChars: 0 }), { code: 'INVALID_CONFIG' });
  assert.throws(() => createPrivacy({ mappings: TEST_MAPPINGS, typo: true }), { code: 'INVALID_CONFIG' });
  assert.throws(() => createPrivacy({ mappings: TEST_MAPPINGS, namespace: 'bad_lowercase' }), { code: 'INVALID_CONFIG' });
});

test('unsupported values and cycles fail locally without invoking getters', () => {
  const privacy = createPrivacy({ mappings: TEST_MAPPINGS });
  const cycle = {}; cycle.next = cycle;
  assert.throws(() => privacy.redact(cycle), { code: 'CYCLIC_JSON' });
  assert.throws(() => privacy.redact(undefined), { code: 'INVALID_JSON' });
  assert.throws(() => privacy.redact(NaN), { code: 'INVALID_JSON' });
  assert.throws(() => privacy.redact(new Date()), { code: 'INVALID_JSON' });
  assert.throws(() => privacy.redact(new Array(10)), { code: 'INVALID_JSON' });
  assert.throws(() => privacy.redact([undefined]), { code: 'INVALID_JSON' });
  assert.throws(() => privacy.restore({ value: () => 'ignored' }), { code: 'INVALID_JSON' });
  let called = false;
  const getter = { get value() { called = true; return 'secret'; } };
  for (const method of ['redact', 'restore', 'containsProtected', 'hasAliases', 'hasUnknownTokens']) {
    assert.throws(() => privacy[method](getter), { code: 'INVALID_JSON' });
  }
  assert.equal(called, false);
});

test('large unrelated tool output needs no generic email or number scan', () => {
  const privacy = createPrivacy({ mappings: TEST_MAPPINGS });
  const text = '@ ' + 'x'.repeat(100_000) + ' other@example.org';
  assert.equal(privacy.redact(text), text);
  assert.equal(privacy.containsProtected(text), false);
});
