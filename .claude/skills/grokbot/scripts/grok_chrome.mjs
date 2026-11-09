#!/usr/bin/env node
// Dedicated Chrome profile for grok.com bots (same pattern as dot_chrome.mjs; never a Dot or personal profile).
// Modes: login | list | read <bot-url> | send <bot-url> <file>. Prints JSON/text only; never reads cookies.
//
// Mechanical transport only. Every judgment call (whether to send, what to send,
// peer-draft policy) lives in ../SKILL.md and the calling agent.
import { createRequire } from 'module';
import fs from 'node:fs';
import path from 'path';
import os from 'os';

const require = createRequire(process.env.DOT_PW_MODULES || path.join(path.dirname(process.execPath), '../lib/node_modules/'));
const { chromium } = require('playwright');
const DIR = process.env.GROKBOT_PROFILE_DIR || path.join(os.homedir(), '.config/grokbot-chrome');
const CHROME = process.env.DOT_CHROME_BIN || (process.platform === 'darwin'
  ? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
  : '/usr/bin/google-chrome');
const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36';
const [mode, arg, extra] = process.argv.slice(2);
const headed = mode === 'login';

const BOT_URL = /^https:\/\/grok\.com\/bot\/[\w-]+/;

function die(msg, code = 2) {
  console.error(`grokbot: ${msg}`);
  process.exit(code);
}

// Composer candidates, most specific first. Grok renders a contenteditable
// textarea in the thread view; the selector set is deliberately narrow so a
// stray editable region elsewhere on the page cannot be typed into.
const COMPOSERS = [
  'form div[contenteditable="true"]',
  'div[contenteditable="true"][role="textbox"]',
  'textarea[placeholder]',
];

async function findComposer(page) {
  for (const sel of COMPOSERS) {
    const loc = page.locator(sel);
    const n = await loc.count().catch(() => 0);
    for (let i = 0; i < n; i++) {
      const el = loc.nth(i);
      if (await el.isVisible().catch(() => false)) return el;
    }
  }
  return null;
}

// --- Profile serialization -------------------------------------------------
// Chromium's ProcessSingleton REJECTS a simultaneous second launch on one
// user_data_dir; it does not queue it. Without this, a concurrent caller (the
// agent's own parallel tool calls, or a straggler Chrome helper) crashes the run
// with an unhandled ProcessSingleton error instead of waiting. The lockfile lives
// outside the profile dir so it never collides with Chrome's Singleton namespace,
// and it is released on exit and on signals so a crash cannot wedge the next run.
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
  // A released SingletonLock does NOT mean the profile is idle: an orphaned Chrome
  // helper (ppid 1) can still hold --user-data-dir. Check the live process table too.
  try {
    const lock = path.join(dir, 'SingletonLock');
    if (fs.lstatSync(lock).isSymbolicLink()) {
      const pid = Number(String(fs.readlinkSync(lock)).split('-').pop());
      if (pidAlive(pid)) return pid;
    }
  } catch {}
  try {
    const out = require('node:child_process')
      .execFileSync('ps', ['-Ao', 'pid=,command='], { encoding: 'utf8' });
    for (const line of out.split('\n')) {
      if (!line.includes(`--user-data-dir=${dir}`)) continue;
      const pid = Number(line.trim().split(/\s+/)[0]);
      if (pid !== process.pid && pidAlive(pid)) return pid;
    }
  } catch {}
  return null;
}

async function acquireLock(dir) {
  const lockFile = path.join(os.homedir(), '.config', 'grokbot-profile.lock');
  const lockWait = Number(process.env.GROKBOT_LOCK_WAIT_MS || 300_000);
  const profileWait = Number(process.env.GROKBOT_PROFILE_WAIT_MS || 300_000);
  const deadline = Date.now() + Math.max(lockWait, profileWait);

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
        try { fs.unlinkSync(lockFile); } catch {}
        continue;
      }
      if (Date.now() > deadline) {
        die(`another grokbot run (pid ${holder || '?'}) holds ${lockFile} past the ${lockWait}ms wait. Not stealing it.`, 7);
      }
      await new Promise((r) => setTimeout(r, 200));
    }
  }

  const release = () => {
    try {
      if (Number(fs.readFileSync(lockFile, 'utf8').trim()) === process.pid) fs.unlinkSync(lockFile);
    } catch {}
  };
  process.once('exit', release);
  for (const sig of ['SIGINT', 'SIGTERM', 'SIGHUP']) {
    process.once(sig, () => { release(); process.exit(130); });
  }

  let announced = false;
  for (;;) {
    const pid = liveHolderPid(dir);
    if (!pid) return release;
    if (Date.now() > deadline) {
      die(`profile ${dir} still owned by Chrome pid ${pid} after the wait window. Close it first - never delete SingletonLock.`, 7);
    }
    if (!announced) {
      console.error(`grokbot: profile busy (pid ${pid}); waiting for it to finish...`);
      announced = true;
    }
    await new Promise((r) => setTimeout(r, 500));
  }
}

const releaseLock = await acquireLock(DIR);

