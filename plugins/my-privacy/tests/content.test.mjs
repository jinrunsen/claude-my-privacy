import test from 'node:test';
import assert from 'node:assert/strict';
import { createPrivacy } from '../lib/privacy.js';
import { TEST_MAPPINGS } from './fixtures/mappings.js';
import { compactMessages } from '../lib/content.js';

test('compaction preserves tool protocol identity while replacing supported text and argument values', () => {
  const privacy = createPrivacy({ mappings: TEST_MAPPINGS });
  const original = [{ role: 'assistant', handle: 'cedarbyte-host-handle', text: 'Cedarbyte', toolUses: [{
    tool: 'mcp__cedarbyte__lookup', tool_use_id: 'cedarbyte-call-id',
    input: { cedarbyte_schema_key: 'chenxinghe@cedarbyte.com' },
    text: '云杉智科 contact other@example.test', result: { company: 'Cedarbyte' },
  }] }, { role: 'user', handle: 'result-handle', text: '', toolUses: [], toolResults: [{
    tool_use_id: 'cedarbyte-call-id', isError: false, text: '陈星河',
  }] }];
  const output = compactMessages(original, value => privacy.redact(value));
  assert.equal(output[0].handle, undefined);
  assert.equal(output[0].text, 'Harborwave');
  assert.equal(output[0].toolUses[0].tool, 'mcp__cedarbyte__lookup');
  assert.equal(output[0].toolUses[0].tool_use_id, 'cedarbyte-call-id');
  assert.deepEqual(output[0].toolUses[0].input, { cedarbyte_schema_key: 'ryanchen@harborwave.com' });
  assert.equal(output[0].toolUses[0].text, '海岚数科 contact other@example.test');
  assert.equal(output[1].toolResults[0].tool_use_id, 'cedarbyte-call-id');
  assert.equal(output[1].toolResults[0].text, '陈瑞恩');
  assert.equal(original[0].text, 'Cedarbyte');
});

test('unchanged compaction rows retain handles so opaque host content is not rebuilt', () => {
  const privacy = createPrivacy({ mappings: TEST_MAPPINGS });
  const message = { role: 'user', handle: 'opaque-cedarbyte-handle', text: 'other@example.test cxh rc', toolUses: [] };
  assert.equal(compactMessages([message], value => privacy.redact(value))[0], message);
});

test('media embedded in a compacted result remains intact beside replaced text', () => {
  const privacy = createPrivacy({ mappings: TEST_MAPPINGS });
  const media = { type: 'image', source: { type: 'base64', data: 'cedarbytechenxinghe', media_type: 'image/png' } };
  const message = { role: 'user', text: 'Cedarbyte', toolUses: [], toolResults: [{
    tool_use_id: 'call', text: 'Cedarbyte', result: [media, { type: 'text', text: 'Cedarbyte' }],
  }] };
  const out = compactMessages([message], value => privacy.redact(value))[0];
  assert.equal(out.toolResults[0].result[0], media);
  assert.equal(out.toolResults[0].result[1].text, 'Harborwave');
});
