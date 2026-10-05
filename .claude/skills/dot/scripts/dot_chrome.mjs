// Headless Google Chrome backend for dot.sh (read | send). Prints the same DOT_* markers as the
// Aside backend. Exit 10 + "DOT_CHROME_UNAVAILABLE: <reason>" means nothing was sent and the
// caller may fall back to Aside. DOT_DRY_RUN=1 types + verifies the message, clears it, never sends.
import { createRequire } from 'module';
import { execSync } from 'child_process';
import fs from 'fs';
import os from 'os';
import path from 'path';

const require = createRequire(process.env.DOT_PW_MODULES || path.join(path.dirname(process.execPath), '../lib/node_modules/'));

const isMac = os.platform() === 'darwin';
const sysChromeDir = isMac
  ? path.join(os.homedir(), 'Library/Application Support/Google/Chrome')
  : path.join(os.homedir(), '.config/google-chrome');
const localStatePath = path.join(sysChromeDir, 'Local State');

// Default target dot URLs by known account / slug
const DEFAULT_URLS = {
  worldarchitect: 'https://chatgpt.com/dots/01a1032f-aa98-7703-91bf-a35b1f95f01c',
  u0: 'https://chatgpt.com/dots/01a0f819-a779-775c-9d48-8c6035034033',
  test: 'https://chatgpt.com/dots/01a0fead-2ea7-71c9-9e87-ac4af984601c',
};
const DEFAULT_FALLBACK_URL = DEFAULT_URLS.worldarchitect;

function detectChromeProfile(requestedAccount) {
  const req = (requestedAccount || 'jleechan@worldarchitect.ai').trim().toLowerCase();
  let localState = {};
  try {
    if (fs.existsSync(localStatePath)) {
      localState = JSON.parse(fs.readFileSync(localStatePath, 'utf8'));
    }
  } catch {}

  const infoCache = (localState.profile && localState.profile.info_cache) || {};
  let matchedKey = null;
  let matchedData = null;

  const isU0 = ['u0', 'jleechan@gmail.com', 'gmail', 'personal', 'default'].includes(req);
  const isWA = ['worldarchitect', 'worldarchitect.ai', 'jleechan@worldarchitect.ai', 'wa'].includes(req);
  const isTest = ['test', 'jleechantest@gmail.com', 'jleechantest', 'testdot'].includes(req);

  for (const [profKey, profData] of Object.entries(infoCache)) {
    const userName = (profData.user_name || '').toLowerCase();
    const email = (profData.email || profData.user_name || '').toLowerCase();
    const name = (profData.name || '').toLowerCase();
    const domain = (profData.hosted_domain || '').toLowerCase();
    const gaiaName = (profData.gaia_name || '').toLowerCase();

    if (isU0) {
      if (profKey === 'Default' || userName.includes('jleechan@gmail.com') || name === 'jeffrey') {
        matchedKey = profKey;
        matchedData = profData;
        break;
      }
    }
    if (isWA) {
      if (domain === 'worldarchitect.ai' || userName.includes('worldarchitect.ai') || name.includes('worldarchitect')) {
        matchedKey = profKey;
        matchedData = profData;
        break;
      }
    }
    if (isTest) {
      if (userName.includes('jleechantest') || name.includes('test') || email.includes('test')) {
        matchedKey = profKey;
        matchedData = profData;
        break;
      }
    }

    // Dynamic matching against requested account
    if (
      req === userName ||
      req === email ||
      req === name ||
      (domain !== 'no_hosted_domain' && req === domain) ||
      userName.includes(req) ||
      email.includes(req) ||
      name.includes(req) ||
      (gaiaName && gaiaName.includes(req)) ||
      (domain !== 'no_hosted_domain' && (domain.includes(req) || req.includes(domain))) ||
      (userName && req.includes(userName))
    ) {
      matchedKey = profKey;
      matchedData = profData;
      break;
    }
  }

  // Derive account slug
  let slug = 'default';
  if (isWA) {
    slug = 'worldarchitect';
  } else if (isU0) {
    slug = 'u0';
  } else if (isTest) {
    slug = 'test';
  } else if (matchedData && matchedData.hosted_domain && matchedData.hosted_domain.toLowerCase() !== 'no_hosted_domain') {
    const prefix = matchedData.hosted_domain.split('.')[0].toLowerCase().replace(/[^a-z0-9_-]/g, '_');
    if (prefix) slug = prefix;
  } else if (matchedData && matchedData.name) {
    const cleanName = matchedData.name.toLowerCase().replace(/[^a-z0-9_-]/g, '_');
    if (cleanName) slug = cleanName;
  } else {
    const base = req.split('@')[0] || req;
    slug = base.replace(/[^a-z0-9_-]/g, '_') || 'default';
  }

  // Target directory
  let profileDir;
  if (process.env.DOT_CHROME_USER_DATA) {
    profileDir = path.resolve(process.env.DOT_CHROME_USER_DATA);
  } else {
    const specificDir = path.join(os.homedir(), `.config/dot-headless-chrome-${slug}`);
    if (slug === 'u0' && !fs.existsSync(specificDir) && fs.existsSync(path.join(os.homedir(), '.config/dot-headless-chrome'))) {
      profileDir = path.join(os.homedir(), '.config/dot-headless-chrome');
    } else {
      profileDir = specificDir;
    }
  }

  // Target URL
  const url = process.env.DOT_URL || DEFAULT_URLS[slug] || DEFAULT_FALLBACK_URL;

  return {
    account: req,
    slug,
    matchedKey,
    matchedData,
    profileDir,
    url,
  };
}

