#!/usr/bin/env node
// Dedicated Chrome profile for grok.com bots (same pattern as dot_chrome.mjs; never a Dot or personal profile).
// Modes: login | list | read <bot-url>. Prints JSON/text only; never reads cookies.
import { createRequire } from 'module';
import path from 'path';
import os from 'os';

const require = createRequire(process.env.DOT_PW_MODULES || path.join(path.dirname(process.execPath), '../lib/node_modules/'));
const { chromium } = require('playwright');
import { isBotUrl, isAllowedListUrl, landedOnRequested, BOT_NAV_SELECTORS } from './url-guard.mjs';
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
  // This script does NOT verify account identity, and must not claim to. No selector it
  // could ship can prove that the node it read is the rendered account control: a unique
  // match can still be the body, and a bot message containing the expected handle would
  // pass any token comparison. Identity must be established before trusting output --
  // through the supported browser-control interface, or by the caller's own probe.
  if (mode !== 'login' && process.env.GROKBOT_IDENTITY_CONFIRMED !== '1') {
    throw new Error('GROKBOT_IDENTITY_UNCONFIRMED: this transport does not verify which account is signed in. Confirm the account first, then set GROKBOT_IDENTITY_CONFIRMED=1 to acknowledge you did.');
  }
  if (mode === 'login') {
    await goto('https://grok.com/');
    console.log('GROKBOT_LOGIN_OPEN sign in in the window; close it when done');
    await new Promise((r) => ctx.on('close', r));
  } else if (mode === 'list') {
    // Same URL discipline as read: an arbitrary page can render links containing /bot/ and
    // we would report them as this account's inventory.
    const listUrl = arg || 'https://grok.com/';
    if (!isAllowedListUrl(listUrl)) {
      throw new Error(`list accepts https://grok.com/ or a bot URL (got ${listUrl})`);
    }
    await goto(listUrl);
    if (new URL(page.url()).origin !== 'https://grok.com') {
      throw new Error(`GROKBOT_UNEXPECTED_NAVIGATION: list left grok.com (ended on ${page.url()})`);
    }
    // Extract ONLY from the account's bot navigation. Scanning the whole page would sweep
    // in links rendered inside a conversation, and a message linking to another bot would
    // be reported as this account's inventory. URL filtering proves a destination, not
    // ownership, so if no nav container matches we report nothing rather than guessing.
    let links = [];
    for (const sel of BOT_NAV_SELECTORS) {
      links = await page.$$eval(sel, (as) => as.map((a) => ({ href: a.href, title: a.innerText.trim().slice(0, 120) })));
      if (links.length) break;
    }
    const scoped = links.length > 0;
    const seen = new Map(links.filter((l) => isBotUrl(l.href)).map((l) => [l.href, l]));
    // Candidates, not a resolved inventory: the caller must confirm each route.
    console.log(JSON.stringify({
      url: page.url(),
      title: await page.title(),
      scope: scoped ? 'bot-navigation' : 'none-matched',
      verified: false,
      candidates: [...seen.values()],
    }, null, 1));
    if (!scoped) {
      console.error('GROKBOT_NO_NAV_SCOPE: no bot-navigation container matched; no routes reported. Set the route explicitly or inspect via browser-control.');
    }
  } else if (mode === 'read') {
    // Validate the NORMALIZED url, not the string prefix. A path like /bot/a/../../settings
    // passes a prefix test but resolves to /settings, and an auth redirect lands anywhere;
    // either way the script would then print that page as if it were the conversation.
    let target;
    try {
      target = new URL(arg || '');
    } catch {
      throw new Error('read needs a valid URL, e.g. https://grok.com/bot/<id>');
    }
    if (!isBotUrl(target.href)) {
      throw new Error(`read needs https://grok.com/bot/<id> (got ${target.href})`);
    }
    await goto(target.href);
    // Compare the landing pathname to the REQUESTED one exactly. An unanchored pattern
    // accepts a redirect to /bot/other or /bot/<id>/settings and would print that page as
    // the conversation.
    const landedHref = page.url();
    if (!landedOnRequested(target.href, landedHref)) {
      throw new Error(`GROKBOT_UNEXPECTED_NAVIGATION: requested ${target.pathname}, ended on ${landedHref}`);
    }
    console.log(((await page.innerText('body')).slice(-5000)));
  } else throw new Error('usage: login | list [url] | read <bot-url>');
} finally { await ctx.close().catch(() => {}); }
