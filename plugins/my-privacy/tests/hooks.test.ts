import { test as modTest, expect, mock } from 'claude-code/testing';
import { TEST_CONFIG_PATH, TEST_CONFIG_TEXT } from './fixtures/mappings.js';

// Every configured test gets an isolated synthetic config; host HOME and the
// actual user's mappings are never read by this suite.
function test(name: string, body: ($: any, on: any) => Promise<void>) {
  modTest(name, async ($, on) => {
    mock.env(on, { CLAUDE_MY_PRIVACY_CONFIG: TEST_CONFIG_PATH, HOME: '/synthetic/home' });
    on('fs.read', { path: TEST_CONFIG_PATH }, () => ({ value: TEST_CONFIG_TEXT }));
    await body($, on);
  });
}

// Native tools and models are stubbed; these tests never execute a shell or network call.
const readResult = (text: string, path = '/synthetic/file.txt') => ({
  type: 'text' as const, file: { filePath: path, content: text, numLines: 1, startLine: 1, totalLines: 1 },
});
const bashResult = (stdout = '') => ({ stdout, stderr: '', interrupted: false });
const prompt = (text: string, extra = {}) => ({ text, wait: false, origin: { kind: 'composer' as const }, ...extra });
const step = () => ({ turnId: 'synthetic-turn', index: 0, model: 'offline-stub', messageCount: 5000 });
const done = (event: any) => ({ turnId: event.turnId, index: event.index, answer: 'model reached', toolUses: [], stopReason: 'end_turn', usage: null });
async function drain(stream: any) {
  let item = await stream.next();
  while (!item.done) item = await stream.next();
  return item.value;
}

test('only the four configured names are replaced in prompts and context', async ($, on) => {
  on('prompt.submit', ($, event) => ({ text: event.text, context: event.context }));
  const out = await $.prompt.submit(prompt('陈星河 chenxinghe 云杉智科 Cedarbyte cxh rc', {
    context: ['other.person@example.test +1 202-555-0147 4111111111111111'],
  }));
  expect(out.text).toBe('陈瑞恩 ryanchen 海岚数科 Harborwave cxh rc');
  expect(out.context).toEqual(['other.person@example.test +1 202-555-0147 4111111111111111']);
});

test('prompt attachments pass through while surrounding text is replaced', async ($, on) => {
  const attachment = { type: 'image', mediaType: 'image/png', data: 'synthetic-base64' };
  let reached = false;
  on('prompt.submit', ($, event) => {
    reached = true;
    expect(event.attachments).toEqual([attachment]);
    return { text: event.text };
  });
  const out = await $.prompt.submit(prompt('Cedarbyte', { attachments: [attachment] }));
  expect(reached).toBe(true);
  expect(out.text).toBe('Harborwave');
  expect(out.drop).toBe(undefined);
});

test('raw originals and arbitrary email arguments are accepted by the native tool once', async ($, on) => {
  let count = 0;
  const command = 'printf "%s" "chenxinghe other.person@example.test Cedarbyte cxh"';
  on('tool.call', { tool: 'Bash' }, ($, event) => {
    count += 1;
    expect(event.command).toBe(command);
    return { result: bashResult('chenxinghe other.person@example.test Cedarbyte cxh') };
  });
  const out = await $.tool.call({ tool: 'Bash', command });
  expect(count).toBe(1);
  expect(out.deny).toBe(undefined);
  expect(out.result.stdout).toBe('ryanchen other.person@example.test Harborwave cxh');
});

test('complex shell grammar and account assignments restore full aliases locally', async ($, on) => {
  const command = 'cd /synthetic/ryanchen; export CONTACT=ryanchen@harborwave.com; python3 - <<\'PY\'\nprint("陈瑞恩 海岚数科 cxh rc")\nPY\nfor x in a b; do printf "%s" "$x"; done | cat';
  const restored = 'cd /synthetic/chenxinghe; export CONTACT=chenxinghe@cedarbyte.com; python3 - <<\'PY\'\nprint("陈星河 云杉智科 cxh rc")\nPY\nfor x in a b; do printf "%s" "$x"; done | cat';
  on('tool.call', { tool: 'Bash' }, ($, event) => {
    expect(event.command).toBe(restored);
    return { result: bashResult('chenxinghe@cedarbyte.com 陈星河 云杉智科') };
  });
  const out = await $.tool.call({ tool: 'Bash', command });
  expect(out.deny).toBe(undefined);
  expect(out.result.stdout).toBe('ryanchen@harborwave.com 陈瑞恩 海岚数科');
});

