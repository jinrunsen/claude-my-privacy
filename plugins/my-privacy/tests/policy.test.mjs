import test from 'node:test';
import assert from 'node:assert/strict';
import { createPrivacy } from '../lib/privacy.js';
import { TEST_MAPPINGS } from './fixtures/mappings.js';
import { resolvePath, prepareTool, prepareBash } from '../lib/tool-policy.js';

const existing = paths => async path => paths.includes(path);

// These tests exercise translation only. No shell, SSH or network command runs.
test('missing alias file paths restore deterministically without checking the original target', async () => {
  const checked = [];
  const path = '/synthetic/ryanchen/Projects/harborwave/missing.txt';
  const result = await resolvePath(path, createPrivacy({ mappings: TEST_MAPPINGS }), async candidate => { checked.push(candidate); return false; });
  assert.equal(result, '/synthetic/chenxinghe/Projects/cedarbyte/missing.txt');
  assert.deepEqual(checked, [path]);
});

test('existing literal alias paths are preserved even when an alternate target exists', async () => {
  const path = '/synthetic/ryanchen/file.txt';
  assert.equal(await resolvePath(path, createPrivacy({ mappings: TEST_MAPPINGS }), existing([path, '/synthetic/chenxinghe/file.txt'])), path);
});

test('existing alias selection never needs canonical path inspection', async () => {
  const path = '/synthetic/ryanchen/file.txt';
  let canonicalCalled = false;
  const result = await resolvePath(path, createPrivacy({ mappings: TEST_MAPPINGS }), existing([path]), false, async () => {
    canonicalCalled = true;
    throw new Error('synthetic canonical lookup unavailable');
  });
  assert.equal(result, path);
  assert.equal(canonicalCalled, false);
});

test('new file paths do not require a preexisting parent or target', async () => {
  const out = await prepareTool({ tool: 'Write', file_path: '/synthetic/ryanchen/new/harborwave.txt', content: 'Harborwave' }, createPrivacy({ mappings: TEST_MAPPINGS }), existing([]));
  assert.equal(out.file_path, '/synthetic/chenxinghe/new/cedarbyte.txt');
  assert.equal(out.content, 'Cedarbyte');
});

test('missing and failed filesystem helpers fall back to restored paths', async () => {
  const path = '/synthetic/ryanchen/file.txt';
  for (const exists of [undefined, async () => { throw new Error('synthetic lookup failure'); }]) {
    assert.equal(await resolvePath(path, createPrivacy({ mappings: TEST_MAPPINGS }), exists), '/synthetic/chenxinghe/file.txt');
  }
});

test('paths without configured aliases and old short aliases do not need filesystem checks', async () => {
  for (const path of ['/synthetic/rc/file.txt', '/synthetic/cxh/file.txt', '/synthetic/ordinary/file.txt']) {
    let called = false;
    assert.equal(await resolvePath(path, createPrivacy({ mappings: TEST_MAPPINGS }), async () => { called = true; return true; }), path);
    assert.equal(called, false);
  }
});

test('each explicit path field preserves an existing literal target independently', async () => {
  const event = { tool: 'mcp__synthetic__run', file_path: '/synthetic/ryanchen/a', path: '/synthetic/ryanchen/b', notebook_path: '/synthetic/ryanchen/c' };
  const out = await prepareTool(event, createPrivacy({ mappings: TEST_MAPPINGS }), existing([event.path]));
  assert.equal(out.file_path, '/synthetic/chenxinghe/a');
  assert.equal(out.path, event.path);
  assert.equal(out.notebook_path, '/synthetic/chenxinghe/c');
});

test('Bash restores configured aliases throughout a heredoc without parsing or requoting', async () => {
  const command = `cd "/synthetic/ryanchen/a b"; python3 - <<'PY'
p='harborwave.txt'
s='陈瑞恩 /synthetic/ryanchen'
print(s, p)
PY
cat harborwave.txt | sed -n '1,2p'; git diff --stat`;
  const expected = `cd "/synthetic/chenxinghe/a b"; python3 - <<'PY'
p='cedarbyte.txt'
s='陈星河 /synthetic/chenxinghe'
print(s, p)
PY
cat cedarbyte.txt | sed -n '1,2p'; git diff --stat`;
  const out = await prepareBash({ tool: 'Bash', command }, createPrivacy({ mappings: TEST_MAPPINGS }), () => { throw new Error('Bash must not look up paths'); });
  assert.equal(out.command, expected);
});

test('Bash keeps loops, separators, quoting and variable expressions as written', async () => {
  const command = 'cd /synthetic/ryanchen; for f in *.md; do cat "$f"; done && printf "%s" "$TOKEN" | cat; test "$x" || true';
  const out = await prepareBash({ tool: 'Bash', command }, createPrivacy({ mappings: TEST_MAPPINGS }));
  assert.equal(out.command, command.replace('ryanchen', 'chenxinghe'));
});

test('Bash translates synthetic SSH account and company domain strings directly', async () => {
  const command = 'ssh synthetic-host "printf \'%s\\n\' email=ryanchen@harborwave.com"';
  const out = await prepareBash({ tool: 'Bash', command }, createPrivacy({ mappings: TEST_MAPPINGS }));
  assert.equal(out.command, 'ssh synthetic-host "printf \'%s\\n\' email=chenxinghe@cedarbyte.com"');
});

test('unrelated emails, telephone strings and old placeholders pass through all tool arguments', async () => {
  const event = { tool: 'Bash', command: 'printf "%s\\n" other.synthetic@example.test +12025550123 "<PII_EMAIL_OLDSESSION_1>"', description: 'call account@example.test' };
  assert.deepEqual(await prepareBash(event, createPrivacy({ mappings: TEST_MAPPINGS })), event);
});

