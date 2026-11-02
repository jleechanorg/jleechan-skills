#!/usr/bin/env node
// Dedicated Chrome profile for grok.com bots (same pattern as dot_chrome.mjs; never a Dot or personal profile).
// Modes: login | list | read <bot-url>. Prints JSON/text only; never reads cookies.
import { createRequire } from 'module';
import path from 'path';
import os from 'os';

const require = createRequire(process.env.DOT_PW_MODULES || path.join(path.dirname(process.execPath), '../lib/node_modules/'));
const { chromium } = require('playwright');
// Profile isolation: always a dedicated grokbot directory. No env override, so this
// can never be pointed at a Dot or personal Chrome profile.
const DIR = path.join(os.homedir(), '.config/grokbot-chrome');
// Grok-specific setting first; DOT_CHROME_BIN is deliberately NOT consulted, so a Dot
// override cannot silently redirect this skill's browser.
const CHROME = process.env.GROKBOT_CHROME_BIN
  || (process.platform === 'darwin'
      ? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
      : '/usr/bin/google-chrome');
const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36';
const [mode, arg] = process.argv.slice(2);
const headed = mode === 'login';
const ctx = await chromium.launchPersistentContext(DIR, {
  executablePath: CHROME, headless: !headed, userAgent: UA,
  ignoreDefaultArgs: ['--enable-automation'],
  args: ['--no-first-run', '--no-default-browser-check', '--disable-blink-features=AutomationControlled'],
});
try {
  const page = ctx.pages()[0] || await ctx.newPage();
  const goto = (u) => page.goto(u, { waitUntil: 'domcontentloaded', timeout: 30000 }).then(() => page.waitForTimeout(4000));
  // Before printing anything from a read mode, positively verify identity. Checking only
  // for the absence of a sign-in control is not enough: a session belonging to a
  // DIFFERENT account also passes, and would then be reported as this bot's data.
  // GROKBOT_EXPECTED_IDENTITY must be set to the handle this account should be signed in
  // as; the rendered account UI has to contain it before any content is printed.
  const assertSignedIn = async () => {
    const signedOut = await page.$('a[href*="/sign-in"], button[data-testid*="sign-in"]');
    if (signedOut) throw new Error('GROKBOT_SIGNED_OUT: profile has no session; run `login` first');
    const expected = (process.env.GROKBOT_EXPECTED_IDENTITY || '').trim().toLowerCase();
    if (!expected) {
      throw new Error('GROKBOT_IDENTITY_UNKNOWN: set GROKBOT_EXPECTED_IDENTITY to the expected handle before listing or reading');
    }
    // The account element is caller-supplied, never guessed. Any selector this script
    // supplied itself could resolve to the wrong node - a profile link earlier in
    // document order would pass a token match for a different account. GROKBOT_ACCOUNT_SELECTOR
    // must match EXACTLY ONE element; zero or several is a hard failure.
    const selector = (process.env.GROKBOT_ACCOUNT_SELECTOR || '').trim();
    if (!selector) {
      throw new Error('GROKBOT_IDENTITY_NOT_CONFIGURED: set GROKBOT_ACCOUNT_SELECTOR to the single element that shows the signed-in handle');
    }
    const found = await page.evaluate((sel) => {
      const els = Array.from(document.querySelectorAll(sel));
      return els.map((el) => (el.innerText || el.getAttribute('aria-label') || '').trim().toLowerCase());
    }, selector);
    if (found.length === 0) {
      throw new Error('GROKBOT_IDENTITY_UI_NOT_FOUND: account selector matched nothing; refusing to report content');
    }
    if (found.length > 1) {
      throw new Error(`GROKBOT_IDENTITY_AMBIGUOUS: account selector matched ${found.length} elements; narrow it to one`);
    }
    const handle = found[0];
    if (handle.split(/\s+/).indexOf(expected) === -1 && handle !== expected) {
      throw new Error(`GROKBOT_IDENTITY_MISMATCH: account element reads "${handle}", expected ${expected}`);
    }
  };
  if (mode === 'login') {
    await goto('https://grok.com/');
    console.log('GROKBOT_LOGIN_OPEN sign in in the window; close it when done');
    await new Promise((r) => ctx.on('close', r));
  } else if (mode === 'list') {
    await goto(arg || 'https://grok.com/');
    await assertSignedIn();
    const links = await page.$$eval('a[href*="/bot/"]', (as) => as.map((a) => ({ href: a.href, title: a.innerText.trim().slice(0, 120) })));
    const seen = new Map(links.map((l) => [l.href, l]));
    console.log(JSON.stringify({ url: page.url(), title: await page.title(), bots: [...seen.values()] }, null, 1));
  } else if (mode === 'read') {
    if (!/^https:\/\/grok\.com\/bot\/[\w-]+/.test(arg || '')) throw new Error('read needs https://grok.com/bot/<id>');
    await goto(arg);
    await assertSignedIn();
    console.log(((await page.innerText('body')).slice(-5000)));
  } else throw new Error('usage: login | list [url] | read <bot-url>');
} finally { await ctx.close().catch(() => {}); }
