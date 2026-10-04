// Headless Google Chrome backend for dot.sh (read | send). Prints the same DOT_* markers as the
// Aside backend. Exit 10 + "DOT_CHROME_UNAVAILABLE: <reason>" means nothing was sent and the
// caller may fall back to Aside. DOT_DRY_RUN=1 types + verifies the message, clears it, never sends.
import { createRequire } from 'module';
import { execSync } from 'child_process';
import fs from 'fs';
import os from 'os';
import path from 'path';

const require = createRequire(process.env.DOT_PW_MODULES || path.join(path.dirname(process.execPath), '../lib/node_modules/'));
const URL_ = process.env.DOT_URL || 'https://chatgpt.com/dots/01a0f819-a779-775c-9d48-8c6035034033';
const CHROME = process.env.DOT_CHROME_BIN || (os.platform() === 'linux' ? '/usr/bin/google-chrome' : '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome');
const USER_DATA_DIR = process.env.DOT_CHROME_USER_DATA || path.join(os.homedir(), '.config/dot-headless-chrome');
// Cloudflare rejects the default HeadlessChrome UA; any current desktop Chrome UA passes.
const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36';
const COMPOSER = '[contenteditable=true]';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const norm = (t) => t.replace(/\s+/g, ' ').trim();

class Unavailable extends Error {}
const unavailable = (why) => { throw new Unavailable(why); };

const [mode, arg] = process.argv.slice(2);
let ctx = null;
let clicked = false;

async function waitAndCleanSingletonLock(dir) {
  const resolvedDir = path.resolve(dir);
  const lockPath = path.join(dir, 'SingletonLock');
  for (let attempt = 0; attempt < 90; attempt++) {
    let hasLock = false;
    try {
      if (fs.existsSync(lockPath) || fs.lstatSync(lockPath).isSymbolicLink()) {
        hasLock = true;
        const target = fs.readlinkSync(lockPath);
        const match = target.match(/-(\d+)$/);
        if (match) {
          const pid = parseInt(match[1], 10);
          try {
            process.kill(pid, 0); // Is process alive?
            let ppid = 0;
            try { ppid = parseInt(execSync(`ps -o ppid= -p ${pid} 2>/dev/null`).toString().trim(), 10); } catch {}
            if (ppid === 1) {
              // Ensure this is an orphaned Chrome process specifically using our target directory
              let cmd = '';
              try { cmd = execSync(`ps -o command= -p ${pid} 2>/dev/null`).toString(); } catch {}
              const escaped = resolvedDir.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
              const userDirRegex = new RegExp('--user-data-dir=(?:"' + escaped + '"|\'' + escaped + '\'|' + escaped + '(?=[\\s\'"]|$))');
              if (userDirRegex.test(cmd)) {
                try { process.kill(pid, 15); } catch {}
                let dead = false;
                for (let k = 0; k < 10; k++) {
                  await sleep(200);
                  try { process.kill(pid, 0); } catch { dead = true; break; }
                }
                if (!dead) {
                  try { process.kill(pid, 9); } catch {}
                  for (let k = 0; k < 10; k++) {
                    await sleep(100);
                    try { process.kill(pid, 0); } catch { dead = true; break; }
                  }
                }
                if (dead) {
                  for (const f of ['SingletonLock', 'SingletonCookie', 'SingletonSocket']) {
                    try { fs.unlinkSync(path.join(dir, f)); } catch {}
                  }
                  hasLock = false;
                }
              }
            }
          } catch (e) {
            if (e.code === 'ESRCH') {
              // Dead process, clean up stale locks
              for (const f of ['SingletonLock', 'SingletonCookie', 'SingletonSocket']) {
                try { fs.unlinkSync(path.join(dir, f)); } catch {}
              }
              hasLock = false;
            }
          }
        }
      }
    } catch {}
    if (!hasLock) return;
    await sleep(500);
  }
}

