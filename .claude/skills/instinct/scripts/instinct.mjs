#!/usr/bin/env node
/**
 * instinct.mjs — WhatsApp Web transport for /instinct.
 *
 * Mechanical I/O only: open web.whatsapp.com in an agent-owned persistent Chrome
 * profile, find a named contact, read recent messages, or type + submit a message.
 * Every judgment call lives in ../SKILL.md.
 *
 * Verbs:
 *   probe                 verify the profile is signed in to WhatsApp Web
 *   read [--limit N]      print the last N messages of the open chat
 *   open --contact NAME   open the chat for NAME (no send)
 *   send --contact NAME --file PATH
 *   whoami                print resolved profile + browser + contact
 *
 * Read-only by construction: `probe`, `read`, `open` and `whoami` never click Send.
 */

import fs from 'node:fs';
import { execFileSync } from 'node:child_process';
import os from 'node:os';
import path from 'node:path';

const VERB = process.argv[2] || 'whoami';
let SELF_NAME = process.env.INSTINCT_SELF || '';

function arg(name, dflt) {
  const i = process.argv.indexOf(`--${name}`);
  return i > -1 && process.argv[i + 1] ? process.argv[i + 1] : dflt;
}

const PROFILE_DIR = (
  process.env.INSTINCT_PROFILE_DIR ||
  path.join(os.homedir(), '.config', 'instinct-chrome-profile')
).replace(/^~/, os.homedir());

const CONTACT = process.env.INSTINCT_CONTACT || 'Instinct WhatsApp';
const CHROME =
  process.env.INSTINCT_CHROME_BIN ||
  (process.platform === 'darwin'
    ? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
    : '/usr/bin/google-chrome');

function die(msg, code = 2) {
  process.stderr.write(`instinct: ${msg}\n`);
  process.exit(code);
}

/** Fail closed: the profile must be a real directory we own, never a symlink or the system Chrome dir. */
function validateProfileDir(dir) {
  const resolved = path.resolve(dir);
  const home = os.homedir();
  if (!resolved.startsWith(home + path.sep)) {
    die(`profile dir ${resolved} is outside $HOME; refusing`);
  }
  const systemChrome = path.join(home, 'Library', 'Application Support', 'Google', 'Chrome');
  if (resolved === systemChrome || resolved.startsWith(systemChrome + path.sep)) {
    die('profile dir is the personal Chrome profile; refusing (browser-control isolation)');
  }
  if (fs.existsSync(resolved) && fs.lstatSync(resolved).isSymbolicLink()) {
    die(`profile dir ${resolved} is a symlink; refusing`);
  }
  if (!fs.existsSync(resolved)) fs.mkdirSync(resolved, { recursive: true, mode: 0o700 });
  return resolved;
}

const isMac = process.platform === 'darwin';
const isLinux = process.platform === 'linux';

/**
 * Chrome launch flags. The password-store pin is NOT optional:
 * Playwright's default args include --use-mock-keychain / --password-store=basic,
 * which opens the encrypted cookie store with an incompatible backend and damages
 * it (documented in ~/.claude/skills/dot/SKILL.md:253,256 — a realized incident on
 * 2026-10-11 wiped a profile this way). Mirror dot_chrome.mjs:187-205 exactly.
 */
function chromeLaunchOptions(headed) {
  const args = [
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-blink-features=AutomationControlled',
  ];
  const ignoreDefaultArgs = [];
  if (isLinux) {
    args.push('--no-sandbox', '--disable-setuid-sandbox');
    // Always pin a real credential backend, even headless. Skipping the pin left
    // Playwright's default --use-mock-keychain/--password-store=basic active, which
    // reopens the exact cookie-damage vector this pin exists to close.
    args.push('--password-store=gnome-libsecret');
    ignoreDefaultArgs.push('--password-store=basic', '--use-mock-keychain');
  } else if (isMac) {
    args.push('--password-store=keychain', '--disable-features=MacAppCodeSignClone');
    ignoreDefaultArgs.push('--use-mock-keychain', '--password-store=basic');
  }
  return {
    executablePath: CHROME,
    headless: isLinux ? !headed && !process.env.DISPLAY : !headed,
    viewport: { width: 1280, height: 900 },
    args,
    ignoreDefaultArgs,
  };
}