test('old PII placeholders and short identifiers are not blocked or reversed', async ($, on) => {
  const command = 'printf "%s" "<PII_EMAIL_OLDMAP_1> cxh rc acxhb arcb"';
  on('tool.call', { tool: 'Bash' }, ($, event) => {
    expect(event.command).toBe(command);
    return { result: bashResult(command) };
  });
  const out = await $.tool.call({ tool: 'Bash', command });
  expect(out.deny).toBe(undefined);
  expect(out.result.stdout).toBe(command);
});

test('missing explicit file aliases restore to the original filename', async ($, on) => {
  on('fs.exists', () => ({ value: false }));
  on('tool.call', { tool: 'Read' }, ($, event) => {
    expect(event.file_path).toBe('/synthetic/chenxinghe/sase.cedarbyte.com_nginx');
    return { result: readResult('Cedarbyte', event.file_path) };
  });
  const out = await $.tool.call({ tool: 'Read', file_path: '/synthetic/ryanchen/sase.harborwave.com_nginx' });
  expect(out.deny).toBe(undefined);
  expect(out.result.file.filePath).toBe('/synthetic/ryanchen/sase.harborwave.com_nginx');
  expect(out.result.file.content).toBe('Harborwave');
});

test('an existing explicit alias file path is preferred without ambiguity denial', async ($, on) => {
  on('fs.exists', () => ({ value: true }));
  on('tool.call', { tool: 'Read' }, ($, event) => {
    expect(event.file_path).toBe('/synthetic/ryanchen/file.txt');
    return { result: readResult('safe', event.file_path) };
  });
  const out = await $.tool.call({ tool: 'Read', file_path: '/synthetic/ryanchen/file.txt' });
  expect(out.deny).toBe(undefined);
});

test('filesystem lookup failures do not block or duplicate native execution', async ($, on) => {
  let count = 0;
  on('fs.exists', () => { throw new Error('synthetic filesystem failure'); });
  on('tool.call', { tool: 'Read' }, ($, event) => {
    count += 1;
    return { result: readResult('Cedarbyte', event.file_path) };
  });
  const out = await $.tool.call({ tool: 'Read', file_path: '/synthetic/ryanchen/file.txt' });
  expect(count).toBe(1);
  expect(out.deny).toBe(undefined);
});

test('Write restores names and company emails but preserves generic emails and short identifiers', async ($, on) => {
  on('fs.exists', () => ({ value: false }));
  on('tool.call', { tool: 'Write' }, ($, event) => {
    expect(event.file_path).toBe('/synthetic/chenxinghe/new.txt');
    expect(event.content).toBe('陈星河 云杉智科 chenxinghe@cedarbyte.com other.person@example.test cxh rc');
    return { result: { type: 'create', filePath: event.file_path, content: event.content, structuredPatch: [], originalFile: null } };
  });
  const out = await $.tool.call({ tool: 'Write', file_path: '/synthetic/ryanchen/new.txt',
    content: '陈瑞恩 海岚数科 ryanchen@harborwave.com other.person@example.test cxh rc' });
  expect(out.deny).toBe(undefined);
  expect(out.result.content).toBe('陈瑞恩 海岚数科 ryanchen@harborwave.com other.person@example.test cxh rc');
});

test('Edit restores both match and replacement text without collision checks', async ($, on) => {
  on('fs.exists', () => ({ value: false }));
  on('tool.call', { tool: 'Edit' }, ($, event) => {
    expect(event.file_path).toBe('/synthetic/chenxinghe/file.txt');
    expect(event.old_string).toBe('Cedarbyte cxh rc');
    expect(event.new_string).toBe('云杉智科 chenxinghe@cedarbyte.com');
    return { result: { filePath: event.file_path, oldString: event.old_string, newString: event.new_string,
      originalFile: event.old_string, structuredPatch: [], userModified: false, replaceAll: false } };
  });
  const out = await $.tool.call({ tool: 'Edit', file_path: '/synthetic/ryanchen/file.txt',
    old_string: 'Harborwave cxh rc', new_string: '海岚数科 ryanchen@harborwave.com' });
  expect(out.deny).toBe(undefined);
  expect(out.result.newString).toBe('海岚数科 ryanchen@harborwave.com');
});