test('native syntax errors and mutating commands are left for the native tool', async () => {
  for (const command of ['cd /synthetic/ryanchen;; ls', 'rm /synthetic/ryanchen/file.txt', 'rg --pre=cat text /synthetic/ryanchen/file.txt', 'cd "/synthetic/ryanchen/$dir" && echo "$x"', 'cat /synthetic/ryanchen/$(pwd)']) {
    assert.equal((await prepareBash({ tool: 'Bash', command }, createPrivacy({ mappings: TEST_MAPPINGS }))).command, command.replaceAll('ryanchen', 'chenxinghe'));
  }
});

test('all execution tools restore nested string values while keeping keys and metadata intact', async () => {
  const event = {
    tool: 'mcp__harborwave__run', tool_use_id: 'tool-ryanchen', agentId: 'agent-harborwave',
    payload: { harborwave: 'Harborwave', nested: ['ryanchen@harborwave.com', { value: '陈瑞恩 海岚数科', count: 3, enabled: true, nothing: null }] },
    description: 'ryanchen Harborwave',
  };
  const out = await prepareTool(event, createPrivacy({ mappings: TEST_MAPPINGS }));
  assert.equal(out.tool, event.tool);
  assert.equal(out.tool_use_id, event.tool_use_id);
  assert.equal(out.agentId, event.agentId);
  assert.deepEqual(Object.keys(out.payload), ['harborwave', 'nested']);
  assert.deepEqual(out.payload.nested, ['chenxinghe@cedarbyte.com', { value: '陈星河 云杉智科', count: 3, enabled: true, nothing: null }]);
  assert.equal(out.payload.harborwave, 'Cedarbyte');
  assert.equal(out.description, 'chenxinghe Cedarbyte');
  assert.equal(event.payload.harborwave, 'Harborwave');
});

test('nested object keys that resemble sensitive identifiers remain schema keys', async () => {
  const event = { tool: 'mcp__synthetic__run', schema: { properties: { ryanchen: { description: 'Harborwave' } }, required: ['ryanchen'] } };
  const out = await prepareTool(event, createPrivacy({ mappings: TEST_MAPPINGS }));
  assert.deepEqual(Object.keys(out.schema.properties), ['ryanchen']);
  assert.equal(out.schema.properties.ryanchen.description, 'Cedarbyte');
  assert.deepEqual(out.schema.required, ['chenxinghe']);
});

test('Read and Edit preserve working alias paths but restore edit content values', async () => {
  const path = '/synthetic/ryanchen/config.js';
  const event = { tool: 'Edit', file_path: path, old_string: 'Harborwave rc', new_string: '陈瑞恩 cxh', edits: [{ old_string: 'harborwave', new_string: 'ryanchen' }] };
  const out = await prepareTool(event, createPrivacy({ mappings: TEST_MAPPINGS }), existing([path]));
  assert.equal(out.file_path, path);
  assert.equal(out.old_string, 'Cedarbyte rc');
  assert.equal(out.new_string, '陈星河 cxh');
  assert.deepEqual(out.edits, [{ old_string: 'cedarbyte', new_string: 'chenxinghe' }]);
});

test('WebFetch restores destinations while keeping its model-facing prompt pseudonymous', async () => {
  const event = { tool: 'WebFetch', url: 'https://sase.harborwave.com.cn/ryanchen', prompt: 'Read Harborwave documentation' };
  assert.deepEqual(await prepareTool(event, createPrivacy({ mappings: TEST_MAPPINGS })), { tool: 'WebFetch', url: 'https://sase.cedarbyte.com.cn/chenxinghe', prompt: 'Read Harborwave documentation' });
  const originalPrompt = { ...event, prompt: 'Read cedarbyte documentation by chenxinghe' };
  assert.equal((await prepareTool(originalPrompt, createPrivacy({ mappings: TEST_MAPPINGS }))).prompt, 'Read harborwave documentation by ryanchen');
});

test('Agent, Task and Skill arguments remain on the model side of the privacy boundary', async () => {
  for (const tool of ['Agent', 'Task', 'Skill']) {
    const event = { tool, tool_use_id: 'call-chenxinghe', agentId: 'cedarbyte-agent', prompt: '陈星河 chenxinghe 云杉智科 cedarbyte', nested: { path: '/synthetic/chenxinghe', email: 'other@example.test' } };
    const out = await prepareTool(event, createPrivacy({ mappings: TEST_MAPPINGS }), () => { throw new Error('Model context needs no path check'); });
    assert.equal(out.prompt, '陈瑞恩 ryanchen 海岚数科 harborwave');
    assert.deepEqual(out.nested, { path: '/synthetic/ryanchen', email: 'other@example.test' });
    assert.equal(out.tool_use_id, event.tool_use_id);
    assert.equal(out.agentId, event.agentId);
    assert.deepEqual(await prepareTool(out, createPrivacy({ mappings: TEST_MAPPINGS })), out);
  }
});

test('best effort translation failures do not turn valid tools into privacy denials', async () => {
  const event = { tool: 'Bash', command: 'printf safe', description: 'safe synthetic description' };
  const privacy = { restore() { throw new Error('synthetic unavailable translation'); } };
  assert.deepEqual(await prepareBash(event, privacy), event);
});

test('optional undefined argument values remain valid and are not converted to strings', async () => {
  const event = { tool: 'Bash', command: 'printf ryanchen', description: undefined, timeout: 1000, run_in_background: false };
  const out = await prepareBash(event, createPrivacy({ mappings: TEST_MAPPINGS }));
  assert.equal(out.command, 'printf chenxinghe');
  assert.equal(out.description, undefined);
  assert.equal(out.timeout, 1000);
  assert.equal(out.run_in_background, false);
});