/**
 * Refuse to launch over a live holder. Dot's verdict: sharing a profile is sound only
 * with "serialized ownership plus clean shutdown", so this yields rather than colliding.
 *
 * Two traps, both real:
 *  - Chrome's SingletonLock is a DANGLING symlink to "<hostname>-<pid>"; existsSync()
 *    follows the link and always reports false. lstat the link itself.
 *  - process.kill(pid,0) throws EPERM for a root-owned LIVE process. EPERM means alive;
 *    only ESRCH means gone. Treating EPERM as dead would delete a live lock.
 */
function pidAlive(pid) {
  if (!Number.isFinite(pid) || pid <= 0) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (e) {
    return e.code === 'EPERM';
  }
}

function liveHolderPid(dir) {
  const lock = path.join(dir, 'SingletonLock');
  let target = null;
  try {
    if (fs.lstatSync(lock).isSymbolicLink()) target = fs.readlinkSync(lock).toString();
  } catch {
    target = null;
  }
  if (target !== null) {
    const pid = Number(String(target).split('-').pop());
    if (pidAlive(pid)) return pid;
  }
  // Independent check: a Chrome actually holding the dir, even with an odd lock.
  try {
    const out = execFileSync('pgrep', ['-f', `user-data-dir=${dir}`], { encoding: 'utf8' }).trim();
    if (out) return Number(out.split('\n')[0]);
  } catch {
    // pgrep exits 1 when nothing matches — the healthy case.
  }
  return null;
}

/**
 * Yield to a busy profile instead of colliding with it.
 *
 * Dot's verdict was "serialized ownership plus clean shutdown". This lock serializes
 * instinct's OWN runs and makes instinct WAIT on a profile Chrome already holds; it is
 * one-sided because dot.sh takes no lock, so it does not by itself exclude Dot. Chromium's
 * ProcessSingleton REJECTS a simultaneous second launch (it does not queue it), and there is a
 * check-to-launch window here, so operator serialization remains necessary.
 * The lockfile lives outside the profile dir so it never collides with Chrome's
 * Singleton namespace, and it is released on exit AND on signals so a crash cannot
 * wedge the next run.
 */
async function acquireLock(dir) {
  const lockFile = path.join(os.homedir(), '.config', 'instinct-profile.lock');
  const lockWait = Number(process.env.INSTINCT_LOCK_WAIT_MS || 300_000);
  const profileWait = Number(process.env.INSTINCT_PROFILE_WAIT_MS || 300_000);
  const deadline = Date.now() + Math.max(lockWait, profileWait);

  // Phase 1: take the advisory lockfile (steal only from a provably dead runner).
  for (;;) {
    try {
      const fd = fs.openSync(lockFile, 'wx', 0o600);
      fs.writeSync(fd, String(process.pid));
      fs.closeSync(fd);
      break;
    } catch (e) {
      if (e.code !== 'EEXIST') die(`cannot create ${lockFile}: ${e.code}`, 7);
      let holder = null;
      try {
        holder = Number(fs.readFileSync(lockFile, 'utf8').trim());
      } catch {}
      if (holder && !pidAlive(holder)) {
        try {
          fs.unlinkSync(lockFile);
        } catch {}
        continue;
      }
      if (Date.now() > deadline) {
        die(
          `another instinct run (pid ${holder || '?'}) holds ${lockFile} past the ` +
            `${lockWait}ms wait. Not stealing it.`,
          7
        );
      }
      await new Promise((r) => setTimeout(r, 200));
    }
  }

  const release = () => {
    try {
      const held = Number(fs.readFileSync(lockFile, 'utf8').trim());
      if (held === process.pid) fs.unlinkSync(lockFile);
    } catch {}
  };
  // A crash or Ctrl-C must not wedge the next run.
  process.once('exit', release);
  for (const sig of ['SIGINT', 'SIGTERM', 'SIGHUP']) {
    process.once(sig, () => {
      release();
      process.exit(130);
    });
  }

  // Phase 2: wait for any live Chrome (dot.sh, a straggler helper) to finish.
  let announced = false;
  for (;;) {
    const pid = liveHolderPid(dir);
    if (!pid) return release;
    if (Date.now() > deadline) {
      die(
        `profile ${dir} still owned by Chrome pid ${pid} after the wait window. ` +
          'Close it first — never delete SingletonLock.',
        7
      );
    }
    if (!announced) {
      process.stderr.write(`instinct: profile busy (pid ${pid}); waiting for it to finish...\n`);
      announced = true;
    }
    await new Promise((r) => setTimeout(r, 500));
  }
}

