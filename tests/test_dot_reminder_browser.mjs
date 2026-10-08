// Task 1 contract fixtures. These call the actual baseline sender, never a browser.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';
import * as transport from '../.claude/skills/dot/scripts/dot_chrome.mjs';

const source = fs.readFileSync(new URL('../.claude/skills/dot/scripts/dot_chrome.mjs', import.meta.url), 'utf8');
const body = '[automated reminder] [event:test] ' + 'x'.repeat(300);
const expected = { sender: 'configured-sender', room: 'configured-room', body, marker: '[event:test]' };

// Expose the existing lexical sender without modifying production code; retain its
// actual normalization and branching. The page fixture only models UI effects.
function baselineSender(log) {
  const script = source.slice(source.indexOf('async function send('), source.indexOf('\nif (isMainModule()) {'));
  const context = vm.createContext({
    fs: { readFileSync: () => body },
    process: { env: {} },
    console: { log: value => log.push(value) },
    COMPOSER: '[contenteditable=true]',
    isMac: false,
    norm: text => text.replace(/\s+/g, ' ').trim(),
    stripReadReceipt: text => text.replace(/Read\s+\d{1,2}:\d{2}\s*(?:[AP]M)?/gi, '').replace(/\s+/g, ' ').trim(),
    sleep: async () => {},
    aborted: false,
    clicked: false,
  });
  return vm.runInContext(script + '\nsend', context);
}

function fixture({ draft = '', sender = expected.sender, room = expected.room, echo = body } = {}) {
  const state = { draft, sender, room, clicks: 0, messages: [{ id: 'old-message', sender, room, body: 'earlier text' }], edits: 0 };
  const evidence = { sender, room, messages: new Map([['old-message', { sender, room }]]) };
  const composer = { first: () => composer, innerText: async () => state.draft, focus: async () => {}, evaluate: async (_, text) => {
    if (state.draft.trim()) return false;
    state.draft += text;
    state.edits += 1;
    return true;
  } };
  const page = {
    state, evidence,
    locator: selector => selector.startsWith('[contenteditable=true]') ? composer : {
      allInnerTexts: async () => state.messages.map(message => message.body),
      evaluateAll: async () => state.messages,
    },
    evaluate: async () => '', // No limit banner. Identity is present in state, not invented by sender.
    click: async selector => {
      if (selector.includes('send-button')) {
        state.clicks += 1;
        state.messages.push({ id: 'stable-message-1', sender, room, body: echo });
        evidence.messages.set('stable-message-1', { sender, room });
        state.draft = '';
      }
    },
    keyboard: {
      press: async key => { if (key === 'Backspace') { state.draft = ''; state.edits += 1; } },
      insertText: async text => { state.draft = text; state.edits += 1; },
    },
  };
  return page;
}

async function exercise(options) {
  const page = fixture(options);
  const log = [];
  // Future strict primitive must be explicitly selected, preserving default callers.
  if (typeof transport.sendReminderOnce === 'function') {
    const receipt = await transport.sendReminderOnce(page, { ...expected, deadline: Date.now()+30 }, page.evidence, async () => {});
    if (receipt.kind === 'delivered') log.push('DOT_SENT_VERIFIED');
  } else {
    await baselineSender(log)(page, 'fixture-message.txt', false);
  }
  return { ...page.state, log };
}

for (const key of ['sender', 'room']) {
  test(`strict ${key} mismatch never edits or sends`, async () => {
    const result = await exercise({ [key]: 'wrong-identity' });
    assert.equal(result.clicks, 0);
    assert.equal(result.edits, 0);
  });
}

test('peer draft resembling an old or intended message remains untouched', async () => {
  const result = await exercise({ draft: body });
  assert.equal(result.draft, body);
  assert.equal(result.edits, 0);
  assert.equal(result.clicks, 0);
});

test('a 96-percent echo is not delivery evidence', async () => {
  const result = await exercise({ echo: body.slice(0, Math.ceil(body.length * 0.96)) });
  assert.ok(!result.log.includes('DOT_SENT_VERIFIED'));
});