test('Agent and Skill prompts keep aliases instead of restoring private values for a model', async ($, on) => {
  const seen: string[] = [];
  on('tool.call', ($, event) => {
    seen.push(JSON.stringify(event));
    return { result: 'safe synthetic delegated result' };
  });
  await $.tool.call({ tool: 'Agent', prompt: '陈瑞恩 ryanchen Harborwave other.person@example.test', description: 'Synthetic delegation' });
  await $.tool.call({ tool: 'Skill', skill: 'synthetic', args: 'ryanchen@harborwave.com' });
  expect(seen.length).toBe(2);
  expect(seen[0].includes('chenxinghe')).toBe(false);
  expect(seen[0].includes('ryanchen')).toBe(true);
  expect(seen[1].includes('ryanchen@harborwave.com')).toBe(true);
});

test('optional undefined output fields keep native Bash object shape', async ($, on) => {
  on('tool.call', { tool: 'Bash' }, () => ({ ref: 819, text: 'chenxinghe', result: {
    stdout: 'chenxinghe other.person@example.test', stderr: '', interrupted: false,
    backgroundTaskId: undefined, backgroundedByUser: undefined,
  } }));
  const out = await $.tool.call({ tool: 'Bash', command: 'printf safe', description: undefined });
  expect(out.ref).toBe(undefined);
  expect(out.text).toBe(undefined);
  expect(out.result.stdout).toBe('ryanchen other.person@example.test');
  expect(out.result.interrupted).toBe(false);
});

test('native error text stays an error envelope instead of a string-shaped Bash result', async ($, on) => {
  let count = 0;
  on('tool.call', { tool: 'Bash' }, () => {
    count += 1;
    return { isError: true, ref: 820, result: undefined, text: 'Synthetic failure chenxinghe Cedarbyte other.person@example.test' };
  });
  const out = await $.tool.call({ tool: 'Bash', command: 'false' });
  expect(count).toBe(1);
  expect(out.result).toBe(undefined);
  expect(out.ref).toBe(undefined);
  expect(out.deny).toContain('ryanchen Harborwave other.person@example.test');
});

test('native permission denial remains a denial with targeted replacements', async ($, on) => {
  on('tool.call', { tool: 'Bash' }, () => ({ deny: 'Permission denied for chenxinghe' }));
  const out = await $.tool.call({ tool: 'Bash', command: 'synthetic-command' });
  expect(out.deny).toBe('Permission denied for ryanchen');
});

test('a native tool exception is never retried', async ($, on) => {
  let count = 0;
  on('tool.call', { tool: 'Bash' }, () => { count += 1; throw new Error('Synthetic native error'); });
  const out = await $.tool.call({ tool: 'Bash', command: 'synthetic-command' });
  expect(out.deny).toContain('Underlying tool failed');
  expect(out.deny.includes('MyPrivacy guard')).toBe(false);
  expect(count).toBe(1);
});

test('oversized prompt filtering falls back to original text and records metadata', async ($, on) => {
  const rows: any[] = [];
  const text = 'chenxinghe ' + 'x'.repeat(8_000_001);
  let count = 0;
  on('clock.now', () => ({ value: 1791079200000 }));
  on('store.set', ($, event) => { rows.push(event.value); return { value: undefined }; });
  on('store.keys', () => ({ value: [] }));
  on('prompt.submit', ($, event) => {
    count += 1;
    expect(event.text === text).toBe(true);
    return { text: 'original forwarded' };
  });
  const out = await $.prompt.submit(prompt(text));
  expect(count).toBe(1);
  expect(out.text).toBe('original forwarded');
  expect(out.drop).toBe(undefined);
  expect(rows.some(row => row.kind === 'filter_fallback' && row.stage === 'prompt.submit')).toBe(true);
  expect(JSON.stringify(rows).includes('chenxinghe')).toBe(false);
  expect(JSON.stringify(rows).length < 2000).toBe(true);
});

test('output key collisions pass the original result and record a fallback without retrying', async ($, on) => {
  const rows: any[] = [];
  let count = 0;
  const result = { stdout: 'chenxinghe', stderr: '', interrupted: false, chenxinghe: 'first', ryanchen: 'second' };
  on('clock.now', () => ({ value: 1791079200000 }));
  on('store.set', ($, event) => { rows.push(event.value); return { value: undefined }; });
  on('store.keys', () => ({ value: [] }));
  on('tool.call', { tool: 'Bash' }, () => { count += 1; return { result }; });
  const out = await $.tool.call({ tool: 'Bash', command: 'synthetic-command' });
  expect(count).toBe(1);
  expect(out.deny).toBe(undefined);
  expect(out.result).toEqual(result);
  expect(rows.some(row => row.kind === 'filter_fallback' && row.stage === 'result')).toBe(true);
  expect(JSON.stringify(rows).includes('chenxinghe')).toBe(false);
});