/**
 * Resolve playwright the way dot.sh does: NODE_PATH, then the nvm/npm global
 * node_modules next to the running node binary. A bare `import('playwright')`
 * fails on a host where playwright is a GLOBAL package (Linux/jeff-ubuntu).
 */
async function loadChromium() {
  const candidates = [];
  if (process.env.NODE_PATH) candidates.push(...process.env.NODE_PATH.split(':').filter(Boolean));
  candidates.push(path.join(path.dirname(process.execPath), '..', 'lib', 'node_modules'));
  candidates.push(path.join(os.homedir(), '.npm-global', 'lib', 'node_modules'));
  candidates.push(path.join(os.homedir(), 'node_modules'));

  try {
    const pw = await import('playwright');
    return pw.chromium;
  } catch {}

  for (const base of candidates) {
    for (const entry of ['playwright/index.mjs', 'playwright/index.js', 'playwright-core/index.mjs']) {
      const p = path.join(base, entry);
      if (!fs.existsSync(p)) continue;
      try {
        const m = await import(`file://${p}`);
        const c = m.chromium || (m.default && m.default.chromium);
        if (c) return c;
      } catch {}
    }
  }
  die(
    'playwright is not resolvable. Install it globally or set NODE_PATH to the directory ' +
      `containing it (searched: ${candidates.join(', ')}).`,
    3
  );
}

async function withPage(fn, { headed = false } = {}) {
  const chromium = await loadChromium();
  if (!fs.existsSync(CHROME)) die(`Chrome binary not found at ${CHROME}`, 3);

  const dir = validateProfileDir(PROFILE_DIR);
  const release = await acquireLock(dir);
  const ctx = await chromium.launchPersistentContext(dir, chromeLaunchOptions(headed));
  try {
    const page = ctx.pages()[0] || (await ctx.newPage());
    return await fn(page, ctx);
  } finally {
    // Clean shutdown: close the context, then wait for the OS to actually release
    // ProcessSingleton before the next consumer (dot.sh) launches. Dot's own teardown
    // does the same (dot_chrome.mjs:812, await ctx?.close() then sleep(300)).
    await ctx.close().catch(() => {});
    const gone = Date.now() + 10_000;
    while (Date.now() < gone && liveHolderPid(dir)) {
      await new Promise((r) => setTimeout(r, 100));
    }
    await new Promise((r) => setTimeout(r, 300));
    release();
  }
}

const WA = 'https://web.whatsapp.com/';

/** WhatsApp Web renders a QR canvas when signed out and the chat list when signed in. */
async function signedIn(page) {
  // Signed in => the chat list exists. Signed out => the QR canvas is shown.
  const list = await page.locator('#pane-side').count();
  const qr = await page
    .locator('canvas')
    .count()
    .catch(() => 0);
  return list > 0 && qr === 0;
}

/** This WhatsApp build uses a real <input> for search, not a contenteditable div. */
const SEARCH = 'input[aria-label="Search or start a new chat"], input[placeholder="Search or start a new chat"]';
const COMPOSER =
  '[data-testid="conversation-compose-box-input"], footer div[contenteditable="true"]';
const SEND_BTN = 'footer button[aria-label="Send"], button[aria-label="Send"]';