test('exact readback returns stable message ID and full body evidence', async () => {
  assert.equal(typeof transport.lookupReminder, 'function', 'canonical read-only exact lookup is required');
  const page = fixture();
  page.state.messages.push({ id: 'existing-message-1', ...expected });
  page.evidence.messages.set('existing-message-1', { sender: expected.sender, room: expected.room });
  const proof = await transport.lookupReminder(page, expected, page.evidence);
  assert.equal(proof.kind, 'positive_readback');
  assert.equal(proof.message_id, 'existing-message-1');
  assert.equal(proof.sender, expected.sender);
  assert.equal(proof.room, expected.room);
  assert.equal(proof.body, body);
});

test('missing or partial history remains unknown without edits', async () => {
  assert.equal(typeof transport.lookupReminder, 'function', 'canonical read-only exact lookup is required');
  for (const messages of [[], [{ id: 'partial', ...expected, body: body.slice(0, -4) }]]) {
    const page = fixture({ draft: 'peer-owned draft' });
    page.state.messages = messages;
    assert.equal(await transport.lookupReminder(page, expected, page.evidence), null);
    assert.equal(page.state.draft, 'peer-owned draft');
    assert.equal(page.state.edits, 0);
    assert.equal(page.state.clicks, 0);
  }
});

test('exact readback requires API-author identity for the same stable DOM message ID', async () => {
  for (const metadata of [{ sender: 'peer', room: expected.room }, { sender: expected.sender, room: 'other-room' }, null]) {
    const page = fixture();
    page.state.messages.push({ id: 'target', ...expected });
    if (metadata) page.evidence.messages.set('target', metadata);
    assert.equal(await transport.lookupReminder(page, expected, page.evidence), null);
  }
});

test('exact existing message never authorizes another send', async () => {
  const page = fixture();
  page.state.messages.push({ id: 'already-sent', ...expected });
  page.evidence.messages.set('already-sent', { sender: expected.sender, room: expected.room });
  const receipt = await transport.sendReminderOnce(page, expected, page.evidence);
  assert.equal(receipt.kind, 'no_send');
  assert.equal(page.state.clicks, 0);
  assert.equal(page.state.edits, 0);
});

test('full new echo returns one typed receipt and one click', async () => {
  const page = fixture();
  const receipt = await transport.sendReminderOnce(page, expected, page.evidence);
  assert.equal(receipt.kind, 'delivered');
  assert.equal(receipt.message_id, 'stable-message-1');
  assert.match(receipt.digest, /^[a-f0-9]{64}$/);
  assert.equal(page.state.clicks, 1);
});

test('cancelled before-click stage is explicit no-send', async () => {
  const page = fixture();
  const receipt = await transport.sendReminderOnce(page, { ...expected, cancelled: () => true }, page.evidence);
  assert.equal(receipt.kind, 'no_send');
  assert.equal(receipt.before_click, true);
  assert.equal(page.state.clicks, 0);
});

test('duplicate full matches are unknown rather than choosing a message ID', async () => {
  const page = fixture();
  for (const id of ['duplicate-1', 'duplicate-2']) {
    page.state.messages.push({ id, ...expected });
    page.evidence.messages.set(id, { sender: expected.sender, room: expected.room });
  }
  assert.equal(await transport.lookupReminder(page, expected, page.evidence), null);
});

test('passive parser binds exact proven room and message response envelopes', async () => {
  const { observeReminder } = await import('../.claude/skills/dot/scripts/dot_reminder.mjs');
  const page = fixture();
  let observe;
  page.on = (name, handler) => { assert.equal(name, 'response'); observe = handler; };
  const evidence = observeReminder(page, expected);
  const response = (path, data, status=200) => ({ url: () => 'https://chatgpt.com'+path, status: () => status, json: async () => data });
  await observe(response('/api/auth/session', { user: { id: expected.sender } }));
  await observe(response('/backend-api/messaging/rooms/'+expected.room, { id: expected.room, aeon_id: 'configured-aeon', creator_account_user_id: expected.sender, members: [] }));
  await observe(response('/backend-api/messaging/rooms/'+expected.room+'/messages', { items: [{ id: 'existing', role: 'user', account_user_id: expected.sender, deleted_at: null }], prev_cursor: null, next_cursor: null }));
  page.state.messages.push({ id: 'existing', body });
  assert.equal((await transport.lookupReminder(page, expected, evidence)).message_id, 'existing');
  await observe(response('/backend-api/messaging/rooms/'+expected.room+'/messages', { items: [{ id: 'existing', role: 'user', account_user_id: expected.sender, deleted_at: 'deleted' }] }));
  assert.equal(await transport.lookupReminder(page, expected, evidence), null);
});