test('media results pass through with the same binary payload', async ($, on) => {
  const result = { type: 'image', file: { filePath: '/synthetic/image.png', base64: 'synthetic-base64', type: 'image/png', originalSize: 16 } };
  on('tool.call', { tool: 'Read' }, () => ({ result }));
  const out = await $.tool.call({ tool: 'Read', file_path: '/synthetic/image.png' });
  expect(out.deny).toBe(undefined);
  expect(out.result.file.base64).toBe('synthetic-base64');
});

test('session text is replaced while media, signed thinking and pinned tool arguments survive', async ($, on) => {
  const toolUse = { type: 'tool_use', id: 'tool-chenxinghe-1', name: 'Read', input: { file_path: '/synthetic/chenxinghe/file.txt' } };
  const thinking = { type: 'thinking', thinking: 'signed synthetic Cedarbyte text', signature: 'synthetic-signature' };
  const media = { type: 'image', source: { type: 'base64', media_type: 'image/png', data: 'synthetic' } };
  const captures: any[] = [];
  on('session.append', ($, event, next) => { captures.push(event); return next(event); });
  const event: any = { uuid: 'row-chenxinghe-1', door: 'tool-result', origin: { kind: 'tool', tool: 'Read' }, message: {
    type: 'assistant', role: 'assistant', content: [{ type: 'text', text: 'chenxinghe other.person@example.test' }, toolUse, thinking, media],
  } };
  await expect($.session.append(event)).rejects.toThrow('no implementation for session.append');
  expect(captures[0].uuid).toBe('row-chenxinghe-1');
  expect(captures[0].message.content[0].text).toBe('ryanchen other.person@example.test');
  expect(captures[0].message.content[1]).toEqual(toolUse);
  expect(captures[0].message.content[2]).toEqual(thinking);
  expect(captures[0].message.content[3]).toEqual(media);
});

test('a later model step is not blocked by raw pinned history, media, or history length', async ($, on) => {
  let historyRead = false;
  let reached = false;
  on('session.messages', () => { historyRead = true; throw new Error('No history gate should read this'); });
  on('turn.step', async function* ($, event) { reached = true; return done(event); });
  const out = await drain($.turn.step(step()));
  expect(reached).toBe(true);
  expect(historyRead).toBe(false);
  expect(out.answer).toBe('model reached');
});

test('resuming a session does not impose a plugin-specific prompt lock', async ($, on) => {
  on('classic.SessionStart', () => ({}));
  on('prompt.submit', ($, event) => ({ text: event.text }));
  await $.classic.SessionStart({ source: 'resume' });
  const out = await $.prompt.submit(prompt('continue chenxinghe other.person@example.test'));
  expect(out.drop).toBe(undefined);
  expect(out.text).toBe('continue ryanchen other.person@example.test');
});

test('my-privacy-recover is informational and never rewrites history or retries tools', async ($, on) => {
  let compacted = false;
  let toolCalls = 0;
  on('session.compact', () => { compacted = true; return { messages: [] }; });
  on('tool.call', () => { toolCalls += 1; return { deny: 'unused' }; });
  const out = await $.command.run({ command: 'my-privacy-recover' });
  expect(out.text).toContain('no history lock');
  expect(compacted).toBe(false);
  expect(toolCalls).toBe(0);
});

modTest('missing configuration passes through without reading any real user directory', async ($, on) => {
  const paths: string[] = [];
  mock.env(on, { HOME: '/synthetic/config-absent-home' });
  on('fs.read', ($, event) => {
    paths.push(event.path);
    throw new Error('Synthetic missing configuration');
  });
  on('prompt.submit', ($, event) => ({ text: event.text }));
  const original = '陈星河 chenxinghe 云杉智科 cedarbyte private@example.test';
  const out = await $.prompt.submit(prompt(original));
  expect(out.text).toBe(original);
  expect(out.drop).toBe(undefined);
  const status = await $.command.run({ command: 'my-privacy-status' });
  expect(status.text).toContain('Configuration: unavailable; mappings: 0.');
  expect(status.text?.includes('/synthetic/')).toBe(false);
  expect(paths).toEqual(['/synthetic/config-absent-home/.config/claude-my-privacy/mappings.json']);
});

