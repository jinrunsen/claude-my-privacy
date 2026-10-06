import { test as modTest, expect, mock } from 'claude-code/testing';
import { TEST_CONFIG_PATH, TEST_CONFIG_TEXT } from './fixtures/mappings.js';

// These fixtures never consult host mappings, credentials, or session history.
function test(name: string, body: ($: any, on: any) => Promise<void>, options = {}) {
  modTest(name, options, async ($, on) => {
    mock.env(on, { CLAUDE_MY_PRIVACY_CONFIG: TEST_CONFIG_PATH, HOME: '/synthetic/home' });
    on('fs.read', { path: TEST_CONFIG_PATH }, () => ({ value: TEST_CONFIG_TEXT }));
    await body($, on);
  });
}

const message = (text: string, extra = {}) => ({
  surface: 'terminal', component: 'AssistantMessage', requestId: 'reply-ryanchen',
  viewport: { columns: 120, rows: 40, isFullscreen: true },
  props: { text, isFirstOfReply: true, onScreen: { first: 1, last: 4, of: 7 } },
  ...extra,
});
const drawing = (text: string) => ({ type: 'Text', props: {}, children: [text] });

test('AssistantMessage restores configured aliases in Markdown without changing its source event', async ($, on) => {
  const alias = '# 陈瑞恩 / 海岚数科\n\n**RyanChen** RYANCHEN Harborwave HARBORWAVE\n' +
    '`ryanchen@harborwave.example` [account](https://harborwave.example/ryanchen)\n' +
    'other.person@example.test cxh rc <PII_EMAIL_OLDMAP_1>';
  const original = '# 陈星河 / 云杉智科\n\n**ChenXingHe** CHENXINGHE Cedarbyte CEDARBYTE\n' +
    '`chenxinghe@cedarbyte.example` [account](https://cedarbyte.example/chenxinghe)\n' +
    'other.person@example.test cxh rc <PII_EMAIL_OLDMAP_1>';
  const input = message(alias);
  const before = JSON.stringify(input);
  let calls = 0;
  on('ui.render', { component: 'AssistantMessage' }, ($, event) => {
    calls += 1;
    expect(event).toEqual({ ...input, props: { ...input.props, text: original } });
    return drawing(event.props.text);
  });
  const out = await $.ui.render(input);
  expect(out).toEqual(drawing(original));
  expect(calls).toBe(1);
  expect(JSON.stringify(input)).toBe(before);
});

test('AssistantMessage preserves absent, null, and present onScreen across declared surfaces', async ($, on) => {
  const seen: any[] = [];
  on('ui.render', { component: 'AssistantMessage' }, ($, event) => {
    seen.push(event);
    return drawing(event.props.text);
  });
  for (const surface of ['terminal', 'desktop', 'mobile', 'vscode']) {
    for (const screen of [undefined, null, { first: 0, last: 2, of: 3 }]) {
      const props: any = { text: 'Harborwave', isFirstOfReply: false };
      if (screen !== undefined) props.onScreen = screen;
      const input = message(props.text, { surface, props });
      await $.ui.render(input);
      expect(seen.at(-1)).toEqual({ ...input, props: { ...props, text: 'Cedarbyte' } });
    }
  }
  expect(seen.length).toBe(12);
});

test('other render components keep their aliases', async ($, on) => {
  const seen: any[] = [];
  on('ui.render', ($, event) => { seen.push(event); return drawing('unchanged'); });
  const events = [
    { surface: 'terminal', component: 'UserMessage', requestId: 'user-ryanchen', props: {
      text: 'RyanChen Harborwave', origin: { kind: 'composer' }, isExpanded: true,
    } },
    { surface: 'terminal', component: 'ToolUse', requestId: 'tool-ryanchen', props: {
      tool_use_id: 'tool-ryanchen', tool: 'Bash', input: { command: 'echo Harborwave' },
      isRunning: false, isErrored: false, isInterrupted: false,
    } },
    { surface: 'terminal', component: 'ToolResult', requestId: 'tool-ryanchen', props: {
      tool_use_id: 'tool-ryanchen', tool: 'Bash', output: { stdout: 'Harborwave', stderr: '', interrupted: false }, isErrored: false,
    } },
    { surface: 'terminal', component: 'CommandOutput', requestId: 'command-ryanchen', props: {
      text: 'Harborwave', command: 'synthetic-status', args: 'ryanchen', isErrored: false,
    } },
  ];
  for (const event of events) await $.ui.render(event);
  expect(seen).toEqual(events);
});

test('successive partial and full render props restore only the current block', async ($, on) => {
  const seen: string[] = [];
  on('ui.render', { component: 'AssistantMessage' }, ($, event) => {
    seen.push(event.props.text);
    return drawing(event.props.text);
  });
  const inputs = [
    message('ryan'),
    message('ryanchen'),
    message('ryanchen Harbor'),
    message('ryanchen Harborwave'),
    message('unrelated reply', { requestId: 'second-message' }),
    message('chen', { requestId: 'third-message' }),
    message('', { requestId: 'empty-message' }),
    message('ryanchen Harborwave'),
  ];
  for (const input of inputs) await $.ui.render(input);
  expect(seen).toEqual(['ryan', 'chenxinghe', 'chenxinghe Harbor', 'chenxinghe Cedarbyte',
    'unrelated reply', 'chen', '', 'chenxinghe Cedarbyte']);
  expect(inputs.map(input => input.props.text)).toEqual([
    'ryan', 'ryanchen', 'ryanchen Harbor', 'ryanchen Harborwave', 'unrelated reply', 'chen', '', 'ryanchen Harborwave',
  ]);
});