const accountInfo = detectChromeProfile(process.env.DOT_ACCOUNT);
const URL_ = accountInfo.url;
const CHROME = process.env.DOT_CHROME_BIN || (isMac ? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' : '/usr/bin/google-chrome');
const USER_DATA_DIR = accountInfo.profileDir;
// Cloudflare rejects the default HeadlessChrome UA; any current desktop Chrome UA passes.
const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36';
const COMPOSER = '[contenteditable=true]';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const norm = (t) => t.replace(/\s+/g, ' ').trim();
const stripReadReceipt = (t) => t.replace(/Read\s+\d{1,2}:\d{2}\s*(?:[AP]M)?/gi, '').replace(/\s+/g, ' ').trim();

class Unavailable extends Error {}
const unavailable = (why) => { throw new Unavailable(why); };

const [mode, arg] = process.argv.slice(2);
let ctx = null;
let clicked = false;

function ensurePersistentProfile(accInfo, targetDir) {
  // Never recreate an existing persistent profile
  const defaultDir = path.join(targetDir, 'Default');
  if (fs.existsSync(defaultDir)) {
    return;
  }

  if (!fs.existsSync(localStatePath)) {
    fs.mkdirSync(defaultDir, { recursive: true });
    return;
  }

  fs.mkdirSync(targetDir, { recursive: true });
  try {
    fs.copyFileSync(localStatePath, path.join(targetDir, 'Local State'));
  } catch {}

  if (accInfo.matchedKey) {
    const srcProfilePath = path.join(sysChromeDir, accInfo.matchedKey);
    if (fs.existsSync(srcProfilePath)) {
      try {
        execSync(`rsync -a --exclude='Singleton*' --exclude='*lock*' "${srcProfilePath}/" "${defaultDir}/" 2>/dev/null`);
        execSync(`find "${defaultDir}" -name 'LOCK' -delete 2>/dev/null`);
      } catch {
        fs.mkdirSync(defaultDir, { recursive: true });
      }
      return;
    }
  }
  fs.mkdirSync(defaultDir, { recursive: true });
}

async function waitAndCleanSingletonLock(dir) {
  const resolvedDir = path.resolve(dir);
  const lockPath = path.join(dir, 'SingletonLock');

  const isDead = (p) => {
    try {
      process.kill(p, 0);
      return false;
    } catch (e) {
      return e.code === 'ESRCH';
    }
  };

  const killProcessTree = async (pid) => {
    try { process.kill(pid, 15); } catch {}
    let dead = false;
    for (let k = 0; k < 10; k++) {
      await sleep(200);
      if (isDead(pid)) { dead = true; break; }
    }
    if (!dead) {
      try { process.kill(pid, 9); } catch {}
      for (let k = 0; k < 10; k++) {
        await sleep(100);
        if (isDead(pid)) { dead = true; break; }
      }
    }
    return dead;
  };

  const removeLocks = () => {
    for (const f of ['SingletonLock', 'SingletonCookie', 'SingletonSocket']) {
      try { fs.unlinkSync(path.join(dir, f)); } catch {}
    }
  };

  // Clean any stale orphaned Chrome processes tied to this profile directory
  const cleanOrphans = async () => {
    try {
      const escaped = resolvedDir.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      const userDirRegex = new RegExp('(?:^|\\s)--user-data-dir=(?:"' + escaped + '"|\'' + escaped + '\'|' + escaped + '(?=[\\s\'"]|$))');
      const pidsOutput = execSync('pgrep -f "chrome.*--user-data-dir=" 2>/dev/null || true').toString().trim();
      if (!pidsOutput) return;
      const pids = pidsOutput.split(/\s+/).map((p) => parseInt(p, 10)).filter(Boolean);
      for (const p of pids) {
        if (p === process.pid) continue;
        let cmd = '';
        try { cmd = execSync(`ps -o command= -p ${p} 2>/dev/null`).toString(); } catch {}
        if (!userDirRegex.test(cmd)) continue;

        let ppid = 0;
        try { ppid = parseInt(execSync(`ps -o ppid= -p ${p} 2>/dev/null`).toString().trim(), 10); } catch {}
        const isParentDead = ppid > 0 && isDead(ppid);
        let isSystemd = false;
        try {
          const comm = execSync(`ps -o comm= -p ${ppid} 2>/dev/null`).toString().trim();
          isSystemd = comm.includes('systemd') || comm === 'init';
        } catch {}

        if (ppid === 1 || isParentDead || isSystemd) {
          await killProcessTree(p);
        }
      }
    } catch {}
  };

  await cleanOrphans();

  for (let attempt = 0; attempt < 90; attempt++) {
    let hasLock = false;
    try {
      if (fs.existsSync(lockPath) || fs.lstatSync(lockPath).isSymbolicLink()) {
        hasLock = true;
        const target = fs.readlinkSync(lockPath);
        const match = target.match(/-(\d+)$/);
        if (match) {
          const pid = parseInt(match[1], 10);
          if (isDead(pid)) {
            removeLocks();
            hasLock = false;
          } else {
            let cmd = '';
            try { cmd = execSync(`ps -o command= -p ${pid} 2>/dev/null`).toString(); } catch {}
            const escaped = resolvedDir.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            const userDirRegex = new RegExp('(?:^|\\s)--user-data-dir=(?:"' + escaped + '"|\'' + escaped + '\'|' + escaped + '(?=[\\s\'"]|$))');
            if (userDirRegex.test(cmd)) {
              let ppid = 0;
              try { ppid = parseInt(execSync(`ps -o ppid= -p ${pid} 2>/dev/null`).toString().trim(), 10); } catch {}
              const isParentDead = ppid > 0 && isDead(ppid);
              let isSystemd = false;
              try {
                const comm = execSync(`ps -o comm= -p ${ppid} 2>/dev/null`).toString().trim();
                isSystemd = comm.includes('systemd') || comm === 'init';
              } catch {}

              if (ppid === 1 || isParentDead || isSystemd) {
                const dead = await killProcessTree(pid);
                if (dead) {
                  removeLocks();
                  hasLock = false;
                }
              }
            }
          }
        }
      }
    } catch (e) {
      if (e.code === 'ENOENT') {
        hasLock = false;
      }
    }
    if (!hasLock) return;
    await sleep(500);
  }
}

async function launch() {
  let chromium;
  try { ({ chromium } = require('playwright')); } catch { unavailable('playwright module not found'); }
  if (!fs.existsSync(CHROME)) unavailable('Chrome binary missing: ' + CHROME);

  ensurePersistentProfile(accountInfo, USER_DATA_DIR);
  if (!fs.existsSync(USER_DATA_DIR)) unavailable('Profile directory missing: ' + USER_DATA_DIR);

  await waitAndCleanSingletonLock(USER_DATA_DIR);

  const extraArgs = ['--disable-blink-features=AutomationControlled'];
  if (os.platform() === 'linux') {
    extraArgs.push('--no-sandbox', '--disable-setuid-sandbox');
  } else {
    extraArgs.push('--password-store=keychain');
  }

  try {
    ctx = await chromium.launchPersistentContext(USER_DATA_DIR, {
      executablePath: CHROME,
      headless: true,
      userAgent: UA,
      ignoreDefaultArgs: ['--use-mock-keychain', '--enable-automation', '--password-store=basic'],
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
  const getUserMessages = () => page.evaluate(() => Array.from(document.querySelectorAll('[data-message-author-role=user], article.self, article[class*="self"]')).map(el => (el.innerText || '').replace(/\s+/g, ' ').trim()));
  const clear = async () => { await page.keyboard.press('ControlOrMeta+A'); await page.keyboard.press('Backspace'); await sleep(800); };

  const matchesMessage = (userMsg, comp) => {
    if (!userMsg || !comp) return false;
    const sMsg = stripReadReceipt(userMsg);
    const sComp = stripReadReceipt(comp);
    if (sMsg === sComp || sMsg.includes(sComp) || sComp.includes(sMsg)) return true;
    if (sComp.length > 40 && sMsg.includes(sComp.slice(0, 40))) return true;
    if (sMsg.length > 40 && sComp.includes(sMsg.slice(0, 40))) return true;
    return false;
  };

  await page.click(COMPOSER);
  await sleep(1500);
  let composer = (await readComposer()).trim();

  if (composer !== '') {
    const normComposer = norm(composer);
    const userMessages = await getUserMessages();
    const alreadySent = userMessages.some(m => m !== '' && matchesMessage(m, normComposer));
    const ownLeftover = normComposer !== '' && (normComposer === norm(msg) || matchesMessage(norm(msg), normComposer));
    if (process.env.DOT_CLEAR_DRAFT === '1' || ownLeftover || alreadySent) {
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

  const matchMsg = (m, needle) => {
    if (!m || !needle) return false;
    const sM = stripReadReceipt(m);
    const sN = stripReadReceipt(needle);
    return sM === sN || sM.includes(sN) || sN.includes(sM) || (sN.length > 40 && sM.includes(sN.slice(0, 40)));
  };
  const countMatches = (msgs, needle) => msgs.filter(m => matchMsg(m, needle)).length;
  const beforeMsgs = await getUserMessages();
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