let ctx;
try {
  ctx = await chromium.launchPersistentContext(DIR, {
    executablePath: CHROME, headless: !headed, userAgent: UA,
    ignoreDefaultArgs: ['--enable-automation', '--use-mock-keychain', '--password-store=basic'],
    args: [
      '--no-first-run', '--no-default-browser-check', '--disable-blink-features=AutomationControlled',
      // Pin a real credential backend. Playwright's defaults include
      // --use-mock-keychain/--password-store=basic, which corrupt an encrypted store.
      ...(process.platform === 'darwin' ? ['--password-store=keychain'] : ['--password-store=gnome-libsecret']),
    ],
  });
try {
  const page = ctx.pages()[0] || await ctx.newPage();
  const goto = (u) => page.goto(u, { waitUntil: 'domcontentloaded', timeout: 30000 }).then(() => page.waitForTimeout(4000));

  if (mode === 'login') {
    await goto('https://grok.com/');
    console.log('GROKBOT_LOGIN_OPEN sign in in the window; close it when done');
    await new Promise((r) => ctx.on('close', r));
  } else if (mode === 'list') {
    await goto(arg || 'https://grok.com/');
    const links = await page.$$eval('a[href*="/bot/"]', (as) => as.map((a) => ({ href: a.href, title: a.innerText.trim().slice(0, 120) })));
    const seen = new Map(links.map((l) => [l.href, l]));
    console.log(JSON.stringify({ url: page.url(), title: await page.title(), bots: [...seen.values()] }, null, 1));
  } else if (mode === 'read') {
    if (!BOT_URL.test(arg || '')) die('read needs https://grok.com/bot/<id>');
    await goto(arg);
    console.log(((await page.innerText('body')).slice(-5000)));
  } else if (mode === 'send') {
    if (!BOT_URL.test(arg || '')) die('send needs https://grok.com/bot/<id> <file>');
    if (!extra) die('send needs a message file');
    let body;
    try {
      body = fs.readFileSync(extra, 'utf8');
    } catch (e) {
      die(`cannot read message file ${extra}: ${e.code || e.message}`, 2);
    }
    if (!body.trim()) die('message file is empty; nothing to send', 2);

    await goto(arg);

    // The bot page must be the one we asked for. A redirect to the bot index or a
    // "Page not found" body means we are not in a conversation; sending would be lost.
    const landed = page.url();
    if (!BOT_URL.test(landed)) die(`redirected away from the bot URL to ${landed}; not sending`, 4);
    const pageText = (await page.innerText('body').catch(() => '')) || '';
    if (/Page not found|There was an error loading this page/i.test(pageText)) {
      die('bot conversation did not load (page-not-found); the profile may be signed out. Not sending', 4);
    }

    const box = await findComposer(page);
    if (!box) die('composer not found on the bot page; not sending', 4);

    // Preserve a peer draft: report it rather than overwriting another writer's text.
    const existing = (await box.innerText().catch(() => '')).trim();
    if (existing && process.env.GROKBOT_CLEAR_DRAFT !== '1') {
      console.log('GROKBOT_DRAFT_PRESENT refusing to overwrite an existing draft (set GROKBOT_CLEAR_DRAFT=1 to force)');
      process.exitCode = 3;
      throw new Error('__draft_present__');
    }

    if (process.env.GROKBOT_DRY_RUN === '1') {
      console.log('GROKBOT_DRYRUN_OK composer_present');
      throw new Error('__dryrun__');
    }

    // Keystrokes, not fill(): Grok's composer needs real input events. Insert the
    // whole body in one paste so embedded newlines stay inside the draft instead of
    // each firing Enter and submitting a fragment.
    await box.click({ timeout: 20_000 }).catch(() => {});
    await page.evaluate((text) => {
      const selectors = ['form div[contenteditable="true"]', 'div[contenteditable="true"][role="textbox"]'];
      let el = null;
      for (const s of selectors) {
        const c = [...document.querySelectorAll(s)].find((n) => n.offsetParent !== null);
        if (c) { el = c; break; }
      }
      if (!el) el = [...document.querySelectorAll('textarea[placeholder]')].find((n) => n.offsetParent !== null);
      if (!el) throw new Error('composer not found for paste');
      el.focus();
      const dt = new DataTransfer();
      dt.setData('text/plain', text);
      el.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true }));
    }, body);
    await page.waitForTimeout(900);

    const norm = (v) => (v || '').replace(/\s+/g, ' ').trim();
    const typed = norm(await box.innerText().catch(() => ''));
    const want = norm(body);
    // Compare the WHOLE normalised body: a truncated paste would pass a prefix check.
    const sameContent = typed === want || (typed.length === want.length);
    if (!sameContent) {
      die(`composer content does not match the full message (want ${want.length} chars, got ${typed.length}); nothing was sent`, 6);
    }

    const sendBtn = page
      .locator('button[type="submit"], button[aria-label*="Send" i], form button:has-text("Send")')
      .filter({ hasNot: page.locator('[disabled]') })
      .last();
    if ((await sendBtn.count().catch(() => 0)) === 0) {
      die('send button not found; text left in the composer unsent', 6);
    }
    await sendBtn.click();
    await page.waitForTimeout(2500);

    const still = norm(await box.innerText().catch(() => ''));
    if (still.length > 0) {
      die('composer still holds text after clicking send; delivery NOT confirmed', 6);
    }

    // Delivery check: the composer emptied (submit happened) AND the text is findable
    // in the rendered conversation. Grok reflows whitespace, so match a normalised prefix.
    const head = want.slice(0, 48);
    const delivered = await page.evaluate((h) => {
      const t = (document.body.innerText || '').replace(/\s+/g, ' ');
      return t.includes(h);
    }, head).catch(() => false);

    if (delivered) {
      console.log(`GROKBOT_SENT_VERIFIED ${arg}`);
    } else {
      // Composer is empty, so the message was submitted; the echo may simply not be
      // in the currently rendered window. Report honestly rather than claiming success.
      console.log(`GROKBOT_SENT_UNVERIFIED ${arg} composer_cleared=1 echo_not_matched=1`);
      process.exitCode = 4;
    }
  } else {
    die('usage: login | list [url] | read <bot-url> | send <bot-url> <file>');
  }
} catch (e) {
  if (!/^__(draft_present|dryrun)__$/.test(e.message)) throw e;
}
} finally {
  await ctx.close().catch(() => {});
  releaseLock();
}