test('display restoration leaves the session hook-chain text and later model view aliased', async ($, on) => {
  const alias = '陈瑞恩 RyanChen 海岚数科 ryanchen@harborwave.example';
  const saved: any[] = [];
  on('ui.render', { component: 'AssistantMessage' }, ($, event) => drawing(event.props.text));
  on('session.append', ($, event, next) => { saved.push(event.message); return next(event); });
  on('session.messages', () => ({ value: saved }));
  const input = message(alias);
  const out = await $.ui.render(input);
  expect(out).toEqual(drawing('陈星河 ChenXingHe 云杉智科 chenxinghe@cedarbyte.example'));
  // Inject the engine's response event and inspect the hook chain. Durable
  // transcript persistence is checked separately by verification/run-display.py.
  await expect($.session.append({ uuid: 'synthetic-reply', door: 'response', origin: { kind: 'model', model: 'offline-stub' },
    message: { type: 'assistant', role: 'assistant', content: [{ type: 'text', text: input.props.text }] },
  })).rejects.toThrow('no implementation for session.append');
  const stream = $.turn.step({ turnId: 'next-synthetic-turn', index: 0, model: 'offline-stub', messageCount: 1 });
  let item = await stream.next();
  expect(item.value.text).toBe(alias);
  while (!item.done) item = await stream.next();
  expect(item.value.answer).toBe(alias);
  expect(saved[0].content[0].text).toBe(alias);
  expect(input.props.text).toBe(alias);
}, { plugins: [{ name: 'offline-display-model', register(on: any) {
  on('turn.step', async function* ($: any, event: any) {
    const history = await $.session.messages({ as: 'api' });
    const answer = history[0].content[0].text;
    yield { kind: 'text', index: 0, text: answer };
    return { turnId: event.turnId, index: event.index, answer, toolUses: [], stopReason: 'end_turn', usage: null };
  });
} }] });

test('oversized display falls back to the original aliases once and audits metadata only', async ($, on) => {
  const alias = 'ryanchen@harborwave.example ' + 'x'.repeat(8_000_001);
  const rows: any[] = [];
  let calls = 0;
  on('clock.now', () => ({ value: 1791079200000 }));
  on('store.set', ($, event) => { rows.push(event.value); return { value: undefined }; });
  on('store.keys', () => ({ value: [] }));
  on('ui.render', { component: 'AssistantMessage' }, ($, event) => {
    calls += 1;
    expect(event.props.text === alias).toBe(true);
    return drawing('alias reached renderer');
  });
  const out = await $.ui.render(message(alias));
  expect(out).toEqual(drawing('alias reached renderer'));
  expect(calls).toBe(1);
  expect(rows.some(row => row.kind === 'filter_fallback' && row.stage === 'ui.render')).toBe(true);
  expect(JSON.stringify(rows).includes('ryanchen')).toBe(false);
  expect(JSON.stringify(rows).includes('harborwave')).toBe(false);
  expect(JSON.stringify(rows).length < 2000).toBe(true);
});

test('a downstream render failure is not retried by the restoration hook', async ($, on) => {
  let calls = 0;
  on('ui.render', { component: 'AssistantMessage' }, ($, event) => {
    calls += 1;
    expect(event.props.text).toBe('Cedarbyte');
    throw new Error('Synthetic downstream renderer failed');
  });
  // The host skips throwing hooks and exposes its own no-implementation error.
  await expect($.ui.render(message('Harborwave'))).rejects.toThrow('no implementation for ui.render');
  expect(calls).toBe(1);
});

for (const [state, config] of [
  ['unavailable', undefined], ['invalid', '{"mappings":'], ['loaded', '{"mappings":[]}'],
] as const) {
  modTest(`${state} display configuration passes through and is loaded only once`, async ($, on) => {
    const paths: string[] = [];
    let calls = 0;
    mock.env(on, { CLAUDE_MY_PRIVACY_CONFIG: TEST_CONFIG_PATH, HOME: '/synthetic/home' });
    on('fs.read', ($, event) => {
      paths.push(event.path);
      if (config === undefined) throw new Error('Synthetic absent config');
      return { value: config };
    });
    on('ui.render', { component: 'AssistantMessage' }, ($, event) => {
      calls += 1;
      return drawing(event.props.text);
    });
    for (let index = 0; index < 2; index += 1) {
      expect(await $.ui.render(message('RyanChen Harborwave'))).toEqual(drawing('RyanChen Harborwave'));
    }
    const status = await $.command.run({ command: 'my-privacy-status' });
    expect(status.text).toContain(`Configuration: ${state}; mappings: 0.`);
    expect(paths).toEqual([TEST_CONFIG_PATH]);
    expect(calls).toBe(2);
  });
}

modTest('display and prompt filtering share one configuration snapshot per load', async ($, on) => {
  let reads = 0;
  mock.env(on, { CLAUDE_MY_PRIVACY_CONFIG: TEST_CONFIG_PATH, HOME: '/synthetic/home' });
  on('fs.read', { path: TEST_CONFIG_PATH }, () => {
    reads += 1;
    return { value: reads === 1 ? TEST_CONFIG_TEXT : '{"mappings":[]}' };
  });
  on('ui.render', { component: 'AssistantMessage' }, ($, event) => drawing(event.props.text));
  on('prompt.submit', ($, event) => ({ text: event.text }));
  expect(await $.ui.render(message('Harborwave'))).toEqual(drawing('Cedarbyte'));
  const submitted = await $.prompt.submit({ text: 'Cedarbyte', wait: false, origin: { kind: 'composer' } });
  expect(submitted.text).toBe('Harborwave');
  expect(await $.ui.render(message('Harborwave'))).toEqual(drawing('Cedarbyte'));
  expect(reads).toBe(1);
});