modTest('the MyPrivacy config override takes precedence over HOME and the legacy override', async ($, on) => {
  const paths: string[] = [];
  mock.env(on, {
    CLAUDE_MY_PRIVACY_CONFIG: TEST_CONFIG_PATH,
    CLAUDE_PRIVACY_CONFIG: '/synthetic/legacy-mappings.json',
    HOME: '/synthetic/home',
  });
  on('fs.read', ($, event) => {
    paths.push(event.path);
    return { value: TEST_CONFIG_TEXT };
  });
  on('prompt.submit', ($, event) => ({ text: event.text }));
  const out = await $.prompt.submit(prompt('chenxinghe cedarbyte'));
  expect(out.text).toBe('ryanchen harborwave');
  expect(paths).toEqual([TEST_CONFIG_PATH]);
});

modTest('a legacy config override is ignored without a MyPrivacy override', async ($, on) => {
  const paths: string[] = [];
  mock.env(on, {
    CLAUDE_PRIVACY_CONFIG: '/synthetic/legacy-mappings.json',
    HOME: '/synthetic/my-privacy-home',
  });
  on('fs.read', ($, event) => {
    paths.push(event.path);
    return { value: TEST_CONFIG_TEXT };
  });
  on('prompt.submit', ($, event) => ({ text: event.text }));
  const out = await $.prompt.submit(prompt('chenxinghe cedarbyte'));
  expect(out.text).toBe('ryanchen harborwave');
  expect(paths).toEqual(['/synthetic/my-privacy-home/.config/claude-my-privacy/mappings.json']);
});

modTest('malformed configuration passes through and reports only fixed status metadata', async ($, on) => {
  const rows: any[] = [];
  const invalid = '{"mappings": [{"from":"ChenXingHe", broken-json';
  mock.env(on, { CLAUDE_MY_PRIVACY_CONFIG: TEST_CONFIG_PATH, HOME: '/synthetic/home' });
  on('fs.read', { path: TEST_CONFIG_PATH }, () => ({ value: invalid }));
  on('clock.now', () => ({ value: 1791079200000 }));
  on('store.set', ($, event) => { rows.push(event.value); return { value: undefined }; });
  on('store.keys', () => ({ value: [] }));
  on('prompt.submit', ($, event) => ({ text: event.text }));
  const out = await $.prompt.submit(prompt('chenxinghe cedarbyte'));
  expect(out.text).toBe('chenxinghe cedarbyte');
  expect(out.drop).toBe(undefined);
  const status = await $.command.run({ command: 'my-privacy-status' });
  expect(status.text).toContain('Configuration: invalid; mappings: 0.');
  expect(status.text?.includes('ChenXingHe')).toBe(false);
  expect(status.text?.includes('/synthetic/')).toBe(false);
  expect(JSON.stringify(rows).includes('ChenXingHe')).toBe(false);
  expect(JSON.stringify(rows).includes('broken-json')).toBe(false);
});

modTest('empty explicit configuration is valid and leaves account text unchanged', async ($, on) => {
  let reads = 0;
  mock.env(on, { CLAUDE_MY_PRIVACY_CONFIG: TEST_CONFIG_PATH });
  on('fs.read', { path: TEST_CONFIG_PATH }, () => { reads += 1; return { value: '{"mappings":[]}' }; });
  on('tool.call', { tool: 'Bash' }, ($, event) => ({ result: bashResult(event.command) }));
  const command = 'printf "%s" "chenxinghe@cedarbyte.example ryanchen@harborwave.example"';
  const out = await $.tool.call({ tool: 'Bash', command });
  expect(out.deny).toBe(undefined);
  expect(out.result.stdout).toBe(command);
  const status = await $.command.run({ command: 'my-privacy-status' });
  expect(status.text).toContain('Configuration: loaded; mappings: 0.');
  expect(reads).toBe(1);
});

test('configured status reports only load state and mapping count', async ($) => {
  const status = await $.command.run({ command: 'my-privacy-status' });
  expect(status.text).toContain('Configuration: loaded; mappings: 4.');
  expect(status.text?.includes('chenxinghe')).toBe(false);
  expect(status.text?.includes('cedarbyte')).toBe(false);
  expect(status.text?.includes('/synthetic/')).toBe(false);
});
