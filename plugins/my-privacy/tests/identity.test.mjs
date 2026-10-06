import test from 'node:test';
import assert from 'node:assert/strict';
import { register } from '../hooks/register.js';
import { CONFIG_RELATIVE_PATH } from '../config.js';

test('session start registers exactly the three MyPrivacy commands without legacy aliases or status text', async () => {
  const hooks = [];
  register((event, ...args) => hooks.push({ event, args }));
  const commandHooks = hooks.filter(hook => hook.event === 'command.run');
  const expected = ['my-privacy-status', 'my-privacy-audit', 'my-privacy-recover'];
  assert.deepEqual(commandHooks.map(hook => hook.args[0].command), expected);

  const names = [];
  const statuses = [];
  const paths = [];
  const host = {
    env: { get: async name => name === 'HOME' ? '/synthetic/my-privacy-home' : undefined },
    fs: { read: async path => { paths.push(path); return '{"mappings":[]}'; } },
    command: { register: async command => names.push(command.name) },
    ui: { status: value => statuses.push(value) },
  };
  const event = { source: 'startup' };
  const start = hooks.find(hook => hook.event === 'session.start').args[0];
  assert.equal(await start(host, event, async value => value), event);
  assert.deepEqual(names, expected);
  assert.deepEqual(statuses, [undefined]);
  assert.equal(CONFIG_RELATIVE_PATH, '.config/claude-my-privacy/mappings.json');
  assert.deepEqual(paths, ['/synthetic/my-privacy-home/.config/claude-my-privacy/mappings.json']);
});