async function openContact(page, name) {
  await page.goto(WA, { waitUntil: 'domcontentloaded' });
  // The chat list can take a while to hydrate on a cold profile.
  await page.locator('#pane-side').waitFor({ timeout: 90_000 }).catch(() => {});
  if (!(await signedIn(page))) {
    die(
      'not signed in to WhatsApp Web. Link the device once, interactively:\n' +
        `  node ${process.argv[1]} login\n` +
        'then scan the QR from WhatsApp on the phone.',
      4
    );
  }
  const search = page.locator(SEARCH).first();
  await search.waitFor({ timeout: 30_000 });
  await search.click();
  await search.fill('');
  await search.type(name, { delay: 40 });
  await page.waitForTimeout(2500);

  // Titles must be judged on the TITLE node only. A whole-row hasText fallback is unsafe:
  // a row's text includes its message preview, so searching "Bob" could select Ann's chat
  // merely because Ann's last message mentioned Bob — and .first() would silently send there.
  const titleNodes = page.locator('#pane-side span[title]');
  const titles = await titleNodes
    .evaluateAll((els) => els.map((e) => e.getAttribute('title')).filter(Boolean))
    .catch(() => []);

  const exactTitles = titles.filter((t) => t === name);
  if (exactTitles.length === 0) {
    die(
      `contact "${name}" not found by exact title (no message-preview matching, to avoid ` +
        `mis-sending). Visible chats: ${JSON.stringify(titles.slice(0, 20))}`,
      5
    );
  }
  if (exactTitles.length > 1) {
    // Ambiguous: never guess with .first().
    die(
      `${exactTitles.length} chats are titled exactly "${name}"; refusing to guess. ` +
        `Rename one, or pass a unique name. Visible chats: ${JSON.stringify(titles.slice(0, 20))}`,
      5
    );
  }

  // Selection: one page.evaluate pass finds the title nodes, requires exactly one whose
  // title === name, and marks THAT node by reference. Playwright then clicks the marked
  // element. This removes the earlier index/filter mismatch (a filtered list's index applied
  // to a differently-filtered locator). It does NOT make selection and click atomic: the
  // marker is a DOM attribute read a tick later, so the node could in principle be replaced
  // or duplicated in between. Duplicates are therefore rejected before clicking, and the
  // header guard below is the authoritative check before any typing.
  const clicked = await page.evaluate((wanted) => {
    const nodes = [...document.querySelectorAll('#pane-side span[title]')];
    const hits = nodes.filter((n) => n.getAttribute('title') === wanted);
    if (hits.length !== 1) {
      return { ok: false, reason: hits.length === 0 ? 'no exact title match' : `${hits.length} exact title matches`, count: hits.length };
    }
    // Mark the exact node so Playwright clicks THIS element (a synthetic .click() does not
    // reliably open the chat in this build). The marker is removed right after.
    hits[0].setAttribute('data-instinct-target', '1');
    return { ok: true, title: hits[0].getAttribute('title') };
  }, name);

  if (!clicked.ok) {
    die(
      `could not select "${name}": ${clicked.reason}; refusing to guess`,
      5
    );
  }
  const marked = page.locator('[data-instinct-target="1"]');
  let markerCount = 0;
  try {
    markerCount = await marked.count();
  } catch {}
  if (markerCount !== 1) {
    await page
      .evaluate(() =>
        document
          .querySelectorAll('[data-instinct-target]')
          .forEach((el) => el.removeAttribute('data-instinct-target'))
      )
      .catch(() => {});
    die(
      `expected exactly 1 marked chat node, found ${markerCount}; refusing to click`,
      5
    );
  }
  try {
    await marked.click({ timeout: 20_000 });
  } finally {
    // Always clear every marker, including on a click failure.
    await page
      .evaluate(() =>
        document
          .querySelectorAll('[data-instinct-target]')
          .forEach((el) => el.removeAttribute('data-instinct-target'))
      )
      .catch(() => {});
  }
  // Wait for the header to show THIS contact, not merely "a header is visible" — a visible
  // previous header would satisfy a presence check without navigation having happened.
  await page
    .locator('[data-testid="conversation-info-header"]')
    .filter({ hasText: name })
    .first()
    .waitFor({ state: 'visible', timeout: 30_000 })
    .catch(() => {});

  // Verify the OPEN chat is the requested contact before anyone types into it.
  // NOTE: `header span[title]` is NOT the chat title here — it matches the "Business Account"
  // badge inside the header (verified live 2026-11-09). The conversation title lives in
  // [data-testid="conversation-info-header"].
  // Strictly test-id based. No generic-header fallback: a loose fallback could read a badge
  // or another pane's header and pass the guard for the wrong chat.
  const infoHeader = page.locator('[data-testid="conversation-info-header"]').first();
  let openTitle = '';
  try {
    openTitle = (await infoHeader.innerText({ timeout: 10_000 })).split('\n')[0].trim();
  } catch {
    die(
      'could not read [data-testid="conversation-info-header"]; refusing to send without ' +
        'confirming the open chat',
      5
    );
  }
  if (openTitle !== name) {
    die(
      `opened chat header is ${JSON.stringify(openTitle)}, expected ${JSON.stringify(name)}; ` +
        'refusing to send into the wrong chat',
      5
    );
  }
  return true;
}