test('conflicting author metadata latches unknown and 401 never becomes identity', async () => {
  const { observeReminder } = await import('../.claude/skills/dot/scripts/dot_reminder.mjs');
  const page = fixture();
  let observe;
  page.on = (_, handler) => { observe = handler; };
  const evidence = observeReminder(page, expected);
  const response = (path, data, status=200) => ({ url: () => 'https://chatgpt.com'+path, status: () => status, json: async () => data });
  await observe(response('/api/auth/session', { user: { id: expected.sender } }, 401));
  assert.equal(evidence.sender, null);
  await observe(response('/api/auth/session', { user: { id: expected.sender } }));
  await observe(response('/backend-api/messaging/rooms/'+expected.room, { id: expected.room }));
  for (const author of [expected.sender, 'peer', expected.sender]) {
    await observe(response('/backend-api/messaging/rooms/'+expected.room+'/messages', { items: [{ id: 'existing', role: 'user', account_user_id: author, deleted_at: null }] }));
  }
  page.state.messages.push({ id: 'existing', body });
  assert.equal(await transport.lookupReminder(page, expected, evidence), null);
  assert.equal(evidence.conflict, true);
});

test('duplicate existing exact messages suppress dispatch, not merely proof', async () => {
  const page = fixture();
  for (const id of ['duplicate-1', 'duplicate-2']) {
    page.state.messages.push({ id, ...expected });
    page.evidence.messages.set(id, { sender: expected.sender, room: expected.room });
  }
  const receipt = await transport.sendReminderOnce(page, expected, page.evidence);
  assert.equal(receipt.kind, 'no_send');
  assert.equal(page.state.clicks, 0);
  assert.equal(page.state.edits, 0);
});

test('identity invalidated during awaited DOM read cannot prove delivery', async () => {
  const page = fixture();
  page.state.messages.push({ id: 'target', ...expected });
  page.evidence.messages.set('target', { sender: expected.sender, room: expected.room });
  const original = page.locator;
  page.locator = selector => selector.startsWith('article') ? { evaluateAll: async () => {
    page.evidence.sender = 'other';
    return page.state.messages;
  } } : original(selector);
  assert.equal(await transport.lookupReminder(page, expected, page.evidence), null);
});

test('peer draft appearing at insertion is untouched', async () => {
  const page = fixture();
  const original = page.locator;
  page.locator = selector => {
    const value = original(selector);
    if (selector.startsWith('[contenteditable')) value.evaluate = async () => {
      page.state.draft = 'new peer draft';
      return false;
    };
    return value;
  };
  const receipt = await transport.sendReminderOnce(page, expected, page.evidence);
  assert.equal(receipt.kind, 'no_send');
  assert.equal(page.state.draft, 'new peer draft');
  assert.equal(page.state.edits, 0);
  assert.equal(page.state.clicks, 0);
});


test('identity invalidation during final composer read forbids click', async () => {
  const page = fixture();
  const composer = page.locator('[contenteditable=true]');
  let reads = 0;
  composer.innerText = async () => {
    if (++reads === 3) page.evidence.conflict = true;
    return page.state.draft;
  };
  const receipt = await transport.sendReminderOnce(page, { ...expected, deadline: Date.now()+30 }, page.evidence, async () => {});
  assert.equal(receipt.kind, 'no_send');
  assert.equal(page.state.clicks, 0);
});

