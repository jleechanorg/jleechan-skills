#!/usr/bin/env node
// Dedicated Chrome profile for grok.com bots (same pattern as dot_chrome.mjs; never a Dot or personal profile).
// Modes: login | list | read <bot-url>. Prints JSON/text only; never reads cookies.
import { createRequire } from 'module';
import path from 'path';
import os from 'os';

const require = createRequire(process.env.DOT_PW_MODULES || path.join(path.dirname(process.execPath), '../lib/node_modules/'));
const { chromium } = require('playwright');
const DIR = process.env.GROKBOT_PROFILE_DIR || path.join(os.homedir(), '.config/grokbot-chrome');
const CHROME = process.env.DOT_CHROME_BIN || process.env.GROKBOT_CHROME_BIN
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
    if (!/^https:\/\/grok\.com\/bot\/[\w-]+/.test(arg || '')) throw new Error('read needs https://grok.com/bot/<id>');
    await goto(arg);
    console.log(((await page.innerText('body')).slice(-5000)));
  } else throw new Error('usage: login | list [url] | read <bot-url>');
} finally { await ctx.close().catch(() => {}); }
