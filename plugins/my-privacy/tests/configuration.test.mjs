import test from 'node:test';
import assert from 'node:assert/strict';
import { parseMappings, MAX_CONFIG_CHARS } from '../lib/configuration.js';
import { createPrivacy } from '../lib/privacy.js';
import { TEST_MAPPINGS, TEST_CONFIG_TEXT } from './fixtures/mappings.js';

test('configuration parser accepts explicit fictional mappings and casing pairs', () => {
  const mappings = parseMappings(TEST_CONFIG_TEXT);
  assert.deepEqual(mappings, TEST_MAPPINGS);
  const privacy = createPrivacy({ mappings });
  assert.equal(privacy.redact('ChenXingHe Cedarbyte 云杉智科'), 'RyanChen Harborwave 海岚数科');
  assert.equal(createPrivacy({ mappings }).restore('RyanChen Harborwave 海岚数科'), 'ChenXingHe Cedarbyte 云杉智科');
});

test('configuration parser permits an intentionally empty mapping list', () => {
  assert.deepEqual(parseMappings('{"mappings":[]}'), []);
  const literal = '陈星河 chenxinghe 云杉智科 cedarbyte user@example.test';
  assert.equal(createPrivacy().redact(literal), literal);
  assert.equal(createPrivacy({ mappings: [] }).restore(literal), literal);
});

test('invalid JSON, absent mappings and unknown settings are rejected with fixed errors', () => {
  assert.throws(() => parseMappings('{synthetic-not-json'), { code: 'INVALID_JSON' });
  for (const value of [null, {}, [], 42]) assert.throws(() => parseMappings(value), { code: 'INVALID_CONFIG' });
  for (const value of ['{}', '[]', 'null', '{"mappings":{}}', '{"mappings":[],"credential":"synthetic-only"}']) {
    assert.throws(() => parseMappings(value), { code: 'INVALID_CONFIG' });
  }
});

test('configuration size and entry limits stop oversized input without echoing it', () => {
  assert.equal(MAX_CONFIG_CHARS, 262144);
  assert.throws(() => parseMappings('x'.repeat(MAX_CONFIG_CHARS + 1)), { code: 'SIZE_LIMIT' });
  assert.throws(() => parseMappings(TEST_CONFIG_TEXT, { maxChars: 20 }), { code: 'SIZE_LIMIT' });
  assert.throws(() => parseMappings('{"mappings":[]}', { maxChars: 0 }), { code: 'INVALID_CONFIG' });
  const text = JSON.stringify({ mappings: Array.from({ length: 257 }, (_, index) => ({ from: `source${index}`, to: `alias${index}` })) });
  assert.throws(() => parseMappings(text), { code: 'MAPPING_LIMIT' });
});

test('case pairs must belong to one mapping and define an unambiguous reversal', () => {
  const mapping = TEST_MAPPINGS[1];
  assert.throws(() => createPrivacy({ mappings: [{ ...mapping, casePairs: [{ from: 'OtherPerson', to: 'RyanChen' }] }] }), { code: 'INVALID_CONFIG' });
  assert.throws(() => createPrivacy({ mappings: [{ ...mapping, casePairs: [mapping.casePairs[0], mapping.casePairs[0]] }] }), { code: 'AMBIGUOUS_CONFIG' });
  assert.throws(() => parseMappings(JSON.stringify({ mappings: [{ ...mapping, casePairs: [{ ...mapping.casePairs[0], regex: true }] }] })), { code: 'INVALID_CONFIG' });
});