async function launch() {
  let chromium;
  try { ({ chromium } = require('playwright')); } catch { unavailable('playwright module not found'); }
  if (!fs.existsSync(CHROME)) unavailable('Chrome binary missing: ' + CHROME);
  if (!fs.existsSync(USER_DATA_DIR)) unavailable('Profile directory missing: ' + USER_DATA_DIR);

  await waitAndCleanSingletonLock(USER_DATA_DIR);

  const extraArgs = ['--disable-blink-features=AutomationControlled'];
  if (os.platform() === 'linux') {
    extraArgs.push('--no-sandbox', '--disable-setuid-sandbox', '--password-store=basic');
  } else {
    extraArgs.push('--password-store=keychain');
  }

  try {
    ctx = await chromium.launchPersistentContext(USER_DATA_DIR, {
      executablePath: CHROME,
      headless: true,
      userAgent: UA,
      ignoreDefaultArgs: ['--use-mock-keychain', '--enable-automation'],
      args: extraArgs,
    });
  } catch (e) {
    unavailable('failed to launch persistent Chrome context: ' + e.message);
  }
  const page = await ctx.newPage();
  await page.goto(URL_, { waitUntil: 'domcontentloaded', timeout: 45000 });
  // Wait for the Cloudflare interstitial to clear and the signed-in composer to render.
  const deadline = Date.now() + 45000;
  let last = -1, stable = 0;
  while (Date.now() < deadline) {
    const title = await page.title();
    const composers = await page.locator(COMPOSER).count();
    const len = (await page.evaluate(() => document.body.innerText)).length;
    if (composers >= 1 && len > 200 && !/just a moment/i.test(title)) {
      stable = len === last ? stable + 1 : 0;
      if (stable >= 3) return page;
    }
    last = len;
    await sleep(1000);
  }
  const title = await page.title();
  if (/just a moment/i.test(title)) unavailable('Cloudflare challenge');
  if (/log in|sign up/i.test(await page.evaluate(() => document.body.innerText).catch(() => ''))) unavailable('not signed in');
  return unavailable('composer not found');
}

async function read(page, n) {
  console.log((await page.evaluate(() => document.body.innerText)).slice(-n));
}

async function send(page, file, dry) {
  const msg = fs.readFileSync(file, 'utf8').trim();
  const readComposer = () => page.evaluate((s) => (document.querySelector(s) || {}).innerText || '', COMPOSER);
  const getUserMessages = () => page.evaluate(() => Array.from(document.querySelectorAll('[data-message-author-role=user]')).map(el => (el.innerText || '').replace(/\s+/g, ' ').trim()));
  const clear = async () => { await page.keyboard.press('ControlOrMeta+A'); await page.keyboard.press('Backspace'); await sleep(800); };

  await page.click(COMPOSER);
  await sleep(1500);
  let composer = (await readComposer()).trim();

  if (composer !== '') {
    const normComposer = norm(composer);
    const userMessages = await getUserMessages();
    const alreadySent = userMessages.some(m => m !== '' && m === normComposer);
    const ownLeftover = normComposer !== '' && normComposer === norm(msg);
    if (ownLeftover || alreadySent) {
      await clear();
      composer = (await readComposer()).trim();
      console.log('DOT_STALE_DRAFT_CLEARED');
    }
  }
  if (composer !== '') { console.log('DOT_DRAFT_PRESENT: ' + composer.slice(0, 300)); return; }

  await page.keyboard.insertText(msg);
  await sleep(800);
  const typed = (await readComposer()).trim();
  if (norm(typed) !== norm(msg)) {
    console.log('DOT_COMPOSER_MISMATCH: ' + typed.slice(0, 200));
    return;
  }
  if (dry) {
    await clear();
    const left = (await readComposer()).trim();
    console.log(left === '' ? 'DOT_DRYRUN_OK composer_matched_and_cleared' : 'DOT_DRYRUN_CLEAR_FAILED composer_left=' + left.length);
    return;
  }

  const beforeMsgs = await getUserMessages();
  const countMatches = (msgs, needle) => msgs.filter(m => m === needle).length;
  const beforeCount = countMatches(beforeMsgs, norm(msg));
  clicked = true;
  await page.click('button[data-testid=send-button], button[aria-label*=Send]');
  await sleep(4000);
  const left = (await readComposer()).trim();
  const afterMsgs = await getUserMessages();
  const afterCount = countMatches(afterMsgs, norm(msg));
  const sentVerified = left === '' && afterCount > beforeCount;
  console.log(sentVerified ? 'DOT_SENT_VERIFIED' : 'DOT_SEND_UNVERIFIED composer_left=' + left.length);
}

process.on('SIGTERM', async () => { try { await ctx?.close(); } catch {} process.exit(143); });
process.on('SIGINT', async () => { try { await ctx?.close(); } catch {} process.exit(130); });

let code = 0;
try {
  if (mode === 'send' && !(arg && fs.existsSync(arg) && fs.statSync(arg).size > 0)) unavailable('no message file');
  const page = await Promise.race([launch(), sleep(100000).then(() => unavailable('timeout'))]);
  if (mode === 'read') await read(page, Number(arg || 5000));
  else await send(page, arg, process.env.DOT_DRY_RUN === '1');
} catch (e) {
  if (clicked) console.log('DOT_SEND_UNVERIFIED chrome_error=' + e.message);
  else { console.log('DOT_CHROME_UNAVAILABLE: ' + (e instanceof Unavailable ? e.message : 'error: ' + e.message.split('\n')[0])); code = 10; }
} finally {
  try {
    await ctx?.close();
    await sleep(300);
  } catch {}
}
process.exit(code);