// Execute the real browser-side insertion callback in a tiny document fixture,
// rather than replace its implementation with a successful fake.
for (const scenario of ['normal', 'peer-on-focus', 'redirected-focus', 'detached']) {
  test(`atomic insertion callback handles ${scenario}`, async () => {
    const page = fixture();
    const composer = page.locator('[contenteditable=true]');
    composer.evaluate = async (callback, text) => {
      const document = { activeElement: {}, execCommand: (command, ui, value) => {
        assert.equal(command, 'insertText');
        assert.equal(ui, false);
        if (document.activeElement === element) page.state.draft += value;
        else page.state.otherDraft = (page.state.otherDraft || '') + value;
        page.state.edits++;
        return true;
      } };
      const element = {
        isConnected: scenario !== 'detached',
        get innerText() { return page.state.draft; },
        focus() {
          if (!this.isConnected) return;
          document.activeElement = scenario === 'redirected-focus' ? {} : element;
          if (scenario === 'peer-on-focus') page.state.draft = 'peer arrived';
        },
      };
      return vm.runInNewContext('(' + callback.toString() + ')(element, text)', { element, text, document });
    };
    const receipt = await transport.sendReminderOnce(page, expected, page.evidence);
    assert.equal(page.state.edits, scenario === 'normal' ? 1 : 0);
    assert.equal(receipt.kind, scenario === 'normal' ? 'delivered' : 'no_send');
    assert.equal(page.state.clicks, scenario === 'normal' ? 1 : 0);
    if (scenario === 'peer-on-focus') assert.equal(page.state.draft, 'peer arrived');
  });
}

test('click receives remaining deadline and late echo is not delivered', async () => {
  const page = fixture();
  const deadline = Date.now() + 60;
  const click = page.click;
  page.click = async (selector, options) => {
    assert.equal(options.noWaitAfter, true);
    assert.ok(options.timeout > 0 && options.timeout <= 60);
    await new Promise(resolve => setTimeout(resolve, Math.max(0, deadline - Date.now() + 5)));
    await click(selector);
  };
  const receipt = await transport.sendReminderOnce(page, { ...expected, deadline }, page.evidence, async () => {});
  assert.equal(receipt.kind, 'uncertain');
  assert.equal(page.state.clicks, 1);
});

for (const failure of ['401', 'session-conflict', 'room-conflict', 'malformed']) {
  test(`passive ${failure} after valid identity stays untrusted`, async () => {
    const { observeReminder } = await import('../.claude/skills/dot/scripts/dot_reminder.mjs');
    let observe;
    const evidence = observeReminder({ on: (_, handler) => { observe = handler; } }, expected);
    const roomPath = '/backend-api/messaging/rooms/' + expected.room;
    const emit = (pathname, data, status = 200) => observe({
      url: () => 'https://chatgpt.com' + pathname, status: () => status,
      json: async () => { if (data === 'malformed') throw new Error('invalid JSON'); return data; },
    });
    const valid = async () => {
      await emit('/api/auth/session', { user: { id: expected.sender } });
      await emit(roomPath, { id: expected.room });
      await emit(roomPath + '/messages', { items: [{ id: 'existing', role: 'user', account_user_id: expected.sender, deleted_at: null }] });
    };
    await valid();
    if (failure === '401') await emit('/api/auth/session', {}, 401);
    if (failure === 'session-conflict') await emit('/api/auth/session', { user: { id: 'peer' } });
    if (failure === 'room-conflict') await emit(roomPath, { id: 'different-room' });
    if (failure === 'malformed') await emit(roomPath, 'malformed');
    await valid();
    const page = fixture();
    page.state.messages.push({ id: 'existing', body });
    assert.equal(evidence.conflict, true);
    assert.equal(await transport.lookupReminder(page, expected, evidence), null);
  });
}

