// Headless Google Chrome backend for dot.sh (read | send).
// Exit 10 + "DOT_CHROME_UNAVAILABLE: <reason>" means nothing was sent.
// DOT_DRY_RUN=1 types + verifies the message, clears it, never sends.
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

// Dynamic configuration loader supporting ~/.config/dot/config.json
function loadDotConfig() {
  const customConfig = process.env.DOT_CONFIG_FILE;
  const configPath = customConfig || path.join(os.homedir(), '.config/dot/config.json');
  try {
    if (fs.existsSync(configPath)) {
      return JSON.parse(fs.readFileSync(configPath, 'utf8'));
    }
  } catch {}
  return {};
}

function detectChromeProfile(requestedAccount) {
  const dotConfig = loadDotConfig();
  const defaultAccount = dotConfig.default_account || 'default';
  let req = (requestedAccount || process.env.DOT_ACCOUNT || defaultAccount).trim();

  // Resolve aliases if defined in local config
  if (dotConfig.aliases && dotConfig.aliases[req.toLowerCase()]) {
    req = dotConfig.aliases[req.toLowerCase()];
  }

  const reqLower = req.toLowerCase();
  const accountConfig = (dotConfig.accounts && (dotConfig.accounts[req] || dotConfig.accounts[reqLower])) || {};

  let localState = {};
  try {
    if (fs.existsSync(localStatePath)) {
      localState = JSON.parse(fs.readFileSync(localStatePath, 'utf8'));
    }
  } catch {}

  const infoCache = (localState.profile && localState.profile.info_cache) || {};
  let matchedKey = null;
  let matchedData = null;

  const targetMatch = (accountConfig.profile_match || reqLower).toLowerCase();

  // Search infoCache for matching profile
  // Pass 1: exact matches on profile key, email, user name, or domain
  for (const [profKey, profData] of Object.entries(infoCache)) {
    const profKeyLower = profKey.toLowerCase();
    const userName = (profData.user_name || '').toLowerCase();
    const email = (profData.email || profData.user_name || '').toLowerCase();
    const name = (profData.name || '').toLowerCase();
    const domain = (profData.hosted_domain || '').toLowerCase();

    if (
      profKeyLower === targetMatch ||
      userName === targetMatch ||
      email === targetMatch ||
      name === targetMatch ||
      (domain !== 'no_hosted_domain' && domain === targetMatch)
    ) {
      matchedKey = profKey;
      matchedData = profData;
      break;
    }
  }

  // Pass 2: substring matching if no exact match found
  if (!matchedKey) {
    for (const [profKey, profData] of Object.entries(infoCache)) {
      const userName = (profData.user_name || '').toLowerCase();
      const email = (profData.email || profData.user_name || '').toLowerCase();
      const name = (profData.name || '').toLowerCase();
      const domain = (profData.hosted_domain || '').toLowerCase();
      const gaiaName = (profData.gaia_name || '').toLowerCase();

      if (
        userName.includes(targetMatch) ||
        email.includes(targetMatch) ||
        name.includes(targetMatch) ||
        (gaiaName && gaiaName.includes(targetMatch)) ||
        (domain !== 'no_hosted_domain' && domain.includes(targetMatch)) ||
        (targetMatch && targetMatch.includes(userName) && userName.length > 3)
      ) {
        matchedKey = profKey;
        matchedData = profData;
        break;
      }
    }
  }

  // Derive account slug for persistent directory
  let slug = 'default';
  if (accountConfig.slug) {
    slug = accountConfig.slug;
  } else if (matchedData && matchedData.hosted_domain && matchedData.hosted_domain.toLowerCase() !== 'no_hosted_domain') {
    const prefix = matchedData.hosted_domain.split('.')[0].toLowerCase().replace(/[^a-z0-9_-]/g, '_');
    if (prefix) slug = prefix;
  } else if (matchedData && matchedData.name) {
    const cleanName = matchedData.name.toLowerCase().replace(/[^a-z0-9_-]/g, '_');
    if (cleanName) slug = cleanName;
  } else {
    const base = req.split('@')[0] || req;
    slug = base.toLowerCase().replace(/[^a-z0-9_-]/g, '_') || 'default';
  }

  // Target directory
  let profileDir;
  if (process.env.DOT_CHROME_USER_DATA) {
    profileDir = path.resolve(process.env.DOT_CHROME_USER_DATA);
  } else if (accountConfig.user_data_dir) {
    profileDir = path.resolve(accountConfig.user_data_dir.replace(/^~/, os.homedir()));
  } else {
    profileDir = path.join(os.homedir(), `.config/dot-headless-chrome-${slug}`);
  }

  // Target URL
  const url = process.env.DOT_URL || accountConfig.url || dotConfig.default_url || 'https://chatgpt.com/';

  return {
    account: req,
    slug,
    matchedKey,
    matchedData,
    profileDir,
    url,
  };
}