async function readMessages(page, limit) {
  // This WhatsApp build dropped .message-in/.message-out. Bubbles carry
  // [data-pre-plain-text] = "[<time>, <date>] <Sender>: ", which gives direction
  // and timestamp without depending on obfuscated class names.
  return page.evaluate((lim) => {
    const nodes = [...document.querySelectorAll('[data-pre-plain-text]')];
    const out = [];
    for (const n of nodes) {
      const meta = n.getAttribute('data-pre-plain-text') || '';
      const m = meta.match(/^\[(.+?)\]\s*([^:]*):/);
      const when = m ? m[1] : '';
      const sender = m ? m[2].trim() : '';
      const text = (n.innerText || '').replace(/\s+/g, ' ').trim();
      if (!text) continue;
      out.push({ when, sender, text });
    }
    return out.slice(-lim);
  }, limit);
}

function formatMsg(m, selfName) {
  const mine = selfName && m.sender && m.sender.toLowerCase() === selfName.toLowerCase();
  return `${mine ? 'me  ' : 'them'}  [${m.when}] ${m.text}`;
}

async function compose(page, text) {
  const box = page.locator(COMPOSER).last();
  await box.waitFor({ timeout: 30_000 });
  await box.click();
  // Clear any draft first: a leftover draft would be prepended to our text and sent
  // (observed during transport bring-up). Select-all + delete, then confirm empty.
  for (const combo of [['Control', 'a'], ['Meta', 'a']]) {
    await page.keyboard.down(combo[0]);
    await page.keyboard.press('a');
    await page.keyboard.up(combo[0]);
  }
  await page.keyboard.press('Backspace');
  await page.waitForTimeout(300);
  const leftover = (await box.innerText().catch(() => '')).replace(/\s+/g, ' ').trim();
  if (leftover.length > 0) {
    die(
      `composer had an un-clearable draft (${JSON.stringify(leftover.slice(0, 60))}); ` +
        'refusing to send, because it would be prepended to the message',
      6
    );
  }
  // Keystrokes, not fill(): WhatsApp's composer needs real input events.
  // NEVER page.keyboard.type() a multi-line body: every embedded newline fires Enter and
  // submits a fragment (observed live 2026-11-09 — a 24-line review request was split into
  // 5 separate WhatsApp messages). Insert the whole body as one paste instead, so newlines
  // stay inside the draft. Newlines are still preserved as typed text.
  await page.evaluate((body) => {
    const el = document.querySelector(
      '[data-testid="conversation-compose-box-input"]'
    ) || document.querySelector('footer div[contenteditable="true"]');
    if (!el) throw new Error('composer not found for paste');
    el.focus();
    const dt = new DataTransfer();
    dt.setData('text/plain', body);
    el.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true }));
  }, text);
  await page.waitForTimeout(900);
  const typed = (await box.innerText().catch(() => '')).replace(/\s+/g, ' ').trim();
  // Compare the WHOLE normalised body, not a 40-char prefix: a truncated paste would pass a
  // prefix check and be reported as sent (raised by Dot review as a non-P0).
  const norm = (v) => v.replace(/\s+/g, ' ').trim();
  const wantAll = norm(text);
  // Compare normalised content, but tolerate reflow: equal length with a differing string
  // means whitespace was redistributed, not that content was lost.
  const sameContent = typed === wantAll || (typed.length === wantAll.length && norm(typed).length === wantAll.length);
  if (!sameContent) {
    die(
      `composer content does not match the full message (want ${wantAll.length} chars, ` +
        `got ${typed.length}); nothing was sent`,
      6
    );
  }
  return box;
}