test('strict shell dispatch is one local invocation with dangerous overrides scrubbed', () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'dot-strict-routing-'));
  try {
    const reporter = path.join(temporary, 'reporter.mjs');
    const node = path.join(temporary, 'node');
    const keys = ['DOT_ACCOUNT', 'DOT_CONFIG_FILE', 'DOT_ALLOW_REMOTE', 'DOT_ROTATE_ON_LIMIT',
      'DOT_REMOTE_HOST', 'DOT_CHROME_USER_DATA', 'DOT_URL', 'DOT_CLEAR_DRAFT', 'DOT_DRY_RUN'];
    fs.writeFileSync(reporter, 'console.log(JSON.stringify({args:process.argv.slice(2),env:Object.fromEntries(' + JSON.stringify(keys) + '.map(k=>[k,process.env[k]??null]))}));');
    fs.writeFileSync(node, '#!/bin/sh\nexec "' + process.execPath + '" "' + reporter + '" "$@"\n', { mode: 0o700 });
    const shell = fileURLToPath(new URL('../.claude/skills/dot/scripts/dot.sh', import.meta.url));
    const config = path.join(temporary, 'no-config.json');
    const env = { ...process.env, DOT_NODE: node, DOT_ACCOUNT: 'fixture-account', DOT_CONFIG_FILE: config,
      DOT_REMOTE_HOST: 'must-not-contact', DOT_CHROME_USER_DATA: '/must-not-use', DOT_URL: 'https://wrong.invalid',
      DOT_CLEAR_DRAFT: '1', DOT_DRY_RUN: '1', DOT_ALLOW_REMOTE: '1', DOT_ROTATE_ON_LIMIT: '1' };
    for (const action of ['send-once', 'lookup']) {
      const result = spawnSync('bash', [shell, '--strict-reminder', action, '/fixture input.json'], { env, encoding: 'utf8' });
      assert.equal(result.status, 0, result.stderr);
      const lines = result.stdout.trim().split('\n');
      assert.equal(lines.length, 1);
      const report = JSON.parse(lines[0]);
      assert.deepEqual(report.args, [shell.replace(/dot\.sh$/, 'dot_chrome.mjs'), 'reminder-' + action, '/fixture input.json']);
      assert.equal(report.env.DOT_ACCOUNT, 'fixture-account');
      assert.equal(report.env.DOT_CONFIG_FILE, config);
      assert.equal(report.env.DOT_ALLOW_REMOTE, '0');
      assert.equal(report.env.DOT_ROTATE_ON_LIMIT, '0');
      for (const key of keys.slice(4)) assert.equal(report.env[key], null, key);
    }
    for (const args of [['send', '/fixture'], ['lookup'], ['send-once', '/fixture', 'extra']]) {
      const result = spawnSync('bash', [shell, '--strict-reminder', ...args], { env, encoding: 'utf8' });
      assert.equal(result.status, 2);
      assert.equal(result.stdout, '');
    }
    const noAccount = { ...env }; delete noAccount.DOT_ACCOUNT;
    const result = spawnSync('bash', [shell, '--strict-reminder', 'lookup', '/fixture'], { env: noAccount, encoding: 'utf8' });
    assert.equal(result.status, 2);
    assert.equal(result.stdout, '');
  } finally { fs.rmSync(temporary, { recursive: true, force: true }); }
});

test('default sender retains its existing independent send behavior', async () => {
  const page = fixture();
  const log = [];
  await baselineSender(log)(page, 'fixture-message.txt', false);
  assert.equal(page.state.clicks, 1);
  assert.ok(log.includes('DOT_SENT_VERIFIED'));
});


test('strict CLI configuration and binding errors produce one typed pre-click receipt', () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'dot-strict-cli-'));
  try {
    const script = fileURLToPath(new URL('../.claude/skills/dot/scripts/dot_chrome.mjs', import.meta.url));
    const config = path.join(temporary, 'config.json');
    const input = path.join(temporary, 'input.txt');
    const env = { ...process.env, DOT_ACCOUNT: 'fixture-account', DOT_CONFIG_FILE: config };
    const invoke = action => {
      const result = spawnSync(process.execPath, [script, 'reminder-' + action, input], { env, encoding: 'utf8' });
      assert.equal(result.status, 0, result.stderr);
      const lines = result.stdout.trim().split('\n');
      assert.equal(lines.length, 1);
      assert.ok(lines[0].startsWith('DOT_REMINDER '));
      const receipt = JSON.parse(lines[0].slice('DOT_REMINDER '.length));
      assert.equal(receipt.kind, 'no_send');
      assert.equal(receipt.before_click, true);
      return receipt;
    };
    fs.writeFileSync(config, '{}');
    assert.match(invoke('send-once').reason, /configuration/);
    fs.writeFileSync(config, JSON.stringify({ accounts: { 'fixture-account': {
      expected_sender_id: expected.sender, expected_room_id: expected.room, user_data_dir: path.join(temporary, 'must-not-launch'),
    } } }));
    fs.writeFileSync(input, 'no valid marker');
    assert.match(invoke('send-once').reason, /binding/);
    fs.writeFileSync(input, JSON.stringify({ sender: 'wrong-sender', room: expected.room, marker: '[event:' + 'a'.repeat(64) + ']', digest: 'b'.repeat(64) }));
    assert.match(invoke('lookup').reason, /binding/);
  } finally { fs.rmSync(temporary, { recursive: true, force: true }); }
});