// Single-command profile directory resolution helper for dot.sh
if (process.argv[2] === 'resolve-profile') {
  const info = detectChromeProfile(process.env.DOT_ACCOUNT);
  console.log(JSON.stringify(info));
  process.exit(0);
}

const accountInfo = detectChromeProfile(process.env.DOT_ACCOUNT);
const URL_ = accountInfo.url;
const CHROME = process.env.DOT_CHROME_BIN || (isMac ? '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' : '/usr/bin/google-chrome');
const USER_DATA_DIR = accountInfo.profileDir;
// Cloudflare rejects the default HeadlessChrome UA; any current desktop Chrome UA passes.
const UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/154.0.0.0 Safari/537.36';
const COMPOSER = '[contenteditable=true], #prompt-textarea, textarea[placeholder*="Message"]';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const norm = (t) => t.replace(/\s+/g, ' ').trim();
const stripReadReceipt = (t) => t.replace(/Read\s+\d{1,2}:\d{2}\s*(?:[AP]M)?/gi, '').replace(/\s+/g, ' ').trim();

class Unavailable extends Error {}
const unavailable = (why) => { throw new Unavailable(why); };

const [mode, arg] = process.argv.slice(2);
let ctx = null;
let clicked = false;

function ensurePersistentProfile(accInfo, targetDir) {
  // Never recreate or overwrite an existing persistent profile
  const defaultDir = path.join(targetDir, 'Default');
  const networkCookies = path.join(defaultDir, 'Network', 'Cookies');
  const legacyCookies = path.join(defaultDir, 'Cookies');
  const preferences = path.join(defaultDir, 'Preferences');
  if (
    (fs.existsSync(networkCookies) && fs.statSync(networkCookies).size > 0) ||
    (fs.existsSync(legacyCookies) && fs.statSync(legacyCookies).size > 0) ||
    (fs.existsSync(preferences) && fs.statSync(preferences).size > 0)
  ) {
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
  const lockPath = path.join(dir, 'SingletonLock');

  const isDead = (p) => {
    try {
      if (os.platform() === 'linux') {
        return !fs.existsSync(`/proc/${p}`);
      }
      const stat = execSync(`ps -o stat= -p ${p} 2>/dev/null`).toString().trim();
      if (!stat || stat.startsWith('Z')) return true;
      return false;
    } catch {
      return true;
    }
  };

  const removeLocks = () => {
    for (const f of ['SingletonLock', 'SingletonCookie', 'SingletonSocket']) {
      try { fs.unlinkSync(path.join(dir, f)); } catch {}
    }
  };

  // Wait politely up to 20 seconds if locked by an active live process
  for (let attempt = 0; attempt < 40; attempt++) {
    let hasLock = false;
    try {
      if (fs.existsSync(lockPath) || fs.lstatSync(lockPath).isSymbolicLink()) {
        hasLock = true;
        const target = fs.readlinkSync(lockPath);
        const match = target.match(/-(\d+)$/);
        if (match) {
          const pid = parseInt(match[1], 10);
          if (isDead(pid)) {
            // Process is dead; clear stale lock
            removeLocks();
            hasLock = false;
          } else {
            // Process is STILL ALIVE. Do NOT kill it! Wait for peer session to release.
            await sleep(500);
            continue;
          }
        } else {
          removeLocks();
          hasLock = false;
        }
      }
    } catch {
      hasLock = false;
    }
    if (!hasLock) return;
  }

  // If still locked after 20 seconds, report unavailable instead of deleting lock or killing peer
  let activeHolderPid = null;
  try {
    if (fs.existsSync(lockPath) || fs.lstatSync(lockPath).isSymbolicLink()) {
      const target = fs.readlinkSync(lockPath);
      const match = target.match(/-(\d+)$/);
      if (match && !isDead(parseInt(match[1], 10))) {
        activeHolderPid = match[1];
      }
    }
  } catch {}
  if (activeHolderPid) {
    unavailable(`profile directory locked by active process PID ${activeHolderPid}`);
  }
  removeLocks();
}

async function checkAuthSession(page) {
  try {
    return await page.evaluate(async () => {
      try {
        const res = await fetch('/api/auth/session', { credentials: 'include' });
        const text = await res.text();
        let json = null;
        try { json = JSON.parse(text); } catch {}
        return {
          status: res.status,
          hasUser: !!(json && json.user && json.user.email),
          isJson: !!json,
        };
      } catch (err) {
        return { status: 0, error: err.message };
      }
    });
  } catch {
    return { status: 0 };
  }
}

async function launch() {
  if (!fs.existsSync(CHROME)) unavailable('Chrome not found at ' + CHROME);
  let chromium;
  try {
    ({ chromium } = require('playwright'));
  } catch {
    unavailable('playwright not installed for ' + process.execPath);
  }

  ensurePersistentProfile(accountInfo, USER_DATA_DIR);
  await waitAndCleanSingletonLock(USER_DATA_DIR);

  const isLinux = os.platform() === 'linux';
  const hasDisplay = !!process.env.DISPLAY;
  const extraArgs = [
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-blink-features=AutomationControlled',
  ];
  const ignoreDefaultArgs = ['--enable-automation'];

  if (isMac) {
    extraArgs.push('--password-store=keychain');
    ignoreDefaultArgs.push('--use-mock-keychain', '--password-store=basic');
  }

  try {
    ctx = await chromium.launchPersistentContext(USER_DATA_DIR, {
      executablePath: CHROME,
      headless: isLinux ? !hasDisplay : true,
      userAgent: UA,
      ignoreDefaultArgs,
      args: extraArgs,
    });
  } catch (e) {
    unavailable('failed to launch persistent Chrome context: ' + e.message);
  }
  const page = await ctx.newPage();
  await page.goto(URL_, { waitUntil: 'domcontentloaded', timeout: 45000 });

  // Settle loop: wait for Cloudflare challenge to clear and page to render
  const deadline = Date.now() + 45000;
  let last = -1, stable = 0;
  while (Date.now() < deadline) {
    const title = await page.title().catch(() => '');
    const composers = await page.locator(COMPOSER).count().catch(() => 0);
    const bodyText = (await page.evaluate(() => document.body ? document.body.innerText : '').catch(() => ''));

    if (/ChatGPT hit a snag|Something went wrong/i.test(bodyText)) {
      try {
        const tryAgainBtn = page.locator('button:has-text("Try again"), button:has-text("Retry")');
        if (await tryAgainBtn.count() > 0) {
          await tryAgainBtn.first().click();
          await sleep(2000);
          continue;
        }
      } catch {}
    }
    if (/just a moment/i.test(title)) {
      await sleep(1500);
      continue;
    }

    if (composers >= 1) {
      // Validate auth immediately even when composer is visible (distinguishes logged-out anonymous composer)
      const session = await checkAuthSession(page);
      if (session.status === 200 && session.isJson && !session.hasUser) {
        unavailable('not signed in');
      }
      if (session.status === 403) {
        unavailable('Cloudflare 403 on session endpoint');
      }

      if (mode === 'send') return page;
      // For read mode, wait for narrative content length to stabilize
      const len = bodyText.length;
      if (len > 50) {
        stable = len === last ? stable + 1 : 0;
        if (stable >= 2) return page;
      }
      last = len;
      await sleep(1000);
      continue;
    }

    await sleep(1000);
  }

  // Settle deadline elapsed without active composer: diagnose exact failure reason
  const title = await page.title().catch(() => '');
  if (/just a moment/i.test(title)) unavailable('Cloudflare challenge');

  const session = await checkAuthSession(page);
  if (session.status === 403) {
    unavailable('Cloudflare 403 on session endpoint');
  } else if (session.status === 200 && session.isJson && !session.hasUser) {
    unavailable('not signed in');
  }

  const hasLoginButtons = await page.evaluate(() => {
    const btns = Array.from(document.querySelectorAll('button, a'));
    return btns.some(b => /^(log in|sign up)$/i.test((b.innerText || '').trim()));
  }).catch(() => false);

  if (hasLoginButtons) unavailable('not signed in');

  if (mode === 'read') return page;
  return unavailable('composer not found');
}

async function read(page, n) {
  let bodyText = (await page.evaluate(() => document.body.innerText)).trim();
  if (/ChatGPT hit a snag|Something went wrong/i.test(bodyText)) {
    try {
      const tryAgainBtn = page.locator('button:has-text("Try again"), button:has-text("Retry")');
      if (await tryAgainBtn.count() > 0) {
        await tryAgainBtn.first().click();
        await sleep(3000);
        bodyText = (await page.evaluate(() => document.body.innerText)).trim();
      }
    } catch {}
  }

  console.log(bodyText.slice(-n));
}

async function send(page, file, dry) {
  const msg = fs.readFileSync(file, 'utf8').trim();
  const readComposer = () => page.locator(COMPOSER).first().innerText().catch(() => '');
  const clear = async () => {
    await page.locator(COMPOSER).first().focus();
    await page.keyboard.press(isMac ? 'Meta+A' : 'Control+A');
    await page.keyboard.press('Backspace');
    await sleep(800);
  };
  const getUserMessages = () => page.locator('[data-message-author-role=user], article.self, article[class*="self"]')
    .allInnerTexts()
    .then(arr => arr.map(norm))
    .catch(() => []);

  // Check for alert banners before sending
  const alertText = await page.evaluate(() => {
    const alerts = Array.from(document.querySelectorAll('[role="alert"], [data-testid*="alert"], div[class*="banner"], div[class*="error"]'));
    for (const el of alerts) {
      const t = (el.innerText || '').trim();
      if (/usage limit|abuse prevention|rate limit|too many requests|dot is on a break/i.test(t)) {
        return t;
      }
    }
    return '';
  }).catch(() => '');

  if (alertText) {
    console.log('DOT_USAGE_LIMIT_REACHED: ' + alertText.replace(/\s+/g, ' ').slice(0, 200));
    return;
  }

  // Full-content normalized message match (never wiping on short prefix substrings)
  const matchesMessage = (userMsg, comp) => {
    if (!userMsg || !comp) return false;
    const sMsg = stripReadReceipt(norm(userMsg));
    const sComp = stripReadReceipt(norm(comp));
    if (sMsg === sComp) return true;
    if (sMsg.includes(sComp) && sComp.length >= sMsg.length * 0.95) return true;
    if (sComp.includes(sMsg) && sMsg.length >= sComp.length * 0.95) return true;
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
    const sM = stripReadReceipt(norm(m));
    const sN = stripReadReceipt(norm(needle));
    if (sM === sN) return true;
    if (sM.includes(sN) && sN.length >= sM.length * 0.95) return true;
    if (sN.includes(sM) && sM.length >= sN.length * 0.95) return true;
    return false;
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
let launchTimer = null;
try {
  if (mode === 'send' && !(arg && fs.existsSync(arg) && fs.statSync(arg).size > 0)) unavailable('no message file');
  const timeoutPromise = new Promise((_, reject) => {
    launchTimer = setTimeout(() => reject(new Unavailable('timeout')), 120000);
  });
  try {
    await Promise.race([
      (async () => {
        const page = await launch();
        if (mode === 'read') await read(page, Number(arg || 5000));
        else await send(page, arg, process.env.DOT_DRY_RUN === '1');
      })(),
      timeoutPromise
    ]);
  } finally {
    if (launchTimer) clearTimeout(launchTimer);
  }
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