(async () => {
  const headed = process.env.INSTINCT_HEADED === '1';

  if (VERB === 'login') {
    // Interactive one-time device link. Deliberately HEADED and long-lived: the operator
    // must scan the QR from their phone. The advisory lock is held for the whole session so
    // a competing instinct run waits; it does not block dot.sh, which takes no lock.
    if (!fs.existsSync(CHROME)) die(`Chrome binary not found at ${CHROME}`, 3);
    const chromium = await loadChromium();
    const dir = validateProfileDir(PROFILE_DIR);
    const release = await acquireLock(dir);
    process.stderr.write(
      `instinct: opening a visible Chrome on ${dir}\n` +
        'Scan the QR: WhatsApp on your phone -> Settings -> Linked devices -> Link a device\n' +
        `This window stays open until ${CONTACT} appears or the ${Math.round(
          Number(process.env.INSTINCT_LOGIN_WAIT_MS || 600_000) / 1000
        )}s timer expires. Do not close it early.\n`
    );
    const ctx = await chromium.launchPersistentContext(dir, chromeLaunchOptions(true));
    try {
      const page = ctx.pages()[0] || (await ctx.newPage());
      await page.goto(WA, { waitUntil: 'domcontentloaded' });
      const deadline = Date.now() + Number(process.env.INSTINCT_LOGIN_WAIT_MS || 600_000);
      let ok = false;
      while (Date.now() < deadline) {
        if (await signedIn(page)) {
          ok = true;
          break;
        }
        await page.waitForTimeout(2000);
      }
      if (!ok) {
        die('login window expired without a link; nothing was changed', 4);
      }
      // Let the chat list hydrate and persist the device link to disk before closing.
      await page.waitForTimeout(6000);
      const msgs = await readMessages(page, 5).catch(() => []);
      process.stdout.write(`LINKED: ${PROFILE_DIR}\n`);
      if (msgs.length) msgs.forEach((m) => process.stdout.write(`  ${formatMsg(m, SELF_NAME)}\n`));
    } finally {
      await ctx.close().catch(() => {});
      const gone = Date.now() + 10_000;
      while (Date.now() < gone && liveHolderPid(dir)) {
        await new Promise((r) => setTimeout(r, 100));
      }
      await new Promise((r) => setTimeout(r, 300));
      release();
    }
    return;
  }

  if (VERB === 'whoami') {
    process.stdout.write(
      JSON.stringify(
        {
          profile_dir: PROFILE_DIR,
          chrome: CHROME,
          contact: CONTACT,
          contact_source: process.env.INSTINCT_CONTACT ? 'env' : 'default',
          browser: 'Google Chrome (playwright persistent context)',
          rejects: ['personal ~/Library/.../Google/Chrome', 'symlinked profile dir'],
        },
        null,
        2
      ) + '\n'
    );
    return;
  }

  if (VERB === 'probe') {
    await withPage(async (page) => {
      await page.goto(WA, { waitUntil: 'domcontentloaded' });
      // WhatsApp pads startup with a splash; a cold but LINKED profile can need ~40s before the
      // chat list hydrates. A fixed 4s wait therefore reported signed_in:false for a perfectly
      // good session (observed 2026-11-10: pane-side=0 at 4s, pane-side=1 with title
      // "(2) WhatsApp" at 45s). Poll for the decisive element instead of guessing a duration,
      // and keep "still loading" DISTINCT from "signed out" so a slow start cannot be
      // mistaken for a dead device link.
      const timeout = Number(process.env.INSTINCT_PROBE_TIMEOUT_MS || 90_000);
      const started = Date.now();
      const deadline = started + timeout;
      let state = 'loading';
      while (Date.now() < deadline) {
        const seen = await page
          .evaluate(() => ({
            list: document.querySelectorAll('#pane-side').length,
            qr: document.querySelectorAll('canvas').length,
          }))
          .catch(() => ({ list: 0, qr: 0 }));
        if (seen.list > 0) {
          state = 'linked';
          break;
        }
        if (seen.qr > 0) {
          state = 'signed_out';
          break;
        }
        await page.waitForTimeout(1000);
      }
      const ok = state === 'linked' && (await signedIn(page));
      process.stdout.write(
        JSON.stringify({
          signed_in: ok,
          state,
          waited_ms: Date.now() - started,
          profile_dir: PROFILE_DIR,
        }) + '\n'
      );
      if (ok) return;
      if (state === 'loading') {
        die(
          `WhatsApp Web rendered neither a chat list nor a QR within ${timeout}ms; the link ` +
            'state is UNVERIFIED, which is not proof the device link is dead. Raise ' +
            'INSTINCT_PROBE_TIMEOUT_MS or rerun before treating it as signed out.',
          8
        );
      }
      // Genuine signed-out: the QR canvas is on screen.
      process.exit(4);
    }, { headed });
    return;
  }

  if (VERB === 'open') {
    const name = arg('contact', CONTACT);
    await withPage(async (page) => {
      await openContact(page, name);
      const msgs = await readMessages(page, Number(arg('limit', 10)));
      process.stdout.write(`opened: ${name}\n`);
      msgs.forEach((m) => process.stdout.write(`  ${formatMsg(m, SELF_NAME)}\n`));
    }, { headed });
    return;
  }

  if (VERB === 'read') {
    const name = arg('contact', CONTACT);
    const limit = Number(arg('limit', 20));
    await withPage(async (page) => {
      await openContact(page, name);
      const msgs = await readMessages(page, limit);
      process.stdout.write(`chat: ${name} (last ${msgs.length})\n`);
      msgs.forEach((m) => process.stdout.write(`  ${formatMsg(m, SELF_NAME)}\n`));
    }, { headed });
    return;
  }

  if (VERB === 'send') {
    const name = arg('contact', CONTACT);
    const file = arg('file', null);
    if (!file) die('send requires --file <path> (write the message to a file first)', 2);
    if (!fs.existsSync(file)) die(`message file not found: ${file}`, 2);
    const text = fs.readFileSync(file, 'utf8').trim();
    if (!text) die('message file is empty', 2);
    if (text.length > 4000) die(`message is ${text.length} chars; keep it under 4000`, 2);

    await withPage(async (page) => {
      await openContact(page, name);
      await compose(page, text);
      const send = page.locator(SEND_BTN).last();
      if ((await send.count()) === 0) die('send button not found; text left in the composer unsent', 6);
      await send.click();
      await page.waitForTimeout(1500);
      const still = (await page.locator(COMPOSER).last().innerText())
        .replace(/\s+/g, ' ')
        .trim();
      if (still.length > 0) {
        die('composer still holds text after clicking send; delivery NOT confirmed', 6);
      }
      // Delivery check: the composer must be empty (proves submit happened) and the message
      // must be findable in the recent outgoing bubbles. WhatsApp reflows interior whitespace,
      // so match on a normalised prefix rather than demanding byte equality.
      const wantAll = text.replace(/\s+/g, ' ').trim();
      const head = wantAll.slice(0, 48);
      const delivered = await page.evaluate((h) => {
        const nodes = [...document.querySelectorAll('[data-pre-plain-text]')];
        return nodes
          .slice(-8)
          .some((n) => (n.innerText || '').replace(/\s+/g, ' ').trim().startsWith(h));
      }, head);
      if (!delivered) {
        process.stderr.write(
          'instinct: WARNING message not matched in recent bubbles; composer is empty so it was ' +
            'submitted, but delivery is UNCONFIRMED. Re-read the chat to verify.\n'
        );
      }
      const msgs = await readMessages(page, 3);
      process.stdout.write(`sent to ${name}\n`);
      process.stdout.write(`chars: ${text.length}\n`);
      process.stdout.write(`tail:\n`);
      msgs.forEach((m) => process.stdout.write(`  ${formatMsg(m, SELF_NAME)}\n`));
    }, { headed });
    return;
  }

  die(`unknown verb "${VERB}"; use login | probe | read | open | send | whoami`);
})().catch((e) => die(e?.message || String(e), 1));
